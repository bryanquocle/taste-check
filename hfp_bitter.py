"""
Bitterness module (v.2.8.3, Nov 24/25, 2026; Python and web only, not in the workbook).
v.2.8.0 was caffeine + KCl; v.2.8.2 added theobromine and Reb A; v.2.8.3 adds the whole-food basis, the
theobromine solubility cap, Reb A re-sourced to Schiffman 1995 and acesulfame K.

Bitterants: caffeine, potassium chloride, theobromine, rebaudioside A, acesulfame K.
Not modelled (reasons in SESSION_NOTES, Nov 24/25): tea catechins (Xu 2018 has only a one-point caffeine tie and
strong non-additive interactions), chlorogenic-acid lactones, hop acids, naringin, diketopiperazines and
flavan-3-ols in cocoa, saccharin (no DB column), sucralose and aspartame (at the sucrose noise floor at use
levels, Schiffman 1995 Table 1), peptides (protein hydrolysates get a warning only).

BASIS (v.2.8.3). All bitterness inputs are concentrations per 100 g of FOOD (whole-food basis), not per 100 g of
the food's own water as for the other tastes. Source: Stark, Bareuther & Hofmann 2006, J Agric Food Chem
54:5530, Table 1 (p. 5534) and its footnote b: dose-over-threshold = concentration in the food (umol/kg of roasted
cocoa nibs, a low-water solid) / recognition threshold in water (umol/kg). In a solution, % w/v (Torrico,
Schiffman) is close to g per 100 g of solution, i.e. the same basis. For drinks the change is small (coffee
-0.6%, 1.5% KCl -1.5%); for low-water solids it removes the water-phase inflation (milk chocolate has ~1% water,
so its theobromine was read at ~100x its real tasted concentration). The model passes caffeine, theobromine, KCl,
Reb A, acesulfame K, the sodium for suppression and the sucrose-equivalents for masking all on this basis.
ASSUMPTION: the saliva + food bolus is treated as if the food's own mass were the tasting solution (Stark's
convention); saliva dilution and fat-phase partition are not modelled.

SCALE. Torrico & Prinyawiwatkul 2015 (J Food Sci 80:S1885), Spectrum descriptive panel (n = 16), caffeine in water
(Table 3, 0% oil), C in % w/v (g per 100 g, whole-food basis from v.2.8.3):
    caffeine  B = 52.5 * C^0.87    (log k 1.72, n 0.87; tested 0.05-0.15%; R2 0.92)
    KCl       B = 4.37 * C^0.68    (log k 0.64, n 0.68; tested 0.5-1.5%; R2 0.73)
  Below 0.05% caffeine the curve ramps linearly to 0 at the detection threshold 1.2 mM = 0.0233% (Keast & Roper
  2007, Chem Senses 32:245).
  Score 10 = Spectrum 10 (BITTER_REF), Torrico's own fitted data: 0.149% caffeine on the power fit (0.145% on
  their linear fit 0.89 + 62.78 C). The "0.15% = 10, 0.20% = 15" anchors are second-hand and NOT in Torrico (its
  Table 1 lists only 0.05% = 2 and 0.08% = 5). Torrico's panel rated test solutions above its references at the
  low end (0.05% caffeine fits to 3.9, reference 2), so the scale is the panel's working scale.

MIXTURES. Caffeine-type bitterants are put on caffeine-equivalent concentration and added (concentration addition):
    c_xan = caffeine + TB_CAF_EQ * min(theobromine, TB_SOL_MAX_PCT)        (one caffeine curve read once)
  Then the groups (xanthines, KCl, Reb A, acesulfame K) are each converted to an intensity, suppressed, mapped
  back to caffeine-equivalents on the power curve and added.
  Sources: Keast, Bournazel & Breslin 2003, Chem Senses 28:301 (8 bitterants, n = 19, gLMS): "bitter compounds
  generally combine additively in mixture" (abstract); a weak bitter additive was not different from
  self-addition of the target (Fig. 5-6, 8x8x4 ANOVA n.s.), "the vast majority of the 218 unique binary
  interactions ... combined additively" (p. 309). Exceptions were urea (suppressed QHCl, L-phe, SOA, ranitidine,
  DB, L-trp; p. 309), SOA on urea/QHCl and L-trp/L-phe on QHCl at low intensity - none of these are in the model.
  Breslin & Beauchamp 1995: KCl + urea 85-92% of the sum. Self-addition = concentration addition, so v.2.8.2's
  rule is kept. ASSUMPTION: caffeine, theobromine, Reb A and acesulfame K were not among Keast's compounds.
  Note (not modelled): Xu et al. 2018 (Food Chem 258:16, p. 14 of the accepted manuscript) found caffeine
  (1.5 mM) ENHANCED EGCG bitterness at 0.65-1.30 mM EGCG (+3.0, +3.5 vs +2.5 expected) and EGC/EC suppressed
  it - relevant only once catechins are modelled.

THEOBROMINE.
  Potency: Xing et al. 2024, Food Sci Technol Res 30:281 (doi 10.3136/fstr.FSTR-D-23-00215), Table S2: bitterness
  recognition thresholds at 25 C, same trained panel (n = 10, 3-AFC, ISO 13301), caffeine 578.86 +/- 39.91 and
  theobromine 685.08 +/- 49.59 umol/L. Ratio 0.845 mol/mol = 0.911 g caffeine per g theobromine. ASSUMPTION:
  equal dose-over-threshold = equal bitterness.
  Cross-check (v.2.8.3, kept Xing): Stark 2006 Table 1 (same panel, triangle tests in water pH 5.5): theobromine
  800, caffeine 750 umol/kg -> 0.9375 mol/mol = 1.011 g/g, 11% above Xing (same direction: theobromine slightly
  weaker per mole). Stark 2006 Fig. 3 (digitized by eye, salicin-referenced 0-5 scale, 30 mM salicin = 5) has
  theobromine at 0.5x threshold 0, 1x 0.5, 2x 0.7, 4x 1.0, 8x 1.5, but no caffeine curve, so it cannot test the
  equal-DoT assumption.
  Solubility cap (v.2.8.3): Stark 2006 p. 5538: "theobromine reached its maximum solubility already at a
  concentration level of 8-fold above its threshold concentration" (bitterness 1.5 of 5 there), i.e.
  8 x 800 umol/kg = 6.4 mmol/kg = 0.1153 g per 100 g (TB_SOL_MAX_PCT). Theobromine above this cannot be in
  solution, so it is not tasted. Stark's dilution series went in 2-fold steps from the saturated solution, so
  the true limit lies between 8x and 16x; 8x is Stark's stated value. ASSUMPTION: Stark's room-temperature limit
  (sensory room 22-25 C) is also used for hot drinks, where more dissolves (flagged in a warning).

REBAUDIOSIDE A (v.2.8.3, replaces Antenucci 2015 bridged via Low 2017).
  Schiffman, Booth, Losee, Pecore & Warwick 1995, Brain Res Bull 36:505 ("schiffman1995b"), Table 1 (pp. 506-509):
  16 trained tasters, aqueous solutions, % w/v corrected for purity, 15 cm line scale whose bitterness anchors
  were caffeine 0.05% = 2 and 0.08% = 5 (Methods, p. 509) - the same caffeine references as Torrico's Table 1, on
  the same panel that rated the sweeteners. Verified from the page images.
    Reb A % (bitter): 0.007 (0.58), 0.01 (0.49), 0.0175 (0.77), 0.025 (0.69), 0.04375 (1.60), 0.0525 (1.10),
      0.0625 (1.55), 0.075 (2.12), 0.08125 (2.42), 0.1 (2.15), 0.12 (2.75), 0.15 (2.60)
  Non-bitter floor = mean bitterness of the 23 sucrose solutions in the same table (1.6-15%): 0.1170.
  Net rating r = rating - floor, fitted r = a * C^b by least squares in log-log (C in %): a 9.928, b 0.6769,
  R2 0.909, n 12 (exact values computed from the table at import).
  Rating -> caffeine (ASSUMPTION): log-log line through the two caffeine anchors, rating 0 at caffeine 0:
    C_caf = 0.05% * (r / 2)^(1/n_a), n_a = ln(5/2)/ln(0.08/0.05) = 1.9495
  then the Torrico caffeine curve (threshold ramp included). So Reb A crosses the caffeine threshold (r 0.451) at
  0.0104% (104 mg/L) and reads as 0.05% caffeine at ~0.096% (~0.96 g/L).
  Cross-checks: Hellfritsch et al. 2012 (J Agric Food Chem 60:6782, Table 2, >98% pure, n = 10 trained, triangle
  test, pH 6.0) Reb A bitter recognition threshold 194 umol/L = 0.0188% - same order as the Schiffman bridge
  (0.0104%); its bitterness scale is rubusoside-referenced (no caffeine), so it is a threshold check only. The
  v.2.8.2 Antenucci/Low bridge put the threshold at ~0.11% (5-10x higher than both); Allen 2013 (same lab as
  Antenucci) is ~2x lower than Antenucci, so the cross-study gLMS bridge was the outlier.
  Antenucci's ratings (and Schiffman's) are of Reb A alone, so its own sweetness is inside them: sugar masking of
  the Reb A part uses the sucrose-equivalents of the OTHER sweeteners only. Pure Reb A basis (Schiffman corrected
  for purity), so the DB's Reb A mg are used as is. Other steviol glycosides in low grades (stevioside, more
  bitter per Schiffman) are not credited.

ACESULFAME K (v.2.8.3). Schiffman 1995 Table 1, same panel and scale as Reb A.
  The printed concentration column (verified on the page image, p. 506) reads 0.007, 0.01, 0.015, 0.18, 0.25,
  0.35, 0.44, 0.5, 0.6, 0.625, 0.65, 0.76, 0.8, 0.11, 0.156 - not monotone with the sweetness ratings and
  inconsistent with the paper's own Table 2 potencies. ASSUMPTION (misprint correction): rows 4-13 are 10x too
  high (a lost zero): 0.018, 0.025, 0.035, 0.044, 0.05, 0.06, 0.0625, 0.065, 0.076, 0.08. Check: Table 2 gives
  potency 140 at 5% sucrose (5% sucrose-eq at 0.0357%), and the sweet rating is 4.89 at the corrected 0.035%;
  potency 204 at 2% (0.0098%) matches sweet 1.60 at 0.01%. Read literally, potency at 5% would be ~14.
    bitter ratings: 0.54, 0.80, 0.63, 0.53, 0.95, 0.78, 1.25, 1.30, 1.25, 1.92, 1.34, 1.91, 1.35, 1.81, 2.41
  Fit (same floor and method): a 5.893, b 0.5499, R2 0.825, n 15. Crosses the caffeine threshold at 0.0094%.
  Typical diet-soda level (~0.017%) reads ~0.6 Spectrum. Sugar masking uses the OTHER sweeteners only.
  Cross-check: Horne et al. 2002 (Chem Senses 27:31, Fig. 2, experiment 1, LMS, n = 38; digitized by eye, means of
  the 3 PROP groups): bitterness 1.2 mM ace-K ~5, 5.2 mM ace-K ~9, 0.4 mM saccharin ~5, 2.1 mM saccharin ~8 (LMS
  "weak" = 6). Same direction as the Schiffman fits (5.2 mM ace-K 1.70 vs 2.1 mM saccharin 1.24 net rating); no
  caffeine reference, so not used for the bridge. Horne also shows large individual differences (r = 0.84
  between saccharin and ace-K bitterness across people, unrelated to PROP status).

SACCHARIN (data ready, NOT wired: the DB has no saccharin column or row, and saccharin sweetness has no source in
  hfp_sweet.py). Schiffman 1995 Table 1, sodium saccharin % (bitter): 0.0035 (0.35), 0.00616 (0.65), 0.009 (0.43),
  0.0154 (1.01), 0.02 (1.08), 0.022 (0.83), 0.03 (1.32), 0.0385 (1.48), 0.04 (0.76), 0.05 (1.80), 0.055 (1.10),
  0.06 (2.03), 0.09625 (2.32). Fit: a 8.573, b 0.6132, R2 0.785 (SACC_TABLE below, for later).

SUPPRESSION (multipliers on intensity, each bitterant group; all on the whole-food basis from v.2.8.3):
    sodium on caffeine-type bitterness  S = 0.755 * Na / (Na + 0.194 M), Na capped at 0.5 M
        (Breslin & Beauchamp 1995 caffeine: 15/43/54% observed at 0.1/0.3/0.5 M vs 26/46/54% fitted).
        Also applied to theobromine, Reb A and acesulfame K (assumption: Breslin found Na suppresses most
        bitterants).
    sodium on KCl bitterness            S = 0.865 * Na / (Na + 0.023 M), fitted 0.05-0.2 M (Breslin 1995 Fig. 2E)
    sugar  S = SUG_SMAX * x^h / (x^h + SUG_X50^h), x = sucrose-equivalents in g per 100 g food (= % w/w).
        Calvino, Garcia-Medina & Cometto-Muniz 1990, Chem Senses 15:505, Table I: % suppression of caffeine
        bitterness by sucrose, magnitude estimation, n = 14, 37 C, caffeine 6/13/26/52 mM x sucrose 146/292/585 mM:
            146 mM: -, 46.5, -, -     292 mM: 65.9, 67.0, 33.3, 42.3     585 mM: 91.8, 64.3, 71.7, 54.8
        ("-" = not significant, entered as 0). Means over the 4 caffeine levels: 0.116, 0.521, 0.707 at
        4.93, 9.72, 18.93% w/w. Exact 3-point Hill fit: Smax 0.7288, h 3.8033, x50 7.6277%.
        Sensitivity: the 6 and 13 mM caffeine rows alone give Smax 0.793, h 3.71, x50 6.25%. Above 18.93% the
        curve is at its plateau (flagged; solid sweets such as chocolate sit there). Keast 2003 (Fig. 5) also
        found sucrose suppressed bitterness more than any bitter additive.
  Potassium does not suppress bitterness (Breslin 1995), so only sodium counts. KCl's own saltiness masking is
  already inside the Torrico curve.
"""
import math

CAF_K, CAF_N = 52.5, 0.87
KCL_K, KCL_N = 4.37, 0.68
CAF_THRESHOLD_PCT = 0.0233           # 1.2 mM (Keast & Roper 2007)
CAF_FIT_MIN, CAF_FIT_MAX = 0.05, 0.15
KCL_FIT_MIN, KCL_FIT_MAX = 0.5, 1.5
NA_CAP_M = 0.5
BITTER_REF = 10.0                    # Spectrum 10 on Torrico's panel scale (= 0.149% caffeine on their power fit)
KCL_PER_K = 74.551 / 39.098          # g KCl per g K
CAF_MW = 194.19

# Theobromine (Xing 2024 Table S2, 25 C recognition thresholds; threshold-ratio potency, an assumption)
TB_THR_UM, CAF_THR_UM_XING = 685.08, 578.86
TB_CAF_EQ = CAF_THR_UM_XING / TB_THR_UM * 194.19 / 180.16     # = 0.9108 g caffeine-eq per g theobromine
TB_FIT_MIN_PCT, TB_FIT_MAX_PCT = 0.75e-3 * 180.16 / 10, 1.75e-3 * 180.16 / 10   # Xing tested 0.75-1.75 mM
# Solubility cap (Stark 2006 p. 5538: max solubility at 8x the 800 umol/kg threshold of Table 1)
TB_SOL_MAX_PCT = 8 * 800e-6 * 180.16 / 10                    # = 0.11530 g per 100 g

# Schiffman 1995 (Brain Res Bull 36:505) Table 1: caffeine-anchored line scale (0.05% = 2, 0.08% = 5)
SCH_ANCHORS = ((2.0, 0.05), (5.0, 0.08))                      # (rating, caffeine % w/v)
SCH_N = math.log(SCH_ANCHORS[1][0] / SCH_ANCHORS[0][0]) / math.log(SCH_ANCHORS[1][1] / SCH_ANCHORS[0][1])
SCH_SUCROSE_BITTER = [0.38, 0.22, 0.23, 0.07, 0.36, 0.10, 0.10, 0.20, 0.02, 0.25, 0.30, 0.00, 0.06, 0.15, 0.03,
                      0.00, 0.05, 0.00, 0.06, 0.01, 0.00, 0.05, 0.05]          # sucrose 1.6-15%, 23 rows
SCH_FLOOR = sum(SCH_SUCROSE_BITTER) / len(SCH_SUCROSE_BITTER)               # = 0.1170
REBA_TABLE = [(0.007, 0.58), (0.01, 0.49), (0.0175, 0.77), (0.025, 0.69), (0.04375, 1.60), (0.0525, 1.10),
              (0.0625, 1.55), (0.075, 2.12), (0.08125, 2.42), (0.1, 2.15), (0.12, 2.75), (0.15, 2.60)]
# acesulfame K: rows 4-13 misprint-corrected (x0.1), see docstring
ACEK_TABLE = [(0.007, 0.54), (0.01, 0.80), (0.015, 0.63), (0.018, 0.53), (0.025, 0.95), (0.035, 0.78),
              (0.044, 1.25), (0.05, 1.30), (0.06, 1.25), (0.0625, 1.92), (0.065, 1.34), (0.076, 1.91),
              (0.08, 1.35), (0.11, 1.81), (0.156, 2.41)]
SACC_TABLE = [(0.0035, 0.35), (0.00616, 0.65), (0.009, 0.43), (0.0154, 1.01), (0.02, 1.08), (0.022, 0.83),
              (0.03, 1.32), (0.0385, 1.48), (0.04, 0.76), (0.05, 1.80), (0.055, 1.10), (0.06, 2.03),
              (0.09625, 2.32)]                                               # wired in v.2.9.0


def _fit_power(table, floor):
    """Least-squares fit of ln(rating - floor) = ln a + b ln C over rows with rating > floor."""
    pts = [(math.log(c), math.log(r - floor)) for c, r in table if r > floor]
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    b = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)
    return math.exp(my - b * mx), b


REBA_A, REBA_B = _fit_power(REBA_TABLE, SCH_FLOOR)      # 9.928, 0.6769
ACEK_A, ACEK_B = _fit_power(ACEK_TABLE, SCH_FLOOR)      # 5.893, 0.5499
SACC_A, SACC_B = _fit_power(SACC_TABLE, SCH_FLOOR)      # 8.574, 0.6133 (v.2.9.0)
REBA_MAX_PCT, ACEK_MAX_PCT, SACC_MAX_PCT = REBA_TABLE[-1][0], ACEK_TABLE[-1][0], SACC_TABLE[-1][0]

# Sugar suppression (Calvino 1990 Table I, exact Hill fit)
SUG_SMAX, SUG_H, SUG_X50 = 0.7288, 3.8033, 7.6277
SUG_FIT_MAX_PCT = 18.93


def caffeine_intensity(c_pct):
    if c_pct < CAF_THRESHOLD_PCT:
        return 0.0
    if c_pct < CAF_FIT_MIN:
        b_min = CAF_K * CAF_FIT_MIN ** CAF_N
        return b_min * (c_pct - CAF_THRESHOLD_PCT) / (CAF_FIT_MIN - CAF_THRESHOLD_PCT)
    return CAF_K * c_pct ** CAF_N


def kcl_intensity(c_pct):
    return KCL_K * c_pct ** KCL_N if c_pct > 0 else 0.0


def caffeine_equivalent(b):
    """Caffeine % w/v giving bitterness b on the power curve."""
    return (b / CAF_K) ** (1 / CAF_N) if b > 0 else 0.0


def schiffman_caffeine_pct(rating):
    """Caffeine % iso-bitter to a net Schiffman 1995 rating (log-log through the two caffeine anchors)."""
    if rating <= 0:
        return 0.0
    r0, c0 = SCH_ANCHORS[0]
    return c0 * (rating / r0) ** (1 / SCH_N)


def reba_caffeine_eq_pct(reba_pct):
    """Iso-bitter caffeine % for Reb A at reba_pct (g per 100 g food)."""
    return schiffman_caffeine_pct(REBA_A * reba_pct ** REBA_B) if reba_pct > 0 else 0.0


def acek_caffeine_eq_pct(acek_pct):
    """Iso-bitter caffeine % for acesulfame K at acek_pct (g per 100 g food)."""
    return schiffman_caffeine_pct(ACEK_A * acek_pct ** ACEK_B) if acek_pct > 0 else 0.0


def na_suppression_caffeine(na_m):
    na = min(max(na_m, 0.0), NA_CAP_M)
    return 0.755 * na / (na + 0.194)


def na_suppression_kcl(na_m):
    na = min(max(na_m, 0.0), NA_CAP_M)
    return 0.865 * na / (na + 0.023)


def sugar_suppression(sucrose_eq_pct):
    x = max(sucrose_eq_pct, 0.0)
    if x <= 0:
        return 0.0
    return SUG_SMAX * x ** SUG_H / (x ** SUG_H + SUG_X50 ** SUG_H)


def sacc_caffeine_eq_pct(sacc_pct):
    """Iso-bitter caffeine % for sodium saccharin at sacc_pct (g per 100 g food). v.2.9.0."""
    return schiffman_caffeine_pct(SACC_A * sacc_pct ** SACC_B) if sacc_pct > 0 else 0.0


def bitterness(caf_pct, kcl_pct, na_m, sucrose_eq_pct, tb_pct=0.0, reba_pct=0.0, acek_pct=0.0,
               sucrose_eq_pct_reba=None, sucrose_eq_pct_acek=None, sacc_pct=0.0, sucrose_eq_pct_sacc=None):
    """Returns (intensity on the Spectrum scale, details dict, warnings list).
    All concentrations are g per 100 g FOOD (whole-food basis, v.2.8.3); na_m is mol per kg food.
    sucrose_eq_pct_reba / _acek: sucrose-eq % w/w excluding that sweetener's own sweetness; None = same."""
    warn = []
    if sucrose_eq_pct_reba is None:
        sucrose_eq_pct_reba = sucrose_eq_pct
    if sucrose_eq_pct_acek is None:
        sucrose_eq_pct_acek = sucrose_eq_pct
    if sucrose_eq_pct_sacc is None:
        sucrose_eq_pct_sacc = sucrose_eq_pct
    s_na_c, s_na_k = na_suppression_caffeine(na_m), na_suppression_kcl(na_m)
    s_sug = sugar_suppression(sucrose_eq_pct)
    s_sug_r, s_sug_a = sugar_suppression(sucrose_eq_pct_reba), sugar_suppression(sucrose_eq_pct_acek)
    tb_eff = min(tb_pct, TB_SOL_MAX_PCT)
    c_xan = caf_pct + TB_CAF_EQ * tb_eff
    c_reba, c_acek = reba_caffeine_eq_pct(reba_pct), acek_caffeine_eq_pct(acek_pct)
    b_x = caffeine_intensity(c_xan) * (1 - s_na_c) * (1 - s_sug)
    b_k = kcl_intensity(kcl_pct) * (1 - s_na_k) * (1 - s_sug)
    b_r = caffeine_intensity(c_reba) * (1 - s_na_c) * (1 - s_sug_r)
    b_a = caffeine_intensity(c_acek) * (1 - s_na_c) * (1 - s_sug_a)
    s_sug_s = sugar_suppression(sucrose_eq_pct_sacc)
    c_sacc = sacc_caffeine_eq_pct(sacc_pct)
    b_s = caffeine_intensity(c_sacc) * (1 - s_na_c) * (1 - s_sug_s)
    ceq = (caffeine_equivalent(b_x) + caffeine_equivalent(b_k) + caffeine_equivalent(b_r) + caffeine_equivalent(b_a)
           + caffeine_equivalent(b_s))
    b_final = CAF_K * ceq ** CAF_N if ceq > 0 else 0.0
    if c_xan > CAF_FIT_MAX:
        warn.append(f"Caffeine-equivalent {c_xan:.3f}% is above the measured range (0.15%); bitterness is extrapolated.")
    if kcl_pct > KCL_FIT_MAX:
        warn.append(f"KCl {kcl_pct:.2f}% is above the measured range (1.5%); bitterness is extrapolated.")
    if 0 < kcl_pct < KCL_FIT_MIN:
        warn.append(f"KCl {kcl_pct:.2f}% is below the measured range (0.5%); its bitterness is a low-confidence "
                    f"extrapolation (people differ widely in KCl bitterness).")
    if na_m > NA_CAP_M:
        warn.append("Sodium is above 0.5 M; bitterness suppression by sodium is held at its 0.5 M value.")
    if tb_pct > 0:
        warn.append("Theobromine counted as 0.91 g caffeine per g (equal-threshold assumption, Xing 2024)"
                    + (f"; only {TB_SOL_MAX_PCT:.3f}% can dissolve (Stark 2006, room temperature), so the rest "
                       f"({tb_pct - TB_SOL_MAX_PCT:.3f}%) is not tasted; hot drinks may dissolve more."
                       if tb_pct > TB_SOL_MAX_PCT else "."))
    if reba_pct > REBA_MAX_PCT:
        warn.append(f"Reb A {reba_pct:.3f}% is above the tested range (0.15%, Schiffman 1995); "
                    f"its bitterness is extrapolated.")
    if acek_pct > ACEK_MAX_PCT:
        warn.append(f"Acesulfame K {acek_pct:.3f}% is above the tested range (0.156%, Schiffman 1995); "
                    f"its bitterness is extrapolated.")
    if sacc_pct > SACC_MAX_PCT:
        warn.append(f"Saccharin {sacc_pct:.3f}% is above the tested range (0.096%, Schiffman 1995); "
                    f"its bitterness is extrapolated.")
    if b_final > 0 and max(sucrose_eq_pct, sucrose_eq_pct_reba, sucrose_eq_pct_acek, sucrose_eq_pct_sacc) > SUG_FIT_MAX_PCT:
        warn.append("Sugar is above the tested range for bitterness masking (19% sucrose, Calvino 1990); "
                    "suppression is near its plateau.")
    return b_final, {"basis": "g per 100 g food", "caffeine_pct": caf_pct, "theobromine_pct": tb_pct,
                     "theobromine_dissolved_pct": tb_eff, "xanthine_caffeine_eq_pct": c_xan,
                     "reba_pct": reba_pct, "reba_caffeine_eq_pct": c_reba,
                     "acek_pct": acek_pct, "acek_caffeine_eq_pct": c_acek, "kcl_pct": kcl_pct,
                     "bitter_xanthines": b_x, "bitter_kcl": b_k, "bitter_reba": b_r, "bitter_acek": b_a,
                     "sacc_pct": sacc_pct, "sacc_caffeine_eq_pct": c_sacc, "bitter_saccharin": b_s,
                     "caffeine_eq_pct": ceq, "sucrose_eq_pct": sucrose_eq_pct, "sugar_suppression": s_sug,
                     "sugar_suppression_reba": s_sug_r, "sugar_suppression_acek": s_sug_a,
                     "na_molal_food": na_m, "na_suppression_caffeine": s_na_c, "na_suppression_kcl": s_na_k}, warn


if __name__ == "__main__":
    print("floor", SCH_FLOOR, "n_anchor", SCH_N)
    print("RebA", repr(REBA_A), repr(REBA_B), "AceK", repr(ACEK_A), repr(ACEK_B), "TB cap", repr(TB_SOL_MAX_PCT))
    print("SACC fit", _fit_power(SACC_TABLE, SCH_FLOOR))
