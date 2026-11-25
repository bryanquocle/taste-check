/* Taste Check cooking water-loss estimator (v.2.10.0, Nov 25, 2026). Browser port of
   validation/cook_evaporation/cook_evap.py (tests/cook_evap_parity.py checks they agree).
   Below a boil: Shah 2014 (ASHRAE Trans. 120(2) SE-14-001, Eqs. 1-2) natural-convection evaporation,
   times a kitchen factor (ASSUMPTION, calibrated on Opadokun 2019 and Boelter 1946). At a boil: net burner
   power / latent heat (Frontier Energy 2019, report 501318071-R0, Tables 1-2). Lid factors: on 0.01
   (Opadokun 2019; Brundrett & Poultney 1979; Newborough & Probert 1987); ajar 0.4 (ASSUMPTION).
   The loss is averaged over every common pot the recipe fits; low/high = min/max over pots and settings. */
(function (G) {
  "use strict";
  const P_ATM = 101325.0, ROOM_C = 22.0, ROOM_RH = 0.50, HFG = 2.257e6;
  const P_NET_MED_KW = 0.92, P_NET_LARGE_KW = 1.79, MED_BURNER_MAX_CM = 20.5;
  const BOIL_THROTTLE = { low: 0.5, mid: 0.75, high: 1.0 };
  const KITCHEN_K = { low: 1.0, mid: 1.3, high: 1.5 };
  const PAN_MAX_L = 1.5, CAP_FRAC = 0.6, STEP_MIN = 0.5;
  const LID = { off: { mid: 1.0, low: 1.0, high: 1.0 }, ajar: { mid: 0.4, low: 0.25, high: 0.6 }, on: { mid: 0.01, low: 0.003, high: 0.08 } };
  const IN = 2.54, QT = 0.946353;
  // [name, type, capacity L (null = from geometry), top diameter cm, bottom diameter cm, depth cm]
  const POTS = [
    ["Saucepan 2 qt", "saucepan", 2 * QT, 6.0 * IN, 6.0 * IN, 4.5 * IN],
    ["Saucepan 3 qt", "saucepan", 3 * QT, 8.5 * IN, 8.5 * IN, 4.0 * IN],
    ["Saute pan 3 qt", "saute", 3 * QT, 10.5 * IN, 10.5 * IN, 4.0 * IN],
    ["Skillet 10 in", "skillet", null, 10.5 * IN, 8.0 * IN, 2.0 * IN],
    ["Skillet 12 in", "skillet", null, 12.2 * IN, 9.125 * IN, 2.25 * IN],
    ["Wok 14 in flat-bottom", "wok", null, 14.0 * IN, 6.0 * IN, 4.0 * IN],
    ["Dutch oven 3.5 qt (#22)", "dutch", 3.5 * QT, 22.0, 22.0, null],
    ["Dutch oven 5.5 qt (#26)", "dutch", 5.5 * QT, 26.0, 26.0, null],
    ["Dutch oven 7.25 qt (#28)", "dutch", 7.25 * QT, 28.0, 28.0, null],
    ["Stockpot 8 qt", "stockpot", 8 * QT, 11.5 * IN, 11.5 * IN, null],
    ["Stockpot 16 qt", "stockpot", 15.0, 28.0, 28.0, null],
  ];
  const FILL = { saucepan: [0.25, 0.80], dutch: [0.25, 0.80], stockpot: [0.25, 0.80], saute: [0.10, 0.80], skillet: [0.10, 0.80], wok: [0.10, 0.80] };

  function pws(tC) {   // Hyland-Wexler, ASHRAE Fundamentals 2017 Ch. 1 Eq. 6, Pa
    const T = tC + 273.15;
    return Math.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T * T - 1.4452093e-8 * T * T * T + 6.5459673 * Math.log(T));
  }
  function air(tC, pv) {
    const T = tC + 273.15, rhoDa = (P_ATM - pv) / (287.042 * T), rhoV = pv / (461.52 * T);
    return [rhoDa, rhoDa > 0 ? rhoV / rhoDa : Infinity, rhoV];
  }
  function shahFlux(tw) {   // kg/m2/h
    tw = Math.min(tw, 99.97);
    const pw = pws(tw), pr = ROOM_RH * pws(ROOM_C);
    const [rwDa, , rvw] = air(tw, pw), [rrDa, Wr] = air(ROOM_C, pr);
    const drho = Math.max(rrDa - rwDa, 0);
    const e1 = 35.0 * Math.pow(drho, 1 / 3) * (rvw - rwDa * Wr), e2 = 0.00005 * (pw - pr);
    return Math.max(e1, e2, 0);
  }
  const frustum = (r, R, h) => Math.PI * h / 3 * (r * r + r * R + R * R);
  const capacityL = p => (p[2] != null ? p[2] : frustum(p[4] / 2, p[3] / 2, p[5]) / 1000);
  function areaM2(p, volL) {
    const dt = p[3], db = p[4], depth = p[5];
    if (Math.abs(dt - db) < 1e-9) return Math.PI * Math.pow(dt / 200, 2);
    const r = db / 2, Rt = dt / 2, V = volL * 1000;
    let lo = 0, hi = depth * 3;
    for (let i = 0; i < 60; i++) {
      const h = (lo + hi) / 2, R = r + (Rt - r) * Math.min(h, depth) / depth;
      if (frustum(r, R, h) < V) lo = h; else hi = h;
    }
    const R = r + (Rt - r) * Math.min(lo, depth) / depth;
    return Math.PI * Math.pow(R / 100, 2);
  }
  function candidates(volL, type) {
    const out = POTS.filter(p => {
      if (type && p[1] !== type) return false;
      if (!type && ["skillet", "saute", "wok"].includes(p[1]) && volL > PAN_MAX_L) return false;
      const f = volL / capacityL(p), [lo, hi] = FILL[p[1]];
      return lo <= f && f <= hi;
    });
    if (out.length) return out;
    const pool = POTS.filter(p => !type || p[1] === type);
    const miss = p => { const f = volL / capacityL(p), [lo, hi] = FILL[p[1]]; return f < lo ? lo - f : f - hi; };
    return [pool.reduce((a, b) => (miss(b) < miss(a) ? b : a))];
  }
  const boilWeight = tF => Math.min(Math.max((tF - 210) / 2, 0), 1);
  function rate(p, volL, tF, s) {   // g/min
    const tC = (tF - 32) / 1.8, A = areaM2(p, volL);
    const P = p[3] <= MED_BURNER_MAX_CM ? P_NET_MED_KW : P_NET_LARGE_KW;
    const full = P * 1000 / HFG * 1000 * 60;
    const surf = Math.min(KITCHEN_K[s] * shahFlux(tC) * A * 1000 / 60, full);
    const w = boilWeight(tF);
    if (w === 0) return surf;
    const boil = Math.max(BOIL_THROTTLE[s] * full, shahFlux(100) * A * 1000 / 60);
    return (1 - w) * surf + w * boil;
  }
  function lossInPot(p, massG, minutes, tF, lidF, s) {
    let m = massG, t = 0, lost = 0;
    while (t < minutes - 1e-9) {
      const step = Math.min(STEP_MIN, minutes - t), d = rate(p, m / 1000, tF, s) * lidF * step;
      lost += d; m -= d; t += step;
      if (m <= 0) break;
    }
    return lost;
  }
  // massG: recipe mass (~1 g/mL); waterG: recipe water (cap = 60% of it); potType: null = average over all pots
  function estimate(massG, minutes, tF, potType, lid, waterG) {
    lid = LID[lid] ? lid : "off";
    const volL = massG / 1000, pots = candidates(volL, potType || null);
    const mids = [], lows = [], highs = [];
    for (const p of pots) {
      mids.push(lossInPot(p, massG, minutes, tF, LID[lid].mid, "mid"));
      lows.push(lossInPot(p, massG, minutes, tF, LID[lid].low, "low"));
      highs.push(lossInPot(p, massG, minutes, tF, LID[lid].high, "high"));
    }
    const central = mids.reduce((a, b) => a + b, 0) / mids.length;
    const cap = CAP_FRAC * (waterG != null ? waterG : massG), cl = x => Math.min(x, cap);
    return { central_g: cl(central), low_g: cl(Math.min(...lows)), high_g: cl(Math.max(...highs)), capped: central > cap,
      cap_g: cap, pots: pots.map(p => p[0]) };
  }
  G.HFP_COOK = { estimate, shahFlux, POTS };
})(typeof window !== "undefined" ? window : globalThis);
