"""
cook_evap.py  --  PROPOSED pot water-loss estimator for Taste Check (not wired in).

Standard library only. Run:
    python cook_evap.py            # validation + worked examples
    python cook_evap.py --mass 1200 --min 30 --tempF 200 [--pot saucepan] [--lid off|ajar|on]

Model (see REPORT.md for sources):
  * Below a boil: Shah (2012) natural-convection evaporation, as given in
    Shah 2014 ASHRAE Trans. 120(2) SE-14-001, Eq. 1 and Eq. 2 (take the larger):
        E = 35 * rho_w * (rho_r - rho_w)^(1/3) * (W_w - W_r)      [kg/m2/h]
        E = 0.00005 * (p_w - p_r)                                  [kg/m2/h]
    rho = 1/v (kg dry air per m3 moist air, the psychrometric-chart density),
    W = humidity ratio (kg/kg), p = vapour pressure (Pa); w = saturated air at
    the liquid temperature, r = room air.  Verified to 94 C (Shah 2002).
  * At a boil (>= 211 F): burner-limited, net heat to pot / latent heat.
    Net burner power from Frontier Energy 2019 (Tables 1-2).
  * Lid factors: on = 0.01 (Opadokun 2019; Brundrett & Poultney 1979;
    Newborough & Probert 1987). Ajar = 0.4 (ASSUMPTION).
"""
import math, sys, argparse

P_ATM = 101325.0          # Pa
ROOM_C = 22.0             # ASSUMPTION: kitchen air
ROOM_RH = 0.50            # ASSUMPTION
HFG = 2.257e6             # J/kg latent heat at 100 C (steam tables)

# ---------------- psychrometrics (ASHRAE Fundamentals 2017, Ch. 1) ----------
def p_ws(t_c):
    """Saturation vapour pressure over liquid water, Pa (Hyland-Wexler, ASHRAE Eq. 6)."""
    T = t_c + 273.15
    C8, C9, C10 = -5.8002206e3, 1.3914993, -4.8640239e-2
    C11, C12, C13 = 4.1764768e-5, -1.4452093e-8, 6.5459673
    return math.exp(C8 / T + C9 + C10 * T + C11 * T**2 + C12 * T**3 + C13 * math.log(T))

def air_state(t_c, pv, P=P_ATM):
    """Return (rho_dry_per_moist_volume kg/m3, W kg/kg, vapour density kg/m3)."""
    pd = P - pv
    T = t_c + 273.15
    rho_da = pd / (287.042 * T)          # = 1/v, kg dry air per m3 moist air
    rho_v = pv / (461.52 * T)            # kg vapour per m3
    W = rho_v / rho_da if rho_da > 0 else float("inf")
    return rho_da, W, rho_v

def shah_flux(t_water_c, t_air_c=ROOM_C, rh=ROOM_RH, density="dry"):
    """Evaporation flux, kg/m2/h. density='dry' uses 1/v (Shah nomenclature);
    'moist' uses full moist-air density (sensitivity check only)."""
    t_water_c = min(t_water_c, 99.97)
    pw = p_ws(t_water_c)
    pr = rh * p_ws(t_air_c)
    rw_da, Ww, rvw = air_state(t_water_c, pw)
    rr_da, Wr, rvr = air_state(t_air_c, pr)
    if density == "dry":
        rho_w, rho_r = rw_da, rr_da
    else:
        rho_w, rho_r = rw_da + rvw, rr_da + rvr
    drho = max(rho_r - rho_w, 0.0)
    # rho_w*(Ww - Wr) written as (rho_v,w - rho_da,w*Wr): finite as t -> 100 C
    e1 = 35.0 * (drho ** (1 / 3)) * (rvw - rw_da * Wr) if density == "dry" else \
         35.0 * rho_w * (drho ** (1 / 3)) * (Ww - Wr)
    e2 = 0.00005 * (pw - pr)
    return max(e1, e2, 0.0)

# ---------------- burner (Frontier Energy 2019, report 501318071-R0) --------
# Net heat into pot at max setting = rated input x measured heat-up efficiency.
# Medium hob (Table 1): gas 9.5 kBtu/h x 30.6% = 0.85 kW; resistance ceramic
#   1.2 kW x 70.3% = 0.84 kW; coil 1.5 kW x 72.3% = 1.08 kW  -> mean 0.92 kW
# Large hob (Table 2): gas 17 kBtu/h x 31.9% = 1.59 kW; ceramic 2.5 x 75.5% =
#   1.89 kW; coil 2.4 x 79.3% = 1.90 kW -> mean 1.79 kW
# (Induction delivers 2.0-3.2 kW; excluded from the central value.)
P_NET_MED_KW, P_NET_LARGE_KW = 0.92, 1.79
BOIL_THROTTLE = {"low": 0.5, "mid": 0.75, "high": 1.0}   # ASSUMPTION
# Kitchen factor on the Shah surface term: Shah under-predicts the two near-boil
# pan data sets by ~20-30% (Opadokun 2019 pot; Boelter 1946 top point).
KITCHEN_K = {"low": 1.0, "mid": 1.3, "high": 1.5}          # ASSUMPTION (calibrated, n=2 sources)
PAN_MAX_L = 1.5   # auto mode: skillets/saute/wok only considered up to 1.5 L (ASSUMPTION)

LID = {"off": (1.0, 1.0, 1.0), "ajar": (0.4, 0.25, 0.6),   # ajar = ASSUMPTION
       "on": (0.01, 0.003, 0.08)}                         # on: Opadokun/Brundrett; high = Berick 92%

# ---------------- pots -------------------------------------------------------
IN = 2.54  # cm per inch
QT = 0.946353  # L per US quart
# name, type, capacity_L, top_diam_cm, bottom_diam_cm, depth_cm, source tag
POTS = [
    ("Saucepan 2 qt",          "saucepan", 2 * QT,    6.0 * IN,   6.0 * IN,   4.5 * IN, "WS/All-Clad"),
    ("Saucepan 3 qt",          "saucepan", 3 * QT,    8.5 * IN,   8.5 * IN,   4.0 * IN, "WS/All-Clad"),
    ("Saute pan 3 qt",         "saute",    3 * QT,   10.5 * IN,  10.5 * IN,   4.0 * IN, "WS/All-Clad"),
    ("Skillet 10 in",          "skillet",  None,     10.5 * IN,   8.0 * IN,   2.0 * IN, "WS/All-Clad top; bottom ASSUMED"),
    ("Skillet 12 in",          "skillet",  None,     12.2 * IN,  9.125 * IN, 2.25 * IN, "dimensions.com/Lodge; Abt depth"),
    ("Wok 14 in flat-bottom",  "wok",      None,     14.0 * IN,   6.0 * IN,   4.0 * IN, "ASSUMED geometry"),
    ("Dutch oven 3.5 qt (#22)", "dutch",   3.5 * QT, 22.0,       22.0,        None,     "Le Creuset size no. = cm"),
    ("Dutch oven 5.5 qt (#26)", "dutch",   5.5 * QT, 26.0,       26.0,        None,     "Le Creuset size no. = cm"),
    ("Dutch oven 7.25 qt (#28)", "dutch",  7.25 * QT, 28.0,      28.0,        None,     "Le Creuset size no. = cm"),
    ("Stockpot 8 qt",          "stockpot", 8 * QT,   11.5 * IN,  11.5 * IN,   None,     "WS/All-Clad"),
    ("Stockpot 16 qt",         "stockpot", 15.0,     28.0,       28.0,        None,     "Opadokun 2019 test pot"),
]
FILL = {"saucepan": (0.25, 0.80), "dutch": (0.25, 0.80), "stockpot": (0.25, 0.80),
        "saute": (0.10, 0.80), "skillet": (0.10, 0.80), "wok": (0.10, 0.80)}  # ASSUMPTION

def frustum_vol(r, R, h):
    return math.pi * h / 3.0 * (r * r + r * R + R * R)

def pot_capacity_L(p):
    name, typ, cap, dt, db, depth, _ = p
    if cap is not None:
        return cap
    return frustum_vol(db / 2, dt / 2, depth) / 1000.0

def surface_area_m2(p, vol_L):
    """Liquid surface area (m2) for a given liquid volume; frustum for flared pans."""
    name, typ, cap, dt, db, depth, _ = p
    if abs(dt - db) < 1e-9:
        return math.pi * (dt / 200.0) ** 2
    r, Rt = db / 2, dt / 2
    V = vol_L * 1000.0
    lo, hi = 0.0, depth * 3
    for _ in range(60):
        h = (lo + hi) / 2
        R = r + (Rt - r) * min(h, depth) / depth
        if frustum_vol(r, R, h) < V:
            lo = h
        else:
            hi = h
    R = r + (Rt - r) * min(lo, depth) / depth
    return math.pi * (R / 100.0) ** 2

def candidates(vol_L, pot_type=None):
    out = []
    for p in POTS:
        if pot_type and p[1] != pot_type:
            continue
        if not pot_type and p[1] in ("skillet", "saute", "wok") and vol_L > PAN_MAX_L:
            continue
        f = vol_L / pot_capacity_L(p)
        lo, hi = FILL[p[1]]
        if lo <= f <= hi:
            out.append(p)
    if not out:  # fall back: pot whose fill is closest to the window
        pool = [p for p in POTS if (not pot_type or p[1] == pot_type)]
        def miss(p):
            f = vol_L / pot_capacity_L(p); lo, hi = FILL[p[1]]
            return (lo - f) if f < lo else (f - hi)
        out = [min(pool, key=miss)]
    return out

def boil_weight(tF):
    """0 below 210 F, 1 at 212 F (linear ramp: ASSUMPTION to avoid a cliff)."""
    return min(max((tF - 210.0) / 2.0, 0.0), 1.0)

def rate_g_per_min(p, vol_L, tF, throttle="mid"):
    tC = (tF - 32) / 1.8
    A = surface_area_m2(p, vol_L)
    surf = KITCHEN_K[throttle] * shah_flux(tC) * A * 1000 / 60.0   # g/min
    P = P_NET_MED_KW if p[3] <= 20.5 else P_NET_LARGE_KW   # small pot -> medium burner (ASSUMPTION)
    # energy guard: a pot can never evaporate more than its burner delivers at full
    surf = min(surf, P * 1000 / HFG * 1000 * 60)
    w = boil_weight(tF)
    if w == 0:
        return surf
    boil = BOIL_THROTTLE[throttle] * P * 1000 / HFG * 1000 * 60   # g/min
    boil = max(boil, shah_flux(100.0) * A * 1000 / 60.0)
    return (1 - w) * surf + w * boil

def loss_in_pot(p, mass_g, minutes, tF, lid_f, throttle="mid"):
    m = mass_g
    t = 0.0
    dt = 0.5
    lost = 0.0
    while t < minutes - 1e-9:
        step = min(dt, minutes - t)
        r = rate_g_per_min(p, m / 1000.0, tF, throttle) * lid_f
        d = r * step
        lost += d
        m -= d
        t += step
        if m <= 0:
            break
    return lost

def estimate(mass_g, minutes, tF, pot_type=None, lid="off", water_g=None, cap_frac=0.6):
    """Return dict: central, low, high water loss (g) + per-pot detail."""
    vol_L = mass_g / 1000.0       # ASSUMPTION ~1 g/mL
    pots = candidates(vol_L, pot_type)
    lf_mid, lf_lo, lf_hi = LID[lid]
    mids, lows, highs, detail = [], [], [], []
    for p in pots:
        mid = loss_in_pot(p, mass_g, minutes, tF, lf_mid, "mid")
        lo = loss_in_pot(p, mass_g, minutes, tF, lf_lo, "low")
        hi = loss_in_pot(p, mass_g, minutes, tF, lf_hi, "high")
        mids.append(mid); lows.append(lo); highs.append(hi)
        detail.append((p[0], round(vol_L / pot_capacity_L(p) * 100), round(surface_area_m2(p, vol_L) * 1e4), round(mid)))
    central = sum(mids) / len(mids)
    low, high = min(lows), max(highs)
    water = water_g if water_g is not None else mass_g
    cap = cap_frac * water
    capped = central > cap
    clamp = lambda x: min(x, cap)
    return {"central_g": round(clamp(central)), "low_g": round(clamp(low)), "high_g": round(clamp(high)),
            "capped": capped, "cap_g": round(cap), "pots": detail}

# ---------------- validation ------------------------------------------------
def validate():
    print("=== 1. Implementation check vs Shah 2014 Table 12 (larger of Eq.1/Eq.2) ===")
    # water C, air C, RH, published kg/m2/h
    t12 = [(35, 30, .30, 0.443), (35, 30, .70, 0.246), (50, 30, .30, 1.516), (50, 30, .70, 1.26),
           (70, 30, .30, 5.088), (70, 30, .70, 4.809), (70, 35, .30, 4.948), (70, 35, .70, 4.578),
           (65, 30, .30, 3.856), (60, 40, .30, 2.607)]
    for density in ("dry", "moist"):
        errs = []
        for tw, ta, rh, pub in t12:
            e = shah_flux(tw, ta, rh, density)
            errs.append(abs(e - pub) / pub)
        print(f"  density={density:5s}: mean abs dev {100*sum(errs)/len(errs):.1f}%  max {100*max(errs):.1f}%")
    for tw, ta, rh, pub in t12[:6]:
        print(f"    Tw={tw} Ta={ta} RH={rh:.0%}: model {shah_flux(tw,ta,rh):.3f}  Table12 {pub}")

    print("\n=== 2. Boelter, Gordon & Griffin 1946 (0.305 m pan), top of range ===")
    print("  Shah 2014 Table 1: Tw up to 94.2 C, air 18.7-24.7 C, E up to 21.07 kg/m2/h")
    for ta, rh in ((18.7, .64), (21.7, .5), (24.7, .98)):
        print(f"    94.2 C water, air {ta} C RH {rh:.0%}: model {shah_flux(94.2, ta, rh):.2f} kg/m2/h")

    print("\n=== 3. Opadokun 2019 (Iowa State MS thesis) Table 4.1: 28 cm SS pot, 15 L,")
    print("        simmer held at 90 C (max +1 C), 45 min, lid off, induction 865 W ===")
    A = math.pi * 0.14 ** 2
    meas = {25: 833.6, 50: 896.8, 75: 994.6}
    for T in (90.0, 90.5, 91.0):
        for k in (1.0, 1.3):
            pred = k * shah_flux(T) * A * 0.75 * 1000
            errs = [(pred - m) / m * 100 for m in meas.values()]
            print(f"  bulk {T} C, K={k}: predicted {pred:.0f} g vs measured 834/897/995 g -> "
                  + ", ".join(f"{e:+.0f}%" for e in errs)
                  + f"  (mean abs {sum(abs(e) for e in errs)/3:.0f}%)")
    print("  Lid on measured 3-9 g (factor 91-332 lower) -> lid factor 0.003-0.011")
    print("  Energy check: 865 W input x ~0.85 induction eff = ~735 W; latent of 900 g/45 min = "
          f"{0.9*HFG/2700:.0f} W")

def examples():
    print("\n=== Worked examples (kitchen 22 C / 50% RH) ===")
    cases = [("Tomato sauce 1.2 kg, 30 min @ 200 F, lid off", 1200, 30, 200, None, "off"),
             ("Same, saucepan only", 1200, 30, 200, "saucepan", "off"),
             ("Same, lid ajar", 1200, 30, 200, None, "ajar"),
             ("Stock 3 kg, 2 h @ 205 F, lid off", 3000, 120, 205, None, "off"),
             ("Stock 3 kg, 2 h @ 205 F, lid on", 3000, 120, 205, None, "on"),
             ("Pan sauce 400 g, 5 min @ 212 F, skillet", 400, 5, 212, "skillet", "off"),
             ("Pan sauce 400 g, 5 min @ 200 F, skillet", 400, 5, 200, "skillet", "off"),
             ("Pasta water 4 kg, 10 min @ 212 F, lid off", 4000, 10, 212, None, "off")]
    for label, m, mins, tF, pt, lid in cases:
        r = estimate(m, mins, tF, pt, lid)
        print(f"\n{label}\n  -> central {r['central_g']} g  (range {r['low_g']}-{r['high_g']} g)"
              f"{'  [CAPPED at ' + str(r['cap_g']) + ' g]' if r['capped'] else ''}")
        for name, fill, area, mid in r["pots"]:
            print(f"     {name:26s} fill {fill:3d}%  area {area:4d} cm2  loss {mid} g")

def frontier_check():
    print("\n=== 4. Energy cross-check: Frontier Energy 2019 Table 5 simmer (208-209 F) ===")
    print("  10-qt pot, 12 lb water; coil 976 W x 79.3% = 774 W net; ceramic 907 W x 75.5% = 685 W net")
    print("  Lid status during simmer NOT stated; pot diameter NOT stated (ASSUME 11 in).")
    A = math.pi * (11 * 2.54 / 200) ** 2
    tC = (208.5 - 32) / 1.8
    for k in (1.0, 1.3):
        kg_h = k * shah_flux(tC) * A
        print(f"  K={k}: model evaporation {kg_h:.2f} kg/h = {kg_h*HFG/3600:.0f} W latent "
              "(must be <= ~685-774 W net if lid was off)")

def flux_table():
    print("\n=== Flux vs liquid temperature (22 C / 50% RH room) ===")
    for tF in (100, 120, 140, 160, 180, 190, 195, 200, 205, 210):
        tC = (tF - 32) / 1.8
        print(f"  {tF} F ({tC:.1f} C): {shah_flux(tC):6.2f} kg/m2/h = {shah_flux(tC)*1000/60/1e4:.3f} g/cm2/min")
    print(f"  boil, medium burner net 0.92 kW x 0.75: {0.75*0.92e3/HFG*3.6e6/1000:.2f} kg/h total")
    print(f"  boil, large burner net 1.79 kW x 0.75:  {0.75*1.79e3/HFG*3.6e6/1000:.2f} kg/h total")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mass", type=float); ap.add_argument("--min", type=float)
    ap.add_argument("--tempF", type=float); ap.add_argument("--pot"); ap.add_argument("--lid", default="off")
    a = ap.parse_args()
    if a.mass:
        print(estimate(a.mass, a.min, a.tempF, a.pot, a.lid))
    else:
        validate(); frontier_check(); flux_table(); examples()
