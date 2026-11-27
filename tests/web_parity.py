"""Check that web/hfp_model.js gives the same numbers as hfp_model.py (the source of truth).

  python tests/web_parity.py

Runs every golden recipe (tests/golden_recipes.json) through both and compares raw results, 1-10 scores and
pH. Needs Node on PATH (replaces web/parity_test.py, which needed the quickjs package and did not compare
scores). Standard library only on the Python side.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hfp_model as m  # noqa: E402
from run_tests import resolve_strict  # noqa: E402

TOL = 1e-9


def main():
    db = m.load_db()
    with io.open(os.path.join(HERE, "golden_recipes.json"), encoding="utf-8") as fh:
        golden = json.load(fh)
    cases, py = [], []
    for g in golden:
        rec = [{"ingredient": resolve_strict(db, q), "amount": a, "unit": u} for q, a, u in g["items"]]
        o = g["opt"]
        cases.append({"name": g["name"], "recipe": rec, "opt": o})
        py.append(m.compute([dict(r) for r in rec], db=db, water_loss_g=o.get("water_loss_g", 0),
                            cook_min=o.get("cook_min", 0), cook_temp_c=o.get("cook_temp_c")))
    fd, tmp = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(cases, fh)
        res = subprocess.run(["node", os.path.join(HERE, "web_parity_runner.js"), tmp],
                             capture_output=True, text=True, encoding="utf-8")
    finally:
        os.remove(tmp)
    if res.returncode != 0:
        print("Node failed:\n" + res.stderr[:2000])
        return 2
    js = json.loads(res.stdout)
    worst, bad = 0.0, 0
    for c, p, j in zip(cases, py, js):
        diffs = {}
        pairs = [("raw." + k, v, j["results"].get(k)) for k, v in p["results"].items()]
        pairs += [("score." + k, v, j["scores"].get(k)) for k, v in p["scores"].items()]
        pairs.append(("pH", (p.get("acidity") or {}).get("pH"), j.get("pH")))
        for k in ("sodium_mg", "sodium_mg_per_100g"):  # v.2.16.2 label-unit sodium
            pairs.append(("totals." + k, p["totals"][k], (j.get("totals") or {}).get(k)))
        for k, a, b in pairs:
            if isinstance(a, bool) or isinstance(b, bool) or not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                diffs[k] = 0.0 if a == b else float("inf")
            else:
                diffs[k] = abs(a - b) / max(1.0, abs(a))
        d = max(diffs.values())
        worst = max(worst, d)
        ok = d < TOL
        bad += (not ok)
        print("%s  %-46s max diff %.1e%s" % ("PASS" if ok else "FAIL", c["name"], d,
                                             "" if ok else "  worst: " + max(diffs, key=diffs.get)))
    print("\n%s: %d recipes, worst difference %.1e, umami reference py %.6f" % (
        "PARITY PASS" if not bad else "PARITY FAIL", len(cases), worst, m.SCORE_REF["umami"]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
