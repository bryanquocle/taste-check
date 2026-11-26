# Rebuild the Taste Check model

**Taste Check** (https://tools.mendocinofoodconsulting.com/taste-check/) predicts how salty, savory (umami), sweet, sour, bitter and rich (kokumi) a recipe should taste from its chemistry. This document is a complete specification of the model as it runs on the live page, written so that you, or you and your AI, can rebuild it from scratch and check that your version gives the same numbers.

- **Model version:** 2.11.0 (Nov 25, 2026: salt no longer raises umami, SALT_SHIFT_MAX 1.0; aspartate threshold sourced; cooking estimator lid factors fade at a boil). 2.10.0 (taste equations unchanged from 2.9.0; Nov 25, 2026: 824 ingredients, recipe-paste coverage of the 1,000 most common missing recipe ingredients, and a pot-based cooking water-loss estimator on the page). 2.9.0: sourced nucleotide thresholds, kokumi detection floor, Horie cooked GMP, saccharin. **Ingredient data:** the database embedded in the same page (824 research ingredients: workbook data release v.2.6.9, the bitterness and saccharin additions, and 392 composition rows from USDA FoodData Central SR Legacy 2018-04 added in v.2.10.0; section 13).
- **Source of truth:** the JavaScript embedded in the live page between the markers `/*HFP_DB:BEGIN*/ … /*HFP_DB:END*/` (database), `/*HFP_MODEL:BEGIN*/ … /*HFP_MODEL:END*/` (model) and `/*HFP_PASTE:BEGIN*/ … /*HFP_PASTE:END*/` (recipe paste parser). Where this document and that code disagree, the code wins, and that is a bug in this document.
- **Date:** November 25, 2026. **Author of the model:** Dr. Bryan Quoc Le, Mendocino Food Consulting (Human Flavorome Project).

Plain-language promise: every equation below is written in the units the code uses, every constant is listed in the register (section 12) with where it comes from, and every place where the model rests on an assumption, a fit made by the author, or a number with no known source is flagged. Nothing here is hidden behind "see the code": even the recipe paste parser's text-matching tables are published, in `paste_rules.csv`.

---

## 1. Purpose and scope

The model takes a recipe (ingredients and amounts, optional cooking) and returns six intensities, each also shown as a 1–10 score:

| Output | Raw scale | 10/10 reference |
|---|---|---|
| Umami | Yamaguchi's interval scale for MSG (1967) | 5 g/dL MSG-equivalent with the salt and kokumi boosts at their maximum (raw 26.0246 from v.2.11.0, when the salt boost became ×1; 29.61 in v.2.6.2–2.10.0) |
| Saltiness | Murphy et al. 1981 magnitude scale | 0.5 M NaCl, about 3% (seawater) (raw 10.13) |
| Sweetness | Moskowitz 1970 ratio scale | 10% w/w sucrose (raw 10.77) |
| Sourness | Yamaguchi 1979 tartaric-acid scale | 5% w/v citric acid in water, about straight lemon juice (raw 149.6) |
| Kokumi | % of the maximum response of the kokumi (calcium-sensing) receptor curve | 100% |
| Bitterness | Spectrum descriptive scale on Torrico & Prinyawiwatkul's panel | Spectrum 10, about 0.15% caffeine in water |

It also returns a predicted pH, salt and sugar concentrations in the liquid, and notes (warnings).

**In scope:** taste only, for foods eaten as served, best for watery foods (sauces, soups, broths, drinks). **Out of scope:** aroma, heat (capsaicin), texture, fat taste, astringency, temperature effects, saliva dilution, and bitterness from anything other than caffeine, theobromine, potassium chloride, rebaudioside A and acesulfame K.

The six raw scales come from different studies and are **not commensurable**: a saltiness of 6 and an umami of 6 are not "equally strong". The 1–10 scores make each output readable on its own; they do not make them comparable across tastes.

## 2. Files in this package

| File | What it is |
|---|---|
| `REBUILD.md` | This specification. |
| `hfp_ingredients_v2.10.0.csv` | The live ingredient database, exported from the page's HFP_DB block (section 13). SHA-256 (LF line endings, UTF-8): `c34dcac3ceced3336c6476d57f4a751d36d28652fb62bd1a4b4f38cfb3211d16` |
| `hfp_ingredient_provenance.csv` | Where ingredient values came from, where that was recorded: data-quality tier and basis per field, pH source and organic-acid source (section 13.4). |
| `test_recipes.json` | 53 recipes (38 project golden recipes + 15 added for this package) and 3 paste-parser cases, with expected outputs computed by executing the live page's JavaScript, plus tolerances (section 15). |
| `paste_rules.csv` | Every rule table and message of the recipe paste parser, exported programmatically from the live page (section 5.5). |
| `references.csv` | Every paper and dataset the model uses: DOI, open-access status, license, what it is used for, and whether it is hosted here or linked. |
| `papers/` | Copies of the openly licensed (CC BY 4.0) papers only (section 16). |
| `check_spec.py` | Standard-library Python check that every constant in the live model code is documented in this file with a source, and that the CSV hash matches. |
| `tools/oracle.js` | Node script that loads the model straight from a copy of the live page and regenerates `test_recipes.json`. |
| `tools/export_db.py` | Exports the page's database block to CSV (regenerates the ingredient CSV). |
| `tools/test_recipe_inputs.json` | The test recipes without expected values (input to the oracle). |
| `tools/export_paste_rules.js` | Node script that regenerates `paste_rules.csv` from a copy of the live page. |

To get the live page: `curl -L -o index.html https://tools.mendocinofoodconsulting.com/taste-check/`. The page is a single HTML file; the three marked blocks are plain JavaScript.

## 3. How to rebuild and verify (short version)

1. Read sections 4–11 and implement `compute(recipe, options)` in any language. Load ingredients from `hfp_ingredients_v2.10.0.csv` plus the two helper rows in section 5.2.
2. Run every recipe in `test_recipes.json` through your implementation and compare with `expected` using the tolerances in the file (raw outputs within 1e-6 relative, scores within 0.05, pH within 1e-4).
3. Two derived constants must come out the same as the reference: the Miranda logistic fit (S50 = 29.4 mM, Hill = 0.9; section 7.4) and the score references (section 10). They are printed in `test_recipes.json` under `derived_constants`. If yours differ, check the grid search and bisection details first.
4. Optional: `node tools/oracle.js index.html tools/test_recipe_inputs.json test_recipes.json` regenerates the expected values from a fresh copy of the live page; `python check_spec.py index.html` checks this document against that page.

## 4. Architecture overview

All taste-active compounds are summed over the recipe and first expressed as a concentration in the recipe's water (grams per 100 g of water, treated as g per 100 mL; called "water basis" below). The water basis is used for the chemistry (pH, buffering, the pH synergy factor). From v.2.8.5 every **tasted** concentration (salt, sweet, umami, sour, kokumi, and bitterness since v.2.8.3) is converted to a **whole-food basis** (per 100 g of food) by multiplying by `fb = total water / total mass` (constant TASTE_BASIS = "food"; section 5).

Order of computation in `compute()`:

1. Convert each ingredient amount to grams (section 5); look up its composition; apply cooking effects per ingredient (cooked nucleotides, thermal loss of cysteine sulfoxides).
2. For the pH model, convert each ingredient to molar species and calibrate a per-ingredient "unknown charge" term so the ingredient alone sits at its reference pH (section 7).
3. Sum masses, water and compounds; remove evaporated water (section 5.4).
4. Sugars → sucrose-equivalents (section 8.3) → sugar's suppression of sourness.
5. pH of the mixture by charge balance → sour stimulus → sourness, acid suppression of umami, pH factor on synergy (section 7).
6. Concentrations on the water basis; detection thresholds; umami equivalents with nucleotide synergy; saltiness from Na and chloride K; salt boost of umami; kokumi; kokumi boost of umami (section 8.1–8.5).
7. Sweetness with acid suppression (section 8.3).
8. Umami raises saltiness (Sun 2022); kokumi boost of saltiness (section 8.2).
9. Bitterness on the whole-food basis with sodium and sugar suppression (section 8.6).
10. Scores 1–10 (section 10); notes (section 11).

Notation: `ln` natural log, `log2` base-2 log, `clamp(x, a, b)` = min(max(x, a), b). "M" = mol/L of water, "mM" = mmol/L.

## 5. Inputs

### 5.1 Recipe items and options

A recipe is a list of items `{ingredient, amount, unit}`. Optional per-item fields: `cook_min` (overrides the recipe cooking time for that item, e.g. 0 for garlic added at the end) and `cys_loss_on_cut` (0–1, fraction of cysteine sulfoxides lost to enzymes when cut; no default data, the page never sets it).

Options (`opt`): `water_loss_g` (water evaporated, g; default 0), `cook_min` (default 0), `cook_temp_c` (°C; default none), `acidity` (default true; false skips the pH model, sourness becomes null and acid effects are off), `k_source` ("chloride", default: only potassium from chloride salts counts for saltiness; "total": all potassium counts). The page uses only `water_loss_g`, `cook_min` and `cook_temp_c`; `acidity` and `k_source` are API options covered by two test recipes.

**With `acidity: false`** the pH model is skipped entirely: no species or calibration are built, and the outputs are `pH = null`, `sour_stimulus_mM = 0`, `citric_equiv_mM = 0`, `umami_remaining = 1`, `synergy_pH_factor = 1` (so synergy is not reduced), sourness raw and score `null`, and the acid factor on sweetness `q = 1`. Sugar's effect on sourness is still computed internally but has nothing to act on. No `ph_default`, `sour_top` or `sour_umami_extrap` notes can fire. Every other output (umami, saltiness, sweetness, kokumi, bitterness, totals) is computed exactly as with acidity on, using these neutral values.

Ingredient names must match the database exactly (case-sensitive) or the model throws "Unknown ingredient". An unknown unit throws "Unknown unit".

### 5.2 Units and densities

The unit string is trimmed and lower-cased. Mass units are converted directly; volume units are converted to mL and multiplied by the ingredient's density (g/mL, column `density`).

| Unit | Factor | | Unit | Factor (mL) |
|---|---|---|---|---|
| g | 1 g | | ml | 1 |
| kg | 1000 g | | l | 1000 |
| oz | 28.35 g | | fl oz | 29.57 |
| lb | 453.59 g | | cup | 236.59 |
| | | | pt | 473.18 |
| | | | qt | 946.35 |
| | | | gal | 3785.41 |
| | | | tsp | 4.93 |
| | | | tbsp | 14.79 |

If an ingredient has density 0, a volume amount counts as 0 g and a note says so.

**Page helper rows.** The page adds two taste-neutral ingredients that are not in the research database, so weight still counts: **"Oil or fat"** (density 0.92 g/mL, water 0%) and **"Dried spices & herbs"** (density 0.5 g/mL, water 10%). Every other field is 0, ph_ref is none, blank fields = amp, gmp, imp, no tiers. Add them to your ingredient table.

### 5.3 Cooking

- **Cooked nucleotides** (Nguyen et al. 1988; Horie 2012 from v.2.9.0): for the 16 ingredients in the COOKED_NUC table (section 12.3), when the item's cooking time > 0 and the cooking temperature is unknown or ≥ 65 °C (nuclease activity), the raw AMP and GMP values are replaced by the cooked values (mg per 100 g of ingredient). Only AMP and GMP are replaced; IMP is not touched. A null cooked AMP (the five Horie rows: Horie measured GMP only) keeps the raw AMP.
- **Thermal loss of cysteine sulfoxides** (Chen et al. 2017, alliin kinetics, first order): fraction remaining `f = (1 − cut) × exp(−k × t)`, with `k = 4.38e17 × exp(−142494 / (8.314 × (T + 273.15)))` per minute, T in °C, t = item cooking minutes. If t = 0 or T is not given, the thermal factor is 1. Chen fitted 60–89 °C; outside that range a note says the loss is extrapolated. ASSUMPTION: alliin kinetics are applied to all cysteine sulfoxides (isoalliin, methiin), in pure solution, not tissue.
- The item cooking time is the item's own `cook_min` if present, otherwise the recipe `cook_min`.

**What the page does (v.2.10.0):** the cooking box takes minutes, a heat setting (bare simmer 195 °F, simmer 205 °F (default), rolling boil 212 °F), a pot type (or "not sure") and the lid (off, ajar, on). It passes `cook_min` and `cook_temp_c = (°F − 32) × 5/9` only when minutes > 0, and `water_loss_g` from the estimator in 5.3.1 (used only when it is above 0.5 g). An optional "cooked down by P% weight" box overrides the estimate (`water_loss_g = total mass × P/100`). Negative inputs are read as 0. Shared links store {m, t, r, p, l}; an older link's temperature snaps to the nearest heat setting. All three heat settings are above Chen's 60–89 °C range, so cooked recipes on the page carry the extrapolation note.

### 5.3.1 Cooking water-loss estimator (page, block HFP_COOK, v.2.10.0)

Not part of the taste model: it only sets `water_loss_g`. Inputs: recipe mass M (g, read as mL: ASSUMPTION 1 g/mL), minutes, liquid °F, pot type (optional), lid. Sources and validation: `validation/cook_evaporation/REPORT.md` in the model folder; Python reference `cook_evap.py`, parity with the page within 0.5 g on 1,575 cases.

1. **Surface flux** (Shah 2014, ASHRAE Trans. 120(2) SE-14-001, Eqs. 1–2; valid to 94 °C): `E = max(35 × Δρ^(1/3) × (ρv,w − ρda,w × Wr), 0.00005 × (pw − pr), 0)` kg/m²/h, with the liquid temperature capped at 99.97 °C; pw = saturation pressure at the liquid (Hyland–Wexler, ASHRAE Fundamentals 2017 Ch. 1 Eq. 6: `exp(−5.8002206e3/T + 1.3914993 − 4.8640239e−2 T + 4.1764768e−5 T² − 1.4452093e−8 T³ + 6.5459673 ln T)` Pa, T in K); room air ROOM_C 22 °C at ROOM_RH 0.50, pr = 0.5 × pws(22 °C); ρda = (101325 − pv)/(287.042 T), ρv = pv/(461.52 T), W = ρv/ρda; Δρ = max(ρda,room − ρda,w, 0).
2. **Rate in a pot** (g/min) at liquid volume V: surface area A(V) (cylinder: π(d/2)²; flared pan: frustum, solved for the liquid height by 60-step bisection); `surf = min(K × E × A × 1000/60, full)`, where `full = P_net × 1000/2.257e6 × 1000 × 60` and P_net = 0.92 kW if the pot's top diameter ≤ 20.5 cm, else 1.79 kW (Frontier Energy 2019, SMUD report 501318071-R0, Tables 1–2). Boil weight `w = clamp((°F − 210)/2, 0, 1)`; `boil = max(throttle × full, E(100 °C) × A × 1000/60)`; rate = `(1 − w) surf + w boil`, times the lid factor.
3. **Settings** (central / low / high): K 1.3 / 1.0 / 1.5 (ASSUMPTION, calibrated on Opadokun 2019 and Boelter 1946); throttle 0.75 / 0.5 / 1.0 (ASSUMPTION); lid off 1, ajar 0.4 / 0.25 / 0.6 (ASSUMPTION), on 0.01 / 0.003 / 0.08 (Opadokun 2019; Brundrett & Poultney 1979; Newborough & Probert 1987; Aprovecho/Berick). **At a boil (v.2.11.0, LID_BOIL):** the lid factor blends with the boil weight w to on 0.85 / 0.6 / 1.0 (Snitkjær et al. 2017, Food Chem, Fig. 3b: a lidded pot at a boil lost ~85% as much as an open one) and ajar 0.9 / 0.7 / 1.0 (ASSUMPTION): `lid = (1 − w) × LID + w × LID_BOIL`.
4. **Time stepping:** 0.5-minute steps; the volume falls by each step's loss.
5. **Pots** (name, type, capacity L, top/bottom diameter cm, depth cm; IN = 2.54, QT = 0.946353): Saucepan 2 qt (2 QT, 6 in, 6 in, 4.5 in); Saucepan 3 qt (3 QT, 8.5 in, 8.5 in, 4 in); Sauté pan 3 qt (3 QT, 10.5 in, 10.5 in, 4 in); Skillet 10 in (frustum, 10.5 in, 8 in, 2 in); Skillet 12 in (frustum, 12.2 in, 9.125 in, 2.25 in); Wok 14 in (frustum, 14 in, 6 in, 4 in; ASSUMED); Dutch oven 3.5, 5.5, 7.25 QT (22, 26, 28 cm); Stockpot 8 QT (11.5 in); Stockpot 15 L (28 cm). Sources: All-Clad D3 and Le Creuset specs (Williams-Sonoma), Lodge (dimensions.com, Abt).
6. **Which pots:** saucepan, Dutch oven, stockpot when 25–80% full; skillet, sauté pan, wok when 10–80% full and, with no pot picked, only up to PAN_MAX_L 1.5 L. If none fits, the pot whose fill is nearest the window. All ASSUMPTION.
7. **Output:** central = mean over the fitting pots at central settings; low = minimum at low settings; high = maximum at high settings; each capped at CAP_FRAC 0.6 × recipe water (ASSUMPTION), with a page message when the central estimate hits the cap.

Validation (REPORT.md): Shah Table 12 reproduced to 0.1%; Opadokun 2019 (28 cm pot, 90 °C, 45 min) −21 to −34% at K = 1.0 and −14 to +3% at K = 1.3 (a fit); expect about ±30% in real kitchens.

### 5.4 Evaporation (cooking down)

`water_loss_g` is subtracted from both total water and total mass after all ingredients are summed. If it is ≥ the recipe's water, the model throws an error. **The page** sets `water_loss_g = P/100 × total mass`, where total mass is computed first with no options. All concentrations use the water left after evaporation. The pH calibration of each ingredient (section 7.3) uses that ingredient's own water, before evaporation.

If total water is ≤ 0 after evaporation, the model throws "This recipe has no water".

### 5.5 Pasting a recipe (page input helper)

The page's "paste a whole recipe" box turns free-text lines into recipe items. It is not part of the taste model, but it decides what goes into it. **Every rule table is published in `paste_rules.csv`**, exported programmatically from the live page's HFP_PASTE block by `tools/export_paste_rules.js` (the script runs the page's own parser code in a sandbox and dumps its tables; nothing is retyped). Tables in the CSV (column `table`): FRAC (unicode fractions), NUMBER/QTY/SIZE (quantity and package-size regular expressions), UNITS (28 unit-word patterns → unit, first match wins, including synonyms such as ounce/ounces, cups, shots, tbs, T vs t), MAP (227 text patterns → database name, in order; first match wins), SKIP_FIRST, SKIP, HEADER, DESCRIPT, GUARDED, EACH_G, UNIT_G, CAN_G, VOL, APPROX_NOTE, and MESSAGE (every status/note text in the parser). Regex columns hold the JavaScript source and flags (all case-insensitive except NUMBER and DESCRIPT, which has the `g` flag).

**v.2.10.0 additions:** the parser now reads the 1,000 most common RecipeNLG ingredients that were missing (validation/missing_ingredients): rules between `/*AUTO_PHRASES*/` (multi-word names, longest first, top of MAP) and `/*AUTO_SINGLE*/` (one-word names anchored to the whole line, so "green pepper" can never hit a one-word "pepper" rule) are generated from that list by `gen_paste_rules.py`; `/*AUTO_EACH*/` adds per-piece weights from USDA SR portions (1 medium / large / whole). Fixes: "mayo" (a `\b` escape bug), baking soda and powder (no longer skipped; they carry sodium), white wine vinegar (approximate: red wine vinegar), red and bell peppers ("1/2 tsp red pepper" = crushed red pepper via `Red Sweet Pepper|spice-if-spoon`), heavy cream, sherry (cooking wine, approximate). Pasta, rice, bread, zest and yeast are no longer skipped. Refusal messages that new rows made out of date were rewritten as matches.

MAP values: a plain name = match; `name*` = approximate match (status `approx`, note = APPROX_NOTE[name] or "closest match"); `!reason` = refuse the line (status `none`, note = the reason); `BLEND` = refuse as a tabletop blend; `Tomato (Canned)|fresh-if-count` = use "Tomato, Red (Fresh, Whole)" when the line has no unit (or unit `each`) and no package size; `Fish, Salmon (Fresh)|canned-if-can` = use "Fish, Salmon (Canned)" when the unit is can, jar or pkg or a package size is given; `Red Sweet Pepper|spice-if-spoon` = use "Spice, Red Pepper Flakes (Dried)" when the unit is tsp, tbsp or pinch and no package size is given.

**parseLine(line)** → {qty, unit, size, text}:
1. Replace each FRAC character by its value (e.g. "½" → " 1/2"); strip leading spaces, hyphens, en dashes, bullets, asterisks and middle dots; collapse whitespace; trim.
2. Replace a leading "(a |one )pinch/dash(es) of " with "1 pinch ".
3. QTY at the start: a number (`a b/c`, `b/c` or decimal), optionally a range with "-", "–" or "to"; a range gives the midpoint. Remove it.
4. SIZE in parentheses right after: number (optionally a range, first value used) and ounce/oz/fl oz (× 28.35), lb/pound (× 453.59), g/gram or ml (× 1); remove it.
5. UNITS: test each pattern in order against `text + " "`; the first match sets the unit and is removed.
6. Trim; remove a leading "of "; lower-case → `text`.

**parse(text)**, for each line (trimmed; empty lines and HEADER lines are dropped):
1. If `text` is empty → status `none`, "no ingredient name". If it contains "bone(s)" or "carcass" → `skip` with the bones message.
2. `first` = the part of `text` before the first " or " / " (or "; `bare` = `first` with parenthesized parts removed (empty → `first`).
3. If SKIP_FIRST matches `bare` → `skip`, "barely affects these tastes".
4. name = first MAP match on `bare`, else on `first`.
5. If no name and `first` differs from `text`: if SKIP matches `bare` → `skip`; else try the search guess (step 9) on `first`.
6. If still no name: first MAP match on the full `text`.
7. `!reason` → `none` with the reason; `BLEND` → `none` with the blend message.
8. If still no name and SKIP matches `text` → `skip`.
9. If still no name: search guess on `text`. Guess = take the text before the first comma, remove parenthesized parts and DESCRIPT words, collapse spaces, run the ingredient search (5.6) with limit 1. Reject the hit if it matches GUARDED unless the cleaned text contains a word of the hit longer than 3 letters other than fruit/salt/extract. A guess gets status `guess` and note "best guess: NAME".
10. No name → `none`, "not in the database".
11. "Peanut Butter, Salted" / "Potato Chips, Salted" become ", Unsalted" when `text` matches `\bunsalted\b|\bno[- ]salt|\bsalt[- ]free\b|without salt` (case-insensitive).
12. If the base name (without `*` or `|…`) is not in the database → `none`, "not in the database".
13. toItem (below). A successful guess keeps status `guess` and its note; otherwise toItem's status and note are used.

**toItem(p, name)**: no quantity → `skip`, "no amount (\"to taste\")". Apply the `|fresh-if-count` / `|canned-if-can` rules; then "Tomato, Red (Fresh, Whole)" becomes "Tomato (Canned)" when a size is given or the unit is can or jar. Grams: size given → qty × size; oz → × 28.35; lb → × 453.59; g; kg → × 1000. Volume units (VOL): if the ingredient's density is not > 0 → `none` ("no cup or spoon conversion…"); else pass `[name, round(qty × multiplier, 3), unit]` with pt → 2 cup and qt → 4 cup. can/jar/pkg → qty × CAN_G[name] (unknown → `none`, "don't know the UNIT size"). scoop → qty × 0.025 g for names starting "Stevia", else `none`. shot → qty × 29.6 g. inch → `none`. UNIT_G units → qty × grams. No unit or `each` → qty × EACH_G[name] (unknown → `none`, "add a weight or cup/spoon amount"). Grams are rounded to 3 decimals below 1 g, else 1 decimal (JavaScript `toFixed`, then converted back to a number). Status `approx` for `*` names, else `ok`.

Output per line: `{line, status, item: [name, amount, unit] | null, note}`.

### 5.6 Ingredient search (used by the page picker and the paste fallback)

Split the query on spaces, commas and parentheses; keep names containing every word (case-insensitive). Score = −100 if the name equals the query, −10 if it starts with the first word, −5 if the first word starts a word in the name, plus name length / 100; sort ascending; return the first 12 (or the requested limit).

## 6. Concentration basis

For each ingredient row (mass m g): water `w = m × water/100`; each compound X in mg = `m/100 × d[X]` for X in KEYS = glu, asp, amp, imp, gmp, na, k, gsh, cys, evg, caf, tb. Chloride potassium `k_cl` accumulates `k` only for the CHLORIDE_K ingredients (Potassium Chloride, Salt Substitute, Celtic Salt, Himalayan Salt, Pink Salt, Sea Salt). Sugars accumulate in mg per sugar.

Water-basis concentration (g per 100 g water, used as g/100 mL = g/dL): `conc_w[X] = (total_mg[X] / 1000) / (total_water_g / 100)`. Sugars likewise: `sugars[s] = (mg/1000)/(water/100)`.

**Tasted basis (v.2.8.5):** `fFood = total water / total mass` (after evaporation); `fb = fFood` when TASTE_BASIS = "food" (the live value), `fb = 1` for the pre-2.8.5 water basis. Every tasted concentration used from section 7 on is `conc[X] = conc_w[X] × fb`; sugars for sweetness are `sugF[s] = sugars[s] × fFood` with `sucF = sucrose_eq(sugF)` (g sucrose-eq per 100 g food = % w/w; for a plain sugar solution this equals the old `pct(sucrose_eq, T)` exactly). Source: Stark, Bareuther & Hofmann 2006 dose-over-threshold convention (per kg of food), already used for bitterness; validated on a pre-registered hold-out of 43 low-water SVT foods (saltiness rho 0.365 → 0.774, sweetness 0.457 → 0.840).

ASSUMPTION (central to the model): 1 g water = 1 mL; the chemistry happens in the recipe's water, but what is tasted is the solute per 100 g of food (the whole food is diluted in the mouth). Before v.2.8.5 solids were tasted as if their solutes were in the dish's water, which inflated low-water foods (section 14).

## 7. Acid–base chemistry and pH

### 7.1 Species

Per ingredient of mass m (mmol unless noted): organic acid a: `acid_a mg/100 g × m/100 / MW_a`; glutamate and aspartate: `mg × m/100 / MW` (MW 147.13, 133.10); nucleotides: `Σ (row amp/imp/gmp mg after cooking) / MW` (MW AMP 347.22, IMP 348.21, GMP 363.22); Na = mg/22.99; K = mg/39.0983; chloride Cl = Na + K only for CHLORIDE_SALTS names (Salt, Kosher Salt, Sea Salt, Table Salt, Canning Salt, Pickling Salt, Iodized Salt, Celtic Salt, Himalayan Salt, Pink Salt, Sodium Chloride, Potassium Chloride, Salt Substitute); protein in grams = `protein g/100 g × m/100`. Molar concentration = mmol / 1000 / L water (protein as g/L).

| Acid | MW | pKa (charge) | pKa counted for sourness |
|---|---|---|---|
| citric | 192.12 | 3.13, 4.76, 6.40 | all three |
| malic | 134.09 | 3.40, 5.11 | both |
| tartaric | 150.09 | 2.98, 4.34 | both |
| lactic | 90.08 | 3.86 | |
| acetic | 60.05 | 4.76 | |
| ascorbic | 176.12 | 4.10, 11.6 | 4.10 only |
| oxalic | 90.03 | 1.25, 4.14 | both |
| quinic | 192.17 | 3.46 | |
| malonic | 104.06 | 2.83, 5.69 | both |
| fumaric | 116.07 | 3.03, 4.44 | both |
| succinic | 118.09 | 4.21, 5.64 | both |
| pyroglutamic | 129.11 | 3.32 | |
| formic | 46.03 | 3.75 | |

Amino acids (fully protonated form carries +1): glutamate pKa 2.19, 4.25, 9.67; aspartate 1.99, 3.90, 9.90. Nucleotides: primary phosphate always ionized (−1) plus a second phosphate with pKa 6.2. Generic protein buffer (per g protein): acidic groups 1.00 mmol, pKa 4.2 (charge −1 when deprotonated); histidine 0.20 mmol, pKa 6.3 (+1 when protonated); basic groups 0.90 mmol, pKa 10.5 (+1 when protonated). Kw = 1e-14. No ionic-strength or temperature correction (pKa at 25 °C, I = 0).

### 7.2 Charge balance and solver

Ionization fractions for an acid with pKa list p₁…pₙ at [H⁺] = h: `t₀ = 1, tₖ = tₖ₋₁ × 10^(−pₖ) / h`, `αₖ = tₖ / Σt` (α_k = fraction that has lost k protons).

Net charge (mol/L), excluding H⁺/OH⁻:
`q = Na + K − Cl − Σ_acids c_a × Σ_k k·α_k + Σ_amino c × Σ_k (1−k)·α_k − nuc × (1 + α₁(pKa 6.2)) + Σ_protein-groups [c_g × (−α₁ if acidic, (1 − α₁) if basic)]`, with `c_g = protein (g/L) × mmol/g / 1000`.

pH solves `f(pH) = 10^−pH − Kw/10^−pH + q(10^−pH) + Z = 0` by **bisection on [0, 14], 80 iterations** (if f(mid) > 0 then lo = mid, else hi = mid); the answer is (lo + hi)/2. Z is the summed calibration charge (7.3) in mol/L.

### 7.3 Per-ingredient calibration (unknown charge Z)

Each ingredient carries an unknown net strong-ion charge chosen so that the ingredient alone, dissolved in its own water, sits at its reference pH (column `ph_ref`, mostly FDA "Approximate pH of Foods" midpoints).

- If `ph_ref` is missing (null): the code tests `charged = (some species other than cl has a non-zero value) AND (name is not in CHLORIDE_SALTS)`, over the ingredient's species {each organic acid, glu, asp, nuc, na, k, protein_g} (nuc is the row's nucleotide mmol, after cooking). If not charged, Z = 0 and nothing is flagged. If charged, pH 6.0 is used and the ingredient is named in the `ph_default` note (ASSUMPTION). In practice almost every food is "charged", because any sodium, potassium or protein counts. `ph_ref = 0` would also count as missing (none in the database).
- Water volume for calibration: the code computes `wL = max(water_g, mass_g) / 1000` L. Because an ingredient's water can never exceed its mass, this always equals **`mass_g / 1000`**: each ingredient is calibrated as if its whole mass were water (for a dry ingredient, as if dissolved in an equal mass of water). ASSUMPTION.
- The calibration is only done for items with mass > 0 when acidity is on.
- `Z_i (mmol) = −(h − Kw/h + q(h)) × wL × 1000` at `h = 10^−ph_ref`, using that ingredient's species in molar terms.
- Mixture: `Z = Σ Z_i / 1000 / (total water L)`.

This follows the spirit of Price et al. 2020 and Longtin et al. 2020 (charge balance with corrections for undefined buffers); the per-ingredient calibration is the author's construction.

### 7.4 Sour stimulus, citric equivalents and acid suppression of umami

**Sour stimulus** (Neta et al. 2007, restated in Neta 2009), computed from the water-phase species and pH and then multiplied by `fb` (v.2.8.5) to give the tasted stimulus S used everywhere below: `S (mM) = fb × (1000 × [H⁺] + Σ_acids 1000 × c_a × (1 − α_last))`, where α_last is the fully deprotonated fraction computed with the sourness pKa list (so ascorbic counts only its first pKa). All protonated acid molecules and H⁺ count equally.

**Miranda calibration** (Miranda et al. 2021, n = 734, gVAS 0–100): a solution of 50 mM glutamate + 50 mM Na + citric acid at 0, 1.25, 6.25, 31.25 mM gives umami remaining `1, 1 − 2.886/39.756, 1 − 7.211/39.756, 1 − 20.654/39.756` (92.7, 81.9, 48.0%; 39.756 is the mixed-model intercept and the others are the citric-acid coefficients of their Table 1). For each point the model solves the pH of that solution (7.2, Z = 0) and its sour stimulus, giving S ≈ 0.00011, 1.122, 6.164, 31.33 mM. A logistic `R(S) = 1 / (1 + (S/S50)^H)` is fitted by **grid search**: S50 = x/10 for integer x from 5 to 399, H = y/50 for integer y from 10 to 199 (x outer loop, y inner), minimizing the sum of squared errors over the three acid points; the first strict minimum wins. Result: **S50 = 29.4 mM, H = 0.9**. `umami_remaining(S) = 1` if S ≤ 0. The largest calibrated stimulus (31.33 mM) is MIRANDA_S_MAX; above it a note says the effect is extrapolated.

**Citric equivalent:** the citric acid concentration (mM) in Miranda's solution with the same sour stimulus, by bisection on [0, 2000] mM, 60 iterations (if the solution's stimulus at the midpoint is < S then lo = mid, else hi = mid; answer (lo + hi)/2). It uses the **raw stimulus S, before sugar softening** (in the code: `citricEquivalent_mM(s)`, not `s × sourRem`). It drives acid's suppression of sweetness (8.3).

**Sugar softens sourness and its effect on umami:** `S_eff = S × sour_remaining(sucrose-eq)` (8.3). Umami suppression uses S_eff (ASSUMPTION: acid dulls umami through perceived sourness).

### 7.5 pH factor on nucleotide synergy (Yamaguchi 1979 Table VII)

Linear interpolation through (pH 6.5, 1.0), (7.5, 0.535), (8.5, 0.341), (9.5, 0.070); 1.0 at pH ≤ 6.5; 0.070 at pH ≥ 9.5. Measured in histidine buffer only.

## 8. The six outputs

### 8.1 Umami

Concentrations below are g/100 mL on the water basis, free acids as stored in the database.

1. **Glutamate threshold lowered by nucleotides.** IMP-equivalents in mM: `IMPeq = 1e4 × (imp/348.21 + 0.18 × amp/347.22 + 2.3 × gmp/363.22)`. Divisor `D = min(63.16, 1 + (63.16 − 1) × IMPeq / 5)`, with 63.16 = 0.012/0.00019 (Yamaguchi & Ninomiya 2000 Table 3: MSG threshold 0.012% in water, 0.00019% in 5 mM IMP). Thresholds: glutamate `0.01 / D`, aspartate `0.0166 / D`.
2. Glutamate u = conc.glu if above its threshold, else 0; aspartate v likewise.
3. **Nucleotide thresholds** (v.2.9.0, NUC_THRESHOLD_MODE "kuninaka"): if u > 0 (glutamate above its own, nucleotide-lowered threshold) every nucleotide threshold is 0, because synergy is already gated by step 1 and IMP may have no intrinsic umami of its own (Yamaguchi & Ninomiya 2000 p. 923S). Otherwise (nucleotide-alone path) IMP `NUC_THR_IMP = 0.387 × 348.21 / 1e4`, GMP `NUC_THR_GMP = 0.206 × 363.22 / 1e4` (Kuninaka 1980 Table I, mM in distilled water), AMP `NUC_THR_IMP / 0.18` (ASSUMPTION: no human AMP threshold found). Each nucleotide counts only above its threshold (w = AMP, x = IMP, y = GMP). Before v.2.9.0 three unsourced tiers were used (section 14, item 2).
4. **Salt-form conversion** (Yamaguchi's constants are for the sodium salts): glu × 187.13/147.13 (MSG·H₂O), asp × 173.10/133.10, IMP × 527.28/348.21 (Na₂IMP·7.5H₂O), GMP × 533.29/363.22 (Na₂GMP·7H₂O), AMP × 391.18/347.22 (Na₂AMP).
5. **Umami equivalents** (Yamaguchi 1967 synergy equation y = u + γuv, written as a fold): `U = SF_glu·u + 0.077 × SF_asp·v`; `syn = 219·SF_amp·w + 1218·SF_imp·x + 2800·SF_gmp·y`; `fold = min(1 + syn × pHfactor, 63)`; nucleotide-alone term `fold_IG = min(1 + (1218·SF_imp·x + 2800·SF_gmp·y) × pHfactor, 63)`; `umami_eq = U × fold + (0.05/15) × (fold_IG − 1)` in g/dL MSG·H₂O-equivalent. The last term lets IMP/GMP alone taste of umami as if acting on a fixed background glutamate of 0.05/15 g/dL (calibrated so 0.05 g/dL IMP alone ≈ 0.05 g/dL MSG; AMP excluded).
6. **Salt shift** (shape from dog chorda tympani, Ugawa & Kurihara 1994): `x = Na(M) + 0.81 × K(M)` (the Na and K molarities of 8.2, after thresholds); `R = max(0, −37.089x² + 9.9621x − 0.038)` if x < 0.1, else `max(0, −0.6351x + 0.6414)`; `shift = 1 + (SALT_SHIFT_MAX − 1) × min(1, R / 0.5828)` with SALT_SHIFT_MAX = 1.0 from v.2.11.0, so shift = 1 (no salt effect on umami). The formula is kept so a sensitivity value can be set. Before v.2.11.0 the maximum was ×2, a placeholder from dog nerve data.
7. **Intensity:** `I = max(0, 3.6672 × ln(umami_eq × shift) + 12.555)` if umami_eq > 0, else 0 (fit to Yamaguchi 1967 Fig. 2; zero at about 0.0326 g/dL).
8. **Acid:** `I × umami_remaining(S_eff)` (7.4).
9. **Kokumi boost:** `umami = I × (1 + 0.41 × kokumi/100)` (8.5).

Reported total `umami_eq_msg_pct = umami_eq × shift`.

### 8.2 Saltiness

1. **Detection thresholds** as the cation (g/100 mL): Na `0.0037 × 22.99/58.44` (NaCl 0.0037 g/100 mL, Yamaguchi 1979 Table III); K `0.00242 × 39.0983/10` (KCl 0.00242 M, Schiffman et al. 1995). Below threshold the molarity is 0.
2. **Molarity:** `Na(M) = conc.na × 10 / 23` (note: 23, not 22.99, in this step); `K(M) = conc_K × 10 / 39.0983`, where conc_K = chloride potassium (default) or all potassium (`k_source = "total"`).
3. **Sodium curve** (Murphy et al. 1981, fit): `I_Na = max(0, 2.7036 × ln(Na) + 12.008)`. Measured range 0.004–0.108 M; a note flags Na > 0.108 M as extrapolated.
4. **Potassium curve:** for K ≤ 0.112 M, `I_K = max(0, 404.88K² + 6.7462K − 0.1344)`; above, the Na curve scaled to meet the KCl fit at 0.112 M: `I_K = [I_K(0.112) / (2.7036 ln 0.112 + 12.008)] × (2.7036 ln K + 12.008)`, with a note.
5. **Mixing Na and K** (concentration addition, after Bartoshuk 1975): if I_K > 0, convert it to the iso-salty NaCl molarity `exp((I_K − 12.008)/2.7036)`, add to Na and read the Na curve once: `I = max(0, 2.7036 ln(Na + exp((I_K − 12.008)/2.7036)) + 12.008)`; otherwise I = I_Na.
6. **Umami raises saltiness** (Sun et al. 2022, fit by the author to their Table 2): if Na > 0: `s = clamp((umami score − 1)/(2.4 − 1), 0, 1)` using the final umami score (section 10); `f = 1` if Na ≤ 75 mM, else `max(0, (260 − Na_mM)/(260 − 75))`; `E = 0.10 × s × f`; if E > 0 the effective sodium is `Na × (1 + E)` and step 5 is repeated with it.
7. **Kokumi boost:** `saltiness = I × (1 + 0.41 × kokumi/100)`.

Reported `salt_pct_water = Na(M) × 58.44 / 10` (NaCl-equivalent %, sodium only).

### 8.3 Sweetness

1. **Sucrose equivalents** (g per 100 g water): for each sugar s with g > 0:
   - bulk sugars with a relative sweetness RS (Moskowitz 1970 Table 3, % w/w, exponent 1.3): `RS^(1/1.3) × g`. RS: sucrose 1.00, fructose 0.91, glucose 0.45, galactose 0.42, glycerol 0.50, arabinose 0.39, xylose 0.26, maltose 0.31, lactose 0.22. Polyols and allulose use Wee et al. 2018 potencies p at 10% sucrose, stored as `RS = p^1.3` so that the factor equals p: sorbitol 0.72, mannitol 0.68, erythritol 0.75, xylitol 1.01, allulose 0.75, maltitol 0.89.
   - high-intensity sweeteners (Wee 2018 Tables 3–4). Units: Wee's concentrations are % w/v; the model uses them unchanged as g per 100 g water (and, for bitterness masking in 8.6, g per 100 g food). `c = g / purity` (purity of Wee's material: Reb A extract 0.680, mogroside V extract 0.506, others 1.0). Equi-sweet points xs (% w/v) for sucrose ys = 5, 10, 15: Reb A [0.0144, 0.0395, 0.0828], mogroside V [0.0191, 0.0694, 0.141], sucralose [0.0096, 0.0387, 0.0748], aspartame [0.0290, 0.0827, 0.134], acesulfame K [0.0293, 0.0832, 0.170]. If c < xs₀: `5 × (c/xs₀)^(n/1.31)` with exponents n = 0.71, 0.70, 0.65, 0.84, 0.68 respectively (sucrose 1.31); between points (xs₀ ≤ c ≤ xs₂): log-log interpolation; above xs₂ (strictly c > xs₂): held at 15 and the sweetener is listed in the `his_high` note.
   - **saccharin** (v.2.9.0; field = anhydrous sodium saccharin): Wee 2018 did not test it, so it uses its own equi-sweet points from Schiffman et al. 1995 Table 2 p. 512 at HIS_LEVELS 2, 5, 10% sucrose: [0.00392, 0.01126, 0.0405] % w/v, purity 1.0, low-end exponent n = 0.868 × 1.31 (so `2 × (c/0.00392)^0.868` below the first point), log-log interpolation between points, and a cap HIS_CAP = 9.0% sucrose-eq (Schiffman Table 1 reads 7.97–9.04% from 0.04 to 0.096%: a plateau). Above the cap the value is held at 9.0 and listed in the `his_high` note. ASSUMPTION: cross-study offset vs the Wee-based sweeteners about ±25%.
   - maltotriose, mannose and uronic acids have no sweetness value: not counted; a note lists them if ≥ 1% of total sugar.
   - Mixtures add sucrose-equivalents (equivalent-concentration additivity, ASSUMPTION).
2. **Sugar lowers sourness** (Schifferstein & Frijters 1990, 10 mM citric column): `sour_remaining(x)` piecewise-linear through (0, 1) and SOUR_PTS, held beyond the last point, x = sucrose-eq g/100 g water. From v.2.8.5 (food basis) `x = 100 × sucF / (100 − min(sucF, 99))`, the sugar-water equivalent of the food-basis sucrose-eq (identical for plain sugar solutions, bounded for low-water foods); with fb = 1 x is the water-basis sucrose-eq. SOUR_PTS (x, factor) = (4.4, 0.4828), (9.06, 0.3534), (19.2, 0.2586), (43.6, 0.1685), each computed as `invert(SF_SOUR_MIX10[i], SF_CIT, SF_SOUR_UNMIXED) / 10`.
3. **Acid lowers sweetness:** `q(citric-eq mM)` piecewise-linear through (0, 1) and SWEET_Q, clamped to [0, 10] mM. SWEET_Q = (1.25, 0.8361), (2.5, 0.8159), (5, 0.7417), (10, 0.6521); each value is the mean over the four sucrose levels i of `invert(SF_SWEET_MIX[c][i], SF_SUC_M, SF_SWEET_UNMIXED) / SF_SUC_M[i]`. q = 1 when acidity is off.
   - `invert(y, xs, ys)`: piecewise-linear inverse through (0, 0) and the points (xs, ys): find the first segment with y ≤ y₁ and interpolate; beyond the last point return the last x.
   - Digitized data (Schifferstein & Frijters Figs. 3–4): sucrose SF_SUC_M = 0.125, 0.25, 0.5, 1.0 M (= SF_SUC_G 4.40, 9.06, 19.2, 43.6 g per 100 g water); citric SF_CIT = 1.25, 2.5, 5.0, 10.0 mM; sweetness unmixed 24, 45, 79, 111; sweetness in mixtures {1.25: 19.5, 38, 67, 103; 2.5: 19.5, 38, 70, 95; 5: 15, 36.5, 65, 95; 10: 11.5, 28.5, 63.5, 95}; sourness unmixed 27, 50, 79, 105; sourness at 10 mM citric across the four sucrose levels 77, 62, 51, 35.
4. **Concentration % w/w:** `pct(g, T) = 100 g / (100 + T)`, where T = total of all 23 sugar fields (g per 100 g water). `C_eq = pct(sucrose_eq, T)` in water mode; **from v.2.8.5 (food mode) `C_eq = sucF`** (reported as `sucrose_eq_pct`).
5. **Sweetness:** `sweet = 0.54 × C^1.3` with `C = sucF × q` (food mode, v.2.8.5) or `C = pct(sucrose_eq × q, T)` (water mode); 0 if C < 0.086 (sucrose threshold, Yamaguchi 1979 Table III). A note flags C_eq > 32%.

### 8.4 Sourness

`sour = sourness_intensity(S × sour_remaining)`, where the stimulus is converted to the tartaric-acid concentration in pure water with the same stimulus (bisection on [0, 5000] mM, 60 iterations, then g/100 mL = mM × 150.09/10000), and read on Yamaguchi's curve (1979, p. 36): `x < 0.00094` → 0; else `max(0, 14.45 × log2(x / 0.00296))`. Sourness is null when acidity is off. A note flags raw sourness > 100 (above Yamaguchi's top of scale, saturated sucrose).

### 8.5 Kokumi

Glutathione-equivalents (g/100 mL): `GSH_eq = 1.0 × gsh + 12.8 × evg + 1.0 × cys` (γ-Glu-Val-Gly potency 12.8 by weight, Ohsu 2010 Table 2; cysteine sulfoxides 1.0, Ueda 1990, qualitative). mM: `C = GSH_eq / 307.33 × 10 × 1000`. Hill curve: `kokumi % = 100 × C^1.456 / (0.9122^1.456 + C^1.456)`. EC50 0.9122 mM and n 1.456: see section 14 (no primary source; conflicts with published receptor EC50s).

**Detection floor (v.2.9.0, KOK_THR_PTS):** the glutathione threshold falls as umami rises (Ueda et al. 1997, Biosci Biotechnol Biochem 61:1977, Table II, triangle tests, pH 7): 0.04% w/v in water and in 0.05% MSG, 0.02% in 0.8% MSG, 0.01% in 3.1% MSG (and in 0.05% MSG + 0.05% IMP). With x = the recipe's umami MSG-equivalent `umamiEq` (g/dL, after synergy, before the salt shift; x = 0.05 when umamiEq ≤ 0), the threshold % is log-log interpolated through KOK_THR_PTS = (0.05, 0.04), (0.8, 0.02), (3.1, 0.01) and held at the end points; `thr_mM = thr% × 10 / 307.33 × 1000`. Then `kokumi = max(0, (Hill(C) − Hill(thr_mM)) / (100 − Hill(thr_mM)) × 100)`: zero below threshold, the same 100% ceiling above. ASSUMPTION: Ueda's MSG contexts stand for any umami of equal MSG-equivalent.

Kokumi boosts umami and saltiness by `× (1 + 0.41 × kokumi/100)`, gain 0.41 derived from Goto et al. 2016 (×1.38 overall intensity at 5.26 mM glutathione, which is 92.8% on this curve: 0.38/0.928 = 0.41).

### 8.6 Bitterness (v.2.8.3)

**Basis:** whole food. `fFood = total water / total mass` (after evaporation). Every bitterness input is converted to g per 100 g of food with `fw = fFood / fb` (from v.2.8.5 `conc` and Na(M) are already per food, so fw = 1 in food mode and the bitterness numbers are unchanged): caffeine `caf% = conc.caf × fw`, theobromine `tb% = conc.tb × fw`, KCl `kcl% = conc.k_cl × (74.551/39.098) × fw` (always chloride potassium only), sugars `sugF[s] = sugars[s] × fFood` (so Reb A% and acesulfame K% are `sugF.reb_a`, `sugF.ace_k`), sodium `NaF = Na(M) × fw`, where Na(M) is the thresholded sodium molarity of 8.2 step 2, **before** the umami lift of 8.2 step 6 (the lift changes saltiness only). Source: Stark et al. 2006 Table 1 (dose-over-threshold uses concentration in the food). ASSUMPTION: the food's own mass is the tasting solution; saliva and fat partition are ignored.

**Curves** (Torrico & Prinyawiwatkul 2015 Table 3, water, Spectrum scale): caffeine `B(c) = 0` if c < 0.0233; linear ramp `52.5 × 0.05^0.87 × (c − 0.0233)/(0.05 − 0.0233)` for 0.0233 ≤ c < 0.05; `52.5 × c^0.87` above (0.0233% = 1.2 mM caffeine threshold, Keast & Roper 2007). KCl `B = 4.37 × c^0.68` for c > 0. Caffeine-equivalent of an intensity: `ceq(B) = (B/52.5)^(1/0.87)`.

**Sodium suppression** (Breslin & Beauchamp 1995): with Na clamped to [0, 0.5] M, caffeine-type `S_C = 0.755 × Na/(Na + 0.194)`; KCl `S_K = 0.865 × Na/(Na + 0.023)`. Potassium does not suppress.

**Sugar suppression** (Calvino et al. 1990 Table I, Hill fit through 3 points 4.93% → 0.116, 9.72% → 0.521, 18.93% → 0.707): `S_sug(x) = 0.7288 x^3.8033 / (x^3.8033 + 7.6277^3.8033)`, x = sucrose-eq g per 100 g food, i.e. the sucrose-equivalent sum of 8.3 step 1 applied to `sugF` (no % w/w conversion, no acid factor); 0 if x ≤ 0. Three versions: `S_all` (all sweeteners), `S_noRebA` (Reb A set to 0), `S_noAceK` (acesulfame K set to 0), because each sweetener's own sweetness is already inside its bitterness ratings.

**Theobromine:** concentration-added to caffeine at `TB_CAF_EQ = 578.86 / 685.08 × 194.19 / 180.16` (≈ 0.9108, display only; use the formula) g caffeine per g (threshold ratio at 25 °C, Xing et al. 2024 Table S2; ASSUMPTION equal dose-over-threshold = equal bitterness), capped at its solubility `TB_SOL_MAX = 8 × 800e-6 × 180.16 / 10` g/100 g (= 0.1153024; use the formula) (Stark 2006: saturated at 8× its 800 µmol/kg threshold; ASSUMPTION: room-temperature limit used for hot drinks too).

**Reb A and acesulfame K** (Schiffman et al. 1995, Brain Res Bull 36:505, Table 1; caffeine-anchored line scale 0.05% = 2, 0.08% = 5): net rating `r = a × c^b` (Reb A a = 9.928380940042402, b = 0.6768788634937082; acesulfame K a = 5.8931225453905265, b = 0.5499448249760767; least-squares log-log fits to Table 1 after subtracting the mean sucrose bitterness floor 0.117; see section 12.6 for the data). Rating → caffeine % by a log-log line through the two anchors with rating 0 at caffeine 0: `c_caf = 0.05 × (r/2)^(1/n_a)`, `n_a = ln(5/2)/ln(0.08/0.05) = 1.9495`. Tested up to 0.15% (Reb A) and 0.156% (ace-K); notes flag higher. **Saccharin** (v.2.9.0): same method on Schiffman 1995 Table 1 sodium saccharin rows, `r = SACC_A × c^SACC_B` with SACC_A = 8.573335360776412, SACC_B = 0.6132138096664971 (rows in section 12.6), tested to SACC_MAX = 0.09625%; note `bitter_sacc_extrap` above that.

**Combination:**
`c_xan = caf% + TB_CAF_EQ × min(tb%, TB_SOL_MAX)`;
`b_X = B_caf(c_xan) (1 − S_C)(1 − S_all)`; `b_K = B_KCl(kcl%) (1 − S_K)(1 − S_all)`;
`b_R = B_caf(c_caf(RebA%)) (1 − S_C)(1 − S_noRebA)`; `b_A = B_caf(c_caf(AceK%)) (1 − S_C)(1 − S_noAceK)`; `b_S = B_caf(c_caf(Sacc%)) (1 − S_C)(1 − S_noSacc)` (S_noSacc: saccharin set to 0);
`bitterness = 52.5 × (ceq(b_X) + ceq(b_K) + ceq(b_R) + ceq(b_A) + ceq(b_S))^0.87` (0 if the sum is 0). Concentration addition of bitter compounds (Breslin & Beauchamp 1995; Keast et al. 2003). Notes: see the table in section 11.1 (bitter_* keys). Protein hydrolysate/isolate rows (names matching `hydroly[sz]|isolate|protein powder|whey protein|pea protein|soy protein|casein`, case-insensitive, ≥ 1% of mass) get a note, not a score.

## 9. Interactions at a glance

| Effect | Direction | Where |
|---|---|---|
| Nucleotides × glutamate (synergy, capped 63×) | raises umami | 8.1 step 5 |
| Nucleotides lower the glutamate threshold (up to 63×) | raises umami near threshold | 8.1 step 1 |
| pH above 6.5 weakens synergy | lowers umami | 7.5 |
| Na and chloride K shift umami concentration (up to ×2) | raises umami | 8.1 step 6 |
| Acid (sour stimulus, after sugar) | lowers umami | 7.4, 8.1 step 8 |
| Kokumi (×(1 + 0.41·k)) | raises umami and saltiness | 8.5 |
| Umami (score 1 → 2.4) at low sodium | raises saltiness up to 10% of Na | 8.2 step 6 |
| Na + KCl concentration addition | saltiness of blends | 8.2 step 5 |
| Acid (citric equivalent) | lowers sweetness (to 0.65×) | 8.3 step 3 |
| Sugar (sucrose-eq) | lowers sourness (to 0.17×) | 8.3 step 2 |
| Sodium | lowers bitterness | 8.6 |
| Sugar | lowers bitterness (up to 73%) | 8.6 |

## 10. Scores (1–10)

`score = 1 + 9 × min(1, max(0, raw) / REF)`. Linear in each raw scale, capped at 10.

| Output | REF formula | REF value |
|---|---|---|
| umami | `(3.6672 × ln(5.0 × 2.0) + 12.555) × (1 + 0.41)` | 29.608646474769145 |
| saltiness | `2.7036 × ln(0.5) + 12.008` | 10.13400728263813 |
| sweetness | `0.54 × 10^1.3` | 10.77441650083195 |
| sourness | `sourness_intensity(stimulus of 50/192.12 × 1000 mM citric acid alone in water)` | 149.59657262512513 |
| kokumi | 100 | 100 |
| bitterness | 10 (Spectrum 10) | 10 |

Choice of references is the author's: they mark "very strong" real solutions. The umami reference includes the salt and kokumi boosts at their maximum so that seasoned dishes do not all cap at 10. The "0.15% caffeine = 10" phrasing on the page is an approximation: on Torrico's power fit Spectrum 10 is 0.149% caffeine; Torrico's own reference list gives only 0.05% = 2 and 0.08% = 5.

The page labels: ≤ 1.05 "Not detected", < 3 "Faint", < 5 "Light", < 7 "Moderate", < 9 "Pronounced", else "Intense".

## 11. Data-gap flags and notes

### 11.1 Notes

Notes are returned in order as `{key, text}`. The test file checks the **set of keys** (sorted list, duplicates kept); the wording is not tested. Exact trigger conditions in the live code (T = `cook_temp_c`; concentrations as defined in sections 6–8):

| Key | Fires when | How often |
|---|---|---|
| cook_range | T is given AND (recipe `cook_min` is truthy OR any item has a `cook_min` field, even 0) AND NOT (60 ≤ T ≤ 89) | once |
| no_density | an item uses a volume unit and its density ≤ 0 | per item |
| cooked_nuc | cooked nucleotide values were applied to an item (5.3) | per item |
| sour_top | acidity on AND raw sourness > 100 | once |
| ph_default | acidity on AND at least one item was calibrated at the default pH 6.0 | once |
| sour_umami_extrap | acidity on AND S_eff > MIRANDA_S_MAX (31.33 mM) | once |
| salt_extrap | Na(M) > 0.108 | once |
| k_extrap | K(M) > 0.112 | once |
| sweet_extrap | C_eq (sucrose_eq_pct) > 32 | once |
| unscored_sugar | some unscored sugar (maltotriose, mannose, uronic) has g ≥ 0.01 × max(total sugar, 1e-9) (water basis) | once |
| his_high | some high-intensity sweetener has c = g/purity > its 15%-sucrose point (water-basis g) | once |
| his | any high-intensity sweetener (reb_a, mogroside_v, sucralose, aspartame, ace_k) has water-basis g > 0 | once |
| bitter_caf_extrap | c_xan > 0.15 | once |
| bitter_kcl_extrap | kcl% > 1.5 | once |
| bitter_kcl_low | 0 < kcl% < 0.5 | once |
| bitter_tb | tb% > 0 | once |
| bitter_reba_extrap | RebA% (whole-food) > 0.15 | once |
| bitter_acek_extrap | AceK% (whole-food) > 0.156 | once |
| bitter_sugar_high | final bitterness > 0 AND max(sucF, sucF_noRebA, sucF_noAceK) > 18.93, where these are the whole-food sucrose-eq sums used for S_all, S_noRebA, S_noAceK | once |
| bitter_scope | caf% > 0 OR tb% > 0 | once |
| bitter_protein | an item whose name matches the protein pattern has mass_g / total mass ≥ 0.01, using the total mass AFTER evaporation (unlike 11.2) | once |

So `bitter_sugar_high` does not fire for a sweet recipe with no bitterant (bitterness 0), e.g. G26.

Errors (thrown, no result): unknown ingredient; unknown unit; `water_loss_g ≥ total water`; total water ≤ 0 after evaporation.

### 11.2 Data-gap flags (`missing`, `estimated`)

Computed over items in recipe order, before evaporation. An item is skipped if total mass ≤ 0 or `item mass / total mass < 0.01` (so exactly 1% is included). For each remaining item (one entry per item, even if the ingredient repeats):

- `missing.fields`, in this order: "glutamate" if `glu` is in blank_fields; "nucleotides" if amp, imp and gmp are all in blank_fields AND glu ≥ 100 mg/100 g; "organic acids" if `acids` is in blank_fields AND ph_ref is not null AND ph_ref < 5.5. The item is listed only if at least one field applies.
- `estimated.fields`: every tier field of the ingredient whose tier equals 3 (field names as in the `tiers` column, e.g. "ph", "sugars"); listed only if non-empty.

The page shows `missing` as "may read low" (glutamate and nucleotides → umami, organic acids → sourness); `estimated` is not shown. Blank values count as 0 in all calculations. Recipe X15 tests the 1% boundary.

### 11.3 Comparison operators

| Test | Rule (as coded) |
|---|---|
| glutamate, aspartate, AMP, IMP, GMP above threshold | strictly greater (`conc > thr`) |
| nucleotide thresholds (v.2.9.0) | `u > 0` → all 0; else Kuninaka values |
| Na, K count for saltiness | `conc ≥ thr` (zero only if `conc < thr`) |
| K curve branch | K ≤ 0 → 0; K ≤ 0.112 → quadratic; else scaled log |
| dog response branch | x < 0.1 → quadratic; else linear |
| umami → salt fade | Na_mM ≤ 75 → full; else linear to 0 at 260 |
| synergy pH factor | pH ≤ 6.5 → 1; pH ≥ 9.5 → 0.070; else interpolate |
| sweetness threshold | C < 0.086 → 0 |
| sourness threshold | tartaric-eq x < 0.00094 → 0 |
| caffeine curve | c < 0.0233 → 0; c < 0.05 → ramp; else power |
| high-intensity sweetener | c ≤ 0 → 0; c < xs₀ → power extension; c > xs₂ → held at 15; else interpolate (segment chosen by c ≤ xs₁, then c ≤ xs₂) |
| sour_remaining, sweet q, invert | first segment with x ≤ x₁ (or y ≤ y₁) |
| cooked nucleotides | item minutes > 0 AND (T unknown OR T ≥ 65) |
| Chen range note | 60 ≤ T ≤ 89 is inside |
| data-gap share | share < 0.01 skipped |
| umami intensity, Na/K logs | computed only for a positive argument (`> 0`), then floored at 0 |

## 12. Constant register

Every numeric literal and every upper-case constant in the live HFP_MODEL block is listed here (checked by `check_spec.py`). **Status codes:** VERIFIED = the number is printed in the cited primary source and was checked against it for this package; DERIVED = computed from printed numbers (arithmetic given); FIT = a curve the model author fitted to a figure or table (plausibility checked against the source); DIGITIZED = read off a figure; ASSUMPTION = the author's modelling choice; UNSOURCED = no source found; STANDARD = physical/handbook constant, not re-verified from a primary source; IMPLEMENTATION = numerical or software detail with no taste meaning.

### 12.1 General, units and numerics

| Constant | Value(s) | Units | Source | Status |
|---|---|---|---|---|
| MASS_UNITS | g 1, kg 1000, oz 28.35, lb 453.59 | g per unit | US customary avoirdupois definitions (rounded) | STANDARD |
| VOLUME_UNITS | ml 1, l 1000, fl oz 29.57, cup 236.59, pt 473.18, qt 946.35, gal 3785.41, tsp 4.93, tbsp 14.79 | mL per unit | US customary volume definitions (rounded) | STANDARD |
| KW | 1e-14 | (mol/L)² | Water ion product at 25 °C | STANDARD |
| DEFAULT_PH | 6.0 | pH | Author's default for ingredients with charged species and no reference pH | ASSUMPTION |
| MIN_SHARE | 0.01 | mass fraction | Data-gap flag threshold (1% of recipe mass) | ASSUMPTION |
| ACIDS_BELOW_PH | 5.5 | pH | Blank organic acids flagged only for foods below pH 5.5 | ASSUMPTION |
| NUC_FLAG_GLU | 100 | mg/100 g | Blank nucleotides flagged only when glutamate ≥ 100 | ASSUMPTION |
| KEYS | glu, asp, amp, imp, gmp, na, k, gsh, cys, evg, caf, tb | — | Compound list summed per recipe | IMPLEMENTATION |
| LN, POW, DB, NAMES, HFP | Math.log, Math.pow, database object, name list, exported API | — | Implementation names | IMPLEMENTATION |
| Unit conversions in equations | 10, 100, 1000, 1e4 (10000), 0.001 | g/100 mL ↔ g/L, mg ↔ g, mol ↔ mmol | Arithmetic unit conversion | IMPLEMENTATION |
| Bisection pH | bracket 0 to 14, 80 iterations | pH | Numerical solver | IMPLEMENTATION |
| Bisection citric / tartaric equivalent | bracket 0 to 2000 mM and 0 to 5000 mM, 60 iterations | mM | Numerical solver | IMPLEMENTATION |
| Score scaling | 1 + 9 × min(1, raw/REF) | score | Author's 1–10 mapping (v.2.5.0) | ASSUMPTION |
| Unscored sugar note floor | 0.01 × max(total sugar, 1e-9) | g/100 g water | Note threshold and divide-by-zero guard | IMPLEMENTATION |
| Ingredient search ranking | −100 exact, −10 prefix, −5 word start, + length/100, limit 12 | — | Page search heuristic | IMPLEMENTATION |
| Index constants in loops | 3 (segments in SYN), 4 (Miranda points), loop start 1 | — | Loop bounds | IMPLEMENTATION |

### 12.2 Acid–base (section 7)

| Constant | Value(s) | Units | Source | Status |
|---|---|---|---|---|
| ORGANIC_ACIDS citric | MW 192.12; pKa 3.13, 4.76, 6.40 | g/mol; pKa | Price et al. 2020 Table 4 (prints 3.13, 4.76, 6.39; CRC 1995) | VERIFIED (6.40 vs 6.39 printed) |
| ORGANIC_ACIDS acetic | MW 60.05; pKa 4.76 | | Longtin et al. 2020 p. 4 (CRC 1995) | VERIFIED |
| ORGANIC_ACIDS malic, tartaric, lactic | MW 134.09, 150.09, 90.08; pKa 3.40/5.11, 2.98/4.34, 3.86 | | Standard handbook values (CRC Handbook) | STANDARD, not re-verified |
| ORGANIC_ACIDS ascorbic, oxalic, quinic | MW 176.12, 90.03, 192.17; pKa 4.10/11.6 (sourness 4.10 only), 1.25/4.14, 3.46 | | Standard handbook values | STANDARD, not re-verified |
| ORGANIC_ACIDS malonic, fumaric, succinic | MW 104.06, 116.07, 118.09; pKa 2.83/5.69, 3.03/4.44, 4.21/5.64 | | Standard handbook values | STANDARD, not re-verified |
| ORGANIC_ACIDS pyroglutamic, formic | MW 129.11, 46.03; pKa 3.32, 3.75 | | Standard handbook values | STANDARD, not re-verified |
| AMINO | glu MW 147.13, pKa 2.19, 4.25, 9.67; asp MW 133.10, pKa 1.99, 3.90, 9.90 | | Standard amino-acid pKa values | STANDARD, not re-verified |
| NUCLEOTIDE_MW | AMP 347.22, IMP 348.21, GMP 363.22 | g/mol (free acids) | Molecular formulas | STANDARD |
| NUCLEOTIDE_PKA2 | 6.2 | pKa | Secondary phosphate of 5'-nucleotides | STANDARD, not re-verified |
| PROTEIN_GROUPS | acidic (−1) 1.00 mmol/g pKa 4.2; His (+1) 0.20 mmol/g pKa 6.3; basic (+1) 0.90 mmol/g pKa 10.5 | mmol per g protein | Author's generic protein from an average amino-acid composition | ASSUMPTION |
| CHLORIDE_SALTS | Salt, Kosher Salt, Sea Salt, Table Salt, Canning Salt, Pickling Salt, Iodized Salt, Celtic Salt, Himalayan Salt, Pink Salt, Sodium Chloride, Potassium Chloride, Salt Substitute | names | Ingredients whose Na and K are balanced by chloride | ASSUMPTION |
| Na and K atomic masses | 22.99, 39.0983 (also 23 in the saltiness molarity step, 39.098 in KCL_PER_K) | g/mol | Standard atomic weights | STANDARD |
| Calibration slurry | wL = max(water, mass)/1000 | L | Dry ingredients calibrated as a 1:1 slurry | ASSUMPTION |
| MIRANDA_CITRIC | 0.0, 1.25, 6.25, 31.25 | mM citric acid | Miranda et al. 2021, methods p. 3 | VERIFIED |
| Miranda solution | 50 mM MSG (glutamate 50/1000 M, Na 50/1000 M) | mM | Miranda et al. 2021 | VERIFIED |
| MIRANDA_REM | 1.0, 1 − 2.886/39.756, 1 − 7.211/39.756, 1 − 20.654/39.756 | fraction | Miranda et al. 2021 Table 1, p. 4 (intercept 39.756; citric coefficients −2.886, −7.211, −20.654) | VERIFIED (intercept is a mixed-model value, not a raw mean) |
| S50, HILL (fit) | grid S50 = x/10 for 5 ≤ x < 400; H = y/50 for 10 ≤ y < 200 (integers); result 29.4 mM, 0.9 | mM; — | Author's logistic fit to the Miranda points mapped to sour stimulus | FIT |
| MIR_PTS, MIRANDA_S_MAX | stimuli of the 4 Miranda solutions; max 31.33 mM | mM | Computed from the above | DERIVED |
| Sour stimulus rule | [H⁺] + protonated organic acids, equal weight | mM | Neta et al. 2007 (J Food Sci 72:S352), restated Neta 2009 pp. S165–S166 | VERIFIED (via Neta 2009; 2007 paper not on file) |
| SYN | (6.5, 1.0), (7.5, 0.535), (8.5, 0.341), (9.5, 0.070) | pH, relative synergy | Yamaguchi 1979 Table VII, p. 42: (y − 0.072)/(0.33 − 0.072) from y = 0.21, 0.16, 0.09 | DERIVED (pH 6.5 computes to 1.19, set to 1.0) |

### 12.3 Umami (section 8.1)

| Constant | Value(s) | Units | Source | Status |
|---|---|---|---|---|
| Glutamate threshold | 0.01 | g/100 mL free acid | Yamaguchi 1979 Table III p. 35 and Yamaguchi & Ninomiya 2000 Table 3: MSG 0.012 g/100 mL; 0.012 × 147.13/187.13 = 0.0094, rounded to 0.01 | DERIVED |
| Aspartate threshold | 0.0166 | g/100 mL | Yamaguchi 1991, Physiol Behav 49:833, Table 1 p. 834: monosodium aspartate threshold 1.25 mM = 0.01664 g/100 mL as aspartic acid (MW 133.10). Kirimura 1969 Table I gives 100 mg/dL (not used: its MSG threshold runs 2.5× high) | VERIFIED (v.2.11.0; was UNSOURCED) |
| GLU_THR_DROP_MAX | 0.012/0.00019 = 63.16 | fold | Yamaguchi & Ninomiya 2000 Table 3 p. 923S (MSG threshold 0.00019% in 0.25% = 5 mM IMP) | DERIVED; linear scaling between 0 and 5 mM is ASSUMPTION |
| GLU_THR_AT_IMP | 5.0 | mM IMP-equivalent | Same table | VERIFIED |
| NUC_W | AMP 0.18, GMP 2.3 (relative to IMP) | g/g | Yamaguchi et al. 1971 Table 5 p. 848 (AMP 0.18 ± 0.03, GMP·7H₂O 2.3 ± 0.07) | VERIFIED |
| NUC_THR_IMP, NUC_THR_GMP | 0.387 × 348.21/1e4 = 0.013476, 0.206 × 363.22/1e4 = 0.0074823 | g/100 mL free acid | Kuninaka et al. 1980 Agric Biol Chem 44:1437, Table I (threshold 0.387 and 0.206 mM, distilled water, disodium salts, n = 18, Harris method); used only when glutamate is below its threshold (v.2.9.0) | VERIFIED (page image checked) |
| AMP threshold (alone) | NUC_THR_IMP / 0.18 | g/100 mL | No human AMP threshold in water found; derived from the AMP synergy weight 0.18 | ASSUMPTION |
| Nucleotide threshold with glutamate | 0 when u > 0 | g/100 mL | Yamaguchi & Ninomiya 2000 p. 923S ("IMP itself may not have intrinsic umami taste"); synergy already gated by the glutamate threshold. Replaces the three unsourced tiers (v.2.9.0) | ASSUMPTION (sourced reasoning) |
| SALT_FORM | glu 187.13/147.13; asp 173.10/133.10; IMP 527.28/348.21; GMP 533.29/363.22; AMP 391.18/347.22 | g salt per g free acid | Yamaguchi et al. 1971 p. 846 and Table 5 (MSG·H₂O, Na aspartate·H₂O, Na₂IMP·7.5H₂O, Na₂GMP·7H₂O, Na₂AMP); molecular weights | VERIFIED (forms) / STANDARD (MW) |
| Aspartate relative umami | 0.077 | g/g vs MSG | Yamaguchi et al. 1971 Table 3 p. 848 | VERIFIED |
| Synergy γ IMP | 1218 | (g/dL)⁻¹ | Yamaguchi 1967 eq. 9 p. 478 (1.218 × 10³) | VERIFIED |
| Synergy γ GMP | 2800 | (g/dL)⁻¹ | Yamaguchi et al. 1971 p. 846 (2.80 × 10³); = 1218 × 2.3 | VERIFIED |
| Synergy γ AMP | 219 | (g/dL)⁻¹ | 1218 × 0.18 (Yamaguchi 1971 Table 5) | DERIVED |
| TASTE_BASIS | "food" | mode | v.2.8.5 (Bryan, Nov 25, 2026). Tasted concentrations per 100 g food (fb = water/mass); Stark 2006 dose-over-threshold convention; pre-registered hold-out of 43 low-water SVT foods (NEVO composition): saltiness rho 0.365 → 0.774, sweetness 0.457 → 0.840 | VALIDATED (held-out, salt and sweet only) |
| Sugar-water cap for sour suppression | 99 | % sucrose-eq | `min(sucF, 99)` keeps the sugar-water equivalent finite for nearly pure sugar | IMPLEMENTATION |
| SYNERGY_MAX_FOLD | 63 | fold | v.2.8.4 (was 16, v.2.6.0). Yamaguchi & Kimizuka 1979 (Yamaguchi 2000 Table 3): 0.25% (5 mM) IMP lowers the MSG detection threshold 63×, where the synergy equation gives about 305×; same source as GLU_THR_DROP_MAX. Assumes the threshold shift equals the suprathreshold potency shift. See section 14, item 1 | ASSUMPTION (sourced; threshold data applied above threshold) |
| Nucleotide-alone term | 0.05/15 | g/dL MSG-eq | Calibration so 0.05 g/dL IMP alone ≈ 0.05 g/dL MSG (Yamaguchi 1967 Table 2 p. 474: no significant difference) | DERIVED / ASSUMPTION |
| Umami curve | 3.6672 × ln(c) + 12.555 | Yamaguchi scale | Author's fit to Yamaguchi 1967 Fig. 2 p. 476 (independent re-read: 3.689, 12.584) | FIT (consistent) |
| SALT_SHIFT_MAX | 1.0 | fold on concentration | v.2.11.0 (was 2.0, dog-nerve placeholder). Human data show no enhancement: Wang et al. 2022 Food Qual Pref 98:104503 Fig. 1 (0.05–0.08 M NaCl lowered umami to ×0.70–0.73, n = 12); Yamaguchi 1991 p. 833 and Table 4 (MSG threshold unchanged in 150 and 370 mM NaCl); Schiffman 1991 Physiol Behav 49:843 Table 4a. Suppression not modelled (one panel, in water) | SOURCED (no effect); suppression is a sensitivity scenario |
| Dog response R(x) | −37.089x² + 9.9621x − 0.038 (x < 0.1); −0.6351x + 0.6414 (x ≥ 0.1) | relative response | Author's fit to Ugawa & Kurihara 1994 Fig. 4A p. R947 (200 mM MSG + NaCl) | FIT (good) |
| DOG_R_PEAK | 0.5828 | relative response | Peak of the fit at 100 mM | FIT |
| K weight | 0.81 | Na-equivalents per K | Ugawa & Kurihara 1994 Fig. 7A p. R948 (KCl/NaCl response at 100 mM) | DERIVED (one concentration) |
| COOKED_NUC | Asparagus (Fresh) 0.972, 0.436; Green Pepper 2.049, 1.562; Broccoli 1.493, 1.271; Cabbage 0.451, 0.0; Cauliflower 0.833, 3.015; Mushroom, Button 11.736, 4.431; Mushroom, Champignon 11.736, 4.431; Sweet Potato 4.41, 1.126; Potato 1.042, 0.799; Radish 0.764, 0.182; Mushroom, Shiitake (Fresh) 8.214, 14.019; v.2.9.0 GMP only (AMP null = keep raw): Eggplant 1.70, Carrot 0.34, Daikon 0.14, Onion, Welsh 0.21, Spinach 0.76 | mg/100 g (AMP, GMP) | Nguyen et al. 1988 Table II p. 278, nmol/g × MW/10⁴; shiitake from DRIED values × 0.1132 dry-matter factor (fresh moisture not from Nguyen). Horie 2012 (J Cookery Sci Jpn 45:346) Tables 1–2, steamed 100 °C 15 min (spinach 87 °C 10 min), mg/100 g fresh, n = 4, treated as free acid (salt form not stated) | DERIVED (all rows checked) |
| Nuclease temperature | 65 | °C | Nguyen et al. 1988 (nuclease optimum 65–75 °C) | VERIFIED |
| Cooked-nucleotide rule | applied when cook minutes > 0 and T unknown or ≥ 65 | — | Author's rule | ASSUMPTION |

### 12.4 Saltiness (section 8.2)

| Constant | Value(s) | Units | Source | Status |
|---|---|---|---|---|
| NaCl threshold | 0.0037 × 22.99/58.44 | g Na/100 mL | Yamaguchi 1979 Table III p. 35 (NaCl 0.0037 g/100 mL; NaCl MW 58.44) | VERIFIED |
| KCl threshold | 0.00242 × 39.0983/10 | g K/100 mL | Schiffman, Manning, Warwick & Crumbliss 1995 Table 1 p. 624 (KCl 0.00242 M) | VERIFIED (different method from the Na threshold) |
| Na curve | 2.7036 × ln(M) + 12.008 | Murphy scale | Author's fit to Murphy et al. 1981 Fig. 7–8 p. 1088 (n = 10; 0.004, 0.012, 0.036, 0.108 M) | FIT (plausible; negative at 0.004 M, floored) |
| Na measured top | 0.108 | M | Murphy et al. 1981 methods p. 1084 | VERIFIED |
| K curve | 404.88M² + 6.7462M − 0.1344 for M ≤ 0.112 | Murphy scale | Author's fit to Murphy et al. 1981 KCl panel | FIT (plausible) |
| K curve top | 0.112 | M | End of the KCl fit | FIT |
| Na/K mixing | iso-salty NaCl molarity exp((I_K − 12.008)/2.7036) | M | Concentration addition (Bartoshuk 1975), adopted v.2.7.2 | ASSUMPTION |
| CHLORIDE_K | Potassium Chloride, Salt Substitute, Celtic Salt, Himalayan Salt, Pink Salt, Sea Salt | names | Potassium counted for saltiness and KCl bitterness (chloride salts only) | ASSUMPTION |
| UMAMI_SALT_EMAX | 0.10 | fraction of Na | Author's fit to Sun et al. 2022 Table 2 p. 5 (net MSG lift 8–12% at ≤ 84 mM Na) | FIT |
| UMAMI_SALT_S_FULL | 2.4 | umami score | Model umami score of Sun's 0.055% MSG "low umami" solution | FIT |
| UMAMI_SALT_FADE_MM | 75, 260 | mM Na | Sun 2022: lift ~5% at ~170 mM, 1–3% at ~245 mM | FIT |
| NaCl-eq of MSG (used in the fit only) | 0.35 | g NaCl per g MSG | Sodium content of anhydrous MSG (0.346) | DERIVED |

### 12.5 Sweetness and sourness (sections 8.3, 8.4)

| Constant | Value(s) | Units | Source | Status |
|---|---|---|---|---|
| EXPONENT | 1.3 | — | Moskowitz 1970 Table 3 p. 317 (exponent fixed at 1.3, % w/w) | VERIFIED |
| K_SUCROSE | 0.54 | Moskowitz scale | Moskowitz 1970 Table 3 | VERIFIED |
| RS (Moskowitz) | sucrose 1.00, fructose 0.91, glucose 0.45, galactose 0.42, glycerol 0.50, arabinose 0.39, xylose 0.26, maltose 0.31, lactose 0.22 | relative k | Moskowitz 1970 Table 3 p. 317 | VERIFIED |
| RS (Wee) | sorbitol 0.72^1.3, mannitol 0.68^1.3, erythritol 0.75^1.3, xylitol 1.01^1.3, allulose 0.75^1.3, maltitol 0.89^1.3 | potency^1.3 | Wee et al. 2018 Table 4 p. 9 (potency at 10% sucrose) | VERIFIED |
| SUGARS | sucrose, glucose, fructose, lactose, galactose, maltose, maltotriose, uronic, arabinose, xylose, mannose, glycerol, sorbitol, erythritol, xylitol, mannitol, allulose, maltitol, reb_a, mogroside_v, sucralose, aspartame, ace_k, saccharin | fields | Database sugar columns (saccharin added v.2.9.0) | IMPLEMENTATION |
| WEE_LEVELS | 5.0, 10.0, 15.0 | % sucrose | Wee 2018 Table 4 | VERIFIED |
| WEE_SUC_N | 1.31 | — | Wee 2018 Table 3 p. 8 (sucrose exponent) | VERIFIED |
| HIS | Stevia (rebaudioside A) purity 0.680, n 0.71, [0.0144, 0.0395, 0.0828]; Monk fruit (mogroside V) 0.506, 0.70, [0.0191, 0.0694, 0.141]; Sucralose 1.0, 0.65, [0.0096, 0.0387, 0.0748]; Aspartame 1.0, 0.84, [0.0290, 0.0827, 0.134]; Acesulfame K 1.0, 0.68, [0.0293, 0.0832, 0.170] | purity; exponent; % w/v | Wee 2018 p. 3 (extract purities 68.0% Reb A, 50.6% mogroside V), Table 3 (n), Table 4 (equi-sweet points) | VERIFIED; treating a grade as Wee's material at equal active content is ASSUMPTION |
| HIS (saccharin) | Saccharin purity 1.0, n 0.868 × 1.31, [0.00392, 0.01126, 0.0405] | purity; exponent; % w/v | Schiffman et al. 1995 Brain Res Bull 36:505, Table 2 p. 512 (potency 510/444/247 at 2/5/10% sucrose); n from the first-segment slope 0.868 | VERIFIED (points); cross-study offset ±25% is ASSUMPTION |
| HIS_LEVELS | saccharin: 2.0, 5.0, 10.0 | % sucrose | Schiffman 1995 Table 2 sucrose levels (others use WEE_LEVELS) | VERIFIED |
| HIS_CAP | saccharin: 9.0 | % sucrose-eq | Schiffman 1995 Table 1: 0.04–0.096% sodium saccharin rated 7.97–9.04% sucrose-eq (plateau) | DERIVED |
| SUCROSE_THR | 0.086 | g/100 mL | Yamaguchi 1979 Table III p. 35 | VERIFIED |
| MOSK_MAX | 32.0 | % w/w | Upper end of Moskowitz's data used for the note (Table 3 footnote: sucrose fitted on 2–16% only) | ASSUMPTION (note threshold) |
| SF_SUC_M | 0.125, 0.25, 0.5, 1.0 | M sucrose | Schifferstein & Frijters 1990 p. 89 | VERIFIED |
| SF_SUC_G | 4.40, 9.06, 19.2, 43.6 | g sucrose per 100 g water | Converted from SF_SUC_M with sucrose solution densities (check gives 4.40, 9.05, 19.17, 43.53) | DERIVED |
| SF_CIT | 1.25, 2.5, 5.0, 10.0 | mM citric | Schifferstein & Frijters 1990 p. 89 | VERIFIED |
| SF_SWEET_UNMIXED | 24, 45, 79, 111 | paper's scale | Schifferstein & Frijters 1990 Fig. 3 p. 94 | DIGITIZED (±1) |
| SF_SWEET_MIX | 1.25: 19.5, 38, 67, 103; 2.5: 19.5, 38, 70, 95; 5: 15, 36.5, 65, 95; 10: 11.5, 28.5, 63.5, 95 | paper's scale | Schifferstein & Frijters 1990 Fig. 4 p. 95 | DIGITIZED (±1) |
| SF_SOUR_UNMIXED | 27, 50, 79, 105 | paper's scale | Schifferstein & Frijters 1990 Fig. 3 | DIGITIZED (±1) |
| SF_SOUR_MIX10 | 77, 62, 51, 35 | paper's scale | Schifferstein & Frijters 1990 Fig. 4 (10 mM citric) | DIGITIZED (±1) |
| SWEET_Q, SOUR_PTS | see 8.3 | factor | Derived by inversion of the digitized curves | DERIVED |
| Acid-on-sweetness hold | clamp citric-eq to [0, 10] mM | mM | No extrapolation beyond the paper | ASSUMPTION |
| TART_ALPHA | 14.45 | Yamaguchi scale per doubling | Yamaguchi 1979 p. 36 (S_T = 14.45 log2(x/0.00296)) | VERIFIED |
| TART_BETA | 0.00296 | g/100 mL | Yamaguchi 1979 p. 36 | VERIFIED |
| TART_THR | 0.00094 | g/100 mL | Yamaguchi 1979 Table III p. 35 | VERIFIED |
| TART_MW | 150.09 | g/mol | Tartaric acid | STANDARD |
| Sour reference | 50.0 g/L citric = 50/192.12 × 1000 mM | mM | Author's 10/10 anchor ("straight lemon juice") | ASSUMPTION |

### 12.6 Kokumi and bitterness (sections 8.5, 8.6)

| Constant | Value(s) | Units | Source | Status |
|---|---|---|---|---|
| KOKUMI_POT | gsh 1.0, evg 12.8, cys 1.0 | g/g glutathione-eq | evg: Ohsu et al. 2010 Table 2 p. 1020 (0.01% γ-EVG = 0.128% GSH, n = 17) VERIFIED; cys: Ueda et al. 1990 Table IV p. 168 (alliin about as strong as GSH at 0.2%, qualitative; methiin and cycloalliin rated weaker) | VERIFIED / ASSUMPTION |
| Glutathione MW | 307.33 | g/mol | Molecular formula | STANDARD |
| KOK_EC50 | 0.9122 | mM GSH-eq | Not a receptor value. Most likely the author's Hill fit to the GSH CaSR curve of the Koku book Fig. 8.1 (Maruyama & Kuroda; EC50 0.71 µM, axis labelled mM), read as mM; Ohsu 2010 Fig. 3 gives 76.5 nM. Kept as a sensory curve on mouth concentration, checked against human points: 0.33 mM (Ueda 1997 threshold in umami) 18%, 0.65 mM (Ueda 1997 significant effects) 38%, 2.6 mM (Ohsu 2010 Fig. 1) 82%, 5.26 mM (Goto 2016) 93%. No human GSH dose-response curve has been published | ASSUMPTION (sensory curve, calibrated only by human thresholds and single doses) |
| KOK_THR_PTS | (0.05, 0.04), (0.8, 0.02), (3.1, 0.01) | (MSG-eq g/dL, GSH % w/v) | Ueda et al. 1997 Biosci Biotechnol Biochem 61:1977, Table II (triangle tests, pH 7; 0.04% also in water) | VERIFIED (points); log-log interpolation and use of MSG-eq for any umami are ASSUMPTION |
| KOK_N | 1.456 | Hill exponent | Same fit | UNSOURCED |
| KOK_UMAMI_GAIN, KOK_SALT_GAIN | 0.41, 0.41 | fraction at kokumi 100% | Goto et al. 2016 (6.73/4.89 = 1.38 overall intensity at 5.26 mM GSH, n = 26) ÷ 0.928 on this curve | DERIVED (inherits the EC50 assumption; Goto rated the mixture, not umami and saltiness separately) |
| Chen kinetics | A 4.38e17 per min, Ea 142494 J/mol, R 8.314, T + 273.15 | — | Chen et al. 2017 abstract p. 25, §3.1.1 p. 27 (fitted at 60, 80, 89 °C; reproduces printed k 2e-5, 3.6e-4, 1.24e-3) | VERIFIED |
| Cooking range note | 60, 89 | °C | Chen et al. 2017 tested range | VERIFIED |
| CAF_K, CAF_N | 52.5 (= 10^1.72), 0.87 | Spectrum, — | Torrico & Prinyawiwatkul 2015 Table 3 p. S1888 (0% oil) | VERIFIED |
| KCL_K, KCL_N | 4.37 (= 10^0.64), 0.68 | Spectrum, — | Torrico & Prinyawiwatkul 2015 Table 3 | VERIFIED |
| CAF_THR | 0.0233 | % w/v caffeine | Keast & Roper 2007 abstract p. 245 (1.2 mM × 194.19) | DERIVED |
| CAF_MIN, CAF_MAX | 0.05, 0.15 | % | Torrico's tested caffeine range; linear ramp below 0.05 is ASSUMPTION | VERIFIED / ASSUMPTION |
| KCL_MIN, KCL_MAX | 0.5, 1.5 | % | Torrico's tested KCl range | VERIFIED |
| KCL_PER_K | 74.551/39.098 | g KCl per g K | Molecular weights | STANDARD |
| NA_CAP | 0.5 | M | Breslin & Beauchamp 1995 top NaCl level | VERIFIED |
| Na on caffeine | 0.755 × Na/(Na + 0.194) | fraction | Author's fit to Breslin & Beauchamp 1995 Fig. 2B p. 615 (observed 15/43/54% at 0.1/0.3/0.5 M; fit gives 26/46/54%) | FIT (misses the 0.1 M point) |
| Na on KCl | 0.865 × Na/(Na + 0.023) | fraction | Author's fit to Breslin & Beauchamp 1995 Fig. 2E (0.05–0.2 M; independent fit 0.87, 0.024) | FIT (good) |
| SUG_SMAX, SUG_H, SUG_X50 | 0.7288, 3.8033, 7.6277 | fraction, —, % w/w | Exact Hill fit through Calvino et al. 1990 Table I means 0.116, 0.521, 0.707 at 4.93, 9.72, 18.93% sucrose (146, 292, 585 mM; n = 14; non-significant cells = 0) | DERIVED |
| SUG_FIT_MAX | 18.93 | % w/w | Highest Calvino sucrose level | VERIFIED |
| TB_CAF_EQ | 578.86/685.08 × 194.19/180.16 = 0.9108 | g caffeine per g theobromine | Xing et al. 2024 Table S2 (25 °C thresholds: caffeine 578.86, theobromine 685.08 µmol/L); MW caffeine 194.19, theobromine 180.16 | VERIFIED (equal-dose-over-threshold is ASSUMPTION) |
| TB_SOL_MAX | 8 × 800e-6 × 180.16/10 = 0.1153 (800e-6 = 0.0008 mol/kg) | g/100 g | Stark et al. 2006 Table 1 p. 5534 (theobromine threshold 800 µmol/kg) and p. 5538 (maximum solubility at 8× threshold) | VERIFIED; use for hot drinks is ASSUMPTION |
| SCH_N | ln(5.0/2.0)/ln(0.08/0.05) = 1.9495 | — | Schiffman et al. 1995 (Brain Res Bull 36:505) p. 509: caffeine 0.05% = 2, 0.08% = 5 | VERIFIED (anchors); log-log line through them is ASSUMPTION |
| REBA_A, REBA_B | 9.928380940042402, 0.6768788634937082 | rating, exponent | Least-squares log-log fit to Schiffman 1995 Table 1 Reb A rows (0.007: 0.58, 0.01: 0.49, 0.0175: 0.77, 0.025: 0.69, 0.04375: 1.60, 0.0525: 1.10, 0.0625: 1.55, 0.075: 2.12, 0.08125: 2.42, 0.1: 2.15, 0.12: 2.75, 0.15: 2.60) minus the sucrose floor 0.117 (mean of 23 sucrose rows) | FIT (R² 0.91) |
| ACEK_A, ACEK_B | 5.8931225453905265, 0.5499448249760767 | rating, exponent | Same method, Schiffman 1995 Table 1 acesulfame K rows with printed concentrations 0.18–0.8 read as 0.018–0.08 (misprint correction checked against Schiffman's Table 2 potencies) | FIT (R² 0.83); misprint correction is ASSUMPTION |
| REBA_MAX, ACEK_MAX | 0.15, 0.156 | % w/v | Highest tested concentrations, Schiffman 1995 Table 1 | VERIFIED |
| SACC_A, SACC_B | 8.573335360776412, 0.6132138096664971 | rating, exponent | Same method as REBA, Schiffman 1995 Table 1 sodium saccharin rows (0.0035: 0.35, 0.00616: 0.65, 0.009: 0.43, 0.0154: 1.01, 0.02: 1.08, 0.022: 0.83, 0.03: 1.32, 0.0385: 1.48, 0.04: 0.76, 0.05: 1.80, 0.055: 1.10, 0.06: 2.03, 0.09625: 2.32) minus the sucrose floor 0.117 | FIT (R² 0.785, n = 13) |
| SACC_MAX | 0.09625 | % w/v | Highest tested sodium saccharin, Schiffman 1995 Table 1 | VERIFIED |
| PROTEIN_BITTER_RE | hydroly[sz], isolate, protein powder, whey/pea/soy protein, casein | name pattern | Note only, after Sun et al. 2022 (Front Nutr 9:1022257) on bitter peptides | ASSUMPTION |
| SCORE_REF | see section 10 | raw units | Author's anchors | ASSUMPTION |

## 13. Data dictionary (ingredient database)

### 13.1 Structure

`hfp_ingredients_v2.10.0.csv` has one row per ingredient (824 rows), exported by `tools/export_db.py` from the page's HFP_DB block. Blank values in the source are exported as 0, exactly as the model reads them. All amounts are per 100 g of the ingredient as sold or as listed (e.g. "Juice, Lime", "Broth, Chicken").

| Column | Units | Meaning |
|---|---|---|
| ingredient | — | Exact name used by the model (case-sensitive) |
| glu, asp | mg/100 g | Free glutamate, free aspartate (free acids) |
| amp, imp, gmp | mg/100 g | 5'-adenylate, 5'-inosinate, 5'-guanylate (free acids) |
| density | g/mL | For volume amounts (0 = unknown) |
| water | g/100 g | Water content |
| na, k | mg/100 g | Sodium, potassium |
| protein | g/100 g | Protein (pH buffer only) |
| gsh | mg/100 g | Glutathione |
| cys | mg/100 g | Cysteine sulfoxides (alliin, isoalliin, methiin) |
| evg | mg/100 g | γ-Glutamyl-valyl-glycine |
| caf, tb | mg/100 g | Caffeine, theobromine |
| acid_citric … acid_formic | mg/100 g | 13 organic acids (section 7.1) |
| sugar_sucrose … sugar_mannitol | mg/100 g | Sugars and polyols (section 8.3) |
| sugar_allulose, sugar_maltitol | mg/100 g | Bulk sweeteners |
| sugar_reb_a, sugar_mogroside_v | mg/100 g | Rebaudioside A and mogroside V content (not extract mass) |
| sugar_sucralose, sugar_aspartame, sugar_ace_k | mg/100 g | High-intensity sweeteners |
| ph_ref | pH | Reference pH for calibration (blank = none) |
| blank_fields | list | Fields that were blank in the source (glu, amp, imp, gmp, acids); used only for data-gap flags |
| tiers | field:tier list | Data-quality tier for fields with one (see 13.2) |

**USDA composition rows (v.2.10.0).** 392 rows carry composition from USDA FoodData Central SR Legacy (2018-04): water, sodium, potassium (total K: the model's saltiness counts chloride K only), protein, the six individual sugars, caffeine, theobromine, and vitamin C as ascorbic acid. Their source is in the `Organic Acid Source` column ("Composition: USDA FDC SR Legacy <fdc_id>"). Density = USDA cup (236.588 mL), tbsp (14.787) or tsp (4.929) gram weight (bulk density: "1 cup, chopped"); blank when USDA has no volume portion. Umami, kokumi and organic-acid fields are blank (tier 4, flagged), except 18 pure fats, oils and sugars set to 0 by composition; USDA total glutamic and aspartic acid are protein-bound and were not used. Where USDA gives only total sugar (147 rows), the total is counted as sucrose and flagged tier 3 (`sugars`) in the data-quality file. Mapping decisions: `sr_mapping.txt` and `staging_rows.csv` in the model folder (validation/missing_ingredients/usda_fill).

### 13.2 Quality tiers

Tier 1 = measured value from a published source; tier 2 = derived (calculated from a published value, or copied from a close sibling food); tier 3 = category estimate (e.g. median pH of similar foods); blank = no data (counts as 0). Tier field names: acids, amp, aspartate, density, glutamate, gmp, imp, ph, potassium, sodium, sugars, theobromine, umami+acids+pH. Fields without a tier entry are the original database values (mostly tier 1 by the workbook's convention, with no per-value citation recorded).

### 13.3 Main data sources

USDA FoodData Central (Foundation Foods and SR Legacy) for water, sodium, potassium, protein, sugars, caffeine and theobromine; FDA "Approximate pH of Foods and Food Products" for most reference pH values (midpoints of the listed ranges); Yamaguchi & Ninomiya 2000 Table 2 and Nguyen et al. 1988 for nucleotides; the published literature for organic acids, glutamate and kokumi compounds.

### 13.4 Provenance file

`hfp_ingredient_provenance.csv` (ingredient, field, tier, basis_or_source, record) collects what the source workbook recorded: the Data Quality sheet (tier and basis for 2nd- and 3rd-tier and corrected values) and the pH Source and Organic Acid Source columns. It was taken from the workbook export that matches the live database exactly (all 431 rows and all values compared). **Honest limit:** most original glutamate, nucleotide, sodium and sugar values have no per-value citation recorded; only their general sources (13.3) are known.

### 13.5 License note on the data

USDA data are public domain (CC0). Values transcribed from papers are facts with citations. The database is not derived from the Mars et al. SVT dataset (CC BY-SA 4.0), which was used only to validate the model and to find data problems; the fixes themselves came from the sources in the provenance file.

## 14. Known limits and verification findings

**Held-out test of the whole-food basis (v.2.8.5, Nov 25, 2026).** The protocol and pass mark were fixed before any data was viewed. 49 SVT foods outside the 85-unit validation set were chosen from descriptions only (low-water breads, crackers, biscuits, snacks, nuts, cereals, cured meats, sweets, spreads). Composition came from NEVO-Online 2025/9.0 by NEVO code (water, sodium, potassium, total sugars counted as sucrose; NEVO has no glutamate, nucleotides or acids, so only saltiness and sweetness were tested). 43 foods were included and scored once. Saltiness rho 0.365 [95% CI 0.11, 0.60] → 0.774 [0.59, 0.88]; foods at score 10: 31 → 2. Sweetness rho 0.457 [0.24, 0.65] → 0.840 [0.72, 0.90]; foods at 10: 32 → 16. Verdict: PASS. NEVO data were used for validation only and are not part of this package (NEVO's terms forbid charging users for its data).

**Model limits.** Tastes are scored per 100 g of food (v.2.8.5); before that, low-water foods (chocolate, chips, crackers, cheese) read 10 for salt and sweet. On the 81-food SVT panel the change moved umami 0.707 → 0.732, saltiness 0.836 → 0.843, sweetness 0.778 → 0.804 and sourness 0.751 → 0.745 (in-sample); the held-out low-water test is in section 14. Aroma, fat, heat, texture, temperature and saliva are not modelled. Bitterness covers five compounds only (no tea catechins, coffee roast compounds, hop acids, naringin, cocoa flavanols, peptides). The salt shift of umami is a placeholder (×2) from dog nerve data. Raw scales are not comparable across tastes. The predicted pH is an estimate and must not be used for food safety decisions.

**Findings from checking constants against the primary papers for this package** (these are documented, not fixed; the live model is unchanged):

1. **Synergy cap 16×.** Yamaguchi's "16 times" (1979 p. 37; 1967 Fig. 6) compares a 1:1 MSG+IMP mixture with the same total concentration of MSG, not the fold over the glutamate alone that the model caps. At Yamaguchi's own 1:1 point the model's fold would be about 31; he also writes that the amplification "becomes higher with increasing concentration". Zhang 2008's EC50 shift (3.2 → 0.2 mM with 1 mM IMP) was measured on a chimeric receptor (human T1R1 extracellular domain, T1R2 transmembrane domain, rat T1R3), not human T1R1/T1R3. The cap is a modelling choice, not a measured ceiling. *(Resolved in v.2.8.4, Nov 25, 2026: the cap is now 63×, from Yamaguchi & Kimizuka 1979's measured 63× threshold drop at 5 mM IMP.)*
2. **Nucleotide detection thresholds (three tiers) and the aspartate threshold 0.0166** have no source in any paper on file. The middle-tier glutamate breakpoint 0.0037 equals the NaCl threshold in the same Yamaguchi table, a possible copy error. *(Nucleotides resolved in v.2.9.0, Nov 25, 2026: the tiers are gone; Kuninaka 1980 thresholds apply only when glutamate is below its own threshold. The aspartate threshold is still unsourced; Kirimura 1969 is the next paper to check.)*
3. **Kokumi EC50 0.9122 mM** has no recorded source and is about 1,000–10,000× higher than published glutathione EC50s at the calcium-sensing receptor (Ohsu 2010: 76.5 nM; Koku book: 0.71 µM). The kokumi gain 0.41 depends on it. *(Relabelled in v.2.8.4, Nov 25, 2026: most likely the Koku book's 0.71 µM curve read as mM. A receptor EC50 does not transfer to the mouth, and the true µM value would saturate every food, so the curve is kept and documented as an ASSUMPTION calibrated to human thresholds. v.2.9.0 adds the Ueda 1997 detection floor (section 8.5), so foods below the human glutathione threshold now read kokumi 0.)*
4. **Na suppression of caffeine bitterness** fit gives 26/46/54% at 0.1/0.3/0.5 M vs 15/43/54% read from Breslin & Beauchamp 1995 (11 points high at 0.1 M).
5. **Neta citation:** *(Fixed on the live page Nov 25, 2026.)* the page lists "Neta E. et al. (2007) The chemistry of sour taste. J Food Sci 72:S33". The paper that makes the sour-stimulus claim is Da Conceicao Neta et al. 2007, J Food Sci 72(6):S352–S359 (doi 10.1111/j.1750-3841.2007.00400.x).
6. **Salt shift on umami.** A Nov 25, 2026 source search found no human evidence that NaCl raises umami. *(Resolved in v.2.11.0 after reading Wang 2022, Yamaguchi 1991, Schiffman 1991 and Kemp & Beauchamp 1994 in full: SALT_SHIFT_MAX = 1.0. SVT umami rho on 82 foods moved 0.732 → 0.714, within noise.)*
6. **Price 2020 accuracy wording:** *(Fixed on the live page Nov 25, 2026.)* the page says the pH model "was off by about 0.14 pH units on average". Price reports a root-mean-squared error of 0.138 from a regression of observed vs predicted pH (69 buffer solutions). "RMSE about 0.14 pH units" is the accurate wording.
7. **Ohsu Fig. 1 "×1.74":** cited in the Python notes as an alternative kokumi gain; the number is from Goto 2016's citation of Ohsu, not printed in Ohsu 2010. Not used by the live model.
8. **Mixed threshold methods:** the Na threshold (Yamaguchi, 0.00063 M NaCl) and K threshold (Schiffman, 0.00242 M KCl) come from different methods; Schiffman's own NaCl threshold is 3.8× Yamaguchi's.
9. **Moskowitz fit range:** the sucrose function was fitted on 2–16% only (Table 3 footnote); the 32% note threshold is wider than that.
10. **Code comments vs code:** the model block's header comment said "v.2.6.0" *(fixed to v.2.8.4, Nov 25, 2026)* and "hfp_model.py is the source of truth"; the code itself is v.2.8.4 and matches the Python reference model (parity tests by the author). The Python model has options the page does not use (serving temperature, extra units such as "c", "cups", "cm3", "mt", "t", alternative salt-umami modes, a water-content warning); they are not part of this specification.
11. **Page text:** *(Fixed on the live page Nov 25, 2026.)* "380 ingredients and counting" is out of date (431 research ingredients plus 2 helpers).

## 15. Test recipes and tolerances

`test_recipes.json` contains:

- `recipes`: 53 cases. G01–G38 are the project's golden recipes (all outputs, cooking, evaporation, volume units, sweeteners, KCl, coffee, chocolate). X01–X15 were added for this package: synergy cap, nucleotide-alone term, glutamate below threshold, per-item `cys_loss_on_cut`, per-item `cook_min` with a page-style temperature, cooking below the nuclease temperature, the page's tomato-sauce example with the page's percentage evaporation (stored as grams), imperial mass units, theobromine above its solubility, acesulfame K above its tested range, `acidity: false`, `k_source: "total"`, and three exact boundaries (cooking at exactly 65 °C and 89 °C; an ingredient at exactly 1% of the mass for the data-gap flags).
- each case: `recipe` (items as `{ingredient, amount, unit}` plus optional per-item fields), `opt`, and `expected`: `raw` (6 intensities), `score` (6 scores), `pH`, `intermediate` (total mass and water, salt % in water, sucrose-eq %, umami-eq, sour stimulus, citric equivalent, umami remaining, synergy pH factor), `note_keys` (11.1), and `missing` / `estimated` (11.2).
- `paste_cases`: 3 paste-parser inputs with the parser's expected line-by-line output (rules in 5.5 and `paste_rules.csv`).
- `derived_constants`: SCORE_REF values and the Miranda fit (29.4, 0.9).
- `block_sha256`: hashes of the exact page blocks that produced the values.

**Tolerances:** raw intensities and intermediates `|got − expected| ≤ max(1e-6, 1e-6 × |expected|)`; scores ±0.05; pH ±1e-4; sourness must be null when acidity is off; note keys, `missing` and `estimated` must match exactly. A rebuild that uses a different root finder should still meet these. The expected values were produced by `tools/oracle.js` executing the live page's own code under Node.js 26; the 38 golden recipes also agree with the project's frozen golden values to 1.4e-14.

## 16. References

Full table with DOIs, open-access status and licenses: `references.csv`. Hosted copies (openly licensed, unchanged, with their own license):

- Wee M., Tan V., Forde C. (2018). A comparison of psychophysical dose-response behaviour across 16 sweeteners. Nutrients 10(11):1632. https://doi.org/10.3390/nu10111632. CC BY 4.0. `papers/Wee_2018_Nutrients_10_1632_CC-BY-4.0.pdf`
- Ohsu T. et al. (2010). Involvement of the calcium-sensing receptor in human taste perception. J Biol Chem 285(2):1016–1022. https://doi.org/10.1074/jbc.M109.029165. CC BY 4.0 (publisher's open-access version). `papers/Ohsu_2010_JBiolChem_285_1016_CC-BY-4.0.pdf`
- Sun X., Zheng J., Liu B., Huang Z., Chen F. (2022). Characteristics of the enzyme-induced release of bitter peptides from wheat gluten hydrolysates. Front Nutr 9:1022257. https://doi.org/10.3389/fnut.2022.1022257. CC BY 4.0. `papers/Sun_2022_FrontNutr_9_1022257_CC-BY-4.0.pdf`

Linked only (copyrighted, free-to-read without an open license, or non-commercial license):

- Bartoshuk L.M. (1975). Taste mixtures: is mixture suppression related to compression? Physiol Behav 14:643–649. https://doi.org/10.1016/0031-9384(75)90193-6
- Breslin P.A.S., Beauchamp G.K. (1995). Suppression of bitterness by sodium: variation among bitter taste stimuli. Chem Senses 20:609–623. https://doi.org/10.1093/chemse/20.6.609
- Calvino A.M., Garcia-Medina M.R., Cometto-Muniz J.E. (1990). Interactions in caffeine–sucrose and coffee–sucrose mixtures: evidence of taste and flavor suppression. Chem Senses 15:505–519. https://doi.org/10.1093/chemse/15.5.505
- Chen Z. et al. (2017). Thermolysis kinetics and thermal degradation compounds of alliin. Food Chem 223:25–30. https://doi.org/10.1016/j.foodchem.2016.12.011
- Da Conceicao Neta E.R. et al. (2007). A chemical basis for sour taste perception of acid solutions and fresh-pack dill pickles. J Food Sci 72(6):S352–S359. https://doi.org/10.1111/j.1750-3841.2007.00400.x
- Da Conceicao Neta E.R. et al. (2009). Effects of pH adjustment and sodium ions on sour taste intensity of organic acids. J Food Sci 74(4):S165–S169. https://doi.org/10.1111/j.1750-3841.2009.01127.x
- Goto T.K. et al. (2016). Enhancement of combined umami and salty taste by glutathione in the human tongue and brain. Chem Senses. https://doi.org/10.1093/chemse/bjw066
- Hellfritsch C. et al. (2012). Human psychometric and taste receptor responses to steviol glycosides. J Agric Food Chem 60:6782–6793. https://doi.org/10.1021/jf301297n
- Keast R.S.J., Bournazel M.M.E., Breslin P.A.S. (2003). A psychophysical investigation of binary bitter-compound interactions. Chem Senses 28:301–313. https://doi.org/10.1093/chemse/28.4.301
- Keast R.S.J., Roper J. (2007). A complex relationship among chemical concentration, detection threshold, and suprathreshold intensity of bitter compounds. Chem Senses 32:245–253. https://doi.org/10.1093/chemse/bjl052
- Miranda A.M. et al. (2021). Factors affecting detection of a bimodal sour-savory mixture and inter-individual umami taste perception. Food Qual Prefer 89:104147. https://doi.org/10.1016/j.foodqual.2020.104147
- Moskowitz H.R. (1970). Ratio scales of sugar sweetness. Percept Psychophys 7:315–320. https://doi.org/10.3758/BF03210175
- Murphy C., Cardello A.V., Brand J.G. (1981). Tastes of fifteen halide salts following water and NaCl: anion and cation effects. Physiol Behav 26:1083–1095. https://doi.org/10.1016/0031-9384(81)90213-4
- Price R.E. et al. (2020). Modeling buffer capacity and pH in acid and acidified foods. J Food Sci 85:918–925. https://doi.org/10.1111/1750-3841.15091
- Schifferstein H.N.J., Frijters J.E.R. (1990). Sensory integration in citric acid/sucrose mixtures. Chem Senses 15:87–109. https://doi.org/10.1093/chemse/15.1.87
- Schiffman S.S., Booth B.J., Losee M.L., Pecore S.D., Warwick Z.S. (1995). Bitterness of sweeteners as a function of concentration. Brain Res Bull 36:505–513. https://doi.org/10.1016/0361-9230(94)00225-P
- Schiffman S.S., Manning M.P., Warwick Z.S., Crumbliss A.L. (1995). Detection thresholds of potassium salts are related to the molar conductivity of the anion. Brain Res Bull 37:623–626. https://doi.org/10.1016/0361-9230(95)00054-I
- Stark T., Bareuther S., Hofmann T. (2006). Molecular definition of the taste of roasted cocoa nibs (Theobroma cacao) by means of quantitative studies and sensory experiments. J Agric Food Chem 54:5530–5539. https://doi.org/10.1021/jf0608726
- Sun X. et al. (2022). The enhancement of the perception of saltiness by umami sensation elicited by flavor enhancers in salt solutions. Food Res Int 157:111287. https://doi.org/10.1016/j.foodres.2022.111287
- Torrico D.D., Prinyawiwatkul W. (2015). Psychophysical effects of increasing oil concentrations on saltiness and bitterness perception of oil-in-water emulsions. J Food Sci 80:S1885–S1892. https://doi.org/10.1111/1750-3841.12945
- Ueda Y. et al. (1990). Characteristic flavor constituents in water extract of garlic. Agric Biol Chem 54:163–169. https://doi.org/10.1080/00021369.1990.10869909
- Ueda Y. et al. (1997). Flavor characteristics of glutathione in raw and cooked foodstuffs. Biosci Biotechnol Biochem 61:1977–1980. https://doi.org/10.1271/bbb.61.1977
- Ugawa T., Konosu S., Kurihara K. (1992). Enhancing effects of NaCl and Na phosphate on human gustatory responses to amino acids. Chem Senses 17:811–815. https://doi.org/10.1093/chemse/17.6.811
- Ugawa T., Kurihara K. (1994). Enhancement of canine taste responses to umami substances by salts. Am J Physiol 266:R944–R949. https://doi.org/10.1152/ajpregu.1994.266.3.R944
- Xing R. et al. (2024). Comprehensive analyses of the bitterness of alkaloids and simulated taste mechanism of theacrine from Jianghua Kucha tea. Food Sci Technol Res 30:281–294. https://doi.org/10.3136/fstr.FSTR-D-23-00215 (CC BY-NC-SA: not re-hosted on a commercial site)
- Yamaguchi S. (1967). The synergistic taste effect of monosodium glutamate and disodium 5'-inosinate. J Food Sci 32:473–478. https://doi.org/10.1111/j.1365-2621.1967.tb09715.x
- Yamaguchi S., Yoshikawa T., Ikeda S., Ninomiya T. (1971). Measurement of the relative taste intensity of some L-α-amino acids and 5'-nucleotides. J Food Sci 36:846–849. https://doi.org/10.1111/j.1365-2621.1971.tb15541.x
- Yamaguchi S. (1979). The umami taste. In: Food Taste Chemistry, ACS Symposium Series 115:33–51. https://doi.org/10.1021/bk-1979-0115.ch002
- Yamaguchi S., Ninomiya K. (2000). Umami and food palatability. J Nutr 130:921S–926S. https://doi.org/10.1093/jn/130.4.921S
- Zhang F. et al. (2008). Molecular mechanism for the umami taste synergism. PNAS 105:20930–20934. https://doi.org/10.1073/pnas.0810174106
- Nguyen T.T., Palcic M.M., Hadziyev D. (1988). Enzymatic formation of nucleotides and the flavour enhancer 5'-GMP during vegetable processing. In: Bioflavour '87, Walter de Gruyter, pp. 275–286 (no DOI).

Datasets: USDA FoodData Central (https://fdc.nal.usda.gov/, CC0); FDA, Approximate pH of Foods and Food Products (U.S. Government work); Mars M., de Graaf C., Teo P.S., van Langeveld A.W.B. (2020), Taste, Fat and Texture Database – taste values Dutch Foods, DANS, https://doi.org/10.17026/dans-xst-ughm (CC BY-SA 4.0; validation only).

How the open-access check was done: DOIs were resolved on Crossref; open-access status and license came from OpenAlex (which aggregates Unpaywall data). The Unpaywall API itself rejected a placeholder contact address, so it was not queried directly. Only papers whose publisher record or PDF states CC BY were copied here.

## 17. License and how to cite

**License.** The text of this specification, the test recipes, the paste rules, the tools and the ingredient database (CSV and provenance file) are licensed under **Creative Commons Attribution 4.0 International (CC BY 4.0)**, https://creativecommons.org/licenses/by/4.0/. © Bryan Quoc Le, Mendocino Food Consulting. Hosted third-party papers in `papers/` keep their own licenses (all CC BY 4.0; credit their authors). The Mars et al. SVT dataset is CC BY-SA 4.0: anything you derive from it must stay CC BY-SA.

**Cite this as:** Le, B. Q. (2026). *Taste Check model, version 2.8.5: rebuild specification, ingredient database and test recipes.* Mendocino Food Consulting, Human Flavorome Project. https://tools.mendocinofoodconsulting.com/taste-check/rebuild/REBUILD.md Archived on Zenodo: https://doi.org/10.5281/zenodo.24540783 (all versions; v2.8.5 is https://doi.org/10.5281/zenodo.24540784). Source code: https://github.com/bryanquocle/taste-check

## 18. Changelog (model)

| Version | Date (2026) | Change |
|---|---|---|
| 2.2.2–2.2.3 | Sept 23 | Corrected spreadsheet port: salt forms, thresholds as cations, kokumi as glutathione equivalents (γ-EVG ×12.8), kokumi gains 0.41, salt shift of umami (×2 placeholder), cooked nucleotides, cysteine sulfoxide kinetics |
| 2.3.0–2.3.1 | Sept 24–25 | pH by charge balance, sour stimulus, Miranda umami suppression, synergy vs pH; smooth nucleotide drop of the glutamate threshold |
| 2.4.0 | Sept 25 | Sweetness (Moskowitz), sugar–acid interactions (Schifferstein & Frijters) |
| 2.5.0 | Sept 25 | 1–10 scores; unsourced salt → umami threshold rule switched off |
| 2.6.0 | Sept 28 | Synergy capped at 16×; sourness output on Yamaguchi's tartaric curve |
| 2.6.2 | Nov 15 | Umami 10/10 reference includes the salt and kokumi boosts (29.61) |
| 2.6.3, 2.7.0, 2.7.1 | Nov 20 | Polyols, high-intensity sweeteners, allulose and maltitol (Wee 2018) |
| 2.7.2 | Nov 21 | NaCl + KCl by concentration addition |
| 2.7.3 | Nov 21 | IMP/GMP alone taste of umami (background glutamate term) |
| 2.8.0 | Nov 21 | Bitterness: caffeine and KCl (Torrico), sodium and sugar suppression |
| 2.8.1 | Nov 23 | Umami raises saltiness (Sun 2022) |
| 2.8.2 | Nov 24 | Theobromine (Xing 2024), Reb A, sourced sugar masking (Calvino 1990); chocolate rows; theobromine column |
| 2.8.3 | Nov 24 | Bitterness on a whole-food basis (Stark 2006), theobromine solubility cap, Reb A re-sourced and acesulfame K added (Schiffman 1995). Live Nov 24, 2026 |
| 2.8.4 | Nov 25 | Synergy cap 16× → 63× (Yamaguchi & Kimizuka 1979); kokumi EC50 relabelled as an assumption; model header comment fixed |
| 2.8.5 | Nov 25 | Whole-food tasted basis for salt, sweet, umami, sour and kokumi (pH stays water-phase); validated on a pre-registered SVT hold-out |
| 2.9.0 | Nov 25 | Nucleotide thresholds from Kuninaka 1980 (alone only); kokumi detection floor (Ueda 1997); Horie 2012 cooked GMP for 5 vegetables; saccharin sweetness and bitterness (Schiffman 1995); data fixes (3 tomato glutamates, celery and parsley acids, green tea K/Na/water, mint density, 5 raw GMP fills) |
| 2.10.0 | Nov 25 | 824 ingredients (392 USDA SR Legacy composition rows); paste parser covers the 1,000 most common missing recipe ingredients plus fixes; page: paste-first layout and pot-based cooking water-loss estimator. Taste equations unchanged |
| 2.11.0 | Nov 25 | Salt no longer raises umami (SALT_SHIFT_MAX 2.0 → 1.0; umami 10/10 reference recomputes 29.61 → 26.02); aspartate threshold sourced (Yamaguchi 1991); cooking estimator: lid factors fade toward 0.85 (on) and 0.9 (ajar) at a boil (Snitkjær 2017) |

Data: v.2.6.9 (Nov 24, 2026) corrected the database flags found with the SVT validation (sugars and acids for several foods, salted/unsalted chips and peanut butter rows); v.2.8.2 added the theobromine column and three chocolate rows.
