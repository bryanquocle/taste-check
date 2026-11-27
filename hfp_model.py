"""
Human Flavorome Project (HFP) Calculator v.2.2.2 - Python implementation.

Mirrors HFP_Calculator_v.2.2.2_Corrected.xlsx (Bryan Quoc Le, Ph.D.) so a recipe can be
evaluated without Excel. Ingredient data comes from hfp_raw_data.csv (exported from the
workbook's "Raw Data" sheet). Cell references in comments point to the "Calculations" sheet.

Usage:
  python hfp_model.py "Tomato=100 g" "Sauce, Soy=15 mL"      # evaluate a recipe
  python hfp_model.py --json recipe.json                      # [{"ingredient":..,"amount":..,"unit":..}]
  python hfp_model.py --search miso                           # find ingredient names
  python hfp_model.py --detail "Tomato=100 g"                 # include intermediate values
  python hfp_model.py --ranges "Tomato=100 g"                 # add uncertainty ranges (about 15 s)
"""
import csv
import json
import math
import os
import re
import sys

import hfp_acidbase as ab
import hfp_sweet as sw
import hfp_bitter as bt

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "hfp_raw_data.csv")
DQ_PATH = os.path.join(HERE, "hfp_data_quality.csv")

# Data tiers (workbook "Data Quality" sheet): 1 measured, 2 derived/sibling, 3 category estimate,
# 4 blank. Blank key fields count as 0; compute() warns when an ingredient making up at least
# MISSING_DATA_MIN_SHARE of the recipe mass relies on a blank or a tier-3 estimate.
KEY_FIELDS = ("glu", "amp", "imp", "gmp")
MISSING_DATA_MIN_SHARE = 0.01
ACIDS_MATTER_BELOW_PH = 5.5    # blank acid data only flagged for acidic foods (sourness underestimated)
NUCLEOTIDE_FLAG_MIN_GLU = 100  # mg/100 g; below this, missing nucleotides barely move umami

# Units sheet (conversion to g or mL)
MASS_UNITS = {"g": 1, "kg": 1000, "mt": 1_000_000, "oz": 28.35, "lb": 453.59, "t": 907185}
VOLUME_UNITS = {"ml": 1, "cm3": 1, "l": 1000, "m3": 1_000_000, "fl oz": 29.57, "c": 236.59,
                "cup": 236.59, "cups": 236.59, "pt": 473.18, "qt": 946.35, "gal": 3785.41,
                "tsp": 4.93, "tbsp": 14.79}

# Raw Data columns used by the model
COL = {
    "glu": "Glutamate (mg/100g)", "asp": "Aspartate (mg/100g)", "amp": "Adenylate (mg/100g)",
    "imp": "Inosinate (mg/100g)", "gmp": "Guanylate (mg/100g)", "density": "Density (g/mL)",
    "water": "Water Content (%)", "na": "Sodium (mg/100g)", "k": "Potassium (mg/100g)",
    "protein": "Protein (%)", "gsh": "Glutathione (mg/100g)",
    "cys": "Cysteine Sulfoxides (mg/100g)", "evg": "gamma-Glutamyl-Valyl-Glycine (mg/100g)",
    "caf": "Caffeine (mg/100g)", "tb": "Theobromine (mg/100g)",
}

# Potassium counted for saltiness and for the Na/K umami enhancement.
#   "chloride" (default, Python only): only K supplied as chloride salt (KCl, salt substitute,
#              mineral salts). Food potassium (mostly citrate/malate) is excluded because the
#              KCl curve doesn't apply to it; those anions may even be slightly bitter.
#   "total":   all potassium, as in the spreadsheet (use for Excel parity checks).
K_SALTINESS_SOURCE = "chloride"
CHLORIDE_K_INGREDIENTS = {"Potassium Chloride", "Salt Substitute", "Celtic Salt",
                          "Himalayan Salt", "Pink Salt", "Sea Salt"}

# Salt-form conversion for the Yamaguchi umami equation (v.2.2.3).
# Raw Data are free acids (Bryan, Sept 2026: free glutamate; nucleotides and aspartate assumed the
# same basis). Yamaguchi's constants (1967, 1971) are for MSG.H2O, monosodium Asp.H2O,
# Na2IMP.7.5H2O, Na2GMP.7H2O and Na2AMP. Thresholds stay on the free-acid basis (e.g., glutamate
# 0.01 g ~ Yamaguchi's 0.012 g MSG.H2O).
SALT_FORM = {
    "glu": 187.13 / 147.13,   # L-glutamic acid -> MSG.H2O
    "asp": 173.10 / 133.10,   # L-aspartic acid -> monosodium L-aspartate.H2O
    "imp": 527.28 / 348.21,   # 5'-IMP -> Na2IMP.7.5H2O
    "gmp": 533.29 / 363.22,   # 5'-GMP -> Na2GMP.7H2O
    "amp": 391.18 / 347.22,   # 5'-AMP -> Na2AMP (anhydrous; consistent with Yamaguchi's 0.18 vs 0.13)
}

# Nucleotide-driven drop in the glutamate/aspartate threshold (v.2.3.1; Bryan, Sept 2026).
# Yamaguchi 2000 Table 3: 63-fold at 5 mM IMP. See compute().
GLU_THR_DROP_MAX = 0.012 / 0.00019          # = 63.2
GLU_THR_DROP_AT_IMP_mM = 5.0
GLU_THR_NUC_WEIGHT = {"amp": 0.18, "gmp": 2.3}
NUC_MW = {"imp": 348.21, "gmp": 363.22, "amp": 347.22}   # free acids

# Legacy NaCl -> umami threshold multipliers (Calculations!Z37/AA37: x4 glutamate above 150 mM Na; x4/x8
# nucleotides above 20/170 mM Na). No source was ever found, and they act opposite to the modeled salt
# enhancement of umami (double counting): adding 1 tsp salt to 800 g canned tomatoes cut modeled umami
# from 9.4 to 5.0. Switched off in v.2.5.0 (Bryan, Sept 2026). True restores the old behavior.
SALT_THRESHOLD_RULE = False

# Ceiling on the nucleotide synergy multiplier (1 + synergy) = MSG-equivalent per unit of glutamate present.
# v.2.8.4 (Bryan, Nov 25 2026): 63, was 16 (v.2.6.0). The 16 was a misread: Yamaguchi 1967's "~16x" at 1:1 (MSG + IMP
# = 0.05 g/dL, eq. 11: y = 0.79 g/dL) is relative to the TOTAL 0.05 g/dL; relative to the glutamate present (this
# multiplier) that same measured point is ~31x. Zhang 2008's 3.2 -> 0.2 mM EC50 shift at 1 mM IMP is the top dose
# tested on a chimeric receptor, not a ceiling. A ceiling is still needed: the only human high-IMP datum, Yamaguchi &
# Kimizuka 1979 (Yamaguchi 2000 Table 3), 0.25% (5 mM) IMP lowers the MSG threshold 63x where the equation gives 305x.
# 63 = that measurement (same source as GLU_THR_DROP_MAX). ASSUMPTION: the threshold shift equals the suprathreshold
# potency shift. Excel Calculations!AF34 still holds 16 (workbook not updated; harness pins 16). None = uncapped.
SYNERGY_MAX_FOLD = 63

# Sodium saltiness curve (Nov 26, 2026). "murphy_log" = Murphy et al. 1981 log fit everywhere (default, matches
# Excel and the web page). "human_splice" (Python only, NOT adopted; Bryan's call) keeps Murphy up to 0.108 M and
# above it follows the human gLMS data found Nov 26 (validation/salt_literature_2026-11-26/NOTES.md): local power
# exponent 0.8 from 0.108 to 0.3 M (Webb et al. 2015, PMC4475569) and 0.35 above 0.3 M (Rawal et al. 2015,
# PMC5100746), anchored to Murphy's value at 0.108 M. The 10-point reference stays 0.5 M NaCl.
SALT_HIGH_CURVE = "murphy_log"
_NA_A, _NA_B, _NA_KNEE, _NA_KNEE2, _NA_E1, _NA_E2 = 2.7036, 12.008, 0.108, 0.3, 0.8, 0.35


def na_curve(m):
    """Saltiness intensity of sodium at molarity m (Murphy 1981 scale)."""
    if m <= 0:
        return 0.0
    if SALT_HIGH_CURVE != "human_splice" or m <= _NA_KNEE:
        return max(0.0, _NA_A * math.log(m) + _NA_B)
    s0 = _NA_A * math.log(_NA_KNEE) + _NA_B
    if m <= _NA_KNEE2:
        return s0 * (m / _NA_KNEE) ** _NA_E1
    return s0 * (_NA_KNEE2 / _NA_KNEE) ** _NA_E1 * (m / _NA_KNEE2) ** _NA_E2


def na_inverse(s):
    """Sodium molarity whose saltiness is s (inverse of na_curve)."""
    if SALT_HIGH_CURVE == "human_splice":
        s0 = _NA_A * math.log(_NA_KNEE) + _NA_B
        s1 = s0 * (_NA_KNEE2 / _NA_KNEE) ** _NA_E1
        if s > s1:
            return _NA_KNEE2 * (s / s1) ** (1 / _NA_E2)
        if s > s0:
            return _NA_KNEE * (s / s0) ** (1 / _NA_E1)
    return math.exp((s - _NA_B) / _NA_A)


# 1-10 output scores (v.2.5.0, Bryan, Sept 2026): score = 1 + 9 * min(1, raw / reference), where 1 = at or
# below threshold and 10 = a "very strong" reference, roughly the most intense a person would still eat.
# Linear in each output's own intensity scale, so rank and spacing are kept; scales stay not strictly
# commensurable across tastes.
SCORE_REF = {
    "umami": 3.6672 * math.log(5.0) + 12.555,   # 5 g/dL MSG.H2O-equivalent on Yamaguchi's curve (= 18.46)
    "salt": na_curve(0.5),                      # 0.5 M NaCl (~3%, seawater) on the Murphy 1981 fit (= 10.13)
    "sweet": 0.54 * 10.0 ** 1.3,                # 10% w/w sucrose on Moskowitz 1970 (= 10.77); was 20% (Bryan, Sept 2026)
    "kokumi": 100.0,                            # 100% of the GSH-equivalent CaSR response
    "bitter": bt.BITTER_REF,                    # Spectrum 10 ~ 0.15% caffeine in water (v.2.8.0, hfp_bitter.py)
    # 5% w/v citric acid in water (~ straight lemon juice) on Yamaguchi's tartaric curve (= 149.6), v.2.6.0
    "sour": ab.sourness_intensity(ab.acid_in_water_stimulus_mM("citric", 50.0 / 192.12 * 1000)),
}


def to_score(raw, key):
    return 1 + 9 * min(1.0, max(0.0, raw) / SCORE_REF[key])


# Kokumi as glutathione equivalents (v.2.2.3).
# Potency by weight vs GSH: gamma-EVG 12.8 (Ohsu et al. 2010, human PSE, n = 17);
# cysteine sulfoxides 1.0 (Ueda et al. 1990: alliin as effective as GSH at 0.2% w/v; qualitative).
# Dose-response: Hill curve, EC50 0.912 mM, n 1.456. ASSUMPTION, not a receptor value (relabeled v.2.8.4, Nov 25 2026):
# the shape is a fit to the GSH CaSR curve in HEK-293 cells (Koku book Fig. 8.1, Maruyama & Kuroda: EC50 0.71 uM on an
# axis labeled mM; Ohsu 2010 gives 76.5 nM), most likely with uM read as mM. Cell EC50s do not transfer to the mouth (GSH
# water threshold 1.3 mM, Ueda 1997), so the curve is kept as a sensory curve on a mouth-concentration axis, checked only
# against human points: 0.33 mM (Ueda 1997 threshold in umami) 18%, 0.65 mM (Ueda significant effects) 38%, 2.6 mM
# (Ohsu 2010 Fig. 1) 82%, 5.26 mM (Goto 2016) 93%. No human GSH dose-response curve exists (searched Nov 25 2026).
KOKUMI_POTENCY = {"gsh": 1.0, "evg": 12.8, "cys": 1.0}
# Kokumi detection floor (v.2.9.0, Bryan, Nov 25 2026). Ueda et al. 1997 (Biosci Biotechnol Biochem 61:1977, Table II,
# triangle tests, pH 7): GSH threshold 0.04% w/v in water and in 0.05% MSG, 0.02% in 0.8% MSG, 0.01% in 3.1% MSG and in
# 0.05% MSG + 0.05% IMP. Context = the recipe's umami MSG-equivalent (g/dL, after synergy); log-log interpolation,
# held at the end points. Kokumi = 0 below the threshold and rescales the Hill curve above it (same 100% ceiling).
# KOKUMI_FLOOR = False restores pre-2.9.0 (no floor).
KOKUMI_FLOOR = True
KOKUMI_THR_POINTS = [(0.05, 0.04), (0.8, 0.02), (3.1, 0.01)]     # (MSG-eq g/dL, GSH % w/v threshold)


def kokumi_threshold_mM(umami_eq):
    pts = KOKUMI_THR_POINTS
    x = umami_eq if umami_eq and umami_eq > 0 else pts[0][0]
    if x <= pts[0][0]:
        pct = pts[0][1]
    elif x >= pts[-1][0]:
        pct = pts[-1][1]
    else:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x <= x1:
                t = (math.log(x) - math.log(x0)) / (math.log(x1) - math.log(x0))
                pct = math.exp(math.log(y0) + t * (math.log(y1) - math.log(y0)))
                break
    return pct * 10 / 307.33 * 1000      # % w/v GSH -> mM
KOKUMI_EC50_MM = 0.9122
KOKUMI_HILL_N = 1.456

# Cooking-generated 5'-nucleotides in vegetables and mushrooms (Python only).
# Nguyen et al. 1988 (Bioflavour 87, Table II): blanching + steaming lets endogenous nucleases
# (peak activity 65-75 C) release 5'-AMP/5'-GMP from RNA. When a listed ingredient is cooked at
# >= 65 C, its raw AMP/GMP are replaced by these cooked values (mg/100 g, free acids).
# Fresh shiitake is derived from Nguyen's DRIED shiitake (9% moisture) scaled by dry matter (x0.113).
# Broccoli GMP printed as ".35" in the paper, read as 35 nmol/g (0.35 is below the detection limit).
# Not applied to entries whose values already reflect cooking/extraction (e.g., dried shiitake 150).
COOKED_NUCLEOTIDES = {  # name: (AMP, GMP) mg/100 g after cooking
    "Asparagus (Fresh)": (0.972, 0.436), "Green Pepper": (2.049, 1.562),
    "Broccoli": (1.493, 1.271), "Cabbage": (0.451, 0.0), "Cauliflower": (0.833, 3.015),
    "Mushroom, Button": (11.736, 4.431), "Mushroom, Champignon": (11.736, 4.431),
    "Sweet Potato": (4.41, 1.126), "Potato": (1.042, 0.799), "Radish": (0.764, 0.182),
    "Mushroom, Shiitake (Fresh)": (8.214, 14.019),
    # v.2.9.0: Horie 2012 (J Cookery Sci Jpn 45:346, Tables 1-2) steamed GMP (100 C 15 min; spinach 87 C 10 min),
    # enzyme-inactivated raw controls, mg/100 g fresh, assumed free acid. AMP not measured: None = keep the raw AMP.
    "Eggplant": (None, 1.70), "Carrot": (None, 0.34), "Daikon": (None, 0.14),
    "Onion, Welsh": (None, 0.21), "Spinach": (None, 0.76),
}
NUCLEASE_MIN_TEMP_C = 65

# Thermal loss of cysteine sulfoxides during cooking (Python only).
# Chen et al. 2017, Food Chem 223:25-30: alliin in 20% aq. methanol, first order,
# k = 4.38e17 * exp(-142494 / (R*T)) per min, fitted at 60, 80, 89 C.
# Applied to the whole CyS(O)R pool (alliin, isoalliin, methiin) per Bryan's decision (Sept 2026):
# no isoalliin kinetics exist, so alliin kinetics are extrapolated to it.
ALLIIN_A = 4.38e17
ALLIIN_EA = 142494.0
R_GAS = 8.314


def cys_thermal_fraction(minutes, temp_c):
    """Fraction of cysteine sulfoxides remaining after isothermal heating."""
    if not minutes or temp_c is None:
        return 1.0
    k = ALLIIN_A * math.exp(-ALLIIN_EA / (R_GAS * (temp_c + 273.15)))
    return math.exp(-k * minutes)


# Salt effect on umami. The curve shape is from dog chorda tympani data (Ugawa & Kurihara 1994,
# R to 200 mM MSG vs NaCl; peak R = 0.5828 at 100 mM). Both Ugawa papers (1992 human, sweet amino
# acids; 1994 dog) describe salt as shifting the dose-response to lower concentration.
#   "shift" (v.2.2.3 default): umami-eq x M, M = 1 + (SALT_SHIFT_MAX - 1) * min(1, R / 0.5828).
#            SALT_SHIFT_MAX = 2 is a PLACEHOLDER (Bryan, Sept 2026) until human umami data exist.
#   "enhancement" (v.2.2.2): intensity x (1 + R).   "multiplier" (v.2.2.1): intensity x R.
SODIUM_UMAMI_MODE = "shift"
# v.2.11.0 (Bryan, Nov 25 2026): 2.0 -> 1.0 (no salt effect on umami). Human data: Wang et al. 2022 Food Qual Pref
# 98:104503 Fig. 1 (0.05-0.08 M NaCl lowered umami to x0.70-0.73, n = 12); Yamaguchi 1991 Physiol Behav 49:833
# p. 833 (umami 'nor is it enhanced by' the basic tastes) and Table 4 (MSG threshold unchanged in 150 and 370 mM
# NaCl); Schiffman 1991 Physiol Behav 49:843 Table 4a. No human evidence of enhancement. See
# validation/papers_review_2026-11-25/REPORT.md. The shift formula is kept so a sensitivity value can be set.
SALT_SHIFT_MAX = 1.0

# --- Stage 4 fixes (Nov 20, 2026), each a switch; OFF values reproduce v.2.7.1 exactly -----------------------
# KCl/NaCl mixing. "sum" (Excel, v.2.2-2.7) adds the two compressed intensities, which over-predicts blends
# (Chaiya 2026: all 1.5% blends tie at 10 vs NaCl 8.4). "concentration" converts the K saltiness to an iso-salty
# NaCl molarity on the model's own Murphy curve and reads the NaCl curve once (concentration addition for
# same-quality stimuli; Bartoshuk 1975). No new constants.
# v.2.7.2 (Nov 21, 2026): Bryan adopted "concentration" (Chaiya 2026 blends rho 0.91 -> 0.95; workbook v.2.6.4 Z25).
SALT_MIX = "concentration"
# IMP/GMP tasted alone. Yamaguchi 1967 has their alone-terms ~0, so the model scores them 1.0 at any dose.
# NUC_ALONE_U0 > 0 treats them as synergy with a fixed background glutamate (the salivary-glutamate account,
# Shigemura 2009), in g/dL MSG.H2O-eq; 0.05/15 makes 0.05 g/dL IMP alone ~ 0.05 g/dL MSG (Yamaguchi 1967 Fig. 1,
# Table 2) and plateaus as in his Fig. 3. AMP excluded (Tanaka 2025: AMP alone not perceived). 0 = off.
# v.2.7.3 (Nov 21, 2026): adopted. Tanaka 2025 (3 mM nucleotides alone, not used to build it) n/a -> rho 0.89;
# Wang 2021 gets worse (-0.30 -> -0.60) but conflicts with Yamaguchi 1967, Shigemura 2009 and Tanaka 2025.
NUC_ALONE_U0 = 0.05 / 15
NUC_ALONE_U0_PROPOSED = 0.05 / 15
# Umami raising saltiness beyond its own sodium. E = EMAX * S * F applied to the sodium molarity:
#   S = clamp((umami score - 1) / (UMAMI_SALT_S_FULL - 1), 0, 1)  (score includes nucleotide synergy)
#   F = 1 at total Na <= 75 mM, falling linearly to 0 at 260 mM
# v.2.8.1 (Nov 23, 2026): fitted to Sun et al. 2022 Food Res Int 157:111287, Table 2 (16 trained assessors,
# gLMS, NaCl 2.03-13.94 g/L in water, MSG 0.55 g/L "low umami" and 1.40 g/L "moderate umami"). Net lift =
# iso-salty NaCl / (NaCl + MSG's own NaCl-eq, 0.35 g per g) - 1, because the model already counts MSG's sodium.
# Observed MSG net lift 8-12% at <= 84 mM Na, 5% at ~170 mM, 1-3% at ~245 mM; no gain from low to moderate
# umami, so S saturates at the low level (0.055% MSG = model umami score ~2.4). Fit: mean abs error 1.3 points
# over 12 cells. Succinate, IMP and I+G gave larger lifts at low umami (~15-18%); EMAX uses MSG (glutamate is
# the main umami source in foods), so the rule is conservative for nucleotide-rich foods. Replaces the
# Nov 20 placeholder (EMAX 0.12, S full at score 6, fade 50-110 mM). 0 = off.
UMAMI_SALT_EMAX = 0.10
UMAMI_SALT_EMAX_PROPOSED = 0.10
UMAMI_SALT_S_FULL = 2.4
UMAMI_SALT_FADE_mM = (75.0, 260.0)
DOG_R_PEAK = 0.5828

# Protein/peptide bitterness: WARNING ONLY (v.2.8.2), no score. Hydrolysates taste bitter from hydrophobic peptides,
# increasing with degree of hydrolysis (Sun X et al. 2022, Front Nutr 9:1022257, wheat gluten hydrolysates; Ney's
# Q rule). Flags ingredients named as hydrolysates/isolates making up >= MISSING_DATA_MIN_SHARE of the recipe mass.
PROTEIN_BITTER_RE = re.compile(r"hydroly[sz]|isolate|protein powder|whey protein|pea protein|soy protein|casein",
                               re.I)

# Bitterness coverage note `bitter_gap` (v.2.15.0; NOTE ONLY, no score change). Frozen design and validation:
# validation/bitter_flags_2026-11-25/ (PROTOCOL.md, bitter_sources.csv; held-out SVT 5/6 bitter foods flagged, 0/20
# low-bitter foods; blind keyword test 10/14 and 4/337). Per class: dose = sum(share x k x cook) over listed rows,
# share = row mass / recipe mass after evaporation; fires once if any class has dose >= 1.
#   k: "anchor"  (B_ref / 10)^(1/0.87), B_ref = SVT dev-half panel bitterness of the pure food (0-100);
#      "default" B_ref = BITTER_GAP_DEFAULT_B (20, ASSUMPTION); 0.87 = Torrico & Prinyawiwatkul 2015 caffeine exponent
#      "gsl"     total glucosinolates (McNaughton & Marks 2003 Br J Nutr 90:687, Table 2 medians, mg/100 g) / 65
#      "etoh"    ethanol g/100 g (USDA SR Legacy, nutrient 1018) / 2.5
#   cook (row cooked = its cook_min, else the recipe's, > 0 and cook_temp_c None or >= 60 C): "raw_only" 0
#      (alliinase inactivated, Song & Milner 2001); "gsl_loss" 1 - loss (McNaughton & Marks Table 3, else 0.36);
#      "etoh_retention" Augustin et al. 1992 retention (BITTER_GAP_ETOH_RETENTION); "none" 1.
# Rows: ingredient -> [(class, basis, ref_value, cook_rule, loss)]; sources per row in bitter_sources.csv.
BITTER_GAP_TARGET_B = 10.0
BITTER_GAP_EXPONENT = 0.87
BITTER_GAP_DEFAULT_B = 20.0
BITTER_GAP_GSL_MIN = 65.0
BITTER_GAP_ETOH_MIN = 2.5
BITTER_GAP_COOK_MIN_TEMP_C = 60.0
BITTER_GAP_ETOH_RETENTION = ((0.0, 0.85), (15.0, 0.40), (30.0, 0.35), (60.0, 0.25), (90.0, 0.20), (120.0, 0.10),
                             (150.0, 0.05))
BITTER_GAP = {
    "Beer": [("hop_acids", "anchor", 57.0, "none", 0.0), ("ethanol", "etoh", 3.9, "etoh_retention", 0.0)],
    "Wine, Generic": [("ethanol", "etoh", 10.4, "etoh_retention", 0.0)],
    "Wine, Claret": [("ethanol", "etoh", 10.2, "etoh_retention", 0.0), ("wine_flavanols", "anchor", 36.5, "none", 0.0)],
    "Wine, Dry Red": [("ethanol", "etoh", 10.6, "etoh_retention", 0.0), ("wine_flavanols", "anchor", 36.5, "none", 0.0)],
    "Wine, Champagne": [("ethanol", "etoh", 10.4, "etoh_retention", 0.0)],
    "Wine, Moselle": [("ethanol", "etoh", 9.5, "etoh_retention", 0.0)],
    "Wine, Riesling": [("ethanol", "etoh", 9.5, "etoh_retention", 0.0)],
    "Wine, Port": [("ethanol", "etoh", 15.3, "etoh_retention", 0.0), ("wine_flavanols", "anchor", 36.5, "none", 0.0)],
    "Wine, Sake": [("ethanol", "etoh", 16.1, "etoh_retention", 0.0)],
    "Wine, Cooking": [("ethanol", "etoh", 3.3, "etoh_retention", 0.0)],
    "Spirit, Rum": [("ethanol", "etoh", 33.4, "etoh_retention", 0.0)],
    "Spirit, Vodka": [("ethanol", "etoh", 33.4, "etoh_retention", 0.0)],
    "Spirit, Gin": [("ethanol", "etoh", 33.4, "etoh_retention", 0.0)],
    "Spirit, Brandy": [("ethanol", "etoh", 33.4, "etoh_retention", 0.0)],
    "Spirit, Tequila": [("ethanol", "etoh", 33.4, "etoh_retention", 0.0)],
    "Spirit, Whiskey": [("ethanol", "etoh", 36.0, "etoh_retention", 0.0)],
    "Liqueur, Coffee": [("ethanol", "etoh", 21.7, "etoh_retention", 0.0)],
    "Extract, Vanilla": [("ethanol", "etoh", 34.4, "etoh_retention", 0.0)],
    "Mirin": [("ethanol", "etoh", 9.4, "etoh_retention", 0.0)],
    "Juice, Grapefruit": [("citrus_flavanones", "anchor", 57.0, "none", 0.0)],
    "Grapefruit": [("citrus_flavanones", "anchor", 57.0, "none", 0.0)],
    "Jam, Orange Marmalade": [("citrus_flavanones", "default", None, "none", 0.0)],
    "Brussel Sprouts": [("glucosinolates", "gsl", 236.6, "gsl_loss", 0.427)],
    "Broccoli": [("glucosinolates", "gsl", 61.7, "gsl_loss", 0.391)],
    "Cauliflower": [("glucosinolates", "gsl", 43.2, "gsl_loss", 0.323)],
    "Cabbage": [("glucosinolates", "gsl", 58.9, "gsl_loss", 0.278)],
    "Kale": [("glucosinolates", "gsl", 100.7, "gsl_loss", 0.227)],
    "Collard Greens": [("glucosinolates", "gsl", 200.7, "gsl_loss", 0.36)],
    "Mustard Greens": [("glucosinolates", "gsl", 281.5, "gsl_loss", 0.36)],
    "Radish": [("glucosinolates", "gsl", 92.5, "gsl_loss", 0.36)],
    "Daikon": [("glucosinolates", "gsl", 123.4, "gsl_loss", 0.36)],
    "Watercress": [("glucosinolates", "gsl", 95.0, "gsl_loss", 0.36)],
    "Horseradish": [("glucosinolates", "gsl", 160.1, "gsl_loss", 0.36)],
    "Bok Choy": [("glucosinolates", "gsl", 54.1, "gsl_loss", 0.36)],
    "Cabbage (Chinese)": [("glucosinolates", "gsl", 20.6, "gsl_loss", 0.36)],
    "Mix, Coleslaw": [("glucosinolates", "gsl", 42.2, "gsl_loss", 0.36)],
    "Onion": [("raw_allium", "anchor", 52.5, "raw_only", 0.0)],
    "Onion, Welsh": [("raw_allium", "anchor", 52.5, "raw_only", 0.0)],
    "Leek": [("raw_allium", "anchor", 52.5, "raw_only", 0.0)],
    "Shallot": [("raw_allium", "anchor", 52.5, "raw_only", 0.0)],
    "Garlic": [("raw_allium", "anchor", 52.5, "raw_only", 0.0)],
    "Green Onion": [("raw_allium", "anchor", 52.5, "raw_only", 0.0)],
    "Chive": [("raw_allium", "anchor", 52.5, "raw_only", 0.0)],
    "Tea, Black (Brewed)": [("tea_flavanols", "default", None, "none", 0.0)],
    "Tea, Green (Brewed)": [("tea_flavanols", "default", None, "none", 0.0)],
    "Coffee, Brewed": [("coffee_bitters", "anchor", 58.5, "none", 0.0)],
    "Espresso": [("coffee_bitters", "anchor", 58.5, "none", 0.0)],
    "Cocoa Powder (Unsweetened)": [("cocoa_flavanols", "default", None, "none", 0.0)],
    "Cacao Nib": [("cocoa_flavanols", "default", None, "none", 0.0)],
    "Chocolate, Baking (Unsweetened)": [("cocoa_flavanols", "default", None, "none", 0.0)],
    "Chocolate, Dark (70-85%)": [("cocoa_flavanols", "default", None, "none", 0.0)],
    "Chocolate, Dark (45-59%)": [("cocoa_flavanols", "default", None, "none", 0.0)],
    "Chocolate, Bittersweet Chip": [("cocoa_flavanols", "default", None, "none", 0.0)],
    "Radicchio": [("sesquiterpene_lactones", "default", None, "none", 0.0)],
    "Endive": [("sesquiterpene_lactones", "default", None, "none", 0.0)],
    "Olives, Green": [("olive_secoiridoids", "default", None, "none", 0.0)],
    "Oil, Olive (Extra Virgin)": [("olive_secoiridoids", "default", None, "none", 0.0)],
    "Bitter Melon": [("cucurbitanes", "default", None, "none", 0.0)],
}
# Class order (note order) and plain-language compound names.
BITTER_GAP_CLASSES = (
    ("hop_acids", "hop acids"), ("ethanol", "alcohol"), ("wine_flavanols", "tannins and catechins"),
    ("citrus_flavanones", "naringin and limonin"), ("glucosinolates", "glucosinolates"),
    ("raw_allium", "raw-onion sulfur compounds"), ("tea_flavanols", "catechins beyond its caffeine"),
    ("coffee_bitters", "roast bitters beyond its caffeine"),
    ("cocoa_flavanols", "catechins and roast bitters beyond its theobromine and caffeine"),
    ("sesquiterpene_lactones", "lactucin-type bitters"), ("olive_secoiridoids", "oleuropein-type bitters"),
    ("cucurbitanes", "momordicine-type bitters"))


def _bitter_gap_k(basis, ref):
    if basis == "anchor":
        return (ref / BITTER_GAP_TARGET_B) ** (1.0 / BITTER_GAP_EXPONENT)
    if basis == "default":
        return (BITTER_GAP_DEFAULT_B / BITTER_GAP_TARGET_B) ** (1.0 / BITTER_GAP_EXPONENT)
    if basis == "gsl":
        return ref / BITTER_GAP_GSL_MIN
    return ref / BITTER_GAP_ETOH_MIN                    # "etoh"


def _bitter_gap_cook(rule, loss, minutes):
    if minutes <= 0 or rule == "none":
        return 1.0
    if rule == "raw_only":
        return 0.0
    if rule == "gsl_loss":
        return 1.0 - loss
    pts = BITTER_GAP_ETOH_RETENTION                     # "etoh_retention", linear interpolation
    if minutes >= pts[-1][0]:
        return pts[-1][1]
    for (t0, r0), (t1, r1) in zip(pts, pts[1:]):
        if minutes <= t1:
            return r0 + (r1 - r0) * (minutes - t0) / (t1 - t0)
    return pts[-1][1]


def bitter_gap(items, total_mass, cook_temp_c=None):
    """items: [(ingredient, mass_g, item_cook_min)]. Returns (fired list [{class, dose, names}], note text or None)."""
    if total_mass <= 0:
        return [], None
    hot = cook_temp_c is None or cook_temp_c >= BITTER_GAP_COOK_MIN_TEMP_C
    dose, names = {}, {}
    for name, mass, minutes in items:
        for cls, basis, ref, rule, loss in BITTER_GAP.get(name, ()):
            d = mass / total_mass * _bitter_gap_k(basis, ref) * _bitter_gap_cook(rule, loss, minutes if hot else 0.0)
            if d > 0:
                dose[cls] = dose.get(cls, 0.0) + d
                names.setdefault(cls, set()).add(name)
    fired = [{"class": c, "dose": dose[c], "names": sorted(names[c])}
             for c, _ in BITTER_GAP_CLASSES if dose.get(c, 0.0) >= 1.0 - 1e-12]
    if not fired:
        return [], None
    label = dict(BITTER_GAP_CLASSES)
    parts = {}
    for f in fired:
        for n in f["names"]:
            parts.setdefault(n, []).append(label[f["class"]])
    text = ("Bitterness may read low: " + "; ".join("%s (%s)" % (n, ", ".join(v)) for n, v in parts.items())
            + (" adds" if len(parts) == 1 else " add") + " bitterness Taste Check doesn't score yet. "
            "This is a note, not a score change.")
    if any(f["class"] == "raw_allium" for f in fired):
        text += " Onion-family items count only when eaten raw; enter a cooking time if they're cooked."
    return fired, text

# Kokumi gain on umami and saltiness intensity: X22 = umami x (1 + gain x kokumi/100).
# 0.72 / 0.60 trace to Goto et al. 2016 citing Ohsu et al. 2010 as "1.72x / 1.60x more intense",
# but those are Ohsu Fig. 2A thickness scores on a -2..+2 scale, not intensity ratios.
# Human intensity anchors: Goto 2016 x1.38 at 5.26 mM GSH (noodle-soup MSG+NaCl, n = 26) -> gain ~0.41;
# Ohsu 2010 Fig. 1 x1.74 at 2.6 mM GSH (weak MSG+IMP+NaCl) -> gain ~0.90; Ueda 1997: no change in
# single basic tastes at 1.3 mM. Decision (Bryan, Sept 2026): 0.41 for both, per Goto 2016
# (5.26 mM GSH = 92.8% kokumi on the v.2.2.3 curve; 0.38 / 0.928 = 0.41).
KOKUMI_UMAMI_GAIN = 0.41
KOKUMI_SALT_GAIN = 0.41

# Umami 10/10 widened (Bryan, Nov 15, 2026; mirrored in web/hfp_model.js and workbook v.2.6.2 BK25). The old
# reference was 5 g/dL MSG-eq on the bare curve (18.46), but the final umami value also gets the salt shift
# (up to x SALT_SHIFT_MAX on the concentration) and the kokumi gain (up to x 1 + KOKUMI_UMAMI_GAIN), so salted,
# kokumi-rich dishes ran past 10 (53-56% of stews, curries and stir-fries capped). New reference = the same
# 5 g/dL MSG-eq with both boosts at their maximum (= 29.61). Set UMAMI_REF_WITH_BOOSTS = False for the old scale.
UMAMI_REF_WITH_BOOSTS = True
if UMAMI_REF_WITH_BOOSTS:
    SCORE_REF["umami"] = (3.6672 * math.log(5.0 * SALT_SHIFT_MAX) + 12.555) * (1 + KOKUMI_UMAMI_GAIN)


def load_db(path=DB_PATH, dq_path=DQ_PATH):
    db = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row["Ingredient"]
            db[name] = {k: _num(row.get(col, "")) for k, col in COL.items()}
            for a, (col, _, _, _) in ab.ORGANIC_ACIDS.items():
                db[name]["acid_" + a] = _num(row.get(col, ""))
            for sg, col in sw.SUGAR_COLUMNS.items():
                db[name]["sugar_" + sg] = _num(row.get(col, ""))
            ph = row.get("pH (approx.)", "").strip()
            db[name]["ph_ref"] = float(ph) if ph else None
            # tier 4 (blank) key fields: loaded as 0, but flagged so compute() can warn
            blank = {k for k in KEY_FIELDS if not row.get(COL[k], "").strip()}
            if not any(row.get(col, "").strip() for col, _, _, _ in ab.ORGANIC_ACIDS.values()):
                blank.add("acids")
            db[name]["_blank"] = blank
            db[name]["_tier"] = {}
    if dq_path and os.path.exists(dq_path):              # Data Quality sheet export (tiers 2 and 3)
        with open(dq_path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["Ingredient"] in db:
                    db[row["Ingredient"]]["_tier"][row["Field"]] = int(row["Tier"])
    return db


# Cold serving lowers sweetness (v.2.7.3): log10 drop at COLD_SWEET_MIN_C, linear in temperature up to
# COLD_SWEET_ABOVE_C. Sugars not tested (polyols, other sugars) use the sucrose value: an assumption.
COLD_SWEET_K = {"sucrose": 0.43, "glucose": 0.22, "fructose": 0.11}
COLD_SWEET_MIN_C, COLD_SWEET_ABOVE_C = 5.0, 21.0

# Acidity / pH model (v.2.3.0, Python only; see hfp_acidbase.py). False = matches the Excel workbook.
ACIDITY_MODEL = True
# Sugar lowers perceived sourness (Schifferstein & Frijters 1990). If True, the sour stimulus that drives
# Miranda's umami suppression is reduced by the same fraction, assuming the acid's suppression of umami
# acts through perceived sourness (v.2.4.0, an assumption; set False to use the raw sour stimulus).
SUGAR_SOUR_ON_UMAMI = True

# Nucleotide detection thresholds, g/100 mL free acid (v.2.9.0; see compute()). "kuninaka" = current; "tiers" = pre-2.9.0.
NUC_THRESHOLD_MODE = "kuninaka"
NUC_THR_ALONE = {"imp": 0.387 * 348.21 / 1e4, "gmp": 0.206 * 363.22 / 1e4}     # Kuninaka 1980 Table I (0.0135, 0.0075)
NUC_THR_ALONE["amp"] = NUC_THR_ALONE["imp"] / 0.18                           # ASSUMPTION (no human AMP threshold found)

# Tasted-concentration basis (v.2.8.5, Bryan, Nov 25 2026). "food": salt, sweet, umami, sour and kokumi use
# concentration per 100 g of FOOD (water-phase concentration x water/mass), the Stark 2006 dose-over-threshold
# convention already used for bitterness (v.2.8.3). pH, buffering and the pH synergy factor stay in the water phase.
# Sugar solutions are unchanged (sucrose per 100 g food = % w/w of the solution). Validated on a pre-registered
# hold-out of 43 low-water SVT foods (validation/svt_mars/holdout_solid): saltiness rho 0.365 -> 0.774, sweetness
# 0.457 -> 0.840. "water" = pre-2.8.5 behaviour (concentration per 100 g of the food's water).
TASTE_BASIS = "food"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def find(db, term):
    t = term.lower()
    return sorted(n for n in db if t in n.lower())


def resolve(db, name):
    for n in db:
        if n.lower() == name.strip().lower():
            return n
    hits = find(db, name.strip())
    if len(hits) == 1:
        return hits[0]
    raise KeyError(f"Ingredient '{name}' not found exactly."
                   + (f" Did you mean: {', '.join(hits[:15])}" if hits else " No partial matches."))


def parse_arg(s):
    name, _, qty = s.rpartition("=")
    parts = qty.strip().split(None, 1)
    return {"ingredient": name.strip(), "amount": float(parts[0]),
            "unit": parts[1].strip() if len(parts) > 1 else "g"}


def compute(recipe, db=None, mode=None, water_loss_g=0.0, k_source=None,
            cook_min=0.0, cook_temp_c=None, acidity=None, serve_temp_c=None):
    """water_loss_g: water evaporated during cooking (Python-only extension; 0 = matches Excel).
    k_source: "chloride" or "total" (see K_SALTINESS_SOURCE); "total" matches Excel.
    cook_min / cook_temp_c: isothermal cooking applied to cysteine sulfoxides (Chen 2017).
      Per-ingredient overrides in the recipe item: "cook_min" (e.g. 0 for garlic added at the
      end) and "cys_loss_on_cut" (0-1, fraction converted by alliinase before heating; no
      default data - leave 0 unless you have a value)."""
    db = db or load_db()
    mode = mode or SODIUM_UMAMI_MODE
    k_source = k_source or K_SALTINESS_SOURCE
    acidity = ACIDITY_MODEL if acidity is None else acidity
    warnings, rows = [], []
    ab_species, ab_z, ph_defaults = {}, 0.0, []
    if cook_temp_c is not None and (cook_min or any("cook_min" in i for i in recipe)):
        if not 60 <= cook_temp_c <= 89:
            warnings.append(f"Cooking at {cook_temp_c} C is outside Chen 2017's tested range "
                            f"(60-89 C); cysteine sulfoxide loss is extrapolated.")
        warnings.append("Cysteine sulfoxide loss uses alliin kinetics (Chen 2017) for all "
                        "sulfoxides, including isoalliin; pure solution, not tissue.")
    tot = {k: 0.0 for k in ("mass", "water", "glu", "asp", "amp", "imp", "gmp", "na", "k",
                            "k_cl", "protein", "gsh", "cys", "evg", "caf", "tb")}
    sugar_mg = {sg: 0.0 for sg in sw.SUGAR_COLUMNS}

    for item in recipe:
        name = resolve(db, item["ingredient"])
        d = db[name]
        unit = item.get("unit", "g").strip().lower()
        amt = float(item["amount"])
        if unit in MASS_UNITS:
            mass = amt * MASS_UNITS[unit]                          # H = C*G
        elif unit in VOLUME_UNITS:
            if d["density"] <= 0:
                warnings.append(f"{name}: no density in database, volume entry counts as 0 g "
                                f"(the spreadsheet does the same). Enter a weight instead.")
            mass = amt * VOLUME_UNITS[unit] * d["density"]         # L = J*K
        else:
            raise ValueError(f"Unknown unit '{item.get('unit')}'. Mass: {list(MASS_UNITS)}; "
                             f"volume: {list(VOLUME_UNITS)}")
        if d["water"] <= 0:
            warnings.append(f"{name}: water content is 0/blank, so it adds solutes but no water.")
        r = {"ingredient": name, "mass_g": mass, "water_g": mass * d["water"] / 100}
        for k in ("glu", "asp", "amp", "imp", "gmp", "na", "k", "gsh", "cys", "evg", "caf", "tb"):
            r[k + "_mg"] = mass / 100 * d[k]                        # U..Y, AA, AC, AW, AY, BA
        item_cook = float(item.get("cook_min", cook_min) or 0)
        if (name in COOKED_NUCLEOTIDES and item_cook > 0
                and (cook_temp_c is None or cook_temp_c >= NUCLEASE_MIN_TEMP_C)):
            c_amp, c_gmp = COOKED_NUCLEOTIDES[name]
            if c_amp is None:                       # GMP-only source (Horie 2012): keep the raw AMP
                c_amp = d["amp"]
            r["nucleotides_cooked"] = True
            r["amp_mg"], r["gmp_mg"] = mass / 100 * c_amp, mass / 100 * c_gmp
            warnings.append(f"{name}: cooked 5'-AMP/GMP applied (Nguyen 1988; Horie 2012): AMP {d['amp']:.2f} -> "
                            f"{c_amp:.2f}, GMP {d['gmp']:.2f} -> {c_gmp:.2f} mg/100 g.")
        r["protein_g"] = mass / 100 * d["protein"]
        if r["cys_mg"] > 0:
            item_min = float(item.get("cook_min", cook_min) or 0)
            cut = float(item.get("cys_loss_on_cut", 0) or 0)
            frac = (1 - cut) * cys_thermal_fraction(item_min, cook_temp_c)
            r["cys_mg_raw"] = r["cys_mg"]
            r["cys_retained"] = frac
            r["cys_mg"] *= frac
        rows.append(r)
        if acidity and mass > 0:
            sp_i = ab.species_from_composition(d, mass, name)
            # nucleotides: use the (possibly cooked) amounts actually in the row
            sp_i["nuc"] = sum(r[k2 + "_mg"] / ab.NUCLEOTIDE_MW[k2] for k2 in ("amp", "imp", "gmp"))
            for k2, v in sp_i.items():
                ab_species[k2] = ab_species.get(k2, 0.0) + v
            z_i, ref_i, flag_i = ab.calibrate_z_mmol(d, name, mass, r["water_g"], sp_mmol=sp_i)
            ab_z += z_i
            r["ph_ref"], r["ph_ref_source"] = ref_i, flag_i
            if flag_i == "default":
                ph_defaults.append(name)
        tot["mass"] += mass
        tot["water"] += r["water_g"]
        for k in ("glu", "asp", "amp", "imp", "gmp", "na", "k", "gsh", "cys", "evg", "caf", "tb"):
            tot[k] += r[k + "_mg"]
        if name in CHLORIDE_K_INGREDIENTS:
            tot["k_cl"] += r["k_mg"]
        tot["protein"] += r["protein_g"]
        for sg in sugar_mg:
            sugar_mg[sg] += mass / 100 * d.get("sugar_" + sg, 0.0)

    # Data-tier warnings (tier 4 blanks and tier 3 estimates), skipping minor ingredients
    labels = {"glu": "glutamate", "amp": "AMP", "imp": "IMP", "gmp": "GMP", "acids": "organic acids",
              "ph": "pH", "nucleotides": "nucleotides"}
    missing, estimated = [], []
    for r in rows:
        if tot["mass"] <= 0 or r["mass_g"] / tot["mass"] < MISSING_DATA_MIN_SHARE:
            continue
        d = db[r["ingredient"]]
        b = d.get("_blank", set())
        blank = ["glu"] if "glu" in b else []
        # nucleotides: flag only when none were measured and the ingredient is umami-relevant
        # (a partial blank usually means the source measured the nucleotide that matters)
        if {"amp", "imp", "gmp"} <= b and (d["glu"] >= NUCLEOTIDE_FLAG_MIN_GLU or r["ingredient"] in ab.MUSCLE_FOODS):  # v.2.15.0: always for meat/fish (IMP drives their umami)
            blank.append("nucleotides")
        if ("acids" in b and d["ph_ref"] is not None
                and d["ph_ref"] < ACIDS_MATTER_BELOW_PH):
            blank.append("acids")
        if blank:
            missing.append(f"{r['ingredient']} ({', '.join(labels[f] for f in blank)})")
        est = [f for f, t in d.get("_tier", {}).items() if t == 3]
        if est:
            estimated.append(f"{r['ingredient']} ({', '.join(labels.get(f, f) for f in est)})")
    if missing:
        warnings.append("No data, counted as 0 (tier 4): " + "; ".join(missing)
                        + ". Results may be underestimated.")
    if estimated:
        warnings.append("Category estimates used (tier 3): " + "; ".join(estimated) + ".")

    if water_loss_g:
        if water_loss_g >= tot["water"]:
            raise ValueError(f"Evaporated water ({water_loss_g} g) must be less than total water "
                             f"({tot['water']:.1f} g).")
        tot["water"] -= water_loss_g
        tot["mass"] -= water_loss_g
        warnings.append(f"{water_loss_g:g} g water removed for cooking loss (not in the spreadsheet).")

    if tot["water"] <= 0:
        raise ValueError("Total water is 0 g - concentrations (per 100 g water) are undefined. "
                         "Add a water-containing ingredient. (Spreadsheet silently shows 0.)")

    # Acidity (v.2.3.0): mixture pH (charge balance + per-ingredient calibration), sour stimulus,
    # Miranda umami suppression and Yamaguchi pH-synergy factor.
    # Sugars (g/100 g water) -> sucrose-equivalents (Moskowitz 1970), used for sweetness and sour suppression
    sugars = {sg: (v / 1000) / (tot["water"] / 100) for sg, v in sugar_mg.items()}
    sucrose_eq_g, unscored = sw.sucrose_equivalent(sugars)
    # v.2.8.5 tasted basis: fb converts water-phase concentrations to per 100 g food (1.0 in "water" mode)
    f_food = tot["water"] / tot["mass"] if tot["mass"] > 0 else 1.0
    fb = f_food if TASTE_BASIS == "food" else 1.0
    sugars_food = {sg: v * f_food for sg, v in sugars.items()}
    suc_food = sw.sucrose_equivalent(sugars_food)[0]                 # g sucrose-eq per 100 g food = % w/w
    # sugar -> sour suppression was measured in sugar water (g/100 g water): use the sugar-water equivalent of the
    # food-basis sucrose-eq (identical for sugar solutions, bounded for low-water foods)
    sour_sugar_x = (100 * suc_food / (100 - min(suc_food, 99.0))) if TASTE_BASIS == "food" else sucrose_eq_g
    sour_rem = sw.sour_remaining(sour_sugar_x)
    acid = {"pH": None, "sour_stimulus_mM": 0.0, "citric_equiv_mM": 0.0,
            "umami_remaining": 1.0, "synergy_pH_factor": 1.0}
    sour_final = None
    if acidity:
        wL = tot["water"] / 1000
        sp = ab.to_molar(ab_species, wL)
        ph = ab.solve_ph(sp, ab_z / 1000 / wL)
        s = ab.sour_stimulus_mM(sp, ph) * fb             # pH from the water phase; tasted stimulus per food (v.2.8.5)
        s_eff = s * sour_rem if SUGAR_SOUR_ON_UMAMI else s
        # Sourness (v.2.6.0): perceived sour stimulus after sugar (always applied here), on Yamaguchi's curve
        sour_final = ab.sourness_intensity(s * sour_rem)
        acid = {"pH": ph, "sour_stimulus_mM": s, "citric_equiv_mM": ab.citric_equivalent_mM(s),
                "sourness_remaining_after_sugar": sour_rem, "sour_stimulus_effective_mM": s_eff,
                "tartaric_equiv_g_per_100mL": ab.tartaric_equivalent_g(s * sour_rem),
                "umami_remaining": ab.umami_remaining(s_eff), "synergy_pH_factor": ab.synergy_ph_factor(ph)}
        if sour_final > 100:
            warnings.append(f"Sourness {sour_final:.0f} is above the top of Yamaguchi's scale (100 = saturated "
                            f"sucrose); the tartaric acid curve is extrapolated.")
        if ph_defaults:
            warnings.append("No reference pH for " + ", ".join(sorted(set(ph_defaults)))
                            + f" -> calibrated at default pH {ab.DEFAULT_PH}.")
        if s_eff > ab.MIRANDA_S_MAX:
            warnings.append(f"Effective sour stimulus {s_eff:.1f} mM exceeds Miranda's range "
                            f"({ab.MIRANDA_S_MAX:.1f} mM); umami suppression is extrapolated.")
        if ph < 5.0 and (tot["imp"] + tot["gmp"] + tot["amp"]) > 0:
            warnings.append(f"pH {ph:.2f} is below Yamaguchi's synergy data (pH >= 5); synergy held at 1.0.")

    w100 = tot["water"] / 100
    conc = {k: (tot[k] / 1000) / w100 * fb for k in ("glu", "asp", "amp", "imp", "gmp", "na", "k",
                                                  "k_cl", "gsh", "cys", "evg", "caf", "tb")}   # row 16 (g/100 g water; x fb = per 100 g food from v.2.8.5)
    k_for_salt = conc["k_cl"] if k_source == "chloride" else conc["k"]
    if k_source == "chloride" and conc["k"] > conc["k_cl"]:
        warnings.append(f"Potassium: only chloride-salt K counted for saltiness "
                        f"({conc['k_cl']:.4f} of {conc['k']:.4f} g/100 g water).")

    # Salt effects on thresholds (G115, J115, J116; Z37, AA37)
    g115 = (150 / 1000 * 23) / 10
    j115 = (20 / 1000 * 23) / 10
    j116 = (170 / 1000 * 23) / 10
    if SALT_THRESHOLD_RULE:   # legacy rule, source unknown; off since v.2.5.0 (see constant)
        z37 = 4 if conc["na"] > g115 else 1
        aa37 = 8 if conc["na"] > j116 else (4 if conc["na"] > j115 else 1)
    else:
        z37 = aa37 = 1

    # Nucleotides lower the glutamate/aspartate detection threshold (v.2.3.1). Yamaguchi 2000
    # (J Nutr, Table 3; Yamaguchi & Kimizuka 1979): MSG threshold 0.012% in water -> 0.00019% in
    # 5 mM IMP, a 63-fold drop. The divisor scales linearly with IMP-equivalents (same form and
    # relative weights as the synergy equation: AMP 0.18, IMP 1, GMP 2.3), reaching 63 at 5 mM and
    # capped there (no extrapolation). Replaces the old step rule (/100 once IMP > 0.011 or
    # GMP > 0.0056 g/100 g). Asp uses the same divisor (no Asp-specific data).
    imp_eq_mM = 1e4 * (conc["imp"] / NUC_MW["imp"] + GLU_THR_NUC_WEIGHT["amp"] * conc["amp"] / NUC_MW["amp"]
                       + GLU_THR_NUC_WEIGHT["gmp"] * conc["gmp"] / NUC_MW["gmp"])
    glu_thr_div = min(GLU_THR_DROP_MAX, 1 + (GLU_THR_DROP_MAX - 1) * imp_eq_mM / GLU_THR_DROP_AT_IMP_mM)
    thr = {"glu": 0.01 / glu_thr_div * z37,                          # U19
           "asp": 0.0166 / glu_thr_div * z37}                        # V19; Yamaguchi 1991 Table 1: 1.25 mM Na-Asp = 0.01664 g/100 mL Asp
    u16 = conc["glu"] if conc["glu"] > thr["glu"] else 0.0
    v16 = conc["asp"] if conc["asp"] > thr["asp"] else 0.0
    # Nucleotide thresholds (v.2.9.0, Bryan, Nov 25 2026). With glutamate above its own threshold, nucleotides count
    # at any level: synergy is already gated by glutamate, whose threshold drops with nucleotides (above), and IMP may
    # have no umami of its own (Yamaguchi & Ninomiya 2000, p. 923S). Without glutamate (the nucleotide-alone path),
    # human thresholds in water from Kuninaka et al. 1980 (Agric Biol Chem 44:1437, Table I): IMP 0.387 mM, GMP 0.206 mM
    # as free acids; AMP has no human threshold, so IMP / 0.18 (its synergy weight) is an ASSUMPTION. Replaces the old
    # three-tier table (unsourced; its 0.0037 cut was the NaCl threshold copied by mistake). pre-2.9.0: NUC_THRESHOLD_MODE.
    if NUC_THRESHOLD_MODE == "tiers":
        lvl = 0 if u16 > 0.0735 else (1 if u16 > 0.0037 else 2)
        thr["amp"] = (0.00305, 0.0061, 0.061)[lvl] * aa37          # W19
        thr["imp"] = (0.00051, 0.001, 0.011)[lvl] * aa37           # X19
        thr["gmp"] = (0.00028, 0.00056, 0.0056)[lvl] * aa37        # Y19
    elif u16 > 0:
        thr["amp"] = thr["imp"] = thr["gmp"] = 0.0
    else:
        thr["amp"], thr["imp"], thr["gmp"] = (NUC_THR_ALONE["amp"] * aa37, NUC_THR_ALONE["imp"] * aa37,
                                               NUC_THR_ALONE["gmp"] * aa37)
    w16 = conc["amp"] if conc["amp"] > thr["amp"] else 0.0
    x16 = conc["imp"] if conc["imp"] > thr["imp"] else 0.0
    y16 = conc["gmp"] if conc["gmp"] > thr["gmp"] else 0.0

    # Umami equivalents (Yamaguchi synergy, in g/100 mL MSG.H2O) and intensity (U22, V22).
    # Above-threshold free-acid concentrations are converted to Yamaguchi's salt forms first.
    u = SALT_FORM["glu"] * u16 + 0.077 * SALT_FORM["asp"] * v16           # Yamaguchi 1971
    synergy = (219 * SALT_FORM["amp"] * w16 + 1218 * SALT_FORM["imp"] * x16
               + 2800 * SALT_FORM["gmp"] * y16)
    fold = 1 + synergy * acid["synergy_pH_factor"]                      # pH factor: Yamaguchi 1979
    if SYNERGY_MAX_FOLD is not None:
        fold = min(fold, SYNERGY_MAX_FOLD)
    umami_eq = u * fold
    if NUC_ALONE_U0 > 0:
        fold_ig = 1 + (1218 * SALT_FORM["imp"] * x16 + 2800 * SALT_FORM["gmp"] * y16) * acid["synergy_pH_factor"]
        if SYNERGY_MAX_FOLD is not None:
            fold_ig = min(fold_ig, SYNERGY_MAX_FOLD)
        umami_eq += NUC_ALONE_U0 * (fold_ig - 1)
    umami_int_noshift = max(0.0, 3.6672 * math.log(umami_eq) + 12.555) if umami_eq > 0 else 0.0

    # Saltiness. Detection thresholds expressed as the cation:
    #   Na: Yamaguchi & Kimizuka NaCl threshold 0.0037 g NaCl/100 mL (Yamaguchi 1979, Table III)
    #   K:  Schiffman et al. 1995 KCl threshold 0.00242 M (= 0.018 g KCl/100 mL)
    # Intensity fits: Murphy et al. 1981 (Fig. 7-8), data range 0.004-0.108 M.
    thr["na"] = 0.0037 * 22.99 / 58.44                               # AA19
    thr["k"] = 0.00242 * 39.0983 / 10                                # AC19
    na_m = 0.0 if conc["na"] < thr["na"] else conc["na"] * 10 / 23          # Z22
    k_m = 0.0 if k_for_salt < thr["k"] else k_for_salt * 10 / 39.0983      # AB22
    na_salt = na_curve(na_m)                                         # AA22
    if na_m > 0.108:
        warnings.append(f"[Na] = {na_m:.3f} M is above the measured NaCl range (Murphy 1981, max "
                        f"0.108 M); sodium saltiness is extrapolated from a log fit.")
    if k_m <= 0:
        k_salt = 0.0                                                 # AC22
    elif k_m <= 0.112:
        k_salt = max(0.0, 404.88 * k_m**2 + 6.7462 * k_m - 0.1344)
    else:  # beyond measured KCl range: scale the NaCl curve to meet the KCl fit at 0.112 M
        k_salt = ((404.88 * 0.112**2 + 6.7462 * 0.112 - 0.1344)
                  / na_curve(0.112)) * na_curve(k_m)
        warnings.append(f"[K] = {k_m:.3f} M is above the measured KCl range (0.112 M); "
                        f"potassium saltiness is extrapolated.")
    def mix(na_int, na_mol):
        if SALT_MIX == "concentration" and k_salt > 0:
            na_eq_k = na_inverse(k_salt)                         # NaCl molarity iso-salty to the K
            return na_curve(na_mol + na_eq_k)
        return na_int + k_salt                                       # Z25
    salt_total = mix(na_salt, na_m)

    # Na/K effect on umami (Z28, AA28, Z31, AA31, Z34, W22)
    x = na_m + 0.81 * k_m
    effect = max(0.0, -37.089 * x**2 + 9.9621 * x - 0.038) if x < 0.1 \
        else max(0.0, -0.6351 * x + 0.6414)
    shift = 1 + (SALT_SHIFT_MAX - 1) * min(1.0, effect / DOG_R_PEAK)          # AC34
    if mode == "shift":
        umami_int = (max(0.0, 3.6672 * math.log(umami_eq * shift) + 12.555)
                     if umami_eq > 0 else 0.0)                                 # V22
        umami_na = umami_int                                                   # W22
    elif mode == "enhancement":
        umami_int = umami_int_noshift
        umami_na = umami_int * (1 + effect)
    else:
        umami_int = umami_int_noshift
        umami_na = umami_int * effect
    umami_na *= acid["umami_remaining"]                  # sour/acid suppression (Miranda 2021)

    # Kokumi as glutathione equivalents (BC16, BC22, BC25 -> AW28).
    gsh_eq = sum(KOKUMI_POTENCY[k] * conc[k] for k in ("gsh", "evg", "cys"))  # g/100 g water
    gsh_eq_mM = gsh_eq / 307.33 * 10 * 1000
    hill = lambda c: (100 * c**KOKUMI_HILL_N / (KOKUMI_EC50_MM**KOKUMI_HILL_N + c**KOKUMI_HILL_N)) if c > 0 else 0.0
    kokumi = hill(gsh_eq_mM)
    if KOKUMI_FLOOR:
        h_thr = hill(kokumi_threshold_mM(umami_eq))
        kokumi = max(0.0, (kokumi - h_thr) / (100 - h_thr) * 100)
    # contribution of each compound to the GSH-equivalent dose (for reporting)
    k_gsh, k_cys, k_evg = ((KOKUMI_POTENCY[k] * conc[k] / gsh_eq * 100) if gsh_eq > 0 else 0.0
                           for k in ("gsh", "cys", "evg"))

    umami_final = umami_na + umami_na * KOKUMI_UMAMI_GAIN * (kokumi / 100)    # X22

    # Sweetness (v.2.4.0, Python only): Moskowitz 1970 power law on sucrose-equivalents (% w/w of the sugar
    # solution), minus the acid decrement of Schifferstein & Frijters 1990.
    total_sugar_g = sum(sugars.values())
    q_acid = sw.sweet_q(acid["citric_equiv_mM"]) if acidity else 1.0
    if TASTE_BASIS == "food":                                          # v.2.8.5: sucrose-eq per 100 g food
        c_eq_pct = suc_food
        sweet_raw = sw.sweetness(c_eq_pct)
        sweet_final = sw.sweetness(suc_food * q_acid)
    else:
        c_eq_pct = sw.pct_ww(sucrose_eq_g, total_sugar_g)
        sweet_raw = sw.sweetness(c_eq_pct)
        sweet_final = sw.sweetness(sw.pct_ww(sucrose_eq_g * q_acid, total_sugar_g))
    # Serving temperature (v.2.7.3, Python only; None = off). Cold lowers sweetness only (Green & Nachtigal 2015,
    # PMC4542652: log10 drop at 5 C vs 30 C, sucrose 0.43, glucose 0.22, fructose 0.11, high-intensity ~0.60;
    # 21 C rates like 30-37 C). Saltiness and sourness: no effect (Nachtigal 2019); umami: none for MSG (Green 2016).
    if serve_temp_c is not None and serve_temp_c < COLD_SWEET_ABOVE_C and sweet_final > 0:
        parts = {}
        for s_, g in sugars.items():
            if g <= 0:
                continue
            if s_ in sw.HIGH_INTENSITY:
                parts[s_] = sw.his_sucrose_eq(s_, g)[0]
            elif s_ in sw.RELATIVE_SWEETNESS:
                parts[s_] = sw.RELATIVE_SWEETNESS[s_] ** (1 / sw.EXPONENT) * g
        tot_p = sum(parts.values())
        if tot_p > 0:
            k = sum(v * COLD_SWEET_K.get(s_, 0.60 if s_ in sw.HIGH_INTENSITY else COLD_SWEET_K["sucrose"])
                    for s_, v in parts.items()) / tot_p
            t = max(COLD_SWEET_MIN_C, serve_temp_c)
            sweet_final *= 10 ** (-k * (COLD_SWEET_ABOVE_C - t) / (COLD_SWEET_ABOVE_C - COLD_SWEET_MIN_C))
            warnings.append(f"Served at {serve_temp_c:g} C: sweetness lowered for cold serving (Green & Nachtigal 2015, "
                            f"tongue-tip data, so an upper bound for eating)" + (" ; below 5 C is unvalidated." if serve_temp_c < COLD_SWEET_MIN_C else "."))
    if c_eq_pct > sw.MOSKOWITZ_MAX_PCT:
        warnings.append(f"Sucrose-equivalent {c_eq_pct:.1f}% w/w is above Moskowitz's range (32%); "
                        f"sweetness is extrapolated.")
    if acidity and sweet_raw > 0 and acid["citric_equiv_mM"] > sw.SWEET_Q[-1][0]:
        warnings.append(f"Acid level {acid['citric_equiv_mM']:.1f} mM citric-eq is above the measured "
                        f"range (95 mM, McBride & Johnson 1987); sweetness suppression held at its 95 mM value.")
    if acidity and SUGAR_SOUR_ON_UMAMI and sucrose_eq_g > sw.SF_SUCROSE_G_PER_100G_WATER[-1]:
        warnings.append("Sugar level is above Schifferstein & Frijters' range; sour suppression held at "
                        "its 1 M sucrose value.")
    unscored_present = [u for u in unscored if sugars[u] >= 0.01 * max(total_sugar_g, 1e-9)]
    if unscored_present:
        warnings.append("Not counted for sweetness (no Moskowitz 1970 value): " + ", ".join(unscored_present) + ".")
    his_high = sw.his_above_range(sugars)
    if his_high:
        warnings.append("Above the tested range, sweetness held at its top tested level (15% sucrose-eq, Wee 2018; "
                        "saccharin 9%, Schiffman 1995): " + ", ".join(his_high) + ".")
    if any(sugars.get(k, 0) > 0 for k in sw.HIGH_INTENSITY):
        warnings.append("High-intensity sweeteners (Wee 2018; saccharin from Schiffman 1995): bitterness is modelled for "
                        "Reb A, acesulfame K and saccharin (Schiffman 1995); sucralose and aspartame are not bitter at normal levels; lingering and "
                        "synergy between sweeteners are not modelled. Stevia and monk fruit grades are scaled by their "
                        "Reb A / mogroside V content.")
    umami_salt_e = 0.0
    if UMAMI_SALT_EMAX > 0 and na_m > 0:
        s_um = min(1.0, max(0.0, (to_score(umami_final, "umami") - 1) / (UMAMI_SALT_S_FULL - 1)))
        lo, hi = UMAMI_SALT_FADE_mM
        na_mM = na_m * 1000
        f_na = 1.0 if na_mM <= lo else max(0.0, (hi - na_mM) / (hi - lo))
        umami_salt_e = UMAMI_SALT_EMAX * s_um * f_na
        if umami_salt_e > 0:
            na_eff = na_m * (1 + umami_salt_e)
            salt_total = mix(na_curve(na_eff), na_eff)
    salt_final = salt_total + salt_total * KOKUMI_SALT_GAIN * (kokumi / 100)  # AA25

    # Bitterness (v.2.8.3, Python and web only): caffeine + theobromine, KCl, Reb A, acesulfame K; suppressed by
    # sodium and sugar (hfp_bitter.py). WHOLE-FOOD BASIS (v.2.8.3, Stark 2006 dose-over-threshold convention):
    # every bitterness input is per 100 g of food, not per 100 g of the food's water (the other tastes are
    # unchanged). f = water / mass converts the water-phase concentrations. Reb A and acesulfame K are masked
    # only by the OTHER sweeteners (their own sweetness is inside their data).
    fw = f_food / fb                       # conc and na_m are already per food when TASTE_BASIS == "food"
    suc_food_reba = sw.sucrose_equivalent({**sugars_food, "reb_a": 0.0})[0]
    suc_food_acek = sw.sucrose_equivalent({**sugars_food, "ace_k": 0.0})[0]
    suc_food_sacc = sw.sucrose_equivalent({**sugars_food, "saccharin": 0.0})[0]
    bitter_final, bitter_detail, bwarn = bt.bitterness(
        conc["caf"] * fw, conc["k_cl"] * bt.KCL_PER_K * fw, na_m * fw, suc_food,
        tb_pct=conc["tb"] * fw, reba_pct=sugars_food.get("reb_a", 0.0), acek_pct=sugars_food.get("ace_k", 0.0),
        sucrose_eq_pct_reba=suc_food_reba, sucrose_eq_pct_acek=suc_food_acek,
        sacc_pct=sugars_food.get("saccharin", 0.0), sucrose_eq_pct_sacc=suc_food_sacc)
    warnings.extend(bwarn)
    if conc["caf"] > 0 or conc["tb"] > 0:
        warnings.append("Bitterness counts caffeine, theobromine, KCl, Reb A and acesulfame K only. Coffee, tea and "
                        "cocoa also get bitterness from other compounds (chlorogenic lactones, catechins, "
                        "diketopiperazines, polyphenols), so their bitterness may read low.")
    flagged = [r["ingredient"] for r in rows if PROTEIN_BITTER_RE.search(r["ingredient"])
               and tot["mass"] > 0 and r["mass_g"] / tot["mass"] >= MISSING_DATA_MIN_SHARE]
    if flagged:
        warnings.append("Protein hydrolysate/isolate (" + ", ".join(flagged) + "): may taste bitter from hydrophobic "
                        "peptides, more so with more hydrolysis (Sun et al. 2022). Not scored.")
    # Bitterness coverage note (v.2.15.0): rows and recipe items are 1:1, in order.
    gap_fired, gap_text = bitter_gap(
        [(r["ingredient"], r["mass_g"], float(it.get("cook_min", cook_min) or 0)) for r, it in zip(rows, recipe)],
        tot["mass"], cook_temp_c)
    if gap_text:
        warnings.append(gap_text)

    return {
        "results": {"umami_intensity": umami_final, "kokumi_intensity_pct": kokumi,
                    "saltiness_intensity": salt_final, "sweetness_intensity": sweet_final,
                    "sourness_intensity": sour_final, "bitterness_intensity": bitter_final},
        "scores": {"umami": to_score(umami_final, "umami"), "saltiness": to_score(salt_final, "salt"),
                   "sweetness": to_score(sweet_final, "sweet"), "kokumi": to_score(kokumi, "kokumi"),
                   "sourness": to_score(sour_final, "sour") if sour_final is not None else None,
                   "bitterness": to_score(bitter_final, "bitter")},
        "bitterness": bitter_detail,
        "bitter_gap": gap_fired,
        "sweetness": {"sucrose_eq_g_per_100g_water": sucrose_eq_g, "sucrose_eq_pct_ww": c_eq_pct,
                      "sweetness_before_acid": sweet_raw, "acid_multiplier_on_sugar": q_acid,
                      "sugars_g_per_100g_water": sugars},
        "components": {"umami_eq": umami_eq, "umami_intensity_raw": umami_int,
                       "na_k_umami_effect": effect, "salt_conc_shift": shift,
                       "umami_after_na": umami_na,
                       "na_saltiness": na_salt, "k_saltiness": k_salt, "saltiness_raw": salt_total,
                       "gsh_eq_mM": gsh_eq_mM,
                       "gsh_eq_share_gsh_pct": k_gsh, "gsh_eq_share_cys_pct": k_cys,
                       "gsh_eq_share_evg_pct": k_evg,
                       "na_molar": na_m, "k_molar": k_m},
        "acidity": acid,
        "totals": {"mass_g": tot["mass"], "water_g": tot["water"], "protein_g": tot["protein"],
                   # v.2.16.2: sodium in label units (whole recipe and per 100 g of the finished recipe)
                   "sodium_mg": tot["na"], "sodium_mg_per_100g": tot["na"] / tot["mass"] * 100 if tot["mass"] > 0 else 0.0},
        "conc_g_per_100g_water": conc,
        "thresholds": thr,
        "above_threshold": {"glu": u16, "asp": v16, "amp": w16, "imp": x16, "gmp": y16},
        "rows": rows,
        "warnings": warnings,
        "mode": mode,
    }


def report(res, detail=False):
    r = res["results"]
    out = ["Ingredients:"]
    for row in res["rows"]:
        out.append(f"  - {row['ingredient']}: {row['mass_g']:.2f} g (water {row['water_g']:.2f} g)")
    t = res["totals"]
    out.append(f"Total mass {t['mass_g']:.2f} g | total water {t['water_g']:.2f} g")
    out.append(f"Sodium {t['sodium_mg']:.0f} mg in the recipe | {t['sodium_mg_per_100g']:.0f} mg per 100 g")
    out.append("")
    sc = res["scores"]
    sw_ = res.get("sweetness") or {}
    out.append("SCORES (1 = threshold, 10 = very strong reference)     raw model value")
    out.append(f"  UMAMI      {sc['umami']:5.1f} / 10     {r['umami_intensity']:8.2f}  (Yamaguchi scale; 10 = 5% MSG-eq"
               + (" with full salt and kokumi boost)" if UMAMI_REF_WITH_BOOSTS else ")"))
    out.append(f"  SALTINESS  {sc['saltiness']:5.1f} / 10     {r['saltiness_intensity']:8.2f}  (Murphy scale; 10 = 0.5 M NaCl)")
    out.append(f"  SWEETNESS  {sc['sweetness']:5.1f} / 10     {r['sweetness_intensity']:8.2f}  (Moskowitz; 10 = 10% sucrose; "
               f"sucrose-eq {sw_.get('sucrose_eq_pct_ww', 0):.2f}% w/w)")
    out.append(f"  KOKUMI     {sc['kokumi']:5.1f} / 10     {r['kokumi_intensity_pct']:8.2f}  (% of max CaSR response)")
    if sc.get("sourness") is not None:
        out.append(f"  SOURNESS   {sc['sourness']:5.1f} / 10     {r['sourness_intensity']:8.2f}  (Yamaguchi scale; "
                   f"10 = 5% citric acid, ~lemon juice)")
    if sc.get("bitterness") is not None:
        out.append(f"  BITTERNESS {sc['bitterness']:5.1f} / 10     {r['bitterness_intensity']:8.2f}  (Spectrum scale; "
                   f"10 = ~0.15% caffeine; caffeine, theobromine, KCl, Reb A, acesulfame K, saccharin; per 100 g food)")
    a = res.get("acidity") or {}
    if a.get("pH") is not None:
        out.append(f"Predicted pH         {a['pH']:8.2f}   (sour stimulus {a['sour_stimulus_mM']:.2f} mM = "
                   f"{a['citric_equiv_mM']:.2f} mM citric-equivalent; umami x{a['umami_remaining']:.3f}, "
                   f"synergy x{a['synergy_pH_factor']:.2f})")
    if detail:
        out.append("\nComponents:")
        out += [f"  {k}: {v:.5g}" for k, v in res["components"].items()]
        out.append("Concentrations (g/100 g water):")
        out += [f"  {k}: {v:.5g}" for k, v in res["conc_g_per_100g_water"].items()]
        out.append("Thresholds (g/100 g water):")
        out += [f"  {k}: {v:.5g}" for k, v in res["thresholds"].items()]
    if res["warnings"]:
        out.append("\nWarnings:")
        out += [f"  ! {w}" for w in res["warnings"]]
    return "\n".join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    detail = "--detail" in args
    want_ranges = "--ranges" in args                 # uncertainty ranges on the scores (hfp_ranges.py)
    args = [a for a in args if a not in ("--detail", "--ranges")]
    def _flag(name, default=None):
        if name in args:
            i = args.index(name)
            val = float(args[i + 1])
            del args[i:i + 2]
            return val
        return default
    loss = _flag("--evaporate", 0.0)
    cook_min = _flag("--cook", 0.0)
    cook_temp = _flag("--temp", None)
    serve_temp = _flag("--serve-temp", None)        # serving temperature, C (cold lowers sweetness)
    if not args:
        print(__doc__)
        sys.exit(0)
    if args[0] == "--search":
        print("\n".join(find(load_db(), " ".join(args[1:]))) or "No matches.")
        sys.exit(0)
    if args[0] == "--json":
        with open(args[1], encoding="utf-8") as fh:
            recipe = json.load(fh)
    else:
        recipe = [parse_arg(a) for a in args]
    print(report(compute(recipe, water_loss_g=loss, cook_min=cook_min, cook_temp_c=cook_temp, serve_temp_c=serve_temp),
                 detail))
    if want_ranges:
        import hfp_ranges
        print()
        print(hfp_ranges.report(hfp_ranges.ranges(recipe, water_loss_g=loss, cook_min=cook_min,
                                                  cook_temp_c=cook_temp)))
