"""Durable authorization consumption, after CapLease (arXiv:2608.01710).

Model
-----
A user confirmation opens an AuthoritySlot: a budget of N actuations for one
(subject, grant, resource, action) scope, optionally pinned to one canonical
action. Each use goes through Prepare -> Commit (or Abort):

  prepare  reserves one unit. Units in flight count against the budget, so
           concurrent prepares cannot overspend it.
  commit   re-checks authority, then spends the unit. Committing the same
           reservation again is idempotent and never spends twice.
  abort    releases the unit.

Fixes relative to the v0.4 experimental ledger:
  * the semantic key is claimed at prepare time, not commit time, so two
    in-flight records can no longer both commit;
  * budgets above 1 are usable;
  * confirmations are MAC-verified and single-use, so an agent cannot
    mint fresh authority by inventing a confirmation string;
  * authority is re-checked through a caller-supplied reauthorize() that the
    trusted PEP backs with the AEPG engine, not a caller boolean;
  * unknown ids raise ConsumptionError, never KeyError;
  * state can be snapshotted and restored to exercise crash recovery.

This is in-memory reference semantics. Production requires durable,
transactional storage and asymmetric signatures (the HMAC key used here must
be held only by the confirmation service and the ledger, never the agent).
"""
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, replace
from enum import Enum
from threading import Lock
from typing import Callable, Optional

from .canonical import canonical_json


class ConsumptionError(Exception):
    pass


class ReservationState(str, Enum):
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass(frozen=True)
class Confirmation:
    confirmation_id: str
    subject_id: str
    grant_id: str
    resource_id: str
    action: str
    budget: int
    canonical_action_hash: Optional[str]  # None = any action within scope
    mac: str = ""

    def fields(self):
        d = asdict(self)
        d.pop("mac")
        return d


class ConfirmationAuthority:
    """Issues and verifies user confirmations. The agent never holds this key."""

    def __init__(self, key: bytes):
        if len(key) < 16:
            raise ValueError("confirmation key too short")
        self._key = key

    def _mac(self, fields):
        return hmac.new(self._key, canonical_json(fields), hashlib.sha256).hexdigest()

    def confirm(self, **fields) -> Confirmation:
        c = Confirmation(**fields)
        return replace(c, mac=self._mac(c.fields()))

    def verify(self, c: Confirmation) -> bool:
        return isinstance(c.mac, str) and hmac.compare_digest(c.mac, self._mac(c.fields()))


@dataclass(frozen=True)
class AuthoritySlot:
    slot_id: str
    subject_id: str
    grant_id: str
    resource_id: str
    action: str
    pinned_action_hash: Optional[str]
    budget: int
    remaining: int
    in_flight: int
    sequence: int


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    slot_id: str
    canonical_action_hash: str
    effect_hash: str
    state: ReservationState
    sequence: int


class ConsumptionLedger:
    def __init__(self, confirmations: ConfirmationAuthority):
        self._conf = confirmations
        self._lock = Lock()
        self._slots: dict[str, AuthoritySlot] = {}
        self._reservations: dict[str, Reservation] = {}
        self._used_confirmations: set[str] = set()

    # -- helpers ---------------------------------------------------------
    def _slot(self, slot_id):
        s = self._slots.get(slot_id)
        if s is None:
            raise ConsumptionError(f"unknown slot {slot_id!r}")
        return s

    def _res(self, reservation_id):
        r = self._reservations.get(reservation_id)
        if r is None:
            raise ConsumptionError(f"unknown reservation {reservation_id!r}")
        return r

    # -- lifecycle -------------------------------------------------------
    def open(self, confirmation: Confirmation) -> AuthoritySlot:
        if not self._conf.verify(confirmation):
            raise ConsumptionError("confirmation MAC invalid")
        if not isinstance(confirmation.budget, int) or isinstance(confirmation.budget, bool) or confirmation.budget < 1:
            raise ConsumptionError("budget must be a positive integer")
        with self._lock:
            if confirmation.confirmation_id in self._used_confirmations:
                raise ConsumptionError("confirmation already used")
            self._used_confirmations.add(confirmation.confirmation_id)
            s = AuthoritySlot(
                slot_id=confirmation.confirmation_id, subject_id=confirmation.subject_id,
                grant_id=confirmation.grant_id, resource_id=confirmation.resource_id,
                action=confirmation.action, pinned_action_hash=confirmation.canonical_action_hash,
                budget=confirmation.budget, remaining=confirmation.budget, in_flight=0, sequence=0,
            )
            self._slots[s.slot_id] = s
            return s

    def prepare(self, slot_id, *, reservation_id, subject_id, grant_id, resource_id, action,
                canonical_action_hash, effect_hash) -> Reservation:
        with self._lock:
            s = self._slot(slot_id)
            if (subject_id, grant_id, resource_id, action) != (s.subject_id, s.grant_id, s.resource_id, s.action):
                raise ConsumptionError("request is outside the confirmed scope")
            if s.pinned_action_hash is not None and canonical_action_hash != s.pinned_action_hash:
                raise ConsumptionError("confirmation is pinned to a different action")
            if reservation_id in self._reservations:
                raise ConsumptionError("duplicate reservation id")
            if s.remaining - s.in_flight < 1:
                raise ConsumptionError("execution budget exhausted (including in-flight reservations)")
            self._slots[slot_id] = replace(s, in_flight=s.in_flight + 1, sequence=s.sequence + 1)
            r = Reservation(reservation_id, slot_id, canonical_action_hash, effect_hash, ReservationState.PREPARED, 0)
            self._reservations[reservation_id] = r
            return r

    def abort(self, reservation_id) -> Reservation:
        with self._lock:
            r = self._res(reservation_id)
            if r.state == ReservationState.ABORTED:
                return r
            if r.state != ReservationState.PREPARED:
                raise ConsumptionError("only a prepared reservation can abort")
            s = self._slot(r.slot_id)
            self._slots[r.slot_id] = replace(s, in_flight=s.in_flight - 1, sequence=s.sequence + 1)
            nr = replace(r, state=ReservationState.ABORTED, sequence=r.sequence + 1)
            self._reservations[reservation_id] = nr
            return nr

    def commit(self, reservation_id, effect_hash, reauthorize: Callable[[], bool]) -> Reservation:
        if not callable(reauthorize):
            raise ConsumptionError("reauthorize must be a callable backed by the PDP")
        with self._lock:
            r = self._res(reservation_id)
            if r.effect_hash != effect_hash:
                raise ConsumptionError("committed effect differs from prepared effect")
            if r.state == ReservationState.COMMITTED:
                return r  # idempotent: retries and crash recovery never spend twice
            if r.state == ReservationState.ABORTED:
                raise ConsumptionError("reservation was aborted")
            try:
                still_ok = bool(reauthorize())
            except Exception:
                still_ok = False  # indeterminate authority fails closed
            s = self._slot(r.slot_id)
            if not still_ok:
                self._slots[r.slot_id] = replace(s, in_flight=s.in_flight - 1, sequence=s.sequence + 1)
                self._reservations[reservation_id] = replace(r, state=ReservationState.ABORTED, sequence=r.sequence + 1)
                raise ConsumptionError("authority no longer valid at commit")
            self._slots[r.slot_id] = replace(s, remaining=s.remaining - 1, in_flight=s.in_flight - 1,
                                             sequence=s.sequence + 1)
            nr = replace(r, state=ReservationState.COMMITTED, sequence=r.sequence + 1)
            self._reservations[reservation_id] = nr
            return nr

    # -- inspection and crash simulation ---------------------------------
    def slot(self, slot_id) -> AuthoritySlot:
        return self._slot(slot_id)

    def reservation(self, reservation_id) -> Reservation:
        return self._res(reservation_id)

    def snapshot(self) -> str:
        with self._lock:
            return json.dumps({
                "slots": [asdict(s) for s in self._slots.values()],
                "reservations": [dict(asdict(r), state=r.state.value) for r in self._reservations.values()],
                "used_confirmations": sorted(self._used_confirmations),
            })

    @classmethod
    def restore(cls, confirmations: ConfirmationAuthority, data: str) -> "ConsumptionLedger":
        d = json.loads(data)
        led = cls(confirmations)
        led._slots = {s["slot_id"]: AuthoritySlot(**s) for s in d["slots"]}
        led._reservations = {r["reservation_id"]: Reservation(**dict(r, state=ReservationState(r["state"])))
                             for r in d["reservations"]}
        led._used_confirmations = set(d["used_confirmations"])
        return led
