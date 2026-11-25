"""Uncertainty ranges for the 1-10 taste scores (Stage 2, Nov 15, 2026; Python only).

  python hfp_model.py --ranges "Tomato (Canned)=200 g" "Water=100 g"
  python hfp_ranges.py "Tomato (Canned)=200 g" "Water=100 g"          (same thing)

Each score is reported as "7.6 (6.9 to 8.2)": the model's score and the middle 80% of N re-runs in which
the inputs the model is unsure about are redrawn. Three things are redrawn:

1. INGREDIENT DATA, by data tier (one draw per ingredient and compound group, so glutamate and aspartate
   move together, the three nucleotides move together, and so on):
     tier 1 measured            x/÷ 1.20      tier 2 derived or sibling   x/÷ 1.35
     tier 3 category estimate   x/÷ 1.50      defined composition (salt, sugar, MSG, KCl)  x/÷ 1.02
   A BLANK glutamate or nucleotide cell (the model counts it as 0) is drawn between 0 and the median of the
   ingredient's category (hfp_categories.csv; database median if the category has fewer than 3 values).
   Reference pH moves by +/-0.15 (tier 1), 0.25 (tier 2) or 0.40 (tier 3).
2. PLACEHOLDER CONSTANTS, each drawn from a triangle that peaks at the value the model uses:
     salt effect on umami (SALT_SHIFT_MAX)   1.0 to 5.5, peak 2.0   (off ... Ugawa 1992 human sweet amino acids)
     kokumi gain on umami and on saltiness   0 to 0.90, peak 0.41   (Ueda 1997 none ... Ohsu 2010 Fig. 1)
     synergy cap (SYNERGY_MAX_FOLD)          31.5 to 126, peak 63   (half and double; v.2.8.4, was 8-32 peak 16)
     kokumi EC50                             x0.5 to x2
     acid suppression midpoint (Miranda)     x0.5 to x2
3. A FLOOR of +/-0.125 score points on every range, from the outside tasting panels in tests/: model score
   gaps of 0.25 or more agreed with the panel on direction in 310 of 319 sample pairs (the 9 misses are the
   two known gaps, KCl blends and nucleotides alone); gaps under 0.25 agreed in 20 of 76.

These widths are proposals (Bryan, Nov 15, 2026: approved to build; not measured). What the ranges do NOT
cover: things the model leaves out (aroma, bitterness, fat, texture, solids), the shape of the taste curves
themselves, the KCl and nucleotide-alone gaps, and whether food potassium is salty. The panels behind the
floor are simple solutions, so real foods are probably less certain than the floor suggests.

Draws use common random numbers: draw k gives the same factor to the same ingredient in every recipe, so two
recipes can be compared draw by draw (used by the compare tool planned for Stage 3). Standard library only.
"""
import csv
import math
import os
import random
import sys

import hfp_model as m

HERE = os.path.dirname(os.path.abspath(__file__))
CATEGORY_PATH = os.path.join(HERE, "hfp_categories.csv")

N_DRAWS = 150
SEED = 20261115
INTERVAL = (10.0, 90.0)                      # middle 80%
SCORE_FLOOR = 0.125                          # half of the smallest score gap the outside panels support
SPREAD = {1: 0.20, 2: 0.35, 3: 0.50}         # 80% multiplicative spread by data tier
SPREAD_DEFINED = 0.02
PH_SPREAD = {1: 0.15, 2: 0.25, 3: 0.40}      # 80% additive spread on reference pH
Z80 = 1.2815515655446004                     # normal quantile for the 80% interval
BLANK_FILL_FIELDS = ("glu", "amp", "imp", "gmp")
CONSTANTS = {                                # name: (low, high, mode or None = the model's value)
    "SALT_SHIFT_MAX": (1.0, 5.5, None),
    "KOKUMI_UMAMI_GAIN": (0.0, 0.90, None),
    "KOKUMI_SALT_GAIN": (0.0, 0.90, None),
    "SYNERGY_MAX_FOLD": (31.5, 126.0, None),
}
LOG_FACTOR_CONSTANTS = {"KOKUMI_EC50_MM": (m, 2.0), "SUPPRESS_S50": (m.ab, 2.0)}   # x/÷ factor, triangular in log

GROUPS = {
    "amino": (("glu", "asp"), ("glutamate", "aspartate", "glu", "asp")),
    "nucleotides": (("amp", "imp", "gmp"), ("amp", "imp", "gmp", "nucleotides")),
    "sodium": (("na",), ("sodium", "na")),
    "potassium": (("k",), ("potassium", "k")),
    "kokumi": (("gsh", "cys", "evg"), ("glutathione", "gsh", "cys", "evg")),
    "sugars": (None, ("sugars",)),            # None = every sugar_* field
    "acids": (None, ("acids",)),              # every acid_* field
}
TASTES = ("umami", "saltiness", "sweetness", "kokumi", "sourness")


def load_categories(path=CATEGORY_PATH):
    out = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out[row["Ingredient"]] = row["Category"]
    return out


def _median(v):
    v = sorted(v)
    n = len(v)
    return 0.0 if not n else (v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2]))


def blank_fill_caps(db, categories):
    """{(category or None, field): median of the non-blank values}; None = whole database."""
    vals = {}
    for name, e in db.items():
        for f in BLANK_FILL_FIELDS:
            if f in e.get("_blank", ()):
                continue
            v = e.get(f)
            if isinstance(v, (int, float)):
                vals.setdefault((categories.get(name), f), []).append(v)
                vals.setdefault((None, f), []).append(v)
    return {k: (_median(v), len(v)) for k, v in vals.items()}


def is_defined(e):
    """Pure salts, sugars, MSG and water: composition known, so almost no data uncertainty."""
    if e.get("water", 0) >= 99.9:
        return True
    if e.get("water", 0) > 1.0:
        return False
    top_sugar = max([v for k, v in e.items() if k.startswith("sugar_") and isinstance(v, (int, float))] or [0])
    return (e.get("na") or 0) >= 10000 or (e.get("k") or 0) >= 10000 or top_sugar >= 90000 or (e.get("glu") or 0) >= 50000


def _tier(e, keys):
    t = e.get("_tier") or {}
    return max([t.get(k, 1) for k in keys] + [1])


def _rng(seed, k, *parts):
    return random.Random("%s|%s|%s" % (seed, k, "|".join(parts)))


def perturbed_entry(name, e, seed, k, caps, category):
    """One redrawn copy of a database entry for draw k."""
    out = dict(e)
    defined = is_defined(e)
    for group, (fields, tier_keys) in GROUPS.items():
        if fields is None:
            prefix = "sugar_" if group == "sugars" else "acid_"
            fields = [f for f in e if f.startswith(prefix)]
        spread = SPREAD_DEFINED if defined else SPREAD[min(3, _tier(e, tier_keys))]
        factor = math.exp(_rng(seed, k, name, group).gauss(0.0, math.log(1 + spread) / Z80))
        for f in fields:
            v = e.get(f)
            if isinstance(v, (int, float)) and v:
                out[f] = v * factor
    if not defined:
        for f in BLANK_FILL_FIELDS:
            if f in e.get("_blank", ()):
                cap, n = caps.get((category, f), (0.0, 0))
                if n < 3:
                    cap, n = caps.get((None, f), (0.0, 0))
                out[f] = _rng(seed, k, name, "blank", f).uniform(0.0, cap)
        if isinstance(e.get("ph_ref"), (int, float)):
            sd = PH_SPREAD[min(3, _tier(e, ("ph",)))] / Z80
            out["ph_ref"] = e["ph_ref"] + _rng(seed, k, name, "ph").gauss(0.0, sd)
    return out


def draw_constants(seed, k):
    r = _rng(seed, k, "constants")
    vals = {}
    for name, (lo, hi, mode) in CONSTANTS.items():
        cur = getattr(m, name)
        if cur is None:                              # e.g. synergy cap switched off: leave it alone
            continue
        vals[(m, name)] = r.triangular(lo, hi, cur if mode is None else mode)
    for name, (mod, fac) in LOG_FACTOR_CONSTANTS.items():
        vals[(mod, name)] = getattr(mod, name) * math.exp(r.triangular(-math.log(fac), math.log(fac), 0.0))
    return vals


def percentile(v, p):
    v = sorted(v)
    if not v:
        return None
    x = (len(v) - 1) * p / 100.0
    lo = int(math.floor(x))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (x - lo)


def _score(res, taste):
    s = res["scores"].get(taste)
    return s


def sample(recipes, options=None, n=N_DRAWS, seed=SEED, db=None):
    """Run every recipe n times with common random numbers.
    recipes: list of recipes (each a list of {"ingredient", "amount", "unit"}).
    options: list of dicts (water_loss_g, cook_min, cook_temp_c), one per recipe, or None.
    Returns (points, draws): points[i] = {taste: score}; draws[i] = list of n {taste: score}."""
    db = db or m.load_db()
    options = options or [{} for _ in recipes]
    categories = load_categories()
    caps = blank_fill_caps(db, categories)
    names = sorted({m.resolve(db, it["ingredient"]) for rec in recipes for it in rec})

    def run(rec, opt, d):
        r = m.compute([dict(it) for it in rec], db=d, water_loss_g=opt.get("water_loss_g", 0.0),
                      cook_min=opt.get("cook_min", 0.0), cook_temp_c=opt.get("cook_temp_c"))
        return {t: _score(r, t) for t in TASTES}

    points = [run(rec, opt, db) for rec, opt in zip(recipes, options)]
    draws = [[] for _ in recipes]
    for k in range(n):
        d = dict(db)
        for name in names:
            d[name] = perturbed_entry(name, db[name], seed, k, caps, categories.get(name))
        consts = draw_constants(seed, k)
        saved = {key: getattr(key[0], key[1]) for key in consts}
        try:
            for (mod, name), v in consts.items():
                setattr(mod, name, v)
            for i, (rec, opt) in enumerate(zip(recipes, options)):
                draws[i].append(run(rec, opt, d))
        finally:
            for (mod, name), v in saved.items():
                setattr(mod, name, v)
    return points, draws


def summarize(point, draws):
    """{taste: {"score", "low", "high"}} with the floor applied; None for a taste the model did not score."""
    out = {}
    for t in TASTES:
        if point.get(t) is None:
            out[t] = None
            continue
        v = [d[t] for d in draws if d.get(t) is not None]
        lo = min(percentile(v, INTERVAL[0]), point[t]) - SCORE_FLOOR
        hi = max(percentile(v, INTERVAL[1]), point[t]) + SCORE_FLOOR
        out[t] = {"score": point[t], "low": max(1.0, lo), "high": min(10.0, hi)}
    return out


def ranges(recipe, n=N_DRAWS, seed=SEED, db=None, **opt):
    points, draws = sample([recipe], [opt], n=n, seed=seed, db=db)
    return summarize(points[0], draws[0])


def report(rng, n=N_DRAWS):
    lines = ["SCORE RANGES (score, then the middle 80%% of %d re-runs; see hfp_ranges.py for what is varied)" % n]
    for t in TASTES:
        r = rng.get(t)
        if r is None:
            continue
        lines.append("  %-10s %4.1f  (%.1f to %.1f)" % (t.upper(), r["score"], r["low"], r["high"]))
    lines.append("  Differences smaller than the ranges are not real differences. Not covered: aroma, bitterness,")
    lines.append("  fat, texture, solids, and the model's own curve shapes.")
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]

    def _flag(name, default=None):
        if name in args:
            i = args.index(name)
            val = float(args[i + 1])
            del args[i:i + 2]
            return val
        return default

    n_draws = int(_flag("--draws", N_DRAWS))
    loss, cmin, ctemp = _flag("--evaporate", 0.0), _flag("--cook", 0.0), _flag("--temp", None)
    if not args:
        print(__doc__)
        sys.exit(0)
    rec = [m.parse_arg(a) for a in args]
    print(report(ranges(rec, n=n_draws, water_loss_g=loss, cook_min=cmin, cook_temp_c=ctemp), n_draws))
