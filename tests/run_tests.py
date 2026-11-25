"""Flavorome regression tests (Stage 0, Nov 15, 2026).

  python tests/run_tests.py            compare the model against the frozen expected values
  python tests/run_tests.py --freeze   rewrite the frozen values (only after Bryan approves a model change)

Two sets:
  1. Golden recipes (golden_recipes.json): every raw result, score and pH must match golden_expected.json.
  2. Outside tasting panels (panel_studies.json, sources in panel_sources/): published human panel data the
     model was not built from. For each set the test reports the rank agreement (Spearman) between measured
     intensity and model score, and flags it if it differs from the frozen value. These numbers are the
     baseline to beat, not a target the current model passes.
An ingredient name that does not resolve is an error (the old "parmesan water" test silently tested water).
Standard library only. Writes nothing outside this folder.
"""
import copy
import io
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hfp_model as m  # noqa: E402

TOL = 1e-9
EXPECTED = os.path.join(HERE, "golden_expected.json")


def load(name):
    with io.open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


def resolve_strict(db, q):
    try:
        return m.resolve(db, q)
    except KeyError:
        hits = m.find(db, q)
        if len(hits) == 1:
            return hits[0]
        raise KeyError("ingredient %r does not resolve to one entry (matches: %s)" % (q, hits[:5]))


def golden(db):
    out = {}
    for g in load("golden_recipes.json"):
        rec = [{"ingredient": resolve_strict(db, q), "amount": a, "unit": u} for q, a, u in g["items"]]
        o = g["opt"]
        r = m.compute(rec, db=db, water_loss_g=o.get("water_loss_g", 0), cook_min=o.get("cook_min", 0),
                      cook_temp_c=o.get("cook_temp_c"))
        vals = {"raw." + k: v for k, v in r["results"].items() if isinstance(v, (int, float))}
        vals.update({"score." + k: v for k, v in r["scores"].items() if v is not None})
        ph = (r.get("acidity") or {}).get("pH")
        if ph is not None:
            vals["ph"] = ph
        out[g["name"]] = vals
    return out


# ---- outside panels -------------------------------------------------------------------------------------
def panel_db(db):
    d = dict(db)

    def pure(**kw):
        e = copy.deepcopy(db["Water"])
        e["water"] = 0.0
        e["ph_ref"] = None
        e["_blank"] = set()
        e["_tier"] = {}
        e.update(kw)
        return e

    d["X IMP"] = pure(imp=100000.0)
    d["X GMP"] = pure(gmp=100000.0)
    d["X Citric"] = pure(acid_citric=100000.0)
    d["X Fat"] = pure()                                   # unsalted butter / oil: weight only, no taste compounds
    d["X Glutamic acid"] = pure(glu=100000.0)             # free L-glutamic acid (no sodium)
    return d


def predict(db, c, msg_hydrate):
    rec = [{"ingredient": "Water", "amount": 1000.0, "unit": "g"}]

    def add(n, g):
        if g:
            rec.append({"ingredient": n, "amount": g, "unit": "g"})

    add("Salt", c.get("NaCl_g_per_L"))
    add("Potassium Chloride", c.get("KCl_g_per_L"))
    # the database entry is anhydrous MSG; studies that weighed the monohydrate are converted
    add("Monosodium Glutamate", (c.get("MSG_g_per_L") or 0) * (169.11 / 187.13 if msg_hydrate else 1.0))
    add("X IMP", (c.get("IMP_g_per_L") or 0) * 348.21 / 392.17)      # disodium salt -> free acid
    add("X GMP", (c.get("GMP_g_per_L") or 0) * 363.22 / 407.18)
    add("Sugar", c.get("sucrose_g_per_L"))
    add("X Citric", c.get("citric_acid_g_per_L"))
    return m.compute(rec, db=db)["scores"]


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
    ra, rb = rank(a), rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** .5
    dbb = sum((y - mb) ** 2 for y in rb) ** .5
    return num / (da * dbb) if da and dbb else None


def has(*keys):
    return lambda x: any(x["components"].get(k) for k in keys)


def no_tartaric(x):
    return "tartaric" not in (x["components"].get("other") or "")


def no_kcl(x):
    return not x["components"].get("KCl_g_per_L")


PANEL_SETS = [  # (name, study id, taste, sample filter, MSG weighed as monohydrate)
    ("salt in water, 3 levels (Webb 2015)", "webb2015", "saltiness", None, True),
    ("sugar in water, 3 levels (Webb 2015)", "webb2015", "sweetness", None, True),
    ("citric acid in water, 3 levels (Webb 2015)", "webb2015", "sourness", None, True),
    ("MSG in water, 3 levels (Webb 2015)", "webb2015", "umami", None, True),
    ("salt with and without MSG (Hayabuchi 2020)", "hayabuchi2020", "saltiness", None, True),
    ("pure salt, 3 levels (Chaiya 2026)", "chaiya2026", "saltiness", no_kcl, True),
    ("KCl and salt blends plus pure salt, L-arginine ignored (Chaiya 2026)", "chaiya2026", "saltiness", None, True),
    ("sweetness with citric acid, tartaric samples left out (Junge 2020)", "junge2020", "sweetness", no_tartaric, True),
    ("sourness with sugar, tartaric samples left out (Junge 2020)", "junge2020", "sourness", no_tartaric, True),
    ("sweetness of sugar + citric acid, 18 samples (Mao 2025)", "mao2025", "sweetness", None, True),
    ("sourness of citric acid + sugar, 18 samples (Mao 2025)", "mao2025", "sourness", None, True),
    ("MSG, IMP and GMP each alone (Wang 2021)", "wang2021", "umami",
     has("MSG_g_per_L", "IMP_g_per_L", "GMP_g_per_L"), False),
    # Nov 21, 2026: nucleotides alone at 3 mM (AMP, CMP, UMP have no model input, so they score 1.0); n/a while
    # NUC_ALONE_U0 is off, because the model then ties all five at 1.0.
    ("IMP, GMP, AMP, CMP, UMP each alone at 3 mM (Tanaka 2025)", "tanaka2025", "umami", None, False),
    # Nov 21, 2026: bitterness (v.2.8.0). Chaiya measured bitterness of the KCl blends; not used to build the model.
    ("bitterness of KCl blends and pure salt, L-arginine ignored (Chaiya 2026)", "chaiya2026", "bitterness", None, True),
]


def panels(db):
    studies = {s["id"]: s for s in load("panel_studies.json")}
    d = panel_db(db)
    out = {}
    for name, sid, taste, filt, hyd in PANEL_SETS:
        meas, pred = [], []
        for x in studies[sid]["samples"]:
            if x["measured"].get(taste) is None or (filt and not filt(x)):
                continue
            sc = predict(d, x["components"], hyd)[taste]
            meas.append(x["measured"][taste])
            pred.append(1.0 if sc is None else sc)
        out[name] = {"n": len(meas), "spearman": spearman(meas, pred), "model_scores": pred, "measured": meas}
    # Real-food panels (Nov 21, 2026): whole recipes from tests/food_panels.json, one set per study and taste
    for st in load("food_panels.json"):
        for taste in ("saltiness", "umami", "sweetness", "sourness", "bitterness"):
            meas, pred = [], []
            for x in st["samples"]:
                if x["measured"].get(taste) is None:
                    continue
                rec = [{"ingredient": n, "amount": g, "unit": "g"} for n, g in x["items"]]
                sc = m.compute(rec, db=d)["scores"].get(taste)
                meas.append(x["measured"][taste]); pred.append(1.0 if sc is None else sc)
            if meas:
                out["FOOD %s: %s" % (st["id"], taste)] = {"n": len(meas), "spearman": spearman(meas, pred),
                                                          "model_scores": pred, "measured": meas}
    return out


def close(a, b):
    if a is None or b is None:
        return a is b
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def fmt(v):
    return "n/a" if v is None else "%.2f" % v


def main():
    db = m.load_db()
    now = {"golden": golden(db), "panels": panels(db),
           "model": {"umami_ref": m.SCORE_REF["umami"], "synergy_max_fold": m.SYNERGY_MAX_FOLD,
                     "salt_shift_max": m.SALT_SHIFT_MAX, "kokumi_umami_gain": m.KOKUMI_UMAMI_GAIN}}
    if "--freeze" in sys.argv:
        with io.open(EXPECTED, "w", encoding="utf-8") as fh:
            json.dump(now, fh, indent=1, ensure_ascii=False)
        print("Frozen %d golden recipes and %d panel sets to golden_expected.json"
              % (len(now["golden"]), len(now["panels"])))
        return 0
    exp = load("golden_expected.json")
    bad = 0
    for name, vals in exp["golden"].items():
        got = now["golden"].get(name)
        if got is None:
            diffs = ["missing recipe"]
        else:
            diffs = ["%s expected %r got %r" % (k, v, got.get(k)) for k, v in vals.items() if not close(v, got.get(k))]
            diffs += ["new value " + k for k in got if k not in vals]
        print(("PASS  " if not diffs else "FAIL  ") + name)
        for line in diffs[:6]:
            print("        " + line)
        bad += bool(diffs)
    for name, e in exp["panels"].items():
        g = now["panels"].get(name)
        ok = (g is not None and close(e["spearman"], g["spearman"])
              and all(close(a, b) for a, b in zip(e["model_scores"], g["model_scores"])))
        tail = "" if ok or g is None else " -> now " + fmt(g["spearman"])
        print(("PASS  " if ok else "CHANGED  ") + "panel: %s (n=%d) rank agreement %s%s"
              % (name, e["n"], fmt(e["spearman"]), tail))
        bad += (not ok)
    print("\n%s: %d golden recipes, %d panel sets, %d not matching"
          % ("ALL MATCH" if not bad else "DIFFERENCES", len(exp["golden"]), len(exp["panels"]), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
