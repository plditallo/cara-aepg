"""Three ways to put an arm behind (or not behind) a gate."""
from dataclasses import dataclass, field

from aepg_ref.consumption import ConfirmationAuthority, ConsumptionLedger
from aepg_ref.evidence import EvidenceLog
from aepg_ref.pep import Tier3PEP
from aepg_ref.receipts import ReceiptSigner
import random
import hazards
from actuator import Actuator
from authority import ACTION, RESOURCE, PEP_ID, AuthorityState, engine, at, seconds_of
from perception import Perception

CONFIRM_KEY = b"sim-user-confirmation-key-000001"
RECEIPT_SEED = b"sim-pep-receipt-signing-seed-001"


@dataclass
class StepResult:
    executed: bool
    reasons: tuple = ()
    outcome: list = field(default_factory=list)
    receipt: dict | None = None
    settlement: str | None = None


class NoGate:
    """Baseline 0: the model's output goes straight to the arm."""
    name = "no_gate"

    def __init__(self, world, **_):
        self.actuator = Actuator(world)

    def submit(self, p, now):
        return StepResult(True, outcome=self.actuator.execute(p)["outcome"])


class LabelGate:
    """Baseline 1: the v0.4 experimental PAG logic. Trusts the agent's labels."""
    name = "label_gate"
    PROTECTED = {"human", "baby", "animal"}
    DANGEROUS = {"knife", "blade", "weapon"}

    def __init__(self, world, **_):
        self.actuator = Actuator(world)
        self.cumulative_force = 0.0

    def submit(self, p, now):
        r = []
        if p.velocity > 1.0: r.append("VELOCITY_LIMIT")
        if p.force > 20.0: r.append("FORCE_LIMIT")
        if self.cumulative_force + p.force > 45.0: r.append("COMPOSITION_FORCE_LIMIT")
        if p.declared_target in self.PROTECTED and p.declared_operation in {"strike", "stab", "cut", "push"}:
            r.append("PROTECTED_TARGET")
        if p.declared_tool in self.DANGEROUS and p.declared_target in self.PROTECTED:
            r.append("DANGEROUS_TOOL_TARGET_PAIR")
        if r:
            return StepResult(False, tuple(r))
        self.cumulative_force += p.force
        return StepResult(True, outcome=self.actuator.execute(p)["outcome"])


class Network:
    """Heartbeat channel from the revocation service to the actuator.

    The service emits a heartbeat every `cadence_s` of simulated time. Each is
    delivered after `delay_s` plus uniform jitter, or dropped with probability
    `loss`. Deterministic for a given seed.
    """

    def __init__(self, service, actuator, cadence_s=0.1, delay_s=0.02, jitter_s=0.0, loss=0.0, seed=0):
        self.service, self.actuator = service, actuator
        self.cadence, self.delay, self.jitter, self.loss = cadence_s, delay_s, jitter_s, loss
        self.rng = random.Random(seed)
        self.next_emit = 0.0
        self.in_flight = []   # (deliver_at, hb)
        self.sent = self.dropped = self.delivered = 0

    def pump(self, t):
        while self.next_emit <= t + 1e-9:
            hb = self.service.heartbeat(at(self.next_emit))
            self.sent += 1
            if self.rng.random() < self.loss:
                self.dropped += 1
            else:
                self.in_flight.append((self.next_emit + self.delay + self.rng.uniform(0, self.jitter), hb))
            self.next_emit += self.cadence
        due = [x for x in self.in_flight if x[0] <= t + 1e-9]
        self.in_flight = [x for x in self.in_flight if x[0] > t + 1e-9]
        for _, hb in sorted(due, key=lambda x: x[0]):
            self.actuator.receive_heartbeat(hb)
            self.delivered += 1


class CaraPAG:
    """Perception-grounded hazard policy + AEPG authority + consumption +
    Ed25519 receipts + a revocation service reachable only over a Network +
    an actuator that mediates at release and at every control tick."""
    name = "cara_pag"

    def __init__(self, world, authority: AuthorityState, grant_for: dict, budget=64,
                 max_revocation_age_s=0.5, network=None, precontact_sequence_gate=False):
        self.world = world
        self.perception = Perception(world)
        self.authority = authority
        self.grant_for = grant_for
        self.engine = engine()
        self.evidence = EvidenceLog()
        self.confirmations = ConfirmationAuthority(CONFIRM_KEY)
        self.ledger = ConsumptionLedger(self.confirmations)
        self.signer = ReceiptSigner(RECEIPT_SEED, "pag-k1")
        self.pep = Tier3PEP(self.engine, self.ledger, self.signer, self.evidence, PEP_ID)
        self.actuator = Actuator(world, receipt_verifier=self.signer.verifier(),
                                 heartbeat_verifier=authority.revocation_service.verifier(),
                                 max_revocation_age_s=max_revocation_age_s,
                                 precontact_sequence_gate=precontact_sequence_gate)
        self.network = Network(authority.revocation_service, self.actuator, **(network or {}))
        self.t = 0.0
        self.slots = {}
        for actor, gid in grant_for.items():
            c = self.confirmations.confirm(confirmation_id=f"confirm:{actor}", subject_id=actor, grant_id=gid,
                                           resource_id=RESOURCE, action=ACTION, budget=budget,
                                           canonical_action_hash=None)
            self.slots[actor] = self.ledger.open(c).slot_id
        self.advance(0.2)  # warm-up: let the first heartbeats arrive

    def advance(self, t):
        self.t = max(self.t, t)
        self.network.pump(self.t)

    def _clock(self, now):
        self.advance(seconds_of(now) if now is not None else self.t)
        return at(self.t)

    def authorize(self, p, now=None):
        """Physical hazard check, then authority. Returns (StepResult|None, receipt, call)."""
        now = self._clock(now)
        snap, h = self.perception.snapshot()
        hz = hazards.evaluate(p, snap)
        if hz:
            self.evidence.append("PHYSICAL_DENIED", {"actor": p.actor, "reasons": list(hz), "world_state_hash": h})
            return StepResult(False, hz), None, None
        gid = self.grant_for.get(p.actor)
        if gid is None:
            return StepResult(False, ("NO_GRANT_PRESENTED",)), None, None
        call = self.authority.build(p, gid, snap, h, now)
        max_f, max_v = self.authority.physical_envelope(gid)
        limits = {"max_measured_force_n": max_f, "max_measured_velocity_mps": max_v}
        res, receipt = self.pep.authorize(slot_id=self.slots[p.actor], now=now, release_limits=limits, **call)
        if receipt is None:
            return StepResult(False, tuple(sorted({f.code for f in res.findings if f.hard}))), None, call
        return None, receipt, call

    def release(self, p, receipt, now=None):
        now = self._clock(now)
        ack = self.actuator.execute(p, receipt, now, tick_hook=self.advance)
        if "t_end" in ack:
            self.advance(ack["t_end"])
        return ack

    def settle(self, receipt, ack, call, now_settle=None):
        now_settle = self._clock(now_settle)

        def reauthorize():
            fresh = dict(call, revocations=list(self.authority.revocations))
            r = self.engine.authorize(fresh["request"], fresh["activity"], fresh["basis"], fresh["grants"],
                                      fresh["revocations"], fresh["policy"], fresh["current_state"],
                                      action=fresh["action"], pep_id=PEP_ID, now=now_settle)
            return r.allowed
        # A motion that stopped in safe state did not produce its effect:
        # release the budget rather than spend it.
        ack_for_ledger = dict(ack, executed=ack.get("completed", False))
        return self.pep.settle(receipt, ack_for_ledger, reauthorize)

    def submit(self, p, now=None):
        denied, receipt, call = self.authorize(p, now)
        if denied:
            return denied
        ack = self.release(p, receipt)
        s = self.settle(receipt, ack, call)
        reasons = (ack["reason"],) if ack.get("reason") else ()
        return StepResult(ack.get("completed", False), reasons, ack["outcome"], receipt, s)
