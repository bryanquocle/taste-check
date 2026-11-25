"""Formulation tools on top of the taste model (Stage 3, Nov 15, 2026; Python only).

COMPARE two versions of a recipe and say which differences are real:
  python hfp_formulate.py compare --a "Salt=8 g" "Water=1000 g" --b "Salt=6 g" "Monosodium Glutamate=2 g" "Water=1000 g"

SOLVE for the amount of one ingredient that brings one taste to a target score:
  python hfp_formulate.py solve --taste saltiness --target 6.9 --vary "Monosodium Glutamate" "Salt=6 g" "Water=1000 g"
  (the recipe is everything after the options; the --vary ingredient may or may not already be in it)

Both accept --evaporate G, --cook MIN and --temp C (applied to every recipe). Compare also takes --draws N.

How COMPARE decides. Both recipes are re-run 150 times with the SAME redraws of the uncertain inputs
(hfp_ranges.py, common random numbers), so uncertainty the two versions share cancels out. For each taste it
reports B minus A and the middle 80% of the paired differences. A difference is called real only if
  (1) the scores differ by at least 0.25 points (the smallest gap the outside tasting panels support), and
  (2) the middle 80% of the paired differences does not include zero.
Otherwise the answer is "no real difference". This is a statement about the model's own uncertainty, not a
promise about what a panel would find; it does not cover anything the model leaves out.

How SOLVE works. It searches the amount of the chosen ingredient (in grams, by bisection) until the taste's
score hits the target, then re-runs the solved recipe and shows what happened to the other tastes. If the
target cannot be reached by that ingredient it says so and reports the closest it can get.
Standard library only.
"""
import sys

import hfp_model as m
import hfp_ranges as hr

MIN_GAP = 0.25            # score points; see hfp_ranges.py (floor from the outside panels)
SOLVE_TOL = 0.005         # score points
TASTES = hr.TASTES


def _scores(recipe, db, opt):
    r = m.compute([dict(it) for it in recipe], db=db, water_loss_g=opt.get("water_loss_g", 0.0),
                  cook_min=opt.get("cook_min", 0.0), cook_temp_c=opt.get("cook_temp_c"))
    return r["scores"]


def compare(recipe_a, recipe_b, opt_a=None, opt_b=None, n=hr.N_DRAWS, seed=hr.SEED, db=None):
    """{taste: {"a", "b", "diff", "low", "high", "verdict"}}; verdict is "higher", "lower" or "same" (B vs A)."""
    db = db or m.load_db()
    opt_a, opt_b = opt_a or {}, opt_b or {}
    points, draws = hr.sample([recipe_a, recipe_b], [opt_a, opt_b], n=n, seed=seed, db=db)
    out = {}
    for t in TASTES:
        a, b = points[0].get(t), points[1].get(t)
        if a is None or b is None:
            out[t] = None
            continue
        d = b - a
        diffs = [y[t] - x[t] for x, y in zip(draws[0], draws[1]) if x.get(t) is not None and y.get(t) is not None]
        lo = min(hr.percentile(diffs, hr.INTERVAL[0]), d)
        hi = max(hr.percentile(diffs, hr.INTERVAL[1]), d)
        real = abs(d) >= MIN_GAP and (lo > 0 or hi < 0)
        out[t] = {"a": a, "b": b, "diff": d, "low": lo, "high": hi,
                  "verdict": ("higher" if d > 0 else "lower") if real else "same",
                  "both_at_limit": (a >= 10.0 and b >= 10.0) or (a <= 1.0 and b <= 1.0)}
    return out


def compare_report(res, n=hr.N_DRAWS):
    lines = ["COMPARE (B minus A; a difference is real only if it is at least %.2f points and the middle 80%%" % MIN_GAP,
             "         of %d paired re-runs stays on one side of zero)" % n,
             "  %-10s %6s %6s   %-22s %s" % ("", "A", "B", "B minus A (80%)", "call")]
    for t in TASTES:
        r = res.get(t)
        if r is None:
            continue
        call = {"higher": "B is HIGHER", "lower": "B is LOWER", "same": "no real difference"}[r["verdict"]]
        if r["verdict"] == "same" and r["both_at_limit"]:
            call += " (both at the %s of the scale)" % ("top" if r["a"] >= 10 else "bottom")
        lines.append("  %-10s %6.1f %6.1f   %+5.2f (%+.2f to %+.2f)   %s" % (
            t.upper(), r["a"], r["b"], r["diff"], r["low"], r["high"], call))
    lines.append("  Model uncertainty only. Not covered: aroma, bitterness, fat, texture, solids, curve shapes.")
    return "\n".join(lines)


def _with_amount(recipe, name, grams):
    rec = [dict(it) for it in recipe if it["ingredient"] != name]
    if grams > 0:
        rec.append({"ingredient": name, "amount": grams, "unit": "g"})
    return rec


def solve(recipe, vary, taste, target, opt=None, db=None, max_grams=None):
    """Find grams of `vary` so that `taste` scores `target`. Returns a dict with "status":
    "solved", "too_low" (even the maximum amount does not reach it), "too_high" (even zero overshoots)
    or "no_effect" (the ingredient does not move that taste)."""
    db = db or m.load_db()
    opt = opt or {}
    if taste not in TASTES:
        raise ValueError("taste must be one of " + ", ".join(TASTES))
    name = m.resolve(db, vary)
    recipe = [dict(it, ingredient=m.resolve(db, it["ingredient"])) for it in recipe]
    current = [it for it in recipe if it["ingredient"] == name]
    if any(it.get("unit", "g") != "g" for it in current):
        raise ValueError("give the ingredient to vary in grams")
    start = sum(it["amount"] for it in current)
    base_mass = sum(it["amount"] for it in recipe if it.get("unit", "g") == "g" and it["ingredient"] != name)
    hi_g = max_grams if max_grams is not None else max(base_mass, 10.0)   # at most as much as the rest of the recipe

    def f(g):
        s = _scores(_with_amount(recipe, name, g), db, opt)[taste]
        return 1.0 if s is None else s

    before = _scores(recipe, db, opt)
    s0, s1 = f(0.0), f(hi_g)
    result = {"ingredient": name, "taste": taste, "target": target, "start_grams": start, "before": before,
              "score_at_zero": s0, "score_at_max": s1, "max_grams": hi_g}
    if abs(s1 - s0) < 1e-9:
        result.update(status="no_effect", grams=start)
    elif (target - s0) * (target - s1) > 0:                 # target outside what this ingredient can reach
        rising = s1 > s0
        below_all = target < min(s0, s1)
        result.update(status="too_high" if below_all else "too_low",
                      grams=(0.0 if (below_all == rising) else hi_g))
    else:
        lo, hi = 0.0, hi_g
        flo = s0 - target
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            fm = f(mid) - target
            if abs(fm) < SOLVE_TOL * 0.1 or (hi - lo) < 1e-6:
                lo = hi = mid
                break
            if (fm > 0) == (flo > 0):
                lo, flo = mid, fm
            else:
                hi = mid
        result.update(status="solved", grams=0.5 * (lo + hi))
    result["after"] = _scores(_with_amount(recipe, name, result["grams"]), db, opt)
    result["recipe"] = _with_amount(recipe, name, result["grams"])
    return result


def solve_report(r):
    t = r["taste"]
    head = {"solved": "SOLVED", "too_low": "CANNOT REACH THE TARGET (too low even at the maximum tried)",
            "too_high": "CANNOT REACH THE TARGET (already past it with none)",
            "no_effect": "NO EFFECT: this ingredient does not move that taste in the model"}[r["status"]]
    lines = ["SOLVE: %s to reach %s %.2f" % (r["ingredient"], t, r["target"]), "  " + head]
    lines.append("  %s: %.2f g (was %.2f g); tried 0 to %.0f g, where %s runs %.2f to %.2f"
                 % (r["ingredient"], r["grams"], r["start_grams"], r["max_grams"], t, r["score_at_zero"], r["score_at_max"]))
    lines.append("  %-10s %7s %7s" % ("", "before", "after"))
    for k in TASTES:
        b, a = r["before"].get(k), r["after"].get(k)
        if b is None or a is None:
            continue
        lines.append("  %-10s %7.2f %7.2f%s" % (k.upper(), b, a, "   <- target %.2f" % r["target"] if k == t else ""))
    lines.append("  Run compare on the before and after recipes to see which side effects are real.")
    return "\n".join(lines)


# ---- command line -----------------------------------------------------------------------------------------
def _take(args, name, cast=float, default=None):
    if name in args:
        i = args.index(name)
        val = cast(args[i + 1])
        del args[i:i + 2]
        return val
    return default


def main(argv):
    args = list(argv)
    if not args or args[0] not in ("compare", "solve"):
        print(__doc__)
        return 0
    mode = args.pop(0)
    opt = {"water_loss_g": _take(args, "--evaporate", default=0.0), "cook_min": _take(args, "--cook", default=0.0),
           "cook_temp_c": _take(args, "--temp")}
    if mode == "compare":
        n = int(_take(args, "--draws", default=hr.N_DRAWS))
        if "--a" not in args or "--b" not in args:
            print("compare needs --a <recipe> --b <recipe>")
            return 2
        ia, ib = args.index("--a"), args.index("--b")
        a = args[ia + 1:ib] if ia < ib else args[ia + 1:]
        b = args[ib + 1:] if ia < ib else args[ib + 1:ia]
        res = compare([m.parse_arg(x) for x in a], [m.parse_arg(x) for x in b], opt, opt, n=n)
        print(compare_report(res, n))
        return 0
    taste = _take(args, "--taste", cast=str)
    target = _take(args, "--target")
    vary = _take(args, "--vary", cast=str)
    max_g = _take(args, "--max")
    if taste is None or target is None or vary is None or not args:
        print("solve needs --taste, --target, --vary and a recipe")
        return 2
    print(solve_report(solve([m.parse_arg(x) for x in args], vary, taste, target, opt, max_grams=max_g)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
