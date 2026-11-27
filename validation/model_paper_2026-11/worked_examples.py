"""Three worked examples computed by hand from the paper's printed equations (section 3), then compared with the model.
No model code is imported for the hand calculation; only hfp_raw_data.csv values (typed below) and printed constants."""
import math, os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); CM = os.path.dirname(os.path.dirname(HERE))

# composition (mg/100 g, % water) copied from hfp_raw_data.csv v2.16.2
SALT_NA, SALT_W = 39356, 0.1
MSG_GLU, MSG_NA, MSG_W = 87000, 13594, 0.0
SUGAR_SUC, SUGAR_W = 99940, 0.06
FEENEY = [(0.01, 2.1618), (0.032, 4.2689), (0.1, 12.7824), (0.32, 25.5113), (1.0, 43.1228)]   # v2.17.0, Feeney & Hayes 2014 Fig. 4
def feeney_hand(M):                                             # log-log interpolation on the segment containing M
    for (c0, v0), (c1, v1) in zip(FEENEY, FEENEY[1:]):
        if c0 <= M <= c1:
            return v0 * (M / c0) ** (math.log(v1 / v0) / math.log(c1 / c0))
REF_SALT = feeney_hand(0.5)                                     # 31.335
REF_UMAMI = (3.6672 * math.log(5.0) + 12.555) * 1.41            # salt shift x1 since v2.11.0
REF_SWEET = 0.54 * 10 ** 1.3
score = lambda raw, ref: 1 + 9 * min(1.0, max(0.0, raw) / ref)
hand = {}

# 1) 1 g salt in 99 g water: saltiness
M = 100.0; W = 99 + 1 * SALT_W / 100
na_g = 1 * SALT_NA / 1e5                                        # g Na
c_food = na_g / (W / 100) * (W / M)                              # g/100 g food
na_M = c_food * 10 / 23
I = feeney_hand(na_M)
hand["salt_water"] = {"Na_M": na_M, "raw": I, "score": score(I, REF_SALT)}

# 2) 0.2 g MSG in 99.8 g water: umami (no nucleotides, near-neutral pH so acid factor ~1, kokumi 0)
M = 100.0; W = 99.8
glu = 0.2 * MSG_GLU / 1e5 / (W / 100) * (W / M)                   # g/100 g food, free acid
E = glu * 187.13 / 147.13                                       # MSG.H2O equivalent; fold = 1
S = (1000 * 1e-7) * (W / M)                                     # sour stimulus at pH 7.0 (H+ only), mM, food basis
R = 1 / (1 + (S / 24.8) ** 0.64)                                # Miranda logistic as computed by the code (S50 24.8, H 0.64)
I = (3.6672 * math.log(E) + 12.555) * R
hand["msg_water"] = {"umami_eq": E, "raw": I, "score": score(I, REF_UMAMI)}

# 3) 10 g sugar in 90 g water: sweetness (no acid, q = 1)
M = 100.0
suc = 10 * SUGAR_SUC / 1e5 / M * 100                            # g sucrose per 100 g food
I = 0.54 * suc ** 1.3
hand["sugar_water"] = {"sucrose_pct": suc, "raw": I, "score": score(I, REF_SWEET)}

sys.path.insert(0, CM); os.chdir(CM)
import hfp_model as m
db = m.load_db()
runs = {"salt_water": ([("Salt", 1), ("Water", 99)], "saltiness"),
        "msg_water": ([("Monosodium Glutamate", 0.2), ("Water", 99.8)], "umami"),
        "sugar_water": ([("Sugar", 10), ("Water", 90)], "sweetness")}
out = {}
for k, (items, t) in runs.items():
    r = m.compute([{"ingredient": n, "amount": a, "unit": "g"} for n, a in items], db=db)
    out[k] = {"hand_raw": hand[k]["raw"], "model_raw": r["results"][f"{t}_intensity"], "hand_score": hand[k]["score"],
              "model_score": r["scores"][t], "pH": r.get("acidity", {}).get("pH"), "hand": hand[k]}
    print(k, {kk: (round(v, 6) if isinstance(v, float) else v) for kk, v in out[k].items() if kk != "hand"})
json.dump(out, open(os.path.join(HERE, "results", "worked_examples.json"), "w"), indent=1)
