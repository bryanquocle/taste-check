"""Tests for hfp_ranges.py (Stage 2).

  python tests/ranges_test.py            compare against tests/ranges_expected.json
  python tests/ranges_test.py --freeze   rewrite the frozen values (only after an approved change)

Checks: (1) the seeded ranges for four golden recipes match the frozen values; (2) every range contains its
score and stays inside 1 to 10; (3) the same seed gives the same answer twice; (4) redrawing never leaves a
model constant changed; (5) two recipes that share an ingredient get the same draw for it (common random numbers).
Uses 40 draws to stay quick (about 20 seconds).
"""
import io
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hfp_model as m  # noqa: E402
import hfp_ranges as hr  # noqa: E402
from run_tests import resolve_strict  # noqa: E402

N = 40
NAMES = ["kitchen test A: 8 g/L salt", "kitchen test C: 6 g/L salt + 2 g/L MSG", "canned tomato", "parmesan water"]
EXPECTED = os.path.join(HERE, "ranges_expected.json")
TOL = 1e-9


def main():
    db = m.load_db()
    with io.open(os.path.join(HERE, "golden_recipes.json"), encoding="utf-8") as fh:
        golden = {g["name"]: g for g in json.load(fh)}
    recs = [[{"ingredient": resolve_strict(db, q), "amount": a, "unit": u} for q, a, u in golden[n]["items"]] for n in NAMES]
    const_before = {k: getattr(mod, k) for mod, k in [(m, "SALT_SHIFT_MAX"), (m, "KOKUMI_UMAMI_GAIN"),
                    (m, "KOKUMI_SALT_GAIN"), (m, "SYNERGY_MAX_FOLD"), (m, "KOKUMI_EC50_MM"), (m.ab, "SUPPRESS_S50")]}
    points, draws = hr.sample(recs, n=N, db=db)
    now = {n: hr.summarize(p, d) for n, p, d in zip(NAMES, points, draws)}
    problems = []
    const_after = {k: getattr(mod, k) for mod, k in [(m, "SALT_SHIFT_MAX"), (m, "KOKUMI_UMAMI_GAIN"),
                   (m, "KOKUMI_SALT_GAIN"), (m, "SYNERGY_MAX_FOLD"), (m, "KOKUMI_EC50_MM"), (m.ab, "SUPPRESS_S50")]}
    if const_before != const_after:
        problems.append("model constants were left changed after sampling")
    for n, r in now.items():
        for t, v in r.items():
            if v is None:
                continue
            if not (1.0 <= v["low"] <= v["score"] <= v["high"] <= 10.0):
                problems.append("%s %s: range does not contain the score (%r)" % (n, t, v))
    again = hr.summarize(*[x[0] for x in hr.sample([recs[2]], n=N, db=db)])
    if again != now[NAMES[2]]:
        problems.append("same seed gave a different answer the second time")
    # common random numbers: canned tomato alone vs inside a two-recipe call must give identical draws
    if hr.sample([recs[2]], n=5, db=db)[1][0] != hr.sample([recs[0], recs[2]], n=5, db=db)[1][1]:
        problems.append("draws for a recipe changed when another recipe was sampled with it")
    if "--freeze" in sys.argv:
        with io.open(EXPECTED, "w", encoding="utf-8") as fh:
            json.dump({"n": N, "seed": hr.SEED, "ranges": now}, fh, indent=1)
        print("Frozen ranges for %d recipes" % len(now))
    else:
        with io.open(EXPECTED, encoding="utf-8") as fh:
            exp = json.load(fh)["ranges"]
        for n in NAMES:
            for t, v in exp[n].items():
                g = now[n][t]
                if (v is None) != (g is None) or (v and any(abs(v[k] - g[k]) > TOL for k in v)):
                    problems.append("%s %s: expected %r got %r" % (n, t, v, g))
    for n in NAMES:
        print("  %-42s " % n + "  ".join("%s %.1f (%.1f-%.1f)" % (t[:3], v["score"], v["low"], v["high"])
                                         for t, v in now[n].items() if v))
    print("\n" + ("RANGES TEST PASS" if not problems else "RANGES TEST FAIL\n  " + "\n  ".join(problems[:10])))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
