"""DEV-only native reachability witnesses, NOT an agent or synthesis candidate.

Researcher-labelled recipes test actuator/sensor feasibility. They must never be
imported by the candidate or counted as autonomous experiment generation.
"""
import json
from pathlib import Path
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.action_core.world import Sandbox, Action
from scripts.representation_r3_dev import configuration


def probe():
    rows = []
    with tempfile.TemporaryDirectory(prefix="atanor_r10_substrate_") as directory:
        root = Path(directory)
        recipes = {
            "coupled_full": [],
            "coupled_empty": [("empty", ("first",))],
            "detached_absent": [("unlink", ("first",))],
            "detached_empty": [("unlink", ("first",)), ("empty", ("first",))],
            "independent_full": [("unlink", ("first",)), ("copy", ("reference", "first"))],
            "independent_mixed": [("unlink", ("first",)), ("empty", ("first",))],
        }
        for count in (2, 3, 4, 5):
            for label, recipe in recipes.items():
                cfg, aliases, reference, payload = configuration(count, 119031 + count, payload=b"x"*23)
                body = Sandbox(root / f"{count}_{label}", **cfg)
                handles = {"first": aliases[0], "reference": reference}
                before = body.observe().to_dict()
                trace = []
                # Full independence requires detaching every member except the last.
                concrete = ([("unlink", (h,)), ("copy", (reference, h))]
                            for h in aliases[:-1])
                actions = ([step for pair in concrete for step in pair]
                           if label == "independent_full" else
                           [(op, tuple(handles[h] for h in args)) for op, args in recipe])
                if label == "independent_mixed":
                    # v1 mistakenly left the remaining >2 members coupled.
                    # Correct the researcher witness; preserve the v1 evidence.
                    actions.extend(step for h in aliases[1:-1]
                                   for step in (("unlink", (h,)), ("copy", (reference, h))))
                for op, args in actions:
                    action = Action(op, args)
                    if action not in body.actions():
                        raise AssertionError("witness outside permitted actions")
                    observed = body.observe().to_dict()
                    success = body.step(action)
                    trace.append({"before": observed, "action": action.to_dict(), "success": success,
                                  "after": body.observe().to_dict()})
                expected_cfg, _, _, _ = configuration(count, 119031 + count, label, b"x"*23)
                expected = Sandbox(root / f"expected_{count}_{label}", **expected_cfg).observe().to_dict()
                after = body.observe().to_dict()
                rows.append({"count": count, "target": label, "recipe_length": len(actions),
                             "matches_operator_fixture": after == expected,
                             "protected_reference_preserved": body._paths[reference].read_bytes() == payload,
                             "initial": before, "final": after, "trace": trace})
    return {"scope": "researcher native witnesses; no learned synthesis or fresh evaluation",
            "rows": rows}


if __name__ == "__main__":
    target = Path(sys.argv[1])
    result = probe()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
    print(json.dumps({"matches": sum(r["matches_operator_fixture"] for r in result["rows"]),
                      "total": len(result["rows"]),
                      "mismatches": [{k:r[k] for k in ("count","target","recipe_length")}
                                     for r in result["rows"] if not r["matches_operator_fixture"]]}))
