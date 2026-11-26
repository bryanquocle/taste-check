"""
Acid-base module for the HFP model (v.2.3.0): pH prediction, sour stimulus, and acid effects on umami.

pH (Price et al. 2020, J Food Sci): charge balance over weak acids/bases and strong ions,
    0 = [H+] - [OH-] + sum(z_i * c_i(pH)) + Z,
  solved numerically (bisection). Each ingredient carries an unknown net strong-ion term Z,
  calibrated so the ingredient alone reproduces its reference pH (FDA/USDA "Approximate pH of
  Foods", Raw Data column AP), in the spirit of Price/Longtin's anion/cation corrections.
  No ionic-strength correction (pKa at 25 C, I = 0).

Sour stimulus (Neta et al. 2007, J Food Sci 72:S033; Neta 2009): sour intensity is linear in
  [H+] + molar concentration of organic acid molecules with >= 1 protonated carboxyl group;
  all organic acids are equally sour per protonated molecule, and H+ ~ equal to them.
  -> converts any acid mixture to a common sour stimulus S (mM), and from there to
     "citric-acid equivalents" in Miranda's 50 mM MSG solution.

Umami suppression by acidity (Miranda et al. 2021, Food Qual Pref 89:104147; n = 734):
  50 mM MSG + citric acid 0 / 1.25 / 6.25 / 31.25 mM -> 100 / 92.7 / 81.9 / 48.0 % umami.
  Mapped onto S via this solver and fitted with a logistic in log S.

Synergy vs pH (Yamaguchi 1979, Table VII, MSG-IMP in histidine buffer): relative synergy
  1.0 at pH <= 6.5, 0.535 at 7.5, 0.341 at 8.5, 0.070 at 9.5 (linear interpolation).
  No data below pH 5 -> held at 1.0 (acid-side effects are covered by the Miranda term).
"""
import math

KW = 1e-14

# name: (Raw Data column, MW g/mol, all pKa values, pKa values of acid groups counted for sourness)
ORGANIC_ACIDS = {
    "citric":   ("Citric Acid (mg/100g)",   192.12, [3.13, 4.76, 6.40], [3.13, 4.76, 6.40]),
    "malic":    ("Malic Acid (mg/100g)",    134.09, [3.40, 5.11],       [3.40, 5.11]),
    "tartaric": ("Tartaric Acid (mg/100g)", 150.09, [2.98, 4.34],       [2.98, 4.34]),
    "lactic":   ("Lactic Acid (mg/100g)",    90.08, [3.86],             [3.86]),
    "acetic":   ("Acetic Acid (mg/100g)",    60.05, [4.76],             [4.76]),
    "ascorbic": ("Ascorbic Acid (mg/100g)", 176.12, [4.10, 11.6],       [4.10]),
    "oxalic":   ("Oxalic Acid (mg/100g)",    90.03, [1.25, 4.14],       [1.25, 4.14]),
    "quinic":   ("Quinic Acid (mg/100g)",   192.17, [3.46],             [3.46]),
    "malonic":  ("Malonic Acid (mg/100g)",  104.06, [2.83, 5.69],       [2.83, 5.69]),
    "fumaric":  ("Fumaric Acid (mg/100g)",  116.07, [3.03, 4.44],       [3.03, 4.44]),
    "succinic": ("Succinic Acid (mg/100g)", 118.09, [4.21, 5.64],       [4.21, 5.64]),
    "pyroglutamic": ("Pyroglutamic Acid (mg/100g)", 129.11, [3.32], [3.32]),
    "formic":   ("Formic Acid (mg/100g)",    46.03, [3.75],             [3.75]),
}
# amino acids (fully protonated form carries +1): glutamate, aspartate
AMINO = {"glu": (147.13, [2.19, 4.25, 9.67]), "asp": (133.10, [1.99, 3.90, 9.90])}
NUCLEOTIDE_MW = {"amp": 347.22, "imp": 348.21, "gmp": 363.22}
NUCLEOTIDE_PKA2 = 6.2          # secondary phosphate pKa (primary always dissociated)
# generic protein buffer, mmol per g protein (approximate average amino-acid composition)
PROTEIN_GROUPS = [(-1, 1.00, 4.2),   # Asp/Glu side chains + C-termini (acidic)
                  (+1, 0.20, 6.3),   # His
                  (+1, 0.90, 10.5)]  # Lys/Arg/N-termini (basic)
CHLORIDE_SALTS = {"Salt", "Kosher Salt", "Sea Salt", "Table Salt", "Canning Salt", "Pickling Salt",
                  "Iodized Salt", "Celtic Salt", "Himalayan Salt", "Pink Salt", "Sodium Chloride",
                  "Potassium Chloride", "Salt Substitute"}
# v.2.14.0 (Bryan, Nov 25 2026): non-protein muscle buffers (carnosine, anserine, inorganic phosphate). Okuma & Abe
# 1992 (Comp Biochem Physiol 102A:37): low-molecular-weight components give 48-96% of muscle buffering, proteins
# under 50%. Puolanne & Kivikari 2000 (Meat Sci 56:1): post-rigor beef longissimus 51 mmol H+/(pH kg) over pH 5.5-7.0
# (pork 52, broiler breast 58, leg 41). The generic protein groups alone give 27.3 for lean muscle (22 g protein,
# 75 g water per 100 g); one group of pKa MUSCLE_BUF_PKA (between carnosine 6.83, anserine 7.04 and phosphate 6.8)
# at MUSCLE_BUF_MMOL_G per g protein adds the remaining 23.75. ASSUMPTIONS: the 22 g / 75 g lean-muscle composition,
# the single pKa, and scaling by protein for every meat and fish (including cured and dried).
MUSCLE_BUF_PKA = 6.9
MUSCLE_BUF_MMOL_G = 0.3120
MUSCLE_FOODS = {"Beef", "Boar", "Chicken", "Chicken, Barbecued", "Deer", "Bonito Flakes", "Fish, Anchovy (Canned)", "Fish, Anchovy (Dried)", "Fish, Anchovy (Fresh)", "Fish, Angler", "Fish, Black Scraper", "Fish, Bonito", "Fish, Butter", "Fish, Cod", "Fish, Eel", "Fish, Fatty Tuna", "Fish, Flounder", "Fish, Flying (Dried)", "Fish, Flying (Dried, Grilled)", "Fish, Flying (Fresh)", "Fish, Fugu", "Fish, Horse Mackerel", "Fish, Mackerel", "Fish, Rock", "Fish, Salmon (Fresh)", "Fish, Salmon (Canned)", "Fish, Sardine (Fresh)", "Fish, Sardine (Dried)", "Fish, Sardine (Canned)", "Fish, Seabream (Dried)", "Fish, Seabream (Fresh)", "Fish, Spanish Mackerel", "Fish, Tuna (Dried)", "Fish, Tuna (Fresh)", "Fish, Yellowtail", "Fish, Whitebait (Dried)", "Ham, Dry-Cured", "Hamburger Meat", "Lamb", "Pork", "Pork, Iberian", "Bacon", "Sausage, Italian (Pork)", "Hot Dog (Frankfurter)", "Corned Beef", "Tilapia Fillet", "Stew Meat", "Veal", "Trout", "Red Snapper", "Meatballs", "Sirloin", "Ground Sirloin", "Ground Veal", "Cornish Hen", "Bass", "Catfish Fillet", "Brisket", "Haddock", "Rabbit", "Pork Spareribs", "Veal Cutlet", "Rump Roast", "Duck Breast", "Short Rib", "Ground Venison", "Swordfish", "Duck", "Bologna"}
DEFAULT_PH = 6.0               # for water-containing ingredients with no reference pH (flagged)


def _fractions(pkas, h):
    """Fractions alpha_k (k = number of protons lost) for a polyprotic acid at [H+] = h."""
    terms = [1.0]
    for pka in pkas:
        terms.append(terms[-1] * (10 ** -pka) / h)
    tot = sum(terms)
    return [t / tot for t in terms]


def charge_mol_per_L(sp, h):
    """Net charge (mol/L) of all tracked species at [H+] = h (excluding H+/OH- and Z).
    sp: dict of concentrations in mol/L."""
    q = sp.get("na", 0) + sp.get("k", 0) - sp.get("cl", 0)
    for name, (_, _, pkas, _) in ORGANIC_ACIDS.items():
        c = sp.get(name, 0)
        if c:
            a = _fractions(pkas, h)
            q -= c * sum(k * ak for k, ak in enumerate(a))
    for name, (_, pkas) in AMINO.items():
        c = sp.get(name, 0)
        if c:
            a = _fractions(pkas, h)
            q += c * sum((1 - k) * ak for k, ak in enumerate(a))
    nuc = sp.get("nuc", 0)
    if nuc:
        q -= nuc * (1 + _fractions([NUCLEOTIDE_PKA2], h)[1])
    mbuf = sp.get("mbuf", 0)
    if mbuf:                                              # carnosine/anserine/phosphate: +1 when protonated
        q += mbuf * (1 - _fractions([MUSCLE_BUF_PKA], h)[1])
    prot = sp.get("protein_g", 0)
    if prot:
        for z, mmol_g, pka in PROTEIN_GROUPS:
            deprot = _fractions([pka], h)[1]
            c = prot * mmol_g / 1000
            q += c * (-deprot if z < 0 else (1 - deprot))
    return q


def solve_ph(sp, z=0.0):
    """pH at which [H+] - [OH-] + charge + z = 0 (all mol/L)."""
    lo, hi = 0.0, 14.0
    f = lambda ph: (10 ** -ph) - KW / (10 ** -ph) + charge_mol_per_L(sp, 10 ** -ph) + z
    for _ in range(80):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# v.2.13.0 (Bryan, Nov 25 2026): acid groups with pKa >= SOUR_PKA_MAX are not counted for sourness, the same rule
# already applied to ascorbic acid (only its first pKa counts). In practice this drops citrate's third carboxyl
# (pKa 6.40): at near-neutral pH (milk, pH 6.6) ~40% of citrate is HCit2-, which Neta's count scored as sour
# (milk read 3.7/10). Neta's sour data are for acidic solutions, where HCit2- is a few percent at most, so acidic
# foods barely change. ASSUMPTION: the cutoff (6.0, below salivary pH ~6.8) is the author's, not Neta's.
SOUR_PKA_MAX = 6.0


def sour_stimulus_mM(sp, ph):
    """Neta: [H+] + organic-acid molecules with >= 1 protonated carboxyl of pKa < SOUR_PKA_MAX (mM)."""
    h = 10 ** -ph
    s = h * 1000
    for name, (_, _, _, sour_pkas) in ORGANIC_ACIDS.items():
        c = sp.get(name, 0)
        if c:
            pk = [p for p in sour_pkas if p < SOUR_PKA_MAX]
            fully_deprot = _fractions(pk, h)[-1] if pk else 1.0
            s += c * (1 - fully_deprot) * 1000
    return s


def species_from_composition(d, mass_g, name=None):
    """mmol of each species in `mass_g` of an ingredient (d = Raw Data row as floats)."""
    f = mass_g / 100.0
    sp = {}
    for n, (col, mw, _, _) in ORGANIC_ACIDS.items():
        v = d.get("acid_" + n, 0.0)
        if v:
            sp[n] = v * f / mw
    for n, (mw, _) in AMINO.items():
        if d.get(n):
            sp[n] = d[n] * f / mw
    nuc = sum(d.get(n, 0.0) * f / mw for n, mw in NUCLEOTIDE_MW.items())
    if nuc:
        sp["nuc"] = nuc
    sp["na"] = d.get("na", 0.0) * f / 22.99
    sp["k"] = d.get("k", 0.0) * f / 39.0983
    if name in CHLORIDE_SALTS:
        sp["cl"] = sp["na"] + sp["k"]
    sp["protein_g"] = d.get("protein", 0.0) * f
    if name in MUSCLE_FOODS:                               # v.2.14.0 non-protein muscle buffer (mmol)
        sp["mbuf"] = sp["protein_g"] * MUSCLE_BUF_MMOL_G
    return sp


def to_molar(sp_mmol, water_L):
    out = {}
    for k, v in sp_mmol.items():
        out[k] = (v / water_L) if k == "protein_g" else (v / 1000 / water_L)
    return out


def calibrate_z_mmol(d, name, mass_g, water_g, sp_mmol=None):
    """Unknown net strong-ion charge (mmol) that makes the ingredient alone sit at its reference pH.
    sp_mmol: the ingredient's species as actually used in the mixture (e.g. with cooked nucleotides).
    Calibrating on the same composition keeps each ingredient at its reference pH; nucleotides
    released from RNA on cooking were already charged as RNA phosphate, so they add no net acidity.
    Returns (z_mmol, ref_pH, source_flag)."""
    ref = d.get("ph_ref")
    flag = "reference"
    sp_raw = sp_mmol if sp_mmol is not None else species_from_composition(d, mass_g, name)
    charged = any(v for k, v in sp_raw.items() if k not in ("cl",)) and not (
        name in CHLORIDE_SALTS)
    if not ref:
        if not charged:                      # pure salts (balanced by Cl-), sugars, oils: nothing to balance
            return 0.0, None, "none"
        ref, flag = DEFAULT_PH, "default"
    wL = max(water_g, mass_g) / 1000.0      # dry ingredients calibrated as a 1:1 slurry
    sp = to_molar(sp_raw, wL)
    h = 10 ** -ref
    q = h - KW / h + charge_mol_per_L(sp, h)
    return -q * wL * 1000, ref, flag


# --- Miranda 2021 calibration: umami remaining vs sour stimulus ------------------------------
MIRANDA_CITRIC_mM = [0.0, 1.25, 6.25, 31.25]
MIRANDA_REMAINING = [1.0, 1 - 2.886 / 39.756, 1 - 7.211 / 39.756, 1 - 20.654 / 39.756]
MIRANDA_MSG_mM = 50.0


def miranda_solution(citric_mM):
    sp = {"glu": MIRANDA_MSG_mM / 1000, "na": MIRANDA_MSG_mM / 1000, "citric": citric_mM / 1000}
    ph = solve_ph(sp)
    return ph, sour_stimulus_mM(sp, ph)


def _fit_logistic():
    pts = [miranda_solution(c) for c in MIRANDA_CITRIC_mM]
    s = [p[1] for p in pts]
    best = None
    for s50 in [x / 10 for x in range(5, 400)]:
        for hh in [x / 50 for x in range(10, 200)]:
            err = sum((1 / (1 + (si / s50) ** hh) - r) ** 2 for si, r in zip(s[1:], MIRANDA_REMAINING[1:]))
            if best is None or err < best[0]:
                best = (err, s50, hh)
    return best[1], best[2], pts


SUPPRESS_S50, SUPPRESS_HILL, MIRANDA_POINTS = _fit_logistic()
MIRANDA_S_MAX = MIRANDA_POINTS[-1][1]


def umami_remaining(s_mM):
    """Fraction of umami intensity remaining at sour stimulus S (mM), Miranda-calibrated."""
    if s_mM <= 0:
        return 1.0
    return 1 / (1 + (s_mM / SUPPRESS_S50) ** SUPPRESS_HILL)


def citric_equivalent_mM(s_mM):
    """Citric acid (mM) in Miranda's 50 mM MSG solution that gives the same sour stimulus S."""
    lo, hi = 0.0, 2000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if miranda_solution(mid)[1] < s_mM:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# --- Sourness intensity (v.2.6.0, Python only) -------------------------------------------------
# Yamaguchi 1979 (ACS Symp Ser 115, p. 36; Yamaguchi & Kimizuka): tartaric acid in water, n = 30,
#   S_T = 14.45 * log2(x / 0.00296), x in g/100 mL. Same panel and cross-taste scale as the MSG curve
#   (0 at beta, 100 = saturated sucrose). Detection threshold 0.00094 g/100 mL (Table III); below beta
#   the intensity is 0. A mixture's (sugar-adjusted) Neta sour stimulus is converted to the tartaric acid
#   concentration in pure water giving the same stimulus, then read off the curve.
TARTARIC_ALPHA, TARTARIC_BETA_G = 14.45, 0.00296
TARTARIC_THRESHOLD_G = 0.00094
TARTARIC_MW = ORGANIC_ACIDS["tartaric"][1]


def acid_in_water_stimulus_mM(acid, c_mM):
    sp = {acid: c_mM / 1000}
    return sour_stimulus_mM(sp, solve_ph(sp))


def tartaric_equivalent_g(s_mM):
    """Tartaric acid (g/100 mL, in water) with the same Neta sour stimulus S (mM)."""
    if s_mM <= 0:
        return 0.0
    lo, hi = 0.0, 5000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if acid_in_water_stimulus_mM("tartaric", mid) < s_mM:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2 * TARTARIC_MW / 10000


def sourness_intensity(s_mM):
    """Sourness on Yamaguchi's scale from a sour stimulus S (mM)."""
    x = tartaric_equivalent_g(s_mM)
    if x < TARTARIC_THRESHOLD_G:
        return 0.0
    return max(0.0, TARTARIC_ALPHA * math.log2(x / TARTARIC_BETA_G))


# --- Yamaguchi 1979 Table VII: relative synergy vs pH ----------------------------------------
_SYN = [(6.5, 1.0), (7.5, 0.535), (8.5, 0.341), (9.5, 0.070)]


def synergy_ph_factor(ph):
    if ph <= _SYN[0][0]:
        return 1.0
    if ph >= _SYN[-1][0]:
        return _SYN[-1][1]
    for (x0, y0), (x1, y1) in zip(_SYN, _SYN[1:]):
        if x0 <= ph <= x1:
            return y0 + (y1 - y0) * (ph - x0) / (x1 - x0)
    return 1.0
