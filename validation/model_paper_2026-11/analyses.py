"""Analyses for the Taste Check model-description paper (v2.16.2, Nov 26, 2026).

  python -B analyses.py tally      evidence levels in the constant register (rebuild/REBUILD.md, section 12)
  python -B analyses.py coverage   ingredient-database coverage and recipe mass resting on missing/estimated data
  python -B analyses.py validate   held-out SVT test half: Spearman rho per taste, bootstrap 95% CI (and dev half)
  python -B analyses.py morris     Morris elementary-effects screening of 13 uncertain constants (r = 20, p = 4)
Writes results/<name>.json. Standard library only; model imported from the Claude Model folder (v2.16.2 as released).
"""
import csv, io, json, math, os, random, re, statistics as st, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
CM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, CM)
os.chdir(CM)
import hfp_model as m
import hfp_acidbase as ab
import hfp_sweet as sw
OUT = os.path.join(HERE, "results"); os.makedirs(OUT, exist_ok=True)
SEED = 20261126
REBUILD = os.path.join(os.path.dirname(os.path.dirname(CM)), "taste-check-github", "rebuild", "REBUILD.md")


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8"), indent=1, default=float)


# ------------------------------------------------------------------ evidence tally
def tally():
    txt = open(REBUILD, encoding="utf-8").read()
    sec = txt.split("## 12. Constant register")[1].split("## 13.")[0]
    rows, cur = [], None
    for line in sec.splitlines():
        h = re.match(r"### 12\.(\d) (.*)", line)
        if h: cur = h.group(2); continue
        if line.startswith("| ") and not line.startswith("| Constant") and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 5: rows.append({"section": cur, "constant": cells[0], "status": cells[-1]})

    def cls(s):
        s = s.upper()
        if s.startswith("UNSOURCED"): return "Unsourced"
        if s.startswith("VERIFIED") or s.startswith("VALIDATED") or s.startswith("SOURCED"): return "Verified in source"
        if s.startswith("DERIVED"): return "Derived from source"
        if s.startswith("FIT") or s.startswith("DIGITIZED"): return "Fitted or digitized"
        if s.startswith("ASSUMPTION"): return "Assumption"
        if s.startswith("STANDARD"): return "Standard constant"
        if s.startswith("IMPLEMENTATION"): return "Implementation"
        return "Other"
    for r in rows: r["class"] = cls(r["status"])
    from collections import Counter
    by = Counter(r["class"] for r in rows)
    bysec = {}
    for r in rows: bysec.setdefault(r["section"], Counter())[r["class"]] += 1
    res = {"n": len(rows), "by_class": dict(by), "by_section": {k: dict(v) for k, v in bysec.items()},
           "assumptions_and_unsourced": [r for r in rows if r["class"] in ("Assumption", "Unsourced")]}
    save("tally", res); print(json.dumps({"n": res["n"], "by_class": res["by_class"]}, indent=1))


# ------------------------------------------------------------------ database coverage
def coverage():
    raw = list(csv.DictReader(io.open(os.path.join(CM, "hfp_raw_data.csv"), encoding="utf-8")))
    fields = {"glutamate": "Glutamate (mg/100g)", "IMP": "Inosinate (mg/100g)", "GMP": "Guanylate (mg/100g)",
              "sodium": "Sodium (mg/100g)", "water": "Water Content (%)", "density": "Density (g/mL)",
              "sucrose": "Sucrose (mg/100g)", "citric acid": "Citric Acid (mg/100g)", "pH": "pH (approx.)",
              "glutathione": "Glutathione (mg/100g)"}
    n = len(raw); cov = {k: sum(1 for r in raw if (r.get(c) or "").strip() != "") / n for k, c in fields.items()}
    dq = list(csv.DictReader(io.open(os.path.join(CM, "hfp_data_quality.csv"), encoding="utf-8")))
    from collections import Counter
    tiers = Counter((r.get("Tier") or r.get("tier") or "").strip() for r in dq)
    # recipe mass on rows with no glutamate data / no acid data / any tier-3 estimate
    db = {r["Ingredient"]: r for r in raw}
    acid_cols = [c for c in raw[0] if c.endswith("Acid (mg/100g)")]
    tier3 = {(r.get("Ingredient") or r.get("ingredient")) for r in dq if (r.get("Tier") or r.get("tier") or "").strip() == "3"}
    items = json.load(open(os.path.join(CM, "validation", "recipe_rerun_2026-11-26", "out", "items_livefix.json"), encoding="utf-8"))
    VOL = {k.lower(): v for k, v in m.VOLUME_UNITS.items()}; MAS = {k.lower(): v for k, v in m.MASS_UNITS.items()}
    sh_glu, sh_acid, sh_t3, nrec = [], [], [], 0
    for rid, r in items.items():
        tot = gl = ac = t3 = 0.0
        for it in r.get("items", []):
            d = db.get(it["ingredient"]); u = (it["unit"] or "").lower()
            if not d: continue
            if u in MAS: g = it["amount"] * MAS[u]
            elif u in VOL: g = it["amount"] * VOL[u] * float(d["Density (g/mL)"] or 0)
            else: continue
            tot += g
            if (d["Glutamate (mg/100g)"] or "").strip() == "": gl += g
            if all((d[c] or "").strip() == "" for c in acid_cols): ac += g
            if it["ingredient"] in tier3: t3 += g
        if tot > 0:
            nrec += 1; sh_glu.append(gl / tot); sh_acid.append(ac / tot); sh_t3.append(t3 / tot)
    q = lambda v, p: sorted(v)[int(p * (len(v) - 1))]
    res = {"n_ingredients": n, "field_coverage": cov, "data_quality_rows": len(dq), "tiers": dict(tiers),
           "recipes": nrec,
           "mass_share_no_glutamate": {"median": st.median(sh_glu), "p90": q(sh_glu, .9), "share_recipes_over_25pct": sum(x > .25 for x in sh_glu) / nrec},
           "mass_share_no_acids": {"median": st.median(sh_acid), "p90": q(sh_acid, .9), "share_recipes_over_25pct": sum(x > .25 for x in sh_acid) / nrec},
           "mass_share_tier3": {"median": st.median(sh_t3), "p90": q(sh_t3, .9), "share_recipes_over_25pct": sum(x > .25 for x in sh_t3) / nrec}}
    save("coverage", res); print(json.dumps(res, indent=1))


# ------------------------------------------------------------------ SVT validation
TASTES = ("umami", "saltiness", "sweetness", "sourness")


def svt_units():
    panel = json.load(io.open(os.path.join(CM, "tests", "svt_panel.json"), encoding="utf-8"))
    by_code = {}
    for s in panel["samples"]: by_code.setdefault(str(s["code"]), []).append(s)
    units = list(csv.DictReader(io.open(os.path.join(CM, "validation", "bitter_flags_2026-11-25", "svt_units.csv"), encoding="utf-8")))
    db = m.load_db(); out = []
    for u in units:
        items = []
        for part in u["items"].split("; "):
            nme, g = part.rsplit("=", 1); items.append({"ingredient": nme, "amount": float(g.replace(" g", "")), "unit": "g"})
        if any(i["ingredient"] not in db for i in items): continue
        kw = {}
        if float(u["cook_min"]): kw.update(cook_min=float(u["cook_min"]), cook_temp_c=95.0)
        if u["fridge"] == "True": kw["serve_temp_c"] = 5.5
        meas = {}
        for t in TASTES:
            v = [s["measured"].get(t) for c in u["svt_codes"].split(",") for s in by_code.get(c.strip(), []) if s["measured"].get(t) is not None]
            meas[t] = sum(v) / len(v) if v else None
        out.append({"label": u["label"], "half": u["half"], "items": items, "kw": kw, "panel": meas})
    return out, db


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]: j += 1
        for k in range(i, j + 1): r[o[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = rank(x), rank(y); mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry)); den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def score_units(units, db):
    res = []
    for u in units:
        r = m.compute(u["items"], db=db, **u["kw"])
        res.append({t: (r["scores"].get(t) if r["scores"].get(t) is not None else 1.0) for t in TASTES + ("kokumi", "bitterness")})
    return res


def rhos(units, sc, half):
    out = {}
    for t in TASTES:
        pairs = [(s[t], u["panel"][t]) for u, s in zip(units, sc) if u["half"] == half and u["panel"][t] is not None]
        out[t] = spearman([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) > 3 else None
    return out


def validate():
    units, db = svt_units(); sc = score_units(units, db); rng = random.Random(SEED); res = {}
    for half in ("test", "dev"):
        res[half] = {}
        for t in TASTES:
            pairs = [(s[t], u["panel"][t]) for u, s in zip(units, sc) if u["half"] == half and u["panel"][t] is not None]
            rho = spearman([p[0] for p in pairs], [p[1] for p in pairs]); bs = []
            for _ in range(2000):
                smp = [pairs[rng.randrange(len(pairs))] for _ in pairs]
                bs.append(spearman([p[0] for p in smp], [p[1] for p in smp]))
            bs.sort()
            res[half][t] = {"n": len(pairs), "rho": rho, "lo": bs[49], "hi": bs[1949],
                            "points": [{"model": p[0], "panel": p[1]} for p in pairs]}
    save("validate", res)
    for h in res: print(h, {t: (res[h][t]["n"], round(res[h][t]["rho"], 3), round(res[h][t]["lo"], 3), round(res[h][t]["hi"], 3)) for t in TASTES})


# ------------------------------------------------------------------ Morris screening
FACTORS = [  # name, low, high, log-scale, source of the range
    ("SYNERGY_MAX_FOLD", 16, 305, True, "16 (old cap, Yamaguchi '16 times') to 305 (synergy equation at 5 mM IMP)"),
    ("GLU_THR_DROP_MAX", 31.6, 126.3, True, "63.2 (Yamaguchi & Ninomiya 2000) halved or doubled"),
    ("NUC_ALONE_U0", 0.05 / 30, 0.05 / 7.5, True, "author's calibration halved or doubled"),
    ("KOKUMI_EC50_MM", 0.30, 2.74, True, "0.9122 mM (no primary source) divided or multiplied by 3"),
    ("KOKUMI_HILL_N", 1.0, 2.0, False, "1.456 (unsourced), plausible Hill range"),
    ("KOKUMI_UMAMI_GAIN", 0.20, 0.90, False, "Goto 2016 (0.41) to Ohsu 2010 Fig. 1 (0.90)"),
    ("KOKUMI_SALT_GAIN", 0.20, 0.90, False, "same as umami gain"),
    ("KOK_THR_SCALE", 0.5, 2.0, True, "Ueda 1997 glutathione thresholds halved or doubled"),
    ("UMAMI_SALT_EMAX", 0.0, 0.20, False, "0 (no effect) to twice the Sun 2022 fit (0.10)"),
    ("NA_SLOPE_SCALE", 0.85, 1.15, False, "Murphy 1981 log-fit slope +/-15%"),
    ("SALT_HIGH_CURVE", 0.0, 1.0, False, "Murphy log extrapolation (0) vs human gLMS splice (1) above 0.108 M"),
    ("SUPPRESS_S50", 14.7, 58.8, True, "Miranda 2021 logistic S50 29.4 mM halved or doubled"),
    ("SWEET_EXPONENT", 1.1, 1.5, False, "Moskowitz 1970 exponent 1.3 +/-0.2"),
]
BASE = {"SYNERGY_MAX_FOLD": m.SYNERGY_MAX_FOLD, "GLU_THR_DROP_MAX": m.GLU_THR_DROP_MAX, "NUC_ALONE_U0": m.NUC_ALONE_U0,
        "KOKUMI_EC50_MM": m.KOKUMI_EC50_MM, "KOKUMI_HILL_N": m.KOKUMI_HILL_N, "KOKUMI_UMAMI_GAIN": m.KOKUMI_UMAMI_GAIN,
        "KOKUMI_SALT_GAIN": m.KOKUMI_SALT_GAIN, "KOK_THR_SCALE": 1.0, "UMAMI_SALT_EMAX": m.UMAMI_SALT_EMAX,
        "NA_SLOPE_SCALE": 1.0, "SALT_HIGH_CURVE": 0.0, "SUPPRESS_S50": ab.SUPPRESS_S50, "SWEET_EXPONENT": sw.EXPONENT}
_THR0, _NA_A0 = list(m.KOKUMI_THR_POINTS), m._NA_A


def apply(p):
    m.SYNERGY_MAX_FOLD = p["SYNERGY_MAX_FOLD"]; m.GLU_THR_DROP_MAX = p["GLU_THR_DROP_MAX"]; m.NUC_ALONE_U0 = p["NUC_ALONE_U0"]
    m.KOKUMI_EC50_MM = p["KOKUMI_EC50_MM"]; m.KOKUMI_HILL_N = p["KOKUMI_HILL_N"]
    m.KOKUMI_UMAMI_GAIN = p["KOKUMI_UMAMI_GAIN"]; m.KOKUMI_SALT_GAIN = p["KOKUMI_SALT_GAIN"]
    m.KOKUMI_THR_POINTS[:] = [(a, b * p["KOK_THR_SCALE"]) for a, b in _THR0]
    m.UMAMI_SALT_EMAX = p["UMAMI_SALT_EMAX"]; m._NA_A = _NA_A0 * p["NA_SLOPE_SCALE"]
    m.SALT_HIGH_CURVE = "human_splice" if p["SALT_HIGH_CURVE"] >= 0.5 else "murphy_log"
    ab.SUPPRESS_S50 = p["SUPPRESS_S50"]; sw.EXPONENT = p["SWEET_EXPONENT"]
    m.SCORE_REF["salt"] = m.na_curve(0.5)
    m.SCORE_REF["umami"] = (3.6672 * math.log(5.0 * m.SALT_SHIFT_MAX) + 12.555) * (1 + m.KOKUMI_UMAMI_GAIN)
    m.SCORE_REF["sweet"] = sw.K_SUCROSE * 10.0 ** sw.EXPONENT


def morris(r=20, p=4):
    units, db = svt_units(); rng = random.Random(SEED); k = len(FACTORS); delta = p / (2 * (p - 1))
    def val(i, x):
        nme, lo, hi, lg, _ = FACTORS[i]
        return math.exp(math.log(lo) + x * (math.log(hi) - math.log(lo))) if lg else lo + x * (hi - lo)
    def evaluate(xs):
        par = dict(BASE); par.update({FACTORS[i][0]: val(i, x) for i, x in enumerate(xs)}); apply(par)
        sc = score_units(units, db); apply(BASE)
        return sc, rhos(units, sc, "test")
    base_sc = score_units(units, db); base_rho = rhos(units, base_sc, "test")
    outs = TASTES + ("kokumi", "bitterness")
    ee = {f[0]: {t: [] for t in outs} for f in FACTORS}; ee_rho = {f[0]: {t: [] for t in TASTES} for f in FACTORS}
    grid = [i / (p - 1) for i in range(p)]
    for _ in range(r):
        x = [rng.choice([g for g in grid if g + delta <= 1 + 1e-9]) for _ in range(k)]
        sc0, rho0 = evaluate(x)
        for i in rng.sample(range(k), k):
            x2 = list(x); x2[i] = x[i] + delta
            sc1, rho1 = evaluate(x2)
            nm = FACTORS[i][0]
            for t in outs: ee[nm][t].append(st.mean(abs(a[t] - b[t]) for a, b in zip(sc1, sc0)) / delta)
            for t in TASTES: ee_rho[nm][t].append((rho1[t] - rho0[t]) / delta)
            x, sc0, rho0 = x2, sc1, rho1
    res = {"r": r, "p": p, "delta": delta, "n_units": len(units), "base_rho_test": base_rho,
           "factors": [{"name": f[0], "low": f[1], "high": f[2], "log": f[3], "range_source": f[4]} for f in FACTORS],
           "mu_star_score": {f: {t: st.mean(v) for t, v in d.items()} for f, d in ee.items()},
           "mu_star_rho": {f: {t: st.mean(abs(x) for x in v) for t, v in d.items()} for f, d in ee_rho.items()},
           "mu_rho": {f: {t: st.mean(v) for t, v in d.items()} for f, d in ee_rho.items()},
           "sigma_score": {f: {t: (st.stdev(v) if len(v) > 1 else 0) for t, v in d.items()} for f, d in ee.items()}}
    save("morris", res)
    for f in FACTORS:
        print(f"{f[0]:20}", {t: round(res['mu_star_score'][f[0]][t], 3) for t in outs}, {t: round(res['mu_rho'][f[0]][t], 3) for t in TASTES})


if __name__ == "__main__":
    {"tally": tally, "coverage": coverage, "validate": validate, "morris": morris}[sys.argv[1]]()
