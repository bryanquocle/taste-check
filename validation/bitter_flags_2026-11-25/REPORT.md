# Bitterness coverage flags: report

Nov 25, 2026. This is a proposal only. No model, database or website file was edited. The rules were frozen before testing (`FREEZE.txt`, 03:40 UTC Nov 26), and nothing changed after the freeze.

## Summary

- **Verdict: PASS on all three pre-registered checks.** It's ready to wire in once the raw-onion wording is fixed (see the nuisance check below).
- **Held-out SVT half (the primary test):**
  - It fired on **5 of 6** foods that the panel scored bitter (15 or more) but the model scores 0. That's 83%, against a mark of at least 70%.
  - It fired on **0 of 20** foods the panel scored under 3. That's 0%, against a mark of at most 15%.
  - The one miss is **cooked green pepper** (panel 19). I knew before the test that no class covers it.
- **Dev half:** 6 of 6 and 0 of 21. No tuning was needed.
- **Blind keyword test on about 490 SVT foods that were never mapped:** it fired on **10 of 14** bitter foods with no modeled bitterant (71%) and on **4 of 337** low-bitter foods (1%). That's a pass, but only just on the first mark.
- **Nuisance rate on 460 real Food.com recipes:**
  - **5.0%** (23 recipes) as pasted with no cooking entered.
  - **1.1%** (5 recipes) when 30 minutes of cooking is entered.
  - 14 of the 23 hits are raw-onion or raw-garlic flags on dishes that are actually cooked.
- **The samples are small.**
  - 5 of 6 has a 95% CI of 44–97%, and 10 of 14 has a CI of 45–88%.
  - The low-bitter side is solid: 0 of 41 across both SVT halves (CI 0–9%) and 4 of 337 in the keyword test (CI 0–3%).
- **Caveat on the held-out test.** I built the classes knowing the 24 SVT misses from the Nov 25 review. So the held-out half checks the frozen thresholds and the raw/cooked logic, but it's not blind to which ingredients are in the classes. The keyword test on unmapped foods is the blind check.

## How the flag works

- **Inputs:** 62 database rows in 12 compound classes (`bitter_sources.csv`). Each row has a strength number and a cooking rule.
- **Firing rule:**
  - For each class, add up `share of recipe mass × strength × cooking factor` over its rows.
  - If the total is 1 or more, the flag fires.
  - It adds one note and changes no scores.
- **Strength:**
  - Strength means the bitter ingredient stays noticeable (10 of 100 on the SVT scale) once the rest of the recipe dilutes it.
  - Dilution is converted to bitterness with the model's existing caffeine exponent (0.87).
  - Anchors from the dev half (the share of the recipe at which each fires):
    - raw onion 52.5: 15% or more
    - grapefruit juice and beer 57: 13.5%
    - claret 36.5: 23%
    - brewed coffee 58.5: 13%
  - Classes with no anchor use a default of 20, which fires at 45% or more. **The default is an assumption.**
- **Glucosinolates are content-based**, using McNaughton & Marks 2003, the source that came in mid-task.
  - The threshold is 65 mg/100 g as eaten, anchored on boiled Brussels sprouts (dev half).
  - Values are the Table 2 medians (p. 693–694).
  - Cooking losses are per vegetable from Table 3 (p. 695), or 36% where a vegetable has no row.
  - Brussels sprouts fire at 28% of the recipe raw and 48% cooked. Mustard greens fire at 23%.
  - Broccoli, cabbage and cauliflower never fire alone (61.7, 58.9 and 43.2 mg/100 g).
- **Ethanol is content-based.**
  - The threshold is 2.5 g/100 g as eaten, anchored on generic wine (dev half).
  - Ethanol amounts come from USDA SR Legacy.
  - Cooking follows the Augustin 1992 retention curve: 40% left after 15 minutes, 25% after an hour.
- **Raw alliums:** the flag turns off as soon as any cooking at 60 °C or above is entered (Song & Milner 2001).

## Class table

| Class | Example DB ingredients | Cooking | Source (ChemTastesDB ID, CC BY) |
|---|---|---|---|
| Hop acids | Beer | stays | Teng 2024 J Am Soc Mass Spectrom 35:746 (humulone 1592, isohumulones 1345/2092) |
| Ethanol | Wines, beer, spirits, sake, port, coffee liqueur, mirin | retention curve | Scinska 2000 Drug Alcohol Depend 60:199; Noble 1994 Physiol Behav 56:1251; USDA SR Legacy; Augustin 1992 J Am Diet Assoc 92:486 |
| Red-wine tannins/catechins | Claret, Dry Red, Port | stays | Noble 1994 (catechin 1283, epicatechin 0980) |
| Naringin, limonin | Grapefruit, grapefruit juice, orange marmalade | stays | Drewnowski & Gomez-Carneros 2000 Am J Clin Nutr 72:1424; Gordon 2021 Food Chem 352:129367 (naringin 1770, limonin 1672, neohesperidin 1773) |
| Glucosinolates | Brussels sprouts, mustard greens, collards, kale, radish, daikon, watercress, horseradish (broccoli, cabbage etc. count toward the sum) | Table 3 loss | McNaughton & Marks 2003 Br J Nutr 90:687; Wieczorek 2018 Crit Rev Food Sci Nutr 58:3130 (sinigrin 1971, progoitrin 1900, goitrin 1566, AITC 2327) |
| Raw-allium sulfur compounds | Onion, leek, shallot, garlic, green onion, chive | off when cooked | Song & Milner 2001 J Nutr 131:1054S. Weakest class: no paper names the raw-onion bitterant. Caveat: Kubec 2018 J Agric Food Chem 66:8783 found bitter allithiolanes in *processed* onion |
| Tea catechins (partly modeled) | Black and green brewed tea | stays | Scharbert & Hofmann 2005 J Agric Food Chem 53:5377 (EGCG 1487) |
| Coffee roast bitters (partly modeled) | Brewed coffee, espresso | stays | Frank 2006 Eur Food Res Technol 222:492; Blumberg 2010 J Agric Food Chem 58:3720 (caffeoyl-quinide 1107) |
| Cocoa flavan-3-ols (partly modeled) | Cocoa, nibs, unsweetened, dark and bittersweet chocolate | stays | Stark 2006 J Agric Food Chem 54:5530 (epicatechin 0980) |
| Sesquiterpene lactones | Radicchio, endive | stays | Wulfkuehler 2013 J Agric Food Chem 61:7705 (lactucin 1648, lactucopicrin 1650) |
| Olive secoiridoids | Green olives, extra virgin olive oil | stays | Gutiérrez-Rosales 2003 J Agric Food Chem 51:6021; Cui 2021 Sci Rep 11:22340 (oleuropein 1802) |
| Cucurbitanes | Bitter melon | stays | Snee 2011 Nutr J 10:78 (momordicine I 1743) |

- **ChemTastesDB:** I downloaded v1.0 from Zenodo today (record 5747393, license CC BY 4.0 per the record). Every class except ethanol and raw allium has an entry. It lists ethanol only as "non-sweet" and has no allium sulfur tastants.
- **BitterDB** wasn't used.
- **Not flagged, on purpose:**
  - Aged cheese. The hydrolysate note already exists.
  - Orange juice and zests, lettuce, black olives, refined olive oil, cucumber and zucchini.
  - Walnut and green pepper. I found no source.
  - Arugula, wasabi and mustard. McNaughton & Marks give no glucosinolate value for them.
  - Dry concentrates (instant coffee, coffee beans, dry tea leaf).
  - The DB row "Cider", which is apple juice according to its USDA source.

## Results in detail

### SVT held-out half (test)

| Food | Panel | Fired |
|---|---|---|
| Beer | 66 | hop acids, ethanol |
| Leek (raw juice) | 35.5 | raw allium |
| Wine, generic (fridge) | 26 | ethanol |
| Black tea | 20 | tea catechins |
| Green pepper (cooked) | 19 | **miss** |
| Black tea + sugar | 16 | tea catechins |

- Low-bitter foods: 0 of 20 fired.
- Mid-range foods that fired (not scored): dark chocolates, coffee with sugar, daikon (panel 7).

### SVT dev half

- Targets: 6 of 6 fired (beer, grapefruit juice, raw onion, claret, generic wine, cooked Brussels sprouts).
- Low-bitter foods: 0 of 21 fired.
- Mid-range foods that fired (not scored): coffee, cooked kale (panel 7).

### Blind keyword test (unmapped SVT foods)

- **Hits:**
  - IPA 62, strong beer 53, alcohol-free Amstel 49 (via hops), tonic water 38.
  - Rosé wines 28 and 24, whisky 25, sweet white wines 22 and 18, radler 17.
- **Misses:**
  - Hard cider 23. Cider is excluded because the DB row is juice.
  - Marmite 23. Yeast-extract bitterness has no class.
  - Average mineral water 19. Probably minerals or panel noise.
  - Plain olive oil 17. Refined oil was excluded on purpose, but the panel disagrees, so consider adding "Oil, Olive" later.
- **Low-bitter foods that fired (4 of 337):**
  - Two wine gums. Keyword artifact; candy names aren't DB rows.
  - Pickled silver-skin onions. Pickled, not raw.
  - One iced tea.
- **Keyword-only defect:** alcohol-free wines (panel 11) fired "ethanol" because "alcohol free" came after the first 3 words. This doesn't affect the database version.

### Nuisance check (460 Food.com recipes, paste parser)

- **No cooking entered (the page default): 23 of 460 (5.0%).**
  - By class: raw allium 14, ethanol 5, hop acids 3, coffee 1.
  - Truly raw: guacamole, onion and crab dips, a pizza topping.
  - False hits, all cooked dishes where nobody entered cooking: French onion soup, a curry, enchiladas, a stir-fry, a frittata, rum and apricot cakes.
- **30 minutes of cooking entered: 5 of 460 (1.1%).** The hits were beer bread, beer rolls, beer chili, a vodka lemonade and a coffee smoothie.
- **Never fired in this sample:** wine, grapefruit and brassicas. Food.com savory dishes rarely have them at high shares.
- **Fix:**
  - Word the raw-allium part conditionally: "If the onion is eaten raw, …".
  - Better still, show that part only when the cooking box is empty, and say so in the note. The false hits then become a true statement ("if raw").

## Implementation proposal (not applied)

### Python (`hfp_model.py`) and the JS mirror (`web/hfp_model.js`)

1. **Add a constant table `BITTER_GAP`**, mapping each DB name to a list of `(class, k, cook_rule, loss)`.
   - Build it from `bitter_sources.csv`, using the k values computed here (`bitter_flags.load_sources()`).
   - In JS, use a literal object with the same numbers rounded to 6 significant figures. `web_parity.py` checks the notes.
   - Add the constants `BITTER_GAP_GSL_MIN = 65`, `BITTER_GAP_ETOH_MIN = 2.5`, the `ETOH_RETENTION` points and `COOK_MIN_TEMP_C = 60`.
2. **In `compute()`, right after the `bitter_protein` warning:**
   - Loop over `rows`, using `mass_g`, the item's own `cook_min` (else the recipe's), `cook_temp_c` and `water_loss_g`.
   - Sum the dose per class.
   - When any class reaches 1, append one note with the key **`bitter_gap`**.
   - The logic is the same as `bitter_flags.flags()`, about 25 lines.
3. **Note text:**
   - Default: "Bitterness may read low: grapefruit juice (naringin and limonin) adds bitterness Taste Check doesn't score yet. This is a note, not a score change."
   - Partly modeled: "…brewed coffee (roast bitters such as chlorogenic acid lactones; only its caffeine is scored)…"
   - Raw allium: "…onion (raw-onion sulfur compounds, only if eaten raw; enter a cooking time if it's cooked)…"
   - Keep the existing `bitter_scope` note unchanged so no test keys change. Optionally drop it when `bitter_gap` already names coffee, tea or cocoa.
4. **Tests:**
   - Add three golden recipes:
     - grapefruit juice 100 g → `bitter_gap`
     - onion 100 g cooked 10 min → no `bitter_gap`
     - Brussels sprouts 50 g + water 50 g, raw → dose 1.82 → `bitter_gap`
   - Re-freeze the notes in `golden_expected.json` after Bryan approves.
   - `svt_panel_test.py` scores don't change.

### REBUILD.md text (proposed)

**Add to the end of section 8.6:**

> **Coverage note (`bitter_gap`, v.2.x; no score change).** For each class in `BITTER_GAP` (section 12.6), `dose = Σ (mass_g / total mass after evaporation) × k × cook`.
>
> A row counts as cooked when its `cook_min` (else the recipe's) is above 0 and T is missing or ≥ 60. The cook factor is:
> - `raw_only`: 0.
> - `gsl_loss`: 1 − loss.
> - `etoh_retention`: interpolated through (0+, 0.85), (15, 0.40), (30, 0.35), (60, 0.25), (90, 0.20), (120, 0.10), (150, 0.05), then held at 0.05 (Augustin et al. 1992).
> - Any other rule: 1.
>
> The k values are:
> - `k = (B_ref/10)^(1/0.87)`, with B_ref from the SVT anchor or a default of 20.
> - `k = GSL/65` for glucosinolates (McNaughton & Marks 2003, Table 2 medians).
> - `k = EtOH/2.5` for ethanol (USDA SR Legacy, g/100 g).
>
> The note fires once if any class has dose ≥ 1. It lists ingredients and classes in table order. Validation: `validation/bitter_flags_2026-11-25/`.

**Add this row to the section 11.1 table:**

> `bitter_gap` | some class in `BITTER_GAP` has dose ≥ 1 (8.6) | once

**Add to section 12.6:** the `BITTER_GAP` rows (ingredient, class, k, cook_rule, loss) and the constants `BITTER_GAP_GSL_MIN = 65`, `BITTER_GAP_ETOH_MIN = 2.5` and `COOK_MIN_TEMP_C = 60`.

## Open items and caveats

- **The default strength of 20 is a guess.** It covers tea, cocoa, chicory, olives and bitter melon, and only sets the share where they fire (45%). Pure foods fire regardless.
- **The Augustin 1992 retention numbers** come from the USDA retention table. I couldn't re-read the paper (PubMed has no abstract), so check them against the PDF before shipping.
- **Mirin's ethanol** (9.4 g/100 g) is an estimate. USDA has no entry.
- **Possible additions, each needing a source:**
  - plain olive oil (panel 17)
  - hard cider (needs its own DB row with ethanol)
  - yeast extract and Marmite
  - green pepper
  - walnut skin
- **McNaughton & Marks 2003** is already in the protocol; it arrived before the freeze. A future quantitative version could score glucosinolate bitterness directly, but that needs a sensory dose–response study such as van Doorn 1998, which isn't in the Papers folder.

## Files

- `PROTOCOL.md` and `FREEZE.txt`: the frozen rules and their hashes.
- `bitter_sources.csv` (62 rows) and `make_sources.py`, which writes it.
- `bitter_flags.py`: the prototype flag.
- `svt_split.py` and `svt_units.csv`: the SVT units and the seeded split.
- `evaluate.py` and `paste_rows_runner.js`: the runners.
- `results_dev.json`, `results_test.json`, `results_keyword.json` and `results_paste.json`: the outputs.
