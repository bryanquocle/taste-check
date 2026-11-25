"""
Sweetness module for the HFP model (v.2.4.0, Python only).

Sweetness (Moskowitz 1970, Percept Psychophys 7:315, Table 3, per cent by weight, exponent fixed at 1.3):
    S = k * C^1.3,  k(sucrose) = 0.54,  C = % w/w.
  Relative sweetness RS = k_sugar / k_sucrose, so a sugar at C% is as sweet as sucrose at RS^(1/1.3) * C%.
  Mixtures: sucrose-equivalent concentrations are summed (equivalent-concentration additivity), then
  S = 0.54 * C_eq^1.3. Scale: Moskowitz's normalized magnitude estimates (10% sucrose ~ 10.8).
  Fit range: 2-32% sucrose (functions fitted on the lowest four concentrations); above 32% is extrapolated.
  Below the sucrose detection threshold (0.086 g/100 mL; Yamaguchi 1979 Table III) sweetness is 0.
  Sugars without a value (maltotriose, mannose [erratic in the paper], uronic acids) are not counted and
  are flagged. Polyols (sorbitol, mannitol, erythritol, xylitol) use Wee et al. 2018 potencies since v.2.6.3.

Sugar-acid interaction (Schifferstein & Frijters 1990, Chem Senses 15:87; sucrose 0.125-1 M x citric
1.25-10 mM; scale values read from Figs. 3-4). The paper's scale is not Moskowitz's, so both effects are
expressed scale-free as EFFECTIVE CONCENTRATIONS: each mixture rating is converted back to the concentration
of the unmixed substance that gives the same rating (piecewise-linear inversion of the paper's own unmixed
functions), and the ratio mixture-equivalent / actual concentration is used.
  - Acid on sweetness: effective sucrose-equivalent = actual x q(citric-eq), q averaged over the four sucrose
    levels at each citric level; interpolated linearly, held at the 10 mM value above 10 mM (no extrapolation).
  - Sugar on sourness: effective sour stimulus = actual x g(sucrose-eq), using the 10 mM citric column (closest
    to food acid levels; at 23-95 mM McBride & Johnson 1987 found the effect depended on sucrose only),
    interpolated linearly in x = sucrose-equivalent g per 100 g water from (0, 1), held above 43.6 g.
    Other sugars act in proportion to their sweetness (sucrose-equivalents): an assumption.
"""
import math

EXPONENT = 1.3
K_SUCROSE = 0.54
# Moskowitz 1970 Table 3, relative sweetness (per cent by weight, n = 1.3)
# v.2.6.3 (Nov 20, 2026, Bryan's call): the four polyols use Wee et al. 2018 (Nutrients 10:1632, PMC6266678,
# CC BY), Table 4, sweetness potency at 10% sucrose (equi-sweet concentration ratio): sorbitol 0.72,
# mannitol 0.68, erythritol 0.75, xylitol 1.01. Stored as potency^1.3 so the sucrose-eq factor RS^(1/1.3)
# equals Wee's measured potency exactly. Erythritol and xylitol were unscored before. Wee is % w/v; the
# ratio is used unchanged. Other sugars stay on Moskowitz (Research Lab B26 is testing a wider recalibration).
POLYOL_POTENCY_WEE2018 = {"sorbitol": 0.72, "mannitol": 0.68, "erythritol": 0.75, "xylitol": 1.01}
# v.2.7.1 (Nov 20, 2026; Python and web only, not in the workbook): allulose (D-psicose) and maltitol, same
# source and method (Wee 2018 Table 4 at 10% sucrose: allulose 0.75 [0.71-0.80 over 5-15%], maltitol 0.89).
BULK_POTENCY_WEE2018 = {"allulose": 0.75, "maltitol": 0.89}
RELATIVE_SWEETNESS = {
    "sucrose": 1.00, "fructose": 0.91, "glucose": 0.45, "galactose": 0.42, "glycerol": 0.50,
    "arabinose": 0.39, "xylose": 0.26, "maltose": 0.31, "lactose": 0.22,
    **{s: p ** 1.3 for s, p in POLYOL_POTENCY_WEE2018.items()},
    **{s: p ** 1.3 for s, p in BULK_POTENCY_WEE2018.items()},
}
SUGAR_COLUMNS = {
    "sucrose": "Sucrose (mg/100g)", "glucose": "Glucose (mg/100g)", "fructose": "Fructose (mg/100g)",
    "lactose": "Lactose (mg/100g)", "galactose": "Galactose (mg/100g)", "maltose": "Maltose (mg/100g)",
    "maltotriose": "Maltotriose (mg/100g)", "uronic": "Uronic Acid (mg/100g)",
    "arabinose": "Arabinose (mg/100g)", "xylose": "Xylose (mg/100g)", "mannose": "Mannose (mg/100g)",
    "glycerol": "Glycerol (mg/100g)", "sorbitol": "Sorbitol (mg/100g)", "erythritol": "Erythritol (mg/100g)",
    "xylitol": "Xylitol (mg/100g)", "mannitol": "Mannitol (mg/100g)",
    "allulose": "Allulose (mg/100g)", "maltitol": "Maltitol (mg/100g)",
    "reb_a": "Rebaudioside A (mg/100g)", "mogroside_v": "Mogroside V (mg/100g)",
    "sucralose": "Sucralose (mg/100g)", "aspartame": "Aspartame (mg/100g)", "ace_k": "Acesulfame K (mg/100g)",
}

# --- High-intensity sweeteners (v.2.7.0, Python and web only; not in the workbook) ----------------------
# Wee, Tan & Forde 2018 (Nutrients 10:1632, PMC6266678, CC BY; gLMS, n = 40). Their potency falls as
# concentration rises (power-function exponents 0.65-0.84 vs sucrose 1.31), so a single relative-sweetness
# factor cannot work. Instead, Table 4's measured equi-sweet concentrations (% w/v matching 5, 10, 15% w/v
# sucrose) are interpolated log-log. Below the 5% point the curve continues with slope n/1.31 (Table 3);
# above the 15% point sweetness is HELD at 15% sucrose-eq (not tested; these sweeteners plateau) and flagged.
# Purity: Wee's stevia was 68.0% rebaudioside A and their luo han guo (monk fruit) extract 50.6% mogroside V.
# A commercial grade is entered by its Reb A / mogroside V content and treated as Wee's material at the
# same Reb A / mogroside V concentration (an assumption: other steviol glycosides and mogrosides are not
# credited separately). Sucralose, aspartame and acesulfame K are taken as pure.
# Sucrose-eq from these is ADDED to the sugars' (equivalent-concentration additivity); the synergy between
# sweeteners (e.g. Reb A + acesulfame K), bitterness and lingering sweetness are not modelled.
WEE_SUCROSE_LEVELS = [5.0, 10.0, 15.0]     # % w/v sucrose, used as g sucrose-eq per 100 g water
WEE_SUCROSE_N = 1.31
HIGH_INTENSITY = {
    # key: (label, purity of Wee's material, Table 3 slope n, Table 4 equi-sweet % w/v at 5/10/15% sucrose)
    "reb_a": ("Stevia (rebaudioside A)", 0.680, 0.71, [0.0144, 0.0395, 0.0828]),
    "mogroside_v": ("Monk fruit (mogroside V)", 0.506, 0.70, [0.0191, 0.0694, 0.141]),
    "sucralose": ("Sucralose", 1.0, 0.65, [0.0096, 0.0387, 0.0748]),
    "aspartame": ("Aspartame", 1.0, 0.84, [0.0290, 0.0827, 0.134]),
    "ace_k": ("Acesulfame K", 1.0, 0.68, [0.0293, 0.0832, 0.170]),
}


def his_sucrose_eq(key, g_per_100g_water):
    """Sucrose-eq (g per 100 g water) of one high-intensity sweetener, and whether it is above the tested
    range (held at 15%)."""
    _, purity, n, xs = HIGH_INTENSITY[key]
    c = g_per_100g_water / purity                   # concentration of Wee's material giving the same active
    if c <= 0:
        return 0.0, False
    ys = WEE_SUCROSE_LEVELS
    if c < xs[0]:
        return ys[0] * (c / xs[0]) ** (n / WEE_SUCROSE_N), False
    if c > xs[-1]:
        return ys[-1], True
    for x0, x1, y0, y1 in zip(xs, xs[1:], ys, ys[1:]):
        if c <= x1:
            t = (math.log(c) - math.log(x0)) / (math.log(x1) - math.log(x0))
            return math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0))), False
    return ys[-1], False


def his_above_range(sugar_g_per_100g_water):
    """Labels of high-intensity sweeteners above Wee's tested range (sweetness held at 15% sucrose-eq)."""
    return [HIGH_INTENSITY[k][0] for k in HIGH_INTENSITY
            if his_sucrose_eq(k, sugar_g_per_100g_water.get(k, 0.0))[1]]
UNSCORED = [s for s in SUGAR_COLUMNS if s not in RELATIVE_SWEETNESS and s not in HIGH_INTENSITY]
SUCROSE_THRESHOLD_PCT = 0.086      # g/100 mL (Yamaguchi & Kimizuka; Yamaguchi 1979 Table III)
MOSKOWITZ_MAX_PCT = 32.0

# --- Schifferstein & Frijters 1990, digitized ------------------------------------------------------
SF_SUCROSE_M = [0.125, 0.25, 0.5, 1.0]
SF_SUCROSE_G_PER_100G_WATER = [4.40, 9.06, 19.2, 43.6]      # M -> g/100 g water via solution density
SF_CITRIC_mM = [1.25, 2.5, 5.0, 10.0]
SF_SWEET_UNMIXED = [24, 45, 79, 111]                         # Fig. 4A x-axis (sweetness of sucrose alone)
SF_SWEET_MIX = {1.25: [19.5, 38, 67, 103], 2.5: [19.5, 38, 70, 95],   # Fig. 4A, by citric mM
                5.0: [15, 36.5, 65, 95], 10.0: [11.5, 28.5, 63.5, 95]}
SF_SOUR_UNMIXED = [27, 50, 79, 105]                          # Fig. 4B x-axis (sourness of citric alone)
SF_SOUR_MIX_10mM = [77, 62, 51, 35]                          # Fig. 4B, 10 mM citric, by sucrose level


def _invert(y, xs, ys):
    """Concentration of the unmixed substance giving rating y (piecewise linear through the origin)."""
    pts = [(0.0, 0.0)] + list(zip(xs, ys))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y <= y1:
            return x0 + (x1 - x0) * (y - y0) / (y1 - y0)
    return xs[-1]


SWEET_Q = [(0.0, 1.0)] + [
    (c, sum(_invert(v, SF_SUCROSE_M, SF_SWEET_UNMIXED) / m for v, m in zip(SF_SWEET_MIX[c], SF_SUCROSE_M)) / 4)
    for c in SF_CITRIC_mM]
SOUR_EFFECTIVE_POINTS = [(x, _invert(v, SF_CITRIC_mM, SF_SOUR_UNMIXED) / 10.0)
                         for x, v in zip(SF_SUCROSE_G_PER_100G_WATER, SF_SOUR_MIX_10mM)]


def sucrose_equivalent(sugar_g_per_100g_water):
    """Sucrose-equivalent g per 100 g water, and the list of unscored sugars present."""
    eq, unscored = 0.0, []
    for s, g in sugar_g_per_100g_water.items():
        if g <= 0:
            continue
        if s in HIGH_INTENSITY:
            eq += his_sucrose_eq(s, g)[0]
        elif s in RELATIVE_SWEETNESS:
            eq += RELATIVE_SWEETNESS[s] ** (1 / EXPONENT) * g
        else:
            unscored.append(s)
    return eq, unscored


def pct_ww(g_per_100g_water, total_sugar_g_per_100g_water):
    """Convert g/100 g water to % w/w of the sugar solution (water + all dissolved sugars)."""
    return 100 * g_per_100g_water / (100 + total_sugar_g_per_100g_water)


def sweetness(c_eq_pct):
    if c_eq_pct < SUCROSE_THRESHOLD_PCT:
        return 0.0
    return K_SUCROSE * c_eq_pct ** EXPONENT


def sweet_q(citric_eq_mM):
    """Multiplier on the sucrose-equivalent concentration from acid (effective concentration)."""
    c = min(max(citric_eq_mM, 0.0), SWEET_Q[-1][0])
    for (x0, y0), (x1, y1) in zip(SWEET_Q, SWEET_Q[1:]):
        if x0 <= c <= x1:
            return y0 + (y1 - y0) * (c - x0) / (x1 - x0)
    return SWEET_Q[-1][1]


def sour_remaining(sucrose_eq_g_per_100g_water):
    """Multiplier on the effective sour stimulus from sugar: piecewise linear through the measured
    points, anchored at (0, 1), held at the last point above 43.6 g (no extrapolation)."""
    x = max(sucrose_eq_g_per_100g_water, 0.0)
    pts = [(0.0, 1.0)] + SOUR_EFFECTIVE_POINTS
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]
