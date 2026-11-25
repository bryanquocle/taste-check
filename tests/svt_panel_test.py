"""SVT real-food panel layer (Nov 24, 2026).

  python tests/svt_panel_test.py            compare rank agreement against tests/svt_panel_expected.json
  python tests/svt_panel_test.py --freeze   rewrite the baseline (only after Bryan approves a model change)
  python tests/svt_panel_test.py --ci       also print bootstrap 95% CIs and p-values (slower)

Data: tests/svt_panel.json, built by validation/svt_mars/scripts/svt_run.py from the curated mapping
(validation/svt_mars/svt_hfp_map.csv). Mars et al., Wageningen "Taste, Fat and Texture Database" (SVT),
DANS doi:10.17026/dans-xst-ughm, CC-BY-SA-4.0: 627 Dutch foods, 15 trained panellists, modified Spectrum
0-100 line scale. Each mapped food is one HFP ingredient (or a 2-ingredient case stated by the SVT prep).

Method: every food is run through compute() as eaten (cooking minutes at 95 C where cooked, fridge serving
at 5.5 C). Foods the model cannot tell apart (same ingredients, identical raw outputs: e.g. carrot raw,
boiled, juice) are collapsed into one unit and their panel means averaged, so repeated forms do not inflate
n. Spearman rho per taste, on 1-10 scores and on raw (uncapped) intensities. Bitterness only for foods
containing a modelled bitterant (caffeine, theobromine, KCl, Reb A; v.2.8.2 - was caffeine/KCl). Food-group sets where n >= 8 units.
Like run_tests.py, these are baselines to beat, not targets. Standard library only.
"""
import io
import json
import math
import os
import random
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hfp_model as m  # noqa: E402

DATA = os.path.join(HERE, "svt_panel.json")
EXPECTED = os.path.join(HERE, "svt_panel_expected.json")
TOL = 1e-9
TASTES = ("umami", "saltiness", "sweetness", "sourness", "bitterness")
RAW_KEY = {"umami": "umami_intensity", "saltiness": "saltiness_intensity", "sweetness": "sweetness_intensity",
           "sourness": "sourness_intensity", "bitterness": "bitterness_intensity"}
GROUP_MIN_N = 8
BOOT_N = 2000
BOOT_SEED = 2026


# ---- statistics (standard library) ----------------------------------------------------------------------
def rank(v):
    idx = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[idx[j + 1]] == v[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** .5
    dbb = sum((y - mb) ** 2 for y in rb) ** .5
    return num / (da * dbb) if da and dbb else None


def _betacf(a, b, x):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for mm in range(1, 300):
        m2 = 2 * mm
        aa = mm * (b - mm) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(c) > 1e-300 else 1e300
        h *= d * c
        aa = -(a + mm) * (qab + mm) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(c) > 1e-300 else 1e300
        de = d * c
        h *= de
        if abs(de - 1.0) < 3e-14:
            break
    return h


def betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta) * _betacf(b, a, 1 - x) / b


def p_value(r, n):
    """Two-sided p for Spearman rho via the t approximation (df = n-2)."""
    if r is None or n < 4:
        return None
    if abs(r) >= 1:
        return 0.0
    df = n - 2
    t2 = r * r * df / (1 - r * r)
    return betai(df / 2.0, 0.5, df / (df + t2))


def bootstrap_ci(a, b, n_boot=BOOT_N, seed=BOOT_SEED):
    rng = random.Random(seed)
    n = len(a)
    vals = []
    for _ in range(n_boot):
        ix = [rng.randrange(n) for _ in range(n)]
        r = spearman([a[i] for i in ix], [b[i] for i in ix])
        if r is not None:
            vals.append(r)
    if len(vals) < n_boot * 0.5:
        return None
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]


# ---- model runs -----------------------------------------------------------------------------------------
def load_data():
    with io.open(DATA, encoding="utf-8") as fh:
        return json.load(fh)


def run_sample(s, db):
    rec = [{"ingredient": m.resolve(db, n), "amount": g, "unit": "g"} for n, g in s["items"]]
    o = s.get("opt", {})
    r = m.compute(rec, db=db, cook_min=o.get("cook_min") or 0, cook_temp_c=o.get("cook_temp_c"),
                  serve_temp_c=o.get("serve_temp_c"))
    return r


def bitter_relevant(s, db):
    for n, _ in s["items"]:
        d = db[m.resolve(db, n)]
        if (d.get("caf", 0) > 0 or d.get("tb", 0) > 0 or d.get("sugar_reb_a", 0) > 0
                or n in m.CHLORIDE_K_INGREDIENTS):
            return True
    return False


def evaluate(db=None, data=None):
    """Run every sample, collapse indistinguishable foods into units, return (samples_out, units)."""
    db = db or m.load_db()
    data = data or load_data()
    out = []
    for s in data["samples"]:
        r = run_sample(s, db)
        raw = {t: r["results"][RAW_KEY[t]] for t in TASTES}
        sc = {t: (1.0 if r["scores"].get(t) is None else r["scores"][t]) for t in TASTES}
        out.append({"sample": s, "raw": raw, "score": sc, "warnings": r["warnings"],
                    "ph": (r.get("acidity") or {}).get("pH"), "bitter_ok": bitter_relevant(s, db)})
    units = {}
    for o in out:
        key = (tuple((n, g) for n, g in o["sample"]["items"]),
               tuple(round(o["raw"][t], 9) for t in TASTES))
        units.setdefault(key, []).append(o)
    ulist = []
    for key, members in units.items():
        meas = {}
        for t in TASTES:
            v = [x["sample"]["measured"].get(t) for x in members if x["sample"]["measured"].get(t) is not None]
            meas[t] = sum(v) / len(v) if v else None
        groups = sorted({x["sample"]["group"] for x in members})
        cooked = {bool(x["sample"].get("opt", {}).get("cook_min")) for x in members}
        label = " + ".join(n for n, _ in members[0]["sample"]["items"])
        label += {frozenset([True]): " (cooked)", frozenset([False]): "",
                  frozenset([True, False]): " (raw or cooked)"}[frozenset(cooked)]
        if members[0]["sample"].get("opt", {}).get("serve_temp_c") is not None:
            label += " (fridge)"
        ulist.append({"label": label, "items": members[0]["sample"]["items"],
                      "codes": [x["sample"]["code"] for x in members], "group": groups[0] if len(groups) == 1 else "mixed",
                      "measured": meas, "raw": members[0]["raw"], "score": members[0]["score"],
                      "bitter_ok": members[0]["bitter_ok"]})
    ulist.sort(key=lambda u: (u["label"], u["codes"]))
    seen = {}
    for u in ulist:                       # labels must be unique (misses are looked up by label)
        seen[u["label"]] = seen.get(u["label"], 0) + 1
    for u in ulist:
        if seen[u["label"]] > 1:
            u["label"] += " [SVT %s]" % ",".join(u["codes"])
    return out, ulist


def set_values(units, taste, scale, group=None):
    a, b, labels = [], [], []
    for u in units:
        if u["measured"][taste] is None:
            continue
        if taste == "bitterness" and not u["bitter_ok"]:
            continue
        if group and u["group"] != group:
            continue
        a.append(u["measured"][taste])
        b.append(u[scale][taste])
        labels.append(u["label"])
    return a, b, labels


def all_sets(units):
    sets = {}
    for t in TASTES:
        for sc in ("score", "raw"):
            name = "all foods: %s (%s)%s" % (t, sc, " [bitterant foods only]" if t == "bitterness" else "")
            sets[name] = set_values(units, t, sc)
    groups = sorted({u["group"] for u in units})
    for g in groups:
        for t in TASTES:
            if t == "bitterness":
                continue
            for sc in ("score", "raw"):
                a, b, lab = set_values(units, t, sc, g)
                if len(a) >= GROUP_MIN_N:
                    sets["group %s: %s (%s)" % (g, t, sc)] = (a, b, lab)
    return sets


def summarize(units, with_ci=False):
    res = {}
    for name, (a, b, lab) in all_sets(units).items():
        r = spearman(a, b)
        e = {"n": len(a), "spearman": r}
        if with_ci:
            e["p"] = p_value(r, len(a))
            e["ci95"] = bootstrap_ci(a, b) if r is not None else None
        res[name] = e
    return res


def fmt(v):
    return "n/a" if v is None else "%.3f" % v


def close(a, b):
    if a is None or b is None:
        return a is b
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def main():
    with_ci = "--ci" in sys.argv
    _, units = evaluate()
    now = summarize(units, with_ci=with_ci)
    if "--freeze" in sys.argv:
        frozen = {k: {"n": v["n"], "spearman": v["spearman"]} for k, v in now.items()}
        with io.open(EXPECTED, "w", encoding="utf-8") as fh:
            json.dump({"units": len(units), "sets": frozen}, fh, indent=1, ensure_ascii=False)
        print("Frozen %d SVT sets (%d food units) to %s" % (len(frozen), len(units), os.path.basename(EXPECTED)))
        return 0
    with io.open(EXPECTED, encoding="utf-8") as fh:
        exp = json.load(fh)
    bad = 0
    if exp["units"] != len(units):
        print("CHANGED  food units: %d -> %d (model now separates/merges foods differently)" % (exp["units"], len(units)))
        bad += 1
    for name, e in exp["sets"].items():
        g = now.get(name)
        ok = g is not None and g["n"] == e["n"] and close(e["spearman"], g["spearman"])
        tail = "" if ok else (" -> now missing" if g is None else " -> now %s (n=%d)" % (fmt(g["spearman"]), g["n"]))
        extra = ""
        if with_ci and g is not None:
            ci = g.get("ci95")
            extra = "  p=%s  95%% CI %s" % (fmt(g.get("p")), "n/a" if not ci else "[%.2f, %.2f]" % ci)
        print(("PASS  " if ok else "CHANGED  ") + "SVT %s (n=%d) rho %s%s%s" % (name, e["n"], fmt(e["spearman"]), tail, extra))
        bad += (not ok)
    for name in now:
        if name not in exp["sets"]:
            print("NEW  SVT %s (n=%d) rho %s" % (name, now[name]["n"], fmt(now[name]["spearman"])))
            bad += 1
    print("\n%s: %d SVT panel sets, %d food units, %d not matching"
          % ("ALL MATCH" if not bad else "DIFFERENCES", len(exp["sets"]), len(units), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
