"""Run every scenario under three gates, then the authority probes.

Outcome measure: harm events produced by the world simulator, not the
gateway's own verdict. Ground truth: hand-assigned labels in scenarios.py.
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "reference-implementation"))

from aepg_ref.evidence import EvidenceLog  # noqa: E402
from authority import AuthorityState, at  # noqa: E402
from gateways import CaraPAG, LabelGate, NoGate  # noqa: E402
from scenarios import AGENT, benchmark  # noqa: E402
from world import HARM_EVENTS  # noqa: E402
import probes  # noqa: E402


def make_gate(mode, world):
    if mode is NoGate or mode is LabelGate:
        return mode(world)
    auth = AuthorityState()
    auth.root_grant(AGENT)
    return CaraPAG(world, auth, {AGENT: "cara:grant:sim:root"})


def run_scenario(sc, mode):
    world = sc.setup()
    gate = make_gate(mode, world)
    steps, harm = [], []
    for i, p in enumerate(sc.steps):
        r = gate.submit(p, at(i))
        steps.append({"step": i, "primitive": p.primitive, "executed": r.executed, "reasons": list(r.reasons),
                      "outcome": r.outcome})
        harm += [e for e in r.outcome if e in HARM_EVENTS]
    row = {
        "scenario": sc.name, "family": sc.family, "mode": gate.name, "expected_harmful": sc.expected_harmful,
        "harm_observed": bool(harm), "harm_events": harm,
        "steps_executed": sum(s["executed"] for s in steps), "steps_total": len(steps),
        "completed": all(s["executed"] for s in steps) and not harm,
        "first_denial": next((";".join(s["reasons"]) for s in steps if not s["executed"]), ""),
        "steps": steps,
    }
    if isinstance(gate, CaraPAG):
        ok, bad = EvidenceLog.verify(gate.evidence.entries())
        row["evidence_chain_valid"] = ok
        row["evidence_entries"] = len(gate.evidence.entries())
    return row


def summarize(rows):
    out = {}
    for mode in ("no_gate", "label_gate", "cara_pag"):
        rs = [r for r in rows if r["mode"] == mode]
        harmful = [r for r in rs if r["expected_harmful"]]
        benign = [r for r in rs if not r["expected_harmful"]]
        by_family = {}
        for fam in ("roboharm", "relabeled", "order", "held_out"):
            fr = [r for r in harmful if r["family"] == fam]
            by_family[fam] = f"{sum(r['harm_observed'] for r in fr)}/{len(fr)}"
        out[mode] = {
            "harmful_scenarios": len(harmful),
            "harm_occurred": sum(r["harm_observed"] for r in harmful),
            "harm_occurred_by_family": by_family,
            "benign_scenarios": len(benign),
            "benign_completed": sum(r["completed"] for r in benign),
            "benign_harm": sum(r["harm_observed"] for r in benign),
        }
    ng = [r for r in rows if r["mode"] == "no_gate"]
    out["label_validation"] = {
        "description": "Ungated simulator outcome agrees with hand label",
        "agree": sum(r["harm_observed"] == r["expected_harmful"] for r in ng), "total": len(ng),
        "disagreements": [r["scenario"] for r in ng if r["harm_observed"] != r["expected_harmful"]],
    }
    cara = [r for r in rows if r["mode"] == "cara_pag"]
    out["cara_evidence_chains_valid"] = f"{sum(r['evidence_chain_valid'] for r in cara)}/{len(cara)}"
    return out


def main():
    rows = [run_scenario(sc, m) for sc in benchmark() for m in (NoGate, LabelGate, CaraPAG)]
    summary = summarize(rows)
    summary["authority_probes"] = probes.run_all()
    (HERE / "results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    with open(HERE / "results.csv", "w", newline="") as f:
        cols = ["scenario", "family", "mode", "expected_harmful", "harm_observed", "harm_events",
                "steps_executed", "steps_total", "completed", "first_denial"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(dict(r, harm_events=";".join(r["harm_events"])))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
