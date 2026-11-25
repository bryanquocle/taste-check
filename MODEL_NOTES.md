# HFP Calculator v.2.3.1: Python model

A Python version of `HFP_Calculator_v.2.5.0.xlsx`. Claude can use it to evaluate
recipes without Excel. With the Python-only features off (`acidity=False`, `k_source="total"`),
it matches Excel's own calculation on 13 test recipes, all four outputs (max difference 1.4e-14).

## Files
- `hfp_model.py` is the model (standard-library Python, no extra packages).
- `hfp_raw_data.csv` is the ingredient database (374 ingredients), exported from the workbook's
  "Raw Data" sheet. **If you edit Raw Data in Excel, re-export this file.** Claude can do that.

## Usage
```
python hfp_model.py "Tomato (Canned)=200 g" "Sauce, Soy=15 mL" "Water=100 g"
python hfp_model.py --detail "Garlic=10 g" "Water=300 g"    # show intermediate values
python hfp_model.py --search miso                            # find exact ingredient names
python hfp_model.py --json recipe.json                       # [{"ingredient":..,"amount":..,"unit":..}]
python hfp_model.py --evaporate 1000 "..."                   # grams of water lost in cooking (Python only)
```
`--evaporate` is an extension the spreadsheet doesn't have. With it omitted (0), results match Excel.
Units: g, kg, mt, oz, lb, t (mass), and mL, cm3, L, m3, fl oz, cup, pt, qt, gal, tsp, tbsp
(volume, converted using the ingredient's density). Up to 10 ingredients matches the spreadsheet,
but the Python model has no limit.

## v.2.2.3 model changes (in both the workbook and Python)
- **Umami:** Raw Data are free acids, so above-threshold glutamate, aspartate and nucleotides are converted to
  Yamaguchi's salt forms (MSG·H₂O ×1.272, Na-Asp·H₂O ×1.300, Na₂IMP·7.5H₂O ×1.514, Na₂GMP·7H₂O ×1.468,
  Na₂AMP ×1.127) before the synergy equation. The factors are in Calculations!AE16:AI16.
- **Kokumi:** glutathione equivalents (GSH + 12.8×γ-EVG + 1.0×cysteine sulfoxides, by weight) on one Hill
  curve (EC50 0.912 mM, n 1.456, baseline removed). The constants are in Calculations!BC19:BG19.
  **Assumption (v.2.8.4):** 0.912 mM is not a receptor value (the GSH CaSR EC50 is 0.71 µM in the Koku book,
  76.5 nM in Ohsu 2010; 0.912 is most likely µM read as mM). It is kept as a sensory curve, checked only
  against human thresholds and single doses (Ueda 1997, Ohsu 2010, Goto 2016).
- **Tasted basis (v.2.8.5, Python/web; `TASTE_BASIS = "food"`):** Salt, sweet, umami, sour and kokumi use
  concentration per 100 g of FOOD (water-phase value × water/mass), like bitterness since v.2.8.3; pH stays
  water-phase. Pre-registered hold-out (43 low-water SVT foods, NEVO composition): saltiness rho 0.365 → 0.774,
  sweetness 0.457 → 0.840. The workbook stays on the water basis; the Excel harness must set
  `m.TASTE_BASIS = "water"`.
- **Synergy cap (v.2.8.4, Python/web):** 63× (Yamaguchi & Kimizuka 1979: 5 mM IMP lowers the MSG threshold
  63×), was 16× (a misread of Yamaguchi 1967). The workbook's Calculations!AF34 still holds 16.

## Outputs (same as the Dashboard)
- **Umami intensity** (Calculations!X22): umami × Na/K enhancement × kokumi modulation
- **Kokumi intensity (%)** (Calculations!AW28): glutathione + cysteine sulfoxides + γ-EVG, capped at 100
- **Saltiness intensity** (Calculations!AA25): Na + K saltiness × kokumi modulation

Concentrations are per 100 g of **water** in the recipe.

## Python-only rules (differ from the spreadsheet)
- **Potassium: chloride salts only** (`K_SALTINESS_SOURCE = "chloride"`, default). Only K from KCl, salt
  substitute and mineral salts (Celtic, Himalayan, Pink, Sea Salt) counts toward saltiness and the Na/K
  umami enhancement. Food potassium (citrate/malate) is excluded because the KCl curve doesn't apply to
  it. Set to `"total"` to match the spreadsheet exactly. *Open question: citrate/malate bitterness may
  depress saltiness.*
- **`--evaporate`**: water lost in cooking.
- **`--cook MIN --temp C`**: thermal loss of cysteine sulfoxides using alliin kinetics (Chen et al. 2017,
  Food Chem 223:25, 60–89 °C, pure alliin in 20% methanol), applied to the whole sulfoxide pool including
  isoalliin (Bryan's decision; no isoalliin data exist). Per ingredient in JSON: `"cook_min"` (e.g. 0 for
  an ingredient added at the end) and `"cys_loss_on_cut"` (0–1, alliinase conversion before heating;
  no default data).
- **Cooking-generated nucleotides:** when a mapped vegetable or mushroom is cooked at 65 °C or above (`--cook`,
  `--temp`, or per-item `cook_min`), its raw AMP/GMP are replaced by Nguyen et al. 1988 blanched+steamed values
  (e.g., button mushroom GMP 0.25 → 4.43 mg/100 g). Fresh shiitake is scaled from Nguyen's dried shiitake by
  dry matter. The list is in `COOKED_NUCLEOTIDES`.

## Acidity / pH model (v.2.3.0, Python only; `hfp_acidbase.py`; `ACIDITY_MODEL = True`)
- **pH:** charge-balance solver (Price et al. 2020) over 11 organic acids, Glu/Asp, nucleotide phosphates,
  a generic protein buffer, and Na⁺/K⁺/Cl⁻. Each ingredient is calibrated to its reference pH (Raw Data column AP,
  FDA/USDA *Approximate pH of Foods*); if there's no reference, it's calibrated at pH 6.0 and flagged.
  Checked against textbook values (acetic 2.88, citric 2.62, acetate buffer 4.76).
- **Sourness → citric-acid equivalents:** Neta et al. 2007 — sour stimulus S = [H⁺] + organic-acid molecules
  with ≥1 protonated carboxyl (all acids equally sour per mole). S is converted to the citric concentration
  giving the same S in Miranda's 50 mM MSG solution.
- **Umami suppression:** Miranda et al. 2021 (100/93/82/48% at 0/1.25/6.25/31.25 mM citric), fitted as a logistic
  in S (S50 29.4 mM, Hill 0.9). **Beyond S = 31 mM it's extrapolated** (flagged).
- **Synergy vs pH:** Yamaguchi 1979 Table VII (1.0 at pH ≤ 6.5 → 0.07 at 9.5). Not applied below pH 5.
- Glutamate ionization isn't applied separately (it's embedded in Miranda's measurements).
- Output: `res["acidity"]` = pH, sour stimulus, citric equivalent, umami factor, synergy factor.
- `acidity=False` reproduces the Excel workbook exactly.

## Data tiers and missing-data warnings (v.2.3.0)
- Tiers: 1 measured, 2 derived/sibling, 3 category estimate, 4 blank. The workbook's **Data Quality** sheet lists
  every tier-2/3 cell (tier-3 cells are amber in Raw Data); `hfp_data_quality.csv` is its export.
- Blank key fields count as 0. `compute()` warns when an ingredient that makes up ≥1% of the recipe mass has no
  glutamate data, no nucleotide data at all (only if Glu ≥ 100 mg/100 g), or no acid data while its pH is < 5.5.
  It also lists any tier-3 estimates used. Thresholds are at the top of `hfp_model.py`.

## Switch
`SODIUM_UMAMI_MODE` at the top of `hfp_model.py`: `"shift"` (default since v.2.2.3, matches the workbook:
salt raises the umami-equivalent concentration up to ×`SALT_SHIFT_MAX` = 2, a placeholder), `"enhancement"`
(v.2.2.2: intensity × (1 + effect)) or `"multiplier"` (v.2.2.1: intensity × effect).

See the workbook's **Change Log** sheet for all corrections and open items.

## Glutamate threshold and nucleotides (v.2.3.1, workbook and Python)
Nucleotides lower the glutamate/aspartate detection threshold. The threshold is divided by
min(63.2, 1 + 62.2 × IMP-eq / 5 mM), where IMP-eq = IMP + 0.18·AMP + 2.3·GMP (mM, free acids).
Source: Yamaguchi 2000 (J Nutr, Table 3), which reports the MSG threshold falling from 0.012% in water to 0.00019% in 5 mM IMP.
This replaces the older step rule (÷100 once IMP > 0.011 or GMP > 0.0056 g/100 g).
The constants are `GLU_THR_*` in `hfp_model.py`, and the formulas are in Calculations!U19/V19.

## Sweetness and sugar-acid interaction (v.2.4.0; `hfp_sweet.py`)
The base sweetness is in the workbook too (Calculations!BH:BZ, Dashboard L16). The two acid interactions below are Python only.
- **Sweetness** (Moskowitz 1970, Table 3): S = 0.54 · C^1.3, where C is the sucrose-equivalent % w/w of the sugar
  solution. Each sugar counts as RS^(1/1.3) × its concentration (RS: sucrose 1, fructose 0.91, glucose 0.45, lactose 0.22, …).
  On this scale 10% sucrose ≈ 10.8. Below the sucrose threshold (0.086%) sweetness is 0. Above 32% it is extrapolated (flagged).
  Maltotriose, mannose, erythritol, xylitol and uronic acids have no Moskowitz value, so they aren't counted (flagged).
- **Acid lowers sweetness** (Schifferstein & Frijters 1990, Fig. 4A): effective sugar = actual × q(citric-eq).
  q runs from 0.84 at 1.25 mM down to 0.65 at 10 mM, and is held at the 10 mM value above that.
- **Sugar lowers sourness** (Fig. 4B, 10 mM column): effective sour stimulus = S × g(sucrose-eq g/100 g water),
  with g = 0.48 at 4.4 g down to 0.17 at 43.6 g, interpolated linearly from (0, 1).
  With `SUGAR_SOUR_ON_UMAMI = True`, the effective S drives Miranda's umami suppression (an assumption).
- Both interactions are **effective concentrations**, taken from the paper's own unmixed curves, so no rating scale is mixed with another.
- Output: `results["sweetness_intensity"]`, plus details in `res["sweetness"]`.

## v.2.5.0: salt threshold rule off, and 1–10 scores (workbook and Python)
- The unsourced NaCl → umami threshold multipliers (×4 / ×8) are switched off (`SALT_THRESHOLD_RULE = False`; Calculations!Z37/AA37 = 1).
- Outputs are also reported as **1–10 scores**: 1 + 9·min(1, raw / reference). 1 means at or below threshold; 10 means the reference: umami 5% MSG-eq, saltiness 0.5 M NaCl, sweetness 10% sucrose, kokumi 100%, sourness 5% citric acid (~lemon juice; Python only, v.2.6.0: Neta stimulus → Yamaguchi 1979 tartaric curve).
- Python returns them in `res["scores"]`, and the workbook Dashboard shows them. Raw values are unchanged in `res["results"]` and in the Calculations sheet.

## v.2.8.0 (Nov 21, 2026): bitterness output (Python and web only; `hfp_bitter.py`)
- Caffeine and KCl only, on the Spectrum scale: caffeine 52.5*C^0.87 and KCl 4.37*C^0.68 (C = % w/v; Torrico &
  Prinyawiwatkul 2015 J Food Sci 80:S1885, Table 3, water). Caffeine ramps to 0 at its 1.2 mM threshold (Keast &
  Roper 2007). Score 10 = Spectrum 10 ~ 0.15% caffeine. Compounds add as caffeine-equivalents after sodium
  suppression: caffeine-type 0.755*Na/(Na+0.194 M), KCl 0.865*Na/(Na+0.023 M) (Breslin & Beauchamp 1995).
  Sugar suppression 0.75*x/(x+8), x = % sucrose-eq (placeholder, one point). K does not suppress bitterness.
- New column Caffeine (mg/100g); new rows: Coffee, Brewed; Espresso; Coffee, Instant (Powder); Tea, Black/Green
  (Brewed); Cocoa Powder (Unsweetened); Chocolate, Dark (70-85%); Cola (USDA SR Legacy).
- Outside checks (not used to fit): Chaiya 2026 KCl blends rho 0.88; Akgun 2019 tomato soup rho 0.89.
- Caveat: coffee, tea, cocoa and beer get most bitterness from other compounds, so they read low (noted on the page).

## v.2.7.0 (Nov 20, 2026): high-intensity sweeteners (Python and web only)
- New columns: Rebaudioside A, Mogroside V, Sucralose, Aspartame, Acesulfame K (mg/100g). New rows: Stevia Extract
  (Reb A 97/80/60/50%), Monk Fruit Extract (Mogroside V 55/50/40/25%), Sucralose, Aspartame, Acesulfame Potassium.
- Source: Wee, Tan & Forde 2018 (Nutrients 10:1632). Table 4 equi-sweet points (5/10/15% sucrose) interpolated
  log-log; below 5% the Table 3 slope n/1.31; above 15% held at 15% sucrose-eq and flagged. Grades scale by Reb A /
  mogroside V against Wee's material (68.0% Reb A; 50.6% mogroside V). Added to sugars' sucrose-eq (no synergy,
  bitterness or lingering). Not in the workbook: hfp_raw_data.csv rows/columns added by hand (re-exporting Raw Data
  from the workbook would drop them); Excel parity skips recipes containing them. 5 golden recipes added.

## v.2.6.3 (Nov 20, 2026): polyol sweetness from Wee et al. 2018
- Sorbitol, mannitol, erythritol and xylitol now use sweetness potencies from Wee, Tan & Forde 2018
  (Nutrients 10:1632, PMC6266678, CC BY), Table 4 at 10% sucrose: 0.72 / 0.68 / 0.75 / 1.01 sucrose-equivalents.
  Moskowitz 1970 had sorbitol 0.47 and mannitol 0.43 (as sucrose-eq factors) and no erythritol or xylitol, so
  sugar-free recipes scored near 1. Stored as potency^1.3, so RS^(1/1.3) equals Wee's potency exactly.
- Python `POLYOL_POTENCY_WEE2018` (`hfp_sweet.py`), web `RS` (`web/hfp_model.js`), workbook Calculations!BW19:BZ19
  (v.2.6.3). Other sugars unchanged. Tests: 2 polyol golden recipes added; run_tests, web parity and Excel parity PASS.
- Example: 10 g in 90 g water scores erythritol 7.2, sorbitol 6.8, mannitol 6.4, xylitol 10.0 (10% sucrose = 10).

## v.2.6.2 (Nov 15, 2026): wider umami scale, one source of truth, tests
- **Umami 10/10** is now 5% MSG-eq with the salt shift and kokumi gain at their maximum (raw 29.61; was the
  bare curve, 18.46), because the final umami value includes both boosts. Raw values are unchanged; every umami
  score is lower. Python `UMAMI_REF_WITH_BOOSTS`, web `SCORE_REF`, workbook Calculations!BK25 (v.2.6.2).
- **`hfp_model.py` is the source of truth.** Change it first, then mirror the change in `web/hfp_model.js` and
  the workbook, and run the checks below. The workbook mirrors the core formulas only (no acid model, no sourness).
- **Tests (`tests/`, standard library only):**
  - `python tests/run_tests.py`: 18 golden recipes and 12 outside tasting-panel sets against frozen values
    (`--freeze` only after an approved model change).
  - `python tests/web_parity.py`: web model vs Python on the golden recipes, raw values, scores and pH (needs Node).
  - `tests/excel_parity/`: `excel_cases.py` -> `excel_parity.ps1 -Path <scratch copy of the workbook>` ->
    `excel_compare.py`. Run it on a copy outside OneDrive; it sets manual calculation and never saves.

## Score ranges (Stage 2, Nov 15, 2026; Python only; `hfp_ranges.py`)
- `python hfp_model.py --ranges "<recipe>"` adds a range to each score, e.g. `UMAMI 7.6 (7.0 to 9.5)`: the score,
  then the middle 80% of 150 seeded re-runs (about 15 seconds).
- Redrawn in each re-run: ingredient data by tier (x/÷ 1.20 measured, 1.35 derived, 1.50 category estimate, 1.02
  for pure salt, sugar, MSG and KCl); blank glutamate and nucleotide cells between 0 and the category median
  (`hfp_categories.csv`, exported from the workbook's Inputs sheet); reference pH; and the placeholder constants
  (salt effect on umami 1 to 5.5, kokumi gains 0 to 0.90, synergy cap 31.5 to 126, kokumi EC50 and the acid
  suppression midpoint x0.5 to x2), each peaked at the model's value.
- A floor of +/-0.125 points is added, from the outside panels: score gaps of 0.25 or more agreed with the panel
  on direction in 310 of 319 pairs; smaller gaps in 20 of 76.
- The widths are proposals, not measurements. Not covered: anything the model leaves out, the curve shapes, the
  KCl and nucleotide-alone gaps. The web tool and workbook do not show ranges.
- Test: `python tests/ranges_test.py` (about 20 seconds).

## Formulation tools (Stage 3, Nov 15, 2026; Python only; `hfp_formulate.py`)
- **Compare:** `python hfp_formulate.py compare --a <recipe A> --b <recipe B>` reports B minus A for each taste and
  calls it real only if the scores differ by at least 0.25 points and the middle 80% of 150 paired re-runs stays
  on one side of zero. Both recipes get the same redraws (common random numbers), so shared uncertainty cancels.
  About 30 seconds for two simple recipes.
- **Solve:** `python hfp_formulate.py solve --taste saltiness --target 6.9 --vary "Salt" <recipe>` finds the grams
  of one ingredient that bring one taste to a target, re-runs the solved recipe and shows the side effects. It
  reports "cannot reach" or "no effect" instead of forcing an answer. It assumes the taste moves one way as the
  ingredient increases.
- **Known limit for sodium reduction:** in the model MSG raises saltiness only through its own sodium, so
  "how much MSG restores the saltiness" comes back as plain sodium arithmetic (no sodium saved). Stage 4.
- Test: `python tests/formulate_test.py` (about a minute).
