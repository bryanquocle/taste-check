# Pot water-loss estimator: sources and validation (Nov 25, 2026)

Saved by Claude from the helper's report (its tool blocked writing this file). Script: `cook_evap.py` (`python cook_evap.py` prints the validation and worked examples). Browser port: `web/cook_evap.js`; parity test: `tests/cook_evap_parity.py` (1,575 cases, worst 0.5 g). Shipped in Taste Check v.2.10.0.

## Model

- **Below a boil:** Shah 2014, ASHRAE Trans. 120(2) SE-14-001, p. 2, Eqs. 1–2 (final form of Shah 2012, Energy & Buildings 49:306); verified for water to 94 °C (Shah 2002, HVAC&R Research 8(1):125). E (kg/m²/h) = larger of `35 ρw (ρr − ρw)^(1/3) (Ww − Wr)` and `0.00005 (pw − pr)`. ρ = dry air per m³ moist air (1/v); W humidity ratio; p vapor pressure (Pa); w = saturated at the liquid temperature, r = room air (22 °C, 50% RH: ASSUMPTION). Saturation pressure: Hyland–Wexler (ASHRAE Fundamentals 2017 Ch. 1 Eq. 6). ρw·Ww is written as the vapor density so the formula stays finite near 100 °C.
- **Kitchen factor K** on the surface term: 1.3 (low 1.0, high 1.5). ASSUMPTION, calibrated on Opadokun 2019 and Boelter 1946.
- **At a boil:** blend 210 °F (all surface) → 212 °F (all boil). Boil rate = throttle × P_net / h_fg (h_fg 2,257 kJ/kg); throttle 0.75 (0.5–1.0, ASSUMPTION). P_net: medium burner 0.92 kW, large 1.79 kW (Frontier Energy 2019, report 501318071-R0 for SMUD, Tables 1–2: rated input × measured heat-up efficiency, mean of gas, ceramic and coil). Pots ≤ 20.5 cm across use the medium burner (ASSUMPTION). Boil rate never below Shah at 100 °C; surface rate never above the full burner.
- **Lid:** on 0.01 (0.003–0.08; Opadokun 2019 Table 4.1, Brundrett & Poultney 1979, Newborough & Probert 1987, Aprovecho/Berick); ajar 0.4 (0.25–0.6, ASSUMPTION, no data).
- **Pots:** 11 configurations (All-Clad D3, Le Creuset, Lodge specs; wok geometry ASSUMED). Saucepans, Dutch ovens and stockpots count at 25–80% full; skillets, sauté pan and wok at 10–80%, and only up to 1.5 L when no pot is picked. No fit → nearest pot. Flared pans use frustum geometry (surface shrinks as it reduces). 0.5-min time steps.
- **Output:** central = mean over fitting pots (mid settings); range = min (low settings) to max (high settings). Capped at 60% of the recipe's water (ASSUMPTION), with a warning.

## Validation

| Test | Measured | K = 1.0 | K = 1.3 |
|---|---|---|---|
| Shah 2014 Table 12 (code check, 10 cells) | — | 0.1% mean deviation | — |
| Opadokun 2019 Table 4.1: 28 cm pot, 90 °C, 45 min, lid off, 25/50/75% full | 834 / 897 / 995 g | −21 / −26 / −34% | +3 / −4 / −14% (mean abs 7%, a fit) |
| Boelter 1946 top point, 94.2 °C | 21.07 kg/m²/h | −20% | +4% |
| Frontier Table 5 simmer energy (lid and pot not stated) | 685–774 W | 770 W | 1,001 W |

Expect about ±30% in real kitchens. The cook's heat setting is the bigger unknown.

## Worked examples (K = 1.3)

- 1.2 kg tomato sauce, 30 min, 200 °F, lid off, 7 pots averaged: 428 g (36%), range 148–681 g. Saucepan only: 290 g. Lid ajar: 175 g.
- 3 kg stock, 2 h, 205 °F: lid off capped at 1,800 g with a warning; lid on 29 g.
- 400 g pan sauce, 5 min, skillet: 178 g at 212 °F (burner-limited); 73 g at 200 °F.

## Open questions

1. K = 1.3 vs 1.0 and lid ajar 0.4: a 30-minute home test (weigh a pot of water held at a probe-checked 200 °F, lid off, then ajar) would settle both.
2. Not modeled: skins on thick sauces, lower water activity, splatter, solids above the liquid.
3. Unread lead for a blind validation: Snitkjær et al. 2017, Food Chem 230:234 (volume over time in simmering pots; paywalled).

## Verified against the papers (Nov 25, 2026, Claude)

- **Shah 2014** (preprint, ASHRAE SE-14-001; Papers folder): p. 2 gives E0 as the larger of Eqs. 1–2 with C = 35 and b = 0.00005 (SI). Independent check of our code against all of Table 12 (p. 11; water 35–90 °C, air 30–50 °C, RH 30/70%): 113 cells, mean deviation 0.09%, max 1.1%. Table 1 (p. 3) confirms the Boelter et al. 1946 data: 0.073 m² pan, water 24.0–94.2 °C, evaporation up to 21.07 kg/m²·h.
- **Opadokun 2019** Table 4.1 (p. 47): lid off 833.6 / 896.8 / 994.6 g; lid on 9.2 / 7.9 / 3.0 g at 25 / 50 / 75% full. Matches what the model uses.
- **Frontier Energy 2019** p. 11: efficiencies 30.6, 31.9, 70.3, 79.3% as cited; p. 19: simmer defined as 205–210 °F.
