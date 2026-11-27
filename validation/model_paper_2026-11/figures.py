"""Figures for the model paper: validation scatter (SVT test half) and Morris mu* bars."""
import json, os
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(H, "results"); F = os.path.join(H, "figures"); os.makedirs(F, exist_ok=True)
NAVY, BLUE, GREY, LIGHT = "#15223B", "#1D4A86", "#5B6272", "#C9CDD6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GREY,
                     "xtick.color": GREY, "ytick.color": GREY, "axes.labelcolor": NAVY, "axes.titlecolor": NAVY, "axes.titleweight": "bold", "savefig.dpi": 220})
v = json.load(open(os.path.join(R, "validate.json")))
fig, axes = plt.subplots(1, 4, figsize=(11, 3.1))
for ax, t in zip(axes, ("saltiness", "umami", "sourness", "sweetness")):
    d = v["test"][t]; xs = [p["model"] for p in d["points"]]; ys = [p["panel"] for p in d["points"]]
    ax.scatter(xs, ys, s=18, color=BLUE, alpha=.75, lw=0)
    ax.set_title(f"{t.capitalize()}: ρ {d['rho']:.2f} [{d['lo']:.2f}, {d['hi']:.2f}]", loc="left", fontsize=9)
    ax.set_xlim(0.5, 10.5); ax.set_xlabel("Model score (1–10)")
    if t == "saltiness": ax.set_ylabel("Trained panel (0–100)")
fig.suptitle("Held-out foods: model scores rank foods the way a trained panel did (SVT test half, n = 40–42)", x=.01, ha="left", color=NAVY, fontweight="bold", fontsize=10.5)
fig.tight_layout(); fig.savefig(os.path.join(F, "fig_validation.png"), bbox_inches="tight"); plt.close(fig)
m = json.load(open(os.path.join(R, "morris.json"))); ms = m["mu_star_score"]
LAB = {"NA_SLOPE_SCALE": "Feeney curve exponents", "SALT_HIGH_CURVE": "Feeney vs Murphy curve", "KOKUMI_UMAMI_GAIN": "Kokumi gain on umami",
       "SYNERGY_MAX_FOLD": "Synergy cap", "SWEET_EXPONENT": "Sweetness exponent", "KOK_THR_SCALE": "Kokumi detection floor", "KOKUMI_EC50_MM": "Kokumi EC50",
       "KOKUMI_HILL_N": "Kokumi Hill exponent", "UMAMI_SALT_EMAX": "Umami lift of saltiness", "SUPPRESS_S50": "Acid suppression S50",
       "NUC_ALONE_U0": "Nucleotide-alone term", "KOKUMI_SALT_GAIN": "Kokumi gain on saltiness", "GLU_THR_DROP_MAX": "Glutamate threshold drop"}
rows = sorted(((LAB[f], max(d.values()), max(d, key=d.get)) for f, d in ms.items()), key=lambda r: r[1])
fig, ax = plt.subplots(figsize=(7.5, 4.2))
y = range(len(rows)); ax.barh(list(y), [r[1] for r in rows], color=[BLUE if r[1] >= .2 else LIGHT for r in rows])
ax.set_yticks(list(y)); ax.set_yticklabels([f"{r[0]}  ({r[2]})" for r in rows])
for i, r in enumerate(rows): ax.text(r[1] + .01, i, f"{r[1]:.2f}", va="center", color=NAVY, fontsize=8)
ax.set_xlabel("μ*: mean absolute score change across the constant's range (1–10 points)")
ax.set_title("Eight constants move scores by 0.2 points or more; none moves rank agreement by more than 0.011 on average", loc="left", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(F, "fig_sensitivity.png"), bbox_inches="tight"); plt.close(fig)
print("ok")
