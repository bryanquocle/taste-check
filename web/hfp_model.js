/* HFP taste model, browser port of hfp_model.py + hfp_acidbase.py + hfp_sweet.py (v.2.10.0).
   Same equations, constants and defaults as the Python model (acidity on, chloride-only K, shift mode,
   synergy capped at 63x, v.2.8.4). hfp_model.py is the source of truth: change it first, then mirror the change here.
   Parity-tested against Python with tests/web_parity.py (Node), raw values and 1-10 scores. Needs window.HFP_DB. */
(function (G) {
  "use strict";
  const LN = Math.log, POW = Math.pow;

  // ---------------- database ----------------
  const DB = {}, NAMES = [];
  function loadDB(raw) {
    for (const [name, vals, ph, blank, tier] of raw.items) {
      const d = {};
      raw.fields.forEach((f, i) => (d[f] = vals[i] || 0));
      d.ph_ref = ph == null ? null : ph;
      d._blank = new Set(blank);
      d._tier = tier || {};
      DB[name] = d;
      NAMES.push(name);
    }
  }

  // ---------------- acid-base (hfp_acidbase.py) ----------------
  const KW = 1e-14;
  const ORGANIC_ACIDS = {
    citric: [192.12, [3.13, 4.76, 6.40], [3.13, 4.76, 6.40]],
    malic: [134.09, [3.40, 5.11], [3.40, 5.11]],
    tartaric: [150.09, [2.98, 4.34], [2.98, 4.34]],
    lactic: [90.08, [3.86], [3.86]],
    acetic: [60.05, [4.76], [4.76]],
    ascorbic: [176.12, [4.10, 11.6], [4.10]],
    oxalic: [90.03, [1.25, 4.14], [1.25, 4.14]],
    quinic: [192.17, [3.46], [3.46]],
    malonic: [104.06, [2.83, 5.69], [2.83, 5.69]],
    fumaric: [116.07, [3.03, 4.44], [3.03, 4.44]],
    succinic: [118.09, [4.21, 5.64], [4.21, 5.64]],
    pyroglutamic: [129.11, [3.32], [3.32]],
    formic: [46.03, [3.75], [3.75]],
  };
  const AMINO = { glu: [147.13, [2.19, 4.25, 9.67]], asp: [133.10, [1.99, 3.90, 9.90]] };
  const NUCLEOTIDE_MW = { amp: 347.22, imp: 348.21, gmp: 363.22 };
  const NUCLEOTIDE_PKA2 = 6.2;
  const PROTEIN_GROUPS = [[-1, 1.00, 4.2], [+1, 0.20, 6.3], [+1, 0.90, 10.5]];
  const CHLORIDE_SALTS = new Set(["Salt", "Kosher Salt", "Sea Salt", "Table Salt", "Canning Salt", "Pickling Salt",
    "Iodized Salt", "Celtic Salt", "Himalayan Salt", "Pink Salt", "Sodium Chloride", "Potassium Chloride", "Salt Substitute"]);
  const DEFAULT_PH = 6.0;

  function fractions(pkas, h) {
    const terms = [1.0];
    for (const pka of pkas) terms.push(terms[terms.length - 1] * POW(10, -pka) / h);
    let tot = 0; for (const t of terms) tot += t;
    return terms.map(t => t / tot);
  }
  function chargeMolPerL(sp, h) {
    let q = (sp.na || 0) + (sp.k || 0) - (sp.cl || 0);
    for (const name in ORGANIC_ACIDS) {
      const c = sp[name] || 0;
      if (c) { const a = fractions(ORGANIC_ACIDS[name][1], h); let s = 0; a.forEach((ak, k) => (s += k * ak)); q -= c * s; }
    }
    for (const name in AMINO) {
      const c = sp[name] || 0;
      if (c) { const a = fractions(AMINO[name][1], h); let s = 0; a.forEach((ak, k) => (s += (1 - k) * ak)); q += c * s; }
    }
    const nuc = sp.nuc || 0;
    if (nuc) q -= nuc * (1 + fractions([NUCLEOTIDE_PKA2], h)[1]);
    const prot = sp.protein_g || 0;
    if (prot) for (const [z, mmolG, pka] of PROTEIN_GROUPS) {
      const de = fractions([pka], h)[1], c = prot * mmolG / 1000;
      q += c * (z < 0 ? -de : (1 - de));
    }
    return q;
  }
  function solvePH(sp, z) {
    z = z || 0; let lo = 0, hi = 14;
    const f = ph => POW(10, -ph) - KW / POW(10, -ph) + chargeMolPerL(sp, POW(10, -ph)) + z;
    for (let i = 0; i < 80; i++) { const mid = (lo + hi) / 2; if (f(mid) > 0) lo = mid; else hi = mid; }
    return (lo + hi) / 2;
  }
  function sourStimulus_mM(sp, ph) {
    const h = POW(10, -ph); let s = h * 1000;
    for (const name in ORGANIC_ACIDS) {
      const c = sp[name] || 0;
      if (c) { const a = fractions(ORGANIC_ACIDS[name][2], h); s += c * (1 - a[a.length - 1]) * 1000; }
    }
    return s;
  }
  function speciesFromComposition(d, massG, name) {
    const f = massG / 100, sp = {};
    for (const n in ORGANIC_ACIDS) { const v = d["acid_" + n] || 0; if (v) sp[n] = v * f / ORGANIC_ACIDS[n][0]; }
    for (const n in AMINO) if (d[n]) sp[n] = d[n] * f / AMINO[n][0];
    let nuc = 0; for (const n in NUCLEOTIDE_MW) nuc += (d[n] || 0) * f / NUCLEOTIDE_MW[n];
    if (nuc) sp.nuc = nuc;
    sp.na = (d.na || 0) * f / 22.99;
    sp.k = (d.k || 0) * f / 39.0983;
    if (CHLORIDE_SALTS.has(name)) sp.cl = sp.na + sp.k;
    sp.protein_g = (d.protein || 0) * f;
    return sp;
  }
  function toMolar(spMmol, waterL) {
    const out = {};
    for (const k in spMmol) out[k] = k === "protein_g" ? spMmol[k] / waterL : spMmol[k] / 1000 / waterL;
    return out;
  }
  function calibrateZ(d, name, massG, waterG, spMmol) {
    let ref = d.ph_ref, flag = "reference";
    const spRaw = spMmol || speciesFromComposition(d, massG, name);
    const charged = Object.keys(spRaw).some(k => k !== "cl" && spRaw[k]) && !CHLORIDE_SALTS.has(name);
    if (!ref) { if (!charged) return [0, null, "none"]; ref = DEFAULT_PH; flag = "default"; }
    const wL = Math.max(waterG, massG) / 1000;
    const sp = toMolar(spRaw, wL), h = POW(10, -ref);
    const q = h - KW / h + chargeMolPerL(sp, h);
    return [-q * wL * 1000, ref, flag];
  }
  const MIRANDA_CITRIC = [0.0, 1.25, 6.25, 31.25];
  const MIRANDA_REM = [1.0, 1 - 2.886 / 39.756, 1 - 7.211 / 39.756, 1 - 20.654 / 39.756];
  function mirandaSolution(citric) {
    const sp = { glu: 50 / 1000, na: 50 / 1000, citric: citric / 1000 };
    const ph = solvePH(sp); return [ph, sourStimulus_mM(sp, ph)];
  }
  const MIR_PTS = MIRANDA_CITRIC.map(mirandaSolution);
  let S50, HILL;
  (function fit() {
    const s = MIR_PTS.map(p => p[1]); let best = null;
    for (let x = 5; x < 400; x++) {
      const s50 = x / 10;
      for (let y = 10; y < 200; y++) {
        const hh = y / 50; let err = 0;
        for (let i = 1; i < 4; i++) err += POW(1 / (1 + POW(s[i] / s50, hh)) - MIRANDA_REM[i], 2);
        if (best === null || err < best[0]) best = [err, s50, hh];
      }
    }
    S50 = best[1]; HILL = best[2];
  })();
  const MIRANDA_S_MAX = MIR_PTS[3][1];
  const umamiRemaining = s => (s <= 0 ? 1.0 : 1 / (1 + POW(s / S50, HILL)));
  function citricEquivalent_mM(s) {
    let lo = 0, hi = 2000;
    for (let i = 0; i < 60; i++) { const mid = (lo + hi) / 2; if (mirandaSolution(mid)[1] < s) lo = mid; else hi = mid; }
    return (lo + hi) / 2;
  }
  const TART_ALPHA = 14.45, TART_BETA = 0.00296, TART_THR = 0.00094, TART_MW = 150.09;
  function acidInWaterStimulus(acid, c) { const sp = {}; sp[acid] = c / 1000; return sourStimulus_mM(sp, solvePH(sp)); }
  function tartaricEquivalentG(s) {
    if (s <= 0) return 0;
    let lo = 0, hi = 5000;
    for (let i = 0; i < 60; i++) { const mid = (lo + hi) / 2; if (acidInWaterStimulus("tartaric", mid) < s) lo = mid; else hi = mid; }
    return (lo + hi) / 2 * TART_MW / 10000;
  }
  function sournessIntensity(s) {
    const x = tartaricEquivalentG(s);
    if (x < TART_THR) return 0;
    return Math.max(0, TART_ALPHA * Math.log2(x / TART_BETA));
  }
  const SYN = [[6.5, 1.0], [7.5, 0.535], [8.5, 0.341], [9.5, 0.070]];
  function synergyPHFactor(ph) {
    if (ph <= SYN[0][0]) return 1.0;
    if (ph >= SYN[3][0]) return SYN[3][1];
    for (let i = 0; i < 3; i++) {
      const [x0, y0] = SYN[i], [x1, y1] = SYN[i + 1];
      if (x0 <= ph && ph <= x1) return y0 + (y1 - y0) * (ph - x0) / (x1 - x0);
    }
    return 1.0;
  }

  // ---------------- sweetness (hfp_sweet.py) ----------------
  const EXPONENT = 1.3, K_SUCROSE = 0.54;
  const RS = { sucrose: 1.00, fructose: 0.91, glucose: 0.45, galactose: 0.42, glycerol: 0.50,
    arabinose: 0.39, xylose: 0.26, maltose: 0.31, lactose: 0.22,
    // v.2.6.3: polyols from Wee et al. 2018 Table 4 potency at 10% sucrose, stored as potency^1.3 (see hfp_sweet.py)
    sorbitol: Math.pow(0.72, 1.3), mannitol: Math.pow(0.68, 1.3), erythritol: Math.pow(0.75, 1.3),
    xylitol: Math.pow(1.01, 1.3),
    // v.2.7.1: allulose and maltitol (Wee 2018 Table 4 at 10% sucrose)
    allulose: Math.pow(0.75, 1.3), maltitol: Math.pow(0.89, 1.3) };
  const SUGARS = ["sucrose", "glucose", "fructose", "lactose", "galactose", "maltose", "maltotriose", "uronic",
    "arabinose", "xylose", "mannose", "glycerol", "sorbitol", "erythritol", "xylitol", "mannitol",
    "allulose", "maltitol", "reb_a", "mogroside_v", "sucralose", "aspartame", "ace_k", "saccharin"];
  // v.2.7.0 high-intensity sweeteners (Wee 2018 Table 4 equi-sweet points; see hfp_sweet.py)
  const WEE_LEVELS = [5.0, 10.0, 15.0], WEE_SUC_N = 1.31;
  const HIS = {
    reb_a: ["Stevia (rebaudioside A)", 0.680, 0.71, [0.0144, 0.0395, 0.0828]],
    mogroside_v: ["Monk fruit (mogroside V)", 0.506, 0.70, [0.0191, 0.0694, 0.141]],
    sucralose: ["Sucralose", 1.0, 0.65, [0.0096, 0.0387, 0.0748]],
    aspartame: ["Aspartame", 1.0, 0.84, [0.0290, 0.0827, 0.134]],
    ace_k: ["Acesulfame K", 1.0, 0.68, [0.0293, 0.0832, 0.170]],
    // v.2.9.0 saccharin: Schiffman 1995 Table 2 equi-sweet points at 2/5/10% sucrose; capped at 9% (hfp_sweet.py)
    saccharin: ["Saccharin", 1.0, 0.868 * 1.31, [0.00392, 0.01126, 0.0405]] };
  const HIS_LEVELS = { saccharin: [2.0, 5.0, 10.0] }, HIS_CAP = { saccharin: 9.0 };
  function hisSucroseEq(key, g) {
    const [, purity, n, xs] = HIS[key], ys = HIS_LEVELS[key] || WEE_LEVELS, c = g / purity, cap = HIS_CAP[key];
    if (c <= 0) return [0, false];
    let v, high = false;
    if (c < xs[0]) v = ys[0] * POW(c / xs[0], n / WEE_SUC_N);
    else if (c > xs[xs.length - 1]) { v = ys[ys.length - 1]; high = true; }
    else {
      v = ys[ys.length - 1];
      for (let i = 0; i < xs.length - 1; i++) {
        if (c <= xs[i + 1]) { const t = (LN(c) - LN(xs[i])) / (LN(xs[i + 1]) - LN(xs[i])); v = Math.exp(LN(ys[i]) + t * (LN(ys[i + 1]) - LN(ys[i]))); break; }
      }
    }
    if (cap != null && v >= cap) return [cap, true];
    return [v, high];
  }
  const SUCROSE_THR = 0.086, MOSK_MAX = 32.0;
  const SF_SUC_M = [0.125, 0.25, 0.5, 1.0], SF_SUC_G = [4.40, 9.06, 19.2, 43.6], SF_CIT = [1.25, 2.5, 5.0, 10.0];
  const SF_SWEET_UNMIXED = [24, 45, 79, 111];
  const SF_SWEET_MIX = { 1.25: [19.5, 38, 67, 103], 2.5: [19.5, 38, 70, 95], 5: [15, 36.5, 65, 95], 10: [11.5, 28.5, 63.5, 95] };
  const SF_SOUR_UNMIXED = [27, 50, 79, 105], SF_SOUR_MIX10 = [77, 62, 51, 35];
  function invert(y, xs, ys) {
    const pts = [[0, 0]].concat(xs.map((x, i) => [x, ys[i]]));
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
      if (y <= y1) return x0 + (x1 - x0) * (y - y0) / (y1 - y0);
    }
    return xs[xs.length - 1];
  }
  const SWEET_Q = [[0, 1]].concat(SF_CIT.map(c => {
    let s = 0; SF_SWEET_MIX[c].forEach((v, i) => (s += invert(v, SF_SUC_M, SF_SWEET_UNMIXED) / SF_SUC_M[i]));
    return [c, s / 4];
  }));
  const SOUR_PTS = SF_SUC_G.map((x, i) => [x, invert(SF_SOUR_MIX10[i], SF_CIT, SF_SOUR_UNMIXED) / 10]);
  function sucroseEquivalent(sug) {
    let eq = 0; const uns = [];
    for (const s of SUGARS) { const g = sug[s]; if (g <= 0) continue; if (s in HIS) eq += hisSucroseEq(s, g)[0]; else if (s in RS) eq += POW(RS[s], 1 / EXPONENT) * g; else uns.push(s); }
    return [eq, uns];
  }
  const pctWW = (g, tot) => 100 * g / (100 + tot);
  const sweetness = c => (c < SUCROSE_THR ? 0 : K_SUCROSE * POW(c, EXPONENT));
  function sweetQ(cit) {
    const c = Math.min(Math.max(cit, 0), SWEET_Q[SWEET_Q.length - 1][0]);
    for (let i = 0; i < SWEET_Q.length - 1; i++) {
      const [x0, y0] = SWEET_Q[i], [x1, y1] = SWEET_Q[i + 1];
      if (x0 <= c && c <= x1) return y0 + (y1 - y0) * (c - x0) / (x1 - x0);
    }
    return SWEET_Q[SWEET_Q.length - 1][1];
  }
  function sourRemaining(x) {
    x = Math.max(x, 0); const pts = [[0, 1]].concat(SOUR_PTS);
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
      if (x <= x1) return y0 + (y1 - y0) * (x - x0) / (x1 - x0);
    }
    return pts[pts.length - 1][1];
  }

  // ---------------- model (hfp_model.py) ----------------
  const MASS_UNITS = { g: 1, kg: 1000, oz: 28.35, lb: 453.59 };
  const VOLUME_UNITS = { ml: 1, l: 1000, "fl oz": 29.57, cup: 236.59, pt: 473.18, qt: 946.35, gal: 3785.41, tsp: 4.93, tbsp: 14.79 };
  const CHLORIDE_K = new Set(["Potassium Chloride", "Salt Substitute", "Celtic Salt", "Himalayan Salt", "Pink Salt", "Sea Salt"]);
  const SALT_FORM = { glu: 187.13 / 147.13, asp: 173.10 / 133.10, imp: 527.28 / 348.21, gmp: 533.29 / 363.22, amp: 391.18 / 347.22 };
  const GLU_THR_DROP_MAX = 0.012 / 0.00019, GLU_THR_AT_IMP = 5.0, NUC_W = { amp: 0.18, gmp: 2.3 };
  const TASTE_BASIS = "food"; // v.2.8.5
  const KOK_THR_PTS = [[0.05, 0.04], [0.8, 0.02], [3.1, 0.01]]; // Ueda 1997 Table II (v.2.9.0 kokumi floor)
  const NUC_THR_IMP = 0.387 * 348.21 / 1e4, NUC_THR_GMP = 0.206 * 363.22 / 1e4; // Kuninaka 1980 Table I (v.2.9.0)
  const SYNERGY_MAX_FOLD = 63, SALT_SHIFT_MAX = 2.0, DOG_R_PEAK = 0.5828;
  const KOKUMI_POT = { gsh: 1.0, evg: 12.8, cys: 1.0 }, KOK_EC50 = 0.9122, KOK_N = 1.456; // ASSUMPTION: sensory curve on mouth mM, not a receptor EC50 (hfp_model.py)
  const KOK_UMAMI_GAIN = 0.41, KOK_SALT_GAIN = 0.41;
  const UMAMI_SALT_EMAX = 0.10, UMAMI_SALT_S_FULL = 2.4, UMAMI_SALT_FADE_MM = [75, 260]; // Sun 2022 (v.2.8.1)
  const COOKED_NUC = { "Asparagus (Fresh)": [0.972, 0.436], "Green Pepper": [2.049, 1.562], "Broccoli": [1.493, 1.271],
    "Cabbage": [0.451, 0.0], "Cauliflower": [0.833, 3.015], "Mushroom, Button": [11.736, 4.431],
    "Mushroom, Champignon": [11.736, 4.431], "Sweet Potato": [4.41, 1.126], "Potato": [1.042, 0.799],
    "Radish": [0.764, 0.182], "Mushroom, Shiitake (Fresh)": [8.214, 14.019],
    // v.2.9.0 Horie 2012 steamed GMP; null AMP = keep the raw AMP (hfp_model.py)
    "Eggplant": [null, 1.70], "Carrot": [null, 0.34], "Daikon": [null, 0.14], "Onion, Welsh": [null, 0.21], "Spinach": [null, 0.76] };
  const MIN_SHARE = 0.01, ACIDS_BELOW_PH = 5.5, NUC_FLAG_GLU = 100;
  // Umami 10/10 (Nov 15, 2026, Bryan): 5 g/dL MSG-eq with the salt shift and kokumi gain at their maximum
  // (= 29.61; was the bare curve at 5 g/dL, 18.46). Mirrors UMAMI_REF_WITH_BOOSTS in hfp_model.py.
  const SCORE_REF = { bitter: 10, umami: (3.6672 * LN(5.0 * SALT_SHIFT_MAX) + 12.555) * (1 + KOK_UMAMI_GAIN), salt: 2.7036 * LN(0.5) + 12.008, sweet: 0.54 * POW(10, 1.3),
    kokumi: 100, sour: sournessIntensity(acidInWaterStimulus("citric", 50.0 / 192.12 * 1000)) };
  const toScore = (raw, key) => 1 + 9 * Math.min(1, Math.max(0, raw) / SCORE_REF[key]);
  function cysThermalFraction(min, temp) {
    if (!min || temp == null) return 1.0;
    const k = 4.38e17 * Math.exp(-142494.0 / (8.314 * (temp + 273.15)));
    return Math.exp(-k * min);
  }
  const KEYS = ["glu", "asp", "amp", "imp", "gmp", "na", "k", "gsh", "cys", "evg", "caf", "tb"];

  // ---------------- bitterness (hfp_bitter.py, v.2.8.3): caffeine + theobromine, KCl, Reb A, acesulfame K ----------------
  // v.2.8.3: WHOLE-FOOD basis (per 100 g food, Stark 2006 DoT convention), theobromine solubility cap (Stark 2006)
  const CAF_K = 52.5, CAF_N = 0.87, KCL_K = 4.37, KCL_N = 0.68, CAF_THR = 0.0233, CAF_MIN = 0.05, CAF_MAX = 0.15;
  const KCL_MIN = 0.5, KCL_MAX = 1.5, NA_CAP = 0.5, KCL_PER_K = 74.551 / 39.098;
  const cafInt = c => (c < CAF_THR ? 0 : c < CAF_MIN ? CAF_K * POW(CAF_MIN, CAF_N) * (c - CAF_THR) / (CAF_MIN - CAF_THR) : CAF_K * POW(c, CAF_N));
  const kclInt = c => (c > 0 ? KCL_K * POW(c, KCL_N) : 0);
  const cafEq = b => (b > 0 ? POW(b / CAF_K, 1 / CAF_N) : 0);
  const sNaCaf = na => { const x = Math.min(Math.max(na, 0), NA_CAP); return 0.755 * x / (x + 0.194); };
  const sNaKcl = na => { const x = Math.min(Math.max(na, 0), NA_CAP); return 0.865 * x / (x + 0.023); };
  // sugar masking from Calvino 1990 Table I (Hill fit), theobromine by threshold ratio (Xing 2024)
  const SUG_SMAX = 0.7288, SUG_H = 3.8033, SUG_X50 = 7.6277, SUG_FIT_MAX = 18.93;
  const sSugar = x => { x = Math.max(x, 0); return x <= 0 ? 0 : SUG_SMAX * POW(x, SUG_H) / (POW(x, SUG_H) + POW(SUG_X50, SUG_H)); };
  const TB_CAF_EQ = 578.86 / 685.08 * 194.19 / 180.16;
  const TB_SOL_MAX = 8 * 800e-6 * 180.16 / 10;           // Stark 2006: saturated at 8x the 800 umol/kg threshold
  // Reb A and acesulfame K: Schiffman 1995 Table 1 power fits (net of the sucrose floor), caffeine-anchored scale
  // (0.05% = 2, 0.08% = 5); constants = hfp_bitter.py REBA_A/B, ACEK_A/B (fitted there from the table)
  const SCH_N = LN(5.0 / 2.0) / LN(0.08 / 0.05);
  const REBA_A = 9.928380940042402, REBA_B = 0.6768788634937082, REBA_MAX = 0.15;
  const ACEK_A = 5.8931225453905265, ACEK_B = 0.5499448249760767, ACEK_MAX = 0.156;
  const SACC_A = 8.573335360776412, SACC_B = 0.6132138096664971, SACC_MAX = 0.09625; // v.2.9.0 (hfp_bitter.py SACC_A/B)
  const schCaf = r => (r <= 0 ? 0 : 0.05 * POW(r / 2.0, 1 / SCH_N));
  const rebaCafEq = pct => (pct > 0 ? schCaf(REBA_A * POW(pct, REBA_B)) : 0);
  const acekCafEq = pct => (pct > 0 ? schCaf(ACEK_A * POW(pct, ACEK_B)) : 0);
  const saccCafEq = pct => (pct > 0 ? schCaf(SACC_A * POW(pct, SACC_B)) : 0);
  const PROTEIN_BITTER_RE = /hydroly[sz]|isolate|protein powder|whey protein|pea protein|soy protein|casein/i;

  function compute(recipe, opt) {
    opt = opt || {};
    const waterLoss = opt.water_loss_g || 0, cookMin = opt.cook_min || 0, cookTemp = opt.cook_temp_c == null ? null : opt.cook_temp_c;
    const acidity = opt.acidity !== false, kSource = opt.k_source || "chloride";
    const notes = [], rows = [], phDefaults = [];
    const abSp = {}; let abZ = 0;
    const note = (key, text, data) => notes.push({ key, text, data });
    if (cookTemp != null && (cookMin || recipe.some(i => "cook_min" in i))) {
      if (!(cookTemp >= 60 && cookTemp <= 89)) note("cook_range", `Cooking at ${+cookTemp.toFixed(1)} °C is outside the tested range (60–89 °C), so garlic and onion compound losses are extrapolated.`);
    }
    const tot = { mass: 0, water: 0, protein: 0, k_cl: 0 }; KEYS.forEach(k => (tot[k] = 0));
    const sugarMg = {}; SUGARS.forEach(s => (sugarMg[s] = 0));
    for (const item of recipe) {
      const name = item.ingredient, d = DB[name];
      if (!d) throw new Error(`Unknown ingredient: ${name}`);
      const unit = String(item.unit || "g").trim().toLowerCase(), amt = +item.amount || 0;
      let mass;
      if (unit in MASS_UNITS) mass = amt * MASS_UNITS[unit];
      else if (unit in VOLUME_UNITS) {
        if (d.density <= 0) note("no_density", `${name} has no density in the database, so a volume entry counts as 0 g. Enter a weight instead.`, { name });
        mass = amt * VOLUME_UNITS[unit] * d.density;
      } else throw new Error(`Unknown unit: ${item.unit}`);
      const r = { ingredient: name, mass_g: mass, water_g: mass * d.water / 100 };
      KEYS.forEach(k => (r[k + "_mg"] = mass / 100 * d[k]));
      const itemCook = +("cook_min" in item ? item.cook_min : cookMin) || 0;
      if (name in COOKED_NUC && itemCook > 0 && (cookTemp == null || cookTemp >= 65)) {
        const [ca, cg] = COOKED_NUC[name];
        r.nucleotides_cooked = true; r.amp_mg = mass / 100 * (ca == null ? d.amp : ca); r.gmp_mg = mass / 100 * cg;
        note("cooked_nuc", `Cooking releases savory nucleotides in ${name}, so its cooked values are used.`, { name });
      }
      r.protein_g = mass / 100 * d.protein;
      if (r.cys_mg > 0) {
        const cut = +(item.cys_loss_on_cut || 0);
        const frac = (1 - cut) * cysThermalFraction(itemCook, cookTemp);
        r.cys_mg_raw = r.cys_mg; r.cys_retained = frac; r.cys_mg *= frac;
      }
      rows.push(r);
      if (acidity && mass > 0) {
        const sp = speciesFromComposition(d, mass, name);
        sp.nuc = ["amp", "imp", "gmp"].reduce((s, k) => s + r[k + "_mg"] / NUCLEOTIDE_MW[k], 0);
        for (const k in sp) abSp[k] = (abSp[k] || 0) + sp[k];
        const [z, ref, flag] = calibrateZ(d, name, mass, r.water_g, sp);
        abZ += z; r.ph_ref = ref; r.ph_ref_source = flag;
        if (flag === "default") phDefaults.push(name);
      }
      tot.mass += mass; tot.water += r.water_g;
      KEYS.forEach(k => (tot[k] += r[k + "_mg"]));
      if (CHLORIDE_K.has(name)) tot.k_cl += r.k_mg;
      tot.protein += r.protein_g;
      SUGARS.forEach(s => (sugarMg[s] += mass / 100 * (d["sugar_" + s] || 0)));
      r.sugar_eq_mg = SUGARS.reduce((s, sg) => s + (sg in RS ? POW(RS[sg], 1 / EXPONENT) * mass / 100 * (d["sugar_" + sg] || 0) : 0), 0);
      r.acid_mmol = Object.keys(ORGANIC_ACIDS).reduce((s, a) => s + mass / 100 * (d["acid_" + a] || 0) / ORGANIC_ACIDS[a][0], 0);
    }
    // data gaps
    const missing = [], estimated = [];
    for (const r of rows) {
      if (tot.mass <= 0 || r.mass_g / tot.mass < MIN_SHARE) continue;
      const d = DB[r.ingredient], b = d._blank, blank = [];
      if (b.has("glu")) blank.push("glutamate");
      if (b.has("amp") && b.has("imp") && b.has("gmp") && d.glu >= NUC_FLAG_GLU) blank.push("nucleotides");
      if (b.has("acids") && d.ph_ref != null && d.ph_ref < ACIDS_BELOW_PH) blank.push("organic acids");
      if (blank.length) missing.push({ name: r.ingredient, fields: blank });
      const est = Object.keys(d._tier).filter(f => d._tier[f] === 3);
      if (est.length) estimated.push({ name: r.ingredient, fields: est });
    }
    if (waterLoss) {
      if (waterLoss >= tot.water) throw new Error(`You can't cook off more water (${waterLoss.toFixed(0)} g) than the recipe has (${tot.water.toFixed(0)} g).`);
      tot.water -= waterLoss; tot.mass -= waterLoss;
    }
    if (tot.water <= 0) throw new Error("This recipe has no water, so the model can't calculate taste. Add a water-containing ingredient.");

    const sugars = {}; SUGARS.forEach(s => (sugars[s] = (sugarMg[s] / 1000) / (tot.water / 100)));
    // per-ingredient sweetness contribution of high-intensity sweeteners (each alone in the recipe's water)
    for (const r of rows) {
      const d = DB[r.ingredient];
      for (const k in HIS) {
        const g = (r.mass_g / 100 * (d["sugar_" + k] || 0) / 1000) / (tot.water / 100);
        if (g > 0) r.sugar_eq_mg += hisSucroseEq(k, g)[0] * tot.water / 100 * 1000;
      }
    }
    const [sucEq, unscored] = sucroseEquivalent(sugars);
    // v.2.8.5 tasted basis (hfp_model.py TASTE_BASIS = "food"): salt, sweet, umami, sour and kokumi per 100 g FOOD
    // (water-phase concentration x water/mass); pH stays in the water phase. fb = 1 restores the old water basis.
    const fFood = tot.mass > 0 ? tot.water / tot.mass : 1, fb = TASTE_BASIS === "food" ? fFood : 1;
    const sugF = {}; Object.keys(sugars).forEach(s => (sugF[s] = sugars[s] * fFood));
    const sucF = sucroseEquivalent(sugF)[0];
    const sourRem = sourRemaining(TASTE_BASIS === "food" ? 100 * sucF / (100 - Math.min(sucF, 99)) : sucEq);
    let acid = { pH: null, sour_stimulus_mM: 0, citric_equiv_mM: 0, umami_remaining: 1, synergy_pH_factor: 1 };
    let sourFinal = null;
    if (acidity) {
      const wL = tot.water / 1000, sp = toMolar(abSp, wL);
      const ph = solvePH(sp, abZ / 1000 / wL), s = sourStimulus_mM(sp, ph) * fb, sEff = s * sourRem;
      sourFinal = sournessIntensity(s * sourRem);
      acid = { pH: ph, sour_stimulus_mM: s, citric_equiv_mM: citricEquivalent_mM(s), sour_stimulus_effective_mM: sEff,
        umami_remaining: umamiRemaining(sEff), synergy_pH_factor: synergyPHFactor(ph) };
      if (sourFinal > 100) note("sour_top", "Sourness is past the top of the measured scale.");
      if (phDefaults.length) note("ph_default", `No measured pH for ${[...new Set(phDefaults)].sort().join(", ")}, so pH 6.0 is assumed.`, { names: phDefaults });
      if (sEff > MIRANDA_S_MAX) note("sour_umami_extrap", "The acid level is above the tested range for how sourness dulls umami, so that effect is extrapolated.");
    }
    const w100 = tot.water / 100, conc = {};
    KEYS.concat(["k_cl"]).forEach(k => (conc[k] = (tot[k] / 1000) / w100 * fb));
    const kForSalt = kSource === "chloride" ? conc.k_cl : conc.k;
    const impEq = 1e4 * (conc.imp / 348.21 + NUC_W.amp * conc.amp / 347.22 + NUC_W.gmp * conc.gmp / 363.22);
    const div = Math.min(GLU_THR_DROP_MAX, 1 + (GLU_THR_DROP_MAX - 1) * impEq / GLU_THR_AT_IMP);
    const thr = { glu: 0.01 / div, asp: 0.0166 / div };
    const u16 = conc.glu > thr.glu ? conc.glu : 0, v16 = conc.asp > thr.asp ? conc.asp : 0;
    // v.2.9.0 (hfp_model.py NUC_THRESHOLD_MODE "kuninaka"): no nucleotide threshold when glutamate is above its own;
    // nucleotide-alone thresholds from Kuninaka 1980 (IMP 0.387 mM, GMP 0.206 mM); AMP = IMP / 0.18 (assumption)
    if (u16 > 0) { thr.amp = 0; thr.imp = 0; thr.gmp = 0; }
    else { thr.imp = NUC_THR_IMP; thr.gmp = NUC_THR_GMP; thr.amp = NUC_THR_IMP / 0.18; }
    const w16 = conc.amp > thr.amp ? conc.amp : 0, x16 = conc.imp > thr.imp ? conc.imp : 0, y16 = conc.gmp > thr.gmp ? conc.gmp : 0;
    const u = SALT_FORM.glu * u16 + 0.077 * SALT_FORM.asp * v16;
    const synergy = 219 * SALT_FORM.amp * w16 + 1218 * SALT_FORM.imp * x16 + 2800 * SALT_FORM.gmp * y16;
    const fold = Math.min(1 + synergy * acid.synergy_pH_factor, SYNERGY_MAX_FOLD);
    // v.2.7.3: IMP/GMP alone taste of umami via a fixed background glutamate (hfp_model.py NUC_ALONE_U0)
    const foldIG = Math.min(1 + (1218 * SALT_FORM.imp * x16 + 2800 * SALT_FORM.gmp * y16) * acid.synergy_pH_factor, SYNERGY_MAX_FOLD);
    const umamiEq = u * fold + (0.05 / 15) * (foldIG - 1);
    thr.na = 0.0037 * 22.99 / 58.44; thr.k = 0.00242 * 39.0983 / 10;
    const naM = conc.na < thr.na ? 0 : conc.na * 10 / 23;
    const kM = kForSalt < thr.k ? 0 : kForSalt * 10 / 39.0983;
    const naSalt = naM > 0 ? Math.max(0, 2.7036 * LN(naM) + 12.008) : 0;
    if (naM > 0.108) note("salt_extrap", "Salt is above the measured range (about 0.6% in the water), so saltiness is extrapolated.");
    let kSalt;
    if (kM <= 0) kSalt = 0;
    else if (kM <= 0.112) kSalt = Math.max(0, 404.88 * kM * kM + 6.7462 * kM - 0.1344);
    else { kSalt = ((404.88 * 0.112 ** 2 + 6.7462 * 0.112 - 0.1344) / (2.7036 * LN(0.112) + 12.008)) * (2.7036 * LN(kM) + 12.008); note("k_extrap", "Potassium chloride is above the measured range, so its saltiness is extrapolated."); }
    // v.2.7.2: KCl/NaCl by concentration addition (K saltiness -> iso-salty NaCl molarity on the Murphy curve; hfp_model.py SALT_MIX)
    const saltTotal = kSalt > 0 ? Math.max(0, 2.7036 * LN(naM + Math.exp((kSalt - 12.008) / 2.7036)) + 12.008) : naSalt;
    const x = naM + 0.81 * kM;
    const effect = x < 0.1 ? Math.max(0, -37.089 * x * x + 9.9621 * x - 0.038) : Math.max(0, -0.6351 * x + 0.6414);
    const shift = 1 + (SALT_SHIFT_MAX - 1) * Math.min(1, effect / DOG_R_PEAK);
    let umamiNa = umamiEq > 0 ? Math.max(0, 3.6672 * LN(umamiEq * shift) + 12.555) : 0;
    umamiNa *= acid.umami_remaining;
    const gshEq = KOKUMI_POT.gsh * conc.gsh + KOKUMI_POT.evg * conc.evg + KOKUMI_POT.cys * conc.cys;
    const gshMM = gshEq / 307.33 * 10 * 1000;
    const kHill = c => (c > 0 ? 100 * POW(c, KOK_N) / (POW(KOK_EC50, KOK_N) + POW(c, KOK_N)) : 0);
    // v.2.9.0 kokumi floor (hfp_model.py kokumi_threshold_mM; Ueda 1997 Table II): threshold falls with umami
    const kThr = (() => {
      const P = KOK_THR_PTS, x = umamiEq > 0 ? umamiEq : P[0][0];
      let pct;
      if (x <= P[0][0]) pct = P[0][1];
      else if (x >= P[P.length - 1][0]) pct = P[P.length - 1][1];
      else for (let i = 0; i < P.length - 1; i++) {
        const [x0, y0] = P[i], [x1, y1] = P[i + 1];
        if (x <= x1) { const t = (LN(x) - LN(x0)) / (LN(x1) - LN(x0)); pct = Math.exp(LN(y0) + t * (LN(y1) - LN(y0))); break; }
      }
      return pct * 10 / 307.33 * 1000;
    })();
    const hThr = kHill(kThr);
    const kokumi = Math.max(0, (kHill(gshMM) - hThr) / (100 - hThr) * 100);
    const umamiFinal = umamiNa + umamiNa * KOK_UMAMI_GAIN * (kokumi / 100);
    let totalSugar = 0; SUGARS.forEach(s => (totalSugar += sugars[s]));
    const q = acidity ? sweetQ(acid.citric_equiv_mM) : 1;
    const cEq = TASTE_BASIS === "food" ? sucF : pctWW(sucEq, totalSugar);
    const sweetFinal = sweetness(TASTE_BASIS === "food" ? sucF * q : pctWW(sucEq * q, totalSugar));
    if (cEq > MOSK_MAX) note("sweet_extrap", "Sugar is above the measured range (32%), so sweetness is extrapolated.");
    const unsc = unscored.filter(s => sugars[s] >= 0.01 * Math.max(totalSugar, 1e-9));
    if (unsc.length) note("unscored_sugar", `Not counted for sweetness (no published sweetness value): ${unsc.join(", ")}.`);
    const hisHigh = Object.keys(HIS).filter(k => hisSucroseEq(k, sugars[k] || 0)[1]).map(k => HIS[k][0]);
    if (hisHigh.length) note("his_high", `Above the tested range, sweetness is held at its top tested level (15% sucrose-eq, Wee 2018; saccharin 9%, Schiffman 1995): ${hisHigh.join(", ")}.`);
    if (Object.keys(HIS).some(k => (sugars[k] || 0) > 0)) note("his", "High-intensity sweeteners (Wee 2018; saccharin from Schiffman 1995): bitterness is modelled for Reb A, acesulfame K and saccharin (Schiffman 1995); sucralose and aspartame are not bitter at normal levels; lingering and synergy between sweeteners are not modelled. Stevia and monk fruit grades are scaled by their Reb A / mogroside V content.");
    // v.2.8.1: umami raises saltiness beyond its own sodium (Sun 2022 fit; hfp_model.py UMAMI_SALT_*)
    let saltUm = saltTotal;
    if (UMAMI_SALT_EMAX > 0 && naM > 0) {
      const sUm = Math.min(1, Math.max(0, (toScore(umamiFinal, "umami") - 1) / (UMAMI_SALT_S_FULL - 1)));
      const naMM = naM * 1000, lo = UMAMI_SALT_FADE_MM[0], hi = UMAMI_SALT_FADE_MM[1];
      const fNa = naMM <= lo ? 1 : Math.max(0, (hi - naMM) / (hi - lo));
      const eUm = UMAMI_SALT_EMAX * sUm * fNa;
      if (eUm > 0) {
        const naEff = naM * (1 + eUm);
        const naS = Math.max(0, 2.7036 * LN(naEff) + 12.008);
        saltUm = kSalt > 0 ? Math.max(0, 2.7036 * LN(naEff + Math.exp((kSalt - 12.008) / 2.7036)) + 12.008) : naS;
      }
    }
    const saltFinal = saltUm + saltUm * KOK_SALT_GAIN * (kokumi / 100);
    // bitterness (v.2.8.3): whole-food basis (per 100 g food); fFood = water / mass converts water-phase values
    const fw = fFood / fb;   // conc and naM are already per food when TASTE_BASIS === "food"
    const cafPct = conc.caf * fw, tbPct = conc.tb * fw, kclPct = conc.k_cl * KCL_PER_K * fw;
    const rebaPct = sugF.reb_a || 0, acekPct = sugF.ace_k || 0, naF = naM * fw;
    const sNaC = sNaCaf(naF), sNaK = sNaKcl(naF);
    const sucFR = sucroseEquivalent(Object.assign({}, sugF, { reb_a: 0 }))[0];
    const sucFA = sucroseEquivalent(Object.assign({}, sugF, { ace_k: 0 }))[0];
    const sucFS = sucroseEquivalent(Object.assign({}, sugF, { saccharin: 0 }))[0], saccPct = sugF.saccharin || 0;
    const sSug = sSugar(sucF), sSugR = sSugar(sucFR), sSugA = sSugar(sucFA);
    const tbEff = Math.min(tbPct, TB_SOL_MAX);
    const cXan = cafPct + TB_CAF_EQ * tbEff, cReba = rebaCafEq(rebaPct), cAcek = acekCafEq(acekPct);
    const bX = cafInt(cXan) * (1 - sNaC) * (1 - sSug), bK = kclInt(kclPct) * (1 - sNaK) * (1 - sSug);
    const bR = cafInt(cReba) * (1 - sNaC) * (1 - sSugR), bA = cafInt(cAcek) * (1 - sNaC) * (1 - sSugA);
    const sSugS = sSugar(sucFS), bS = cafInt(saccCafEq(saccPct)) * (1 - sNaC) * (1 - sSugS);
    const ceqB = cafEq(bX) + cafEq(bK) + cafEq(bR) + cafEq(bA) + cafEq(bS);
    const bitterFinal = ceqB > 0 ? CAF_K * POW(ceqB, CAF_N) : 0;
    if (cXan > CAF_MAX) note("bitter_caf_extrap", "Caffeine (plus theobromine as caffeine) is above the measured range (0.15%), so bitterness is extrapolated.");
    if (kclPct > KCL_MAX) note("bitter_kcl_extrap", "KCl is above the measured range (1.5%), so bitterness is extrapolated.");
    if (kclPct > 0 && kclPct < KCL_MIN) note("bitter_kcl_low", "KCl is below the measured range (0.5%), so its bitterness is a low-confidence estimate; people differ a lot in how bitter KCl tastes.");
    if (tbPct > 0) note("bitter_tb", "Theobromine (cocoa) counts as 0.91 g of caffeine per gram, assuming equal bitterness at equal multiples of each one's taste threshold" + (tbPct > TB_SOL_MAX ? `. Only ${TB_SOL_MAX.toFixed(3)}% can dissolve at room temperature (Stark 2006), so the rest is not tasted; a hot drink may dissolve more.` : "."));
    if (rebaPct > REBA_MAX) note("bitter_reba_extrap", "Stevia (Reb A) is above the tested range for bitterness (0.15%), so its bitterness is extrapolated.");
    if (acekPct > ACEK_MAX) note("bitter_acek_extrap", "Acesulfame K is above the tested range for bitterness (0.156%), so its bitterness is extrapolated.");
    if (saccPct > SACC_MAX) note("bitter_sacc_extrap", "Saccharin is above the tested range for bitterness (0.096%), so its bitterness is extrapolated.");
    if (bitterFinal > 0 && Math.max(sucF, sucFR, sucFA, sucFS) > SUG_FIT_MAX) note("bitter_sugar_high", "Sugar is above the tested range for masking bitterness (19% sucrose), so the masking is held near its maximum.");
    if (cafPct > 0 || tbPct > 0) note("bitter_scope", "Bitterness counts caffeine, theobromine, potassium chloride, stevia (Reb A) and acesulfame K only. Coffee, tea and cocoa also get bitterness from other compounds, so their bitterness may read low.");
    const protFlag = rows.filter(r => PROTEIN_BITTER_RE.test(r.ingredient) && tot.mass > 0 && r.mass_g / tot.mass >= MIN_SHARE).map(r => r.ingredient);
    if (protFlag.length) note("bitter_protein", `Protein hydrolysates and isolates (${protFlag.join(", ")}) can taste bitter from small peptides. This is not scored.`, { names: protFlag });
    const m100b = tot.mass / 100, tbShare = tbPct > 0 ? tbEff / tbPct : 0;
    rows.forEach(r => {
      const d = DB[r.ingredient];
      const rx = cafEq(cafInt((r.caf_mg + TB_CAF_EQ * r.tb_mg * tbShare) / 1000 / m100b) * (1 - sNaC) * (1 - sSug));
      const rk = CHLORIDE_K.has(r.ingredient) ? cafEq(kclInt((r.k_mg / 1000) / m100b * KCL_PER_K) * (1 - sNaK) * (1 - sSug)) : 0;
      const rr = cafEq(cafInt(rebaCafEq((r.mass_g / 100 * (d.sugar_reb_a || 0) / 1000) / m100b)) * (1 - sNaC) * (1 - sSugR));
      const ra = cafEq(cafInt(acekCafEq((r.mass_g / 100 * (d.sugar_ace_k || 0) / 1000) / m100b)) * (1 - sNaC) * (1 - sSugA));
      const rs = cafEq(cafInt(saccCafEq((r.mass_g / 100 * (d.sugar_saccharin || 0) / 1000) / m100b)) * (1 - sNaC) * (1 - sSugS));
      r.bitter_w = rx + rk + rr + ra + rs;
    });
    return {
      results: { umami_intensity: umamiFinal, kokumi_intensity_pct: kokumi, saltiness_intensity: saltFinal,
        sweetness_intensity: sweetFinal, sourness_intensity: sourFinal, bitterness_intensity: bitterFinal },
      scores: { umami: toScore(umamiFinal, "umami"), saltiness: toScore(saltFinal, "salt"), sweetness: toScore(sweetFinal, "sweet"),
        kokumi: toScore(kokumi, "kokumi"), sourness: sourFinal == null ? null : toScore(sourFinal, "sour"),
        bitterness: toScore(bitterFinal, "bitter") },
      acidity: acid, conc, thr, rows, notes, missing, estimated,
      totals: { mass_g: tot.mass, water_g: tot.water, salt_pct_water: naM * 58.44 / 10, sucrose_eq_pct: cEq,
        umami_eq_msg_pct: umamiEq * shift },
    };
  }

  function search(term, limit) {
    const words = term.toLowerCase().split(/[\s,()]+/).filter(Boolean);
    if (!words.length) return [];
    const scored = [];
    for (const n of NAMES) {
      const l = n.toLowerCase();
      if (!words.every(w => l.includes(w))) continue;
      let s = 0;
      if (l === term.toLowerCase()) s -= 100;
      if (l.startsWith(words[0])) s -= 10;
      if (new RegExp("\\b" + words[0].replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(l)) s -= 5;
      s += n.length / 100;
      scored.push([s, n]);
    }
    return scored.sort((a, b) => a[0] - b[0]).slice(0, limit || 12).map(x => x[1]);
  }

  if (G.HFP_DB) loadDB(G.HFP_DB);
  G.HFP = { compute, search, names: NAMES, db: DB, units: { mass: Object.keys(MASS_UNITS), volume: Object.keys(VOLUME_UNITS) },
    SCORE_REF, _fit: () => [S50, HILL] };
})(typeof window !== "undefined" ? window : globalThis);
