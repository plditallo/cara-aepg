"""AuthorityConsumption ledger. Tests marked "v0.4 regression" failed or were
exploitable against the v0.4 experimental ledger."""
from dataclasses import replace
import threading
import pytest
from aepg_ref.consumption import (ConfirmationAuthority, ConsumptionError, ConsumptionLedger,
                                  ReservationState)

KEY = b"user-confirmation-key-0123456789"
SCOPE = dict(subject_id="agent1", grant_id="g1", resource_id="arm-1", action="actuate")


@pytest.fixture
def ca():
    return ConfirmationAuthority(KEY)


def confirm(ca, cid="conf-1", budget=1, pinned=None):
    return ca.confirm(confirmation_id=cid, budget=budget, canonical_action_hash=pinned, **SCOPE)


def prep(led, slot="conf-1", rid="r1", h="sha256:a1"):
    return led.prepare(slot, reservation_id=rid, canonical_action_hash=h, effect_hash=h, **SCOPE)


def ok():
    return True


def test_control_prepare_commit(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca))
    prep(led)
    assert led.commit("r1", "sha256:a1", ok).state == ReservationState.COMMITTED
    assert led.slot("conf-1").remaining == 0


def test_concurrent_reservations_cannot_overspend(ca):  # v0.4 regression
    led = ConsumptionLedger(ca); led.open(confirm(ca))
    prep(led, rid="a")
    with pytest.raises(ConsumptionError, match="budget exhausted"):
        prep(led, rid="b")


def test_threaded_prepares_respect_budget(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca, budget=5))
    wins, errs = [], []

    def go(i):
        try:
            prep(led, rid=f"t{i}", h=f"sha256:{i:02x}"); wins.append(i)
        except ConsumptionError:
            errs.append(i)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(50)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(wins) == 5 and len(errs) == 45


def test_budget_above_one_is_usable(ca):  # v0.4 regression
    led = ConsumptionLedger(ca); led.open(confirm(ca, budget=3))
    for i in range(3):
        prep(led, rid=f"r{i}", h=f"sha256:{i}0"); led.commit(f"r{i}", f"sha256:{i}0", ok)
    assert led.slot("conf-1").remaining == 0
    with pytest.raises(ConsumptionError):
        prep(led, rid="r9", h="sha256:90")


def test_forged_confirmation_rejected(ca):  # v0.4 regression
    led = ConsumptionLedger(ca)
    forged = replace(confirm(ca), confirmation_id="conf-made-up-by-agent")
    with pytest.raises(ConsumptionError, match="MAC"):
        led.open(forged)


def test_confirmation_budget_cannot_be_inflated(ca):
    led = ConsumptionLedger(ca)
    with pytest.raises(ConsumptionError, match="MAC"):
        led.open(replace(confirm(ca), budget=1000))


def test_confirmation_is_single_use(ca):
    led = ConsumptionLedger(ca); c = confirm(ca); led.open(c)
    with pytest.raises(ConsumptionError, match="already used"):
        led.open(c)


def test_fresh_reservation_id_is_not_fresh_authority(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca))
    prep(led, rid="r1"); led.commit("r1", "sha256:a1", ok)
    with pytest.raises(ConsumptionError):
        prep(led, rid="brand-new-id")


def test_scope_mismatch(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca))
    with pytest.raises(ConsumptionError, match="scope"):
        led.prepare("conf-1", reservation_id="x", subject_id="agent2", grant_id="g1", resource_id="arm-1",
                    action="actuate", canonical_action_hash="sha256:a1", effect_hash="sha256:a1")


def test_pinned_confirmation(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca, pinned="sha256:a1"))
    with pytest.raises(ConsumptionError, match="pinned"):
        prep(led, h="sha256:bb")
    prep(led, rid="r2", h="sha256:a1")


def test_commit_is_idempotent(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca, budget=2))
    prep(led); led.commit("r1", "sha256:a1", ok); led.commit("r1", "sha256:a1", ok)
    assert led.slot("conf-1").remaining == 1


def test_effect_substitution_at_commit(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca)); prep(led)
    with pytest.raises(ConsumptionError, match="differs"):
        led.commit("r1", "sha256:ee", ok)


def test_revocation_at_commit_releases_unit(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca)); prep(led)
    with pytest.raises(ConsumptionError, match="no longer valid"):
        led.commit("r1", "sha256:a1", lambda: False)
    assert led.reservation("r1").state == ReservationState.ABORTED
    assert led.slot("conf-1").in_flight == 0 and led.slot("conf-1").remaining == 1


def test_reauthorize_exception_fails_closed(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca)); prep(led)

    def boom():
        raise RuntimeError("PDP unreachable")
    with pytest.raises(ConsumptionError):
        led.commit("r1", "sha256:a1", boom)


def test_boolean_is_not_accepted_as_reauthorization(ca):  # v0.4 regression
    led = ConsumptionLedger(ca); led.open(confirm(ca)); prep(led)
    with pytest.raises(ConsumptionError, match="callable"):
        led.commit("r1", "sha256:a1", True)


def test_abort_releases_and_retry_works(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca)); prep(led); led.abort("r1")
    prep(led, rid="r2"); led.commit("r2", "sha256:a1", ok)
    with pytest.raises(ConsumptionError, match="aborted"):
        led.commit("r1", "sha256:a1", ok)


def test_unknown_ids_raise_consumption_error(ca):  # v0.4 regression
    led = ConsumptionLedger(ca)
    with pytest.raises(ConsumptionError):
        prep(led, slot="nope")
    with pytest.raises(ConsumptionError):
        led.commit("nope", "sha256:a1", ok)


def test_crash_between_prepare_and_commit(ca):
    led = ConsumptionLedger(ca); led.open(confirm(ca)); prep(led)
    recovered = ConsumptionLedger.restore(ca, led.snapshot())
    with pytest.raises(ConsumptionError):
        prep(recovered, rid="r2")  # in-flight unit survives the crash
    recovered.commit("r1", "sha256:a1", ok)
    again = ConsumptionLedger.restore(ca, recovered.snapshot())
    again.commit("r1", "sha256:a1", ok)  # idempotent after second crash
    assert again.slot("conf-1").remaining == 0
    with pytest.raises(ConsumptionError, match="already used"):
        again.open(confirm(ca))


def test_bad_budget(ca):
    with pytest.raises(ConsumptionError):
        ConsumptionLedger(ca).open(confirm(ca, budget=0))
