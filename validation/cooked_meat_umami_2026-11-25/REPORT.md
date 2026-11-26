# Cooked meat umami: scoping (Nov 25, 2026)

Proposal only. Nothing in `hfp_raw_data.csv`, the model files or the website was changed. All runs use an in-memory copy of the database (`scripts/effect_estimate.py`).

## Summary

| Question | Answer |
|---|---|
| Why does the pan-fried hamburger read umami 2.0 (panel 31)? | **The data, not the cooking.** `Hamburger Meat` has **blank AMP/IMP/GMP**, so it gets no glutamate–IMP synergy. Its umami comes from glutamate alone. |
| Does cooking explain it? | No. Cooking moves the score by about +0.2 to +0.6. Filling in the nucleotides moves it by +5.7. |
| Do cooked meats under-read in general? | No. Cooked pork and chicken dishes (rows that carry IMP) already score **at or above** the panel: schnitzel 6.2 (≈20 vs panel 13), nuggets 6.0 (≈20 vs 21), frikandel 6.8 (≈22 vs 21). Every recipe that reads low is built on minced beef. |
| Recommended rule | **P1: Fill `Hamburger Meat` nucleotides as a tier-2 sibling of `Beef`, scaled by lean content:** AMP 6.7, IMP 66.7, GMP 3.3 mg/100 g. Then do the same for the other muscle rows with blank values (P2) and fix the missing-data warning (P3). |
| Effect on the hamburger | Score 1.96 → **7.64** (≈7 → ≈25 on the panel scale). Adding the cooking loss gets it to 8.0–8.2 (≈26–27). Panel: 31. |
| Effect on the whole benchmark (exploratory, not a new test) | Umami rho goes from 0.567 to **0.612**, and MAE from 8.14 to **7.31**. |
| Skeptic's note | About 4–6 panel points stay unexplained. A score of 10 calibrates to only about 32 on the panel scale, so the scale ceiling is part of it. Maillard aroma, peptides and fat were not modeled, and they don't need to be to close most of the gap. |

## 1. What the literature says (raw vs cooked)

Full table with quotes, pages and DOIs: `literature_table.csv`. Values are mg/100 g as reported, treated as free acid. Not one of these papers says whether its standards were salts or free acids.

| Meat | Method | IMP, cooked ÷ raw | Free Glu, cooked ÷ raw | Source (OA?) |
|---|---|---|---|---|
| Beef semitendinosus | Bag, 70 °C 30 min | 0.94 (49.6 → 46.7) | n/a (acid-hydrolysis Glu, not free) | Hwang 2020, Foods, [10.3390/foods9030251](https://doi.org/10.3390/foods9030251) (OA; in Papers) |
| Beef semitendinosus | Sous vide 70 °C 6–12 h | 0.72–0.80; GMP up to 12.4 | n/a | Hwang 2020, Table 4 p. 7 |
| Beef semitendinosus | Sous vide 60 °C 6–12 h | 0.61–0.62 | n/a | Hwang 2020 |
| Beef longissimus | Steam, boil 90 °C, oven 160 °C | 0.13–0.48 | 1.5–2.8 | Wang 2023, Foods, [10.3390/foods12030446](https://doi.org/10.3390/foods12030446) (OA). **Units look wrong** (raw IMP 1.01), so use direction only. |
| Pork loin | Sous vide 60–80 °C, 1–3 h | ≈1.0 | ≈1.0 in meat; juice Glu rises at 80 °C | Rotola-Pukkila 2015, J Food Sci, [10.1111/1750-3841.13127](https://doi.org/10.1111/1750-3841.13127) (paywalled; abstract and dissertation summary) |
| Pork | Moist heat to 180 min | Meat ↓, juice ↑; **meat + juice: up at 10 min, then flat** | Meat ↓, juice ↑; **meat + juice: unchanged** | Sasaki 2007, Meat Sci, [10.1016/j.meatsci.2007.02.025](https://doi.org/10.1016/j.meatsci.2007.02.025) (abstract) |
| Chicken breast | Boiled 40 min, core >72 °C | 0.46 (351 → 161) | 0.73 (28 → 21) | Jayasena 2015, Poultry Sci, [10.3382/ps/pev154](https://doi.org/10.3382/ps/pev154), Table 1 p. 1968 (free PDF on the authors' lab site) |
| Chicken leg | Same | 0.45 (136 → 61) | 0.66 (37 → 24) | Same |
| Fish | — | No usable raw-vs-cooked data found | — | Gap |

What the papers agree on:
- **Free glutamate is conserved.** Normal cooking moves it out of the meat into the juice; it doesn't make or destroy it. Glu only rises with long low-temperature holds (Yuhara 2021: 16 h at 55 °C, faster in chicken than beef).
- **IMP loss is enzymatic and slow at cooking temperatures.** 5′-nucleotidase works fastest around 50–60 °C and is dead above about 64 °C (Hwang citing Ishiwatari 2013; Arya 1979). Real thermal breakdown needs about 120 °C. A quick sear loses little, while a long 60 °C sous vide loses about 40%.
- **Ageing matters more than cooking.** During conditioning IMP turns into inosine and then hypoxanthine (Koutsidis 2008: ribose up 6×; Tikk 2006: IMP goes with "meaty/brothy", hypoxanthine with bitter). Retail beef may carry less IMP than the DB's Beef row. That's why the low-end sensitivity runs below matter.
- **The human-panel link exists.** In roasted Japanese Black sirloin, IMP correlated with panel umami intensity, and raw composition predicted roasted composition (Suzuki 2017, [10.1111/asj.12663](https://doi.org/10.1111/asj.12663)).

## 2. Decomposition: water loss vs chemistry

USDA SR Legacy raw vs cooked pairs (`usda_yields.csv`). Yield = protein raw ÷ protein cooked.

| Item | Yield | Water lost (g per 100 g raw) | Fat lost (g per 100 g raw) | Concentration if fully retained |
|---|---|---|---|---|
| Ground beef 70/30, pan-broiled | 62.8% | 17.0 | 20.2 | ×1.59 |
| Ground beef 80/20, pan-broiled | 71.4% | 19.7 | 8.6 | ×1.40 |
| Ground beef 85/15, pan-broiled | 75.5% | 19.9 | 4.4 | ×1.32 |
| Chicken breast, roasted / stewed / fried | 72.5 / 77.6 / 67.3% | 26.6 / 20.9 / 33.4 | ~0 | ×1.38 / 1.29 / 1.49 |
| Pork tenderloin, roasted | 80.1% | 20.4 | ~0 | ×1.25 |
| Cod, dry heat | 78.0% | 22.0 | 0 | ×1.28 |

- **(a) Concentration.** Water and fat loss would raise every retained solute per gram eaten by ×1.3 to ×1.6.
- **(b) Real change.** Boiled chicken, per raw-weight basis (observed ratio × 0.776 yield): the meat keeps about 0.35 of its IMP and 0.56 of its Glu. The rest went into the water, plus some IMP degradation. So the boiling losses are mostly leaching, not chemistry (Sasaki 2007).
- **Hamburger (dry heat, short, core ≈70 °C).** Chemistry gives IMP about ×0.94 and Glu about ×1.0. Concentration gives up to ×1.59, minus solutes lost in the drip. **Net per gram eaten: roughly ×1.2 to ×1.5 for both.** No paper measured a pan-fried patty directly; this is an estimate.

## 3. Proposed rules (`proposals.csv`)

1. **P1, do first:** Fill the `Hamburger Meat` nucleotides with AMP 6.7, IMP 66.7, GMP 3.3, which is the Beef row (Yamaguchi & Ninomiya 2000, tier 1) × 14.35/17.2 protein. Mark it tier 2 in the Data Quality sheet.
2. **P2:** 37 of the 69 muscle rows in `muscle_foods_v2140.json` have blank AMP/IMP/GMP, and most of those also have blank glutamate. Fill the fresh rows by species sibling × protein ratio. Leave the cured, canned and processed rows (ham, bacon, hot dog, canned fish, bologna) blank until they're sourced, because curing and retorting destroy IMP.
3. **P3:** The missing-nucleotide warning only fires when glu ≥ 100 mg/100 g, so the hamburger gap was never flagged. Flag muscle foods regardless of glutamate.
4. **P4 (later, small):** Add a `COOKED_MEAT_YIELD` dict in the style of `COOKED_NUCLEOTIDES`, using the USDA yields above. When cook_min > 0, remove the meat row's own water **and rendered fat**, with no chemistry change for dry heat.
5. **Don't build:** a kinetic IMP-loss term (P6) or a cooked-glutamate formation factor (P7). The evidence is against the glutamate factor. Also, IMP sits on the model's synergy plateau: IMP ×0.6 gives the same score.

**Is the meat's own water loss already handled?** No.
- `cook_min`/`cook_temp_c` only drive cysteine-sulfoxide loss and the vegetable `COOKED_NUCLEOTIDES` swap.
- `--evaporate` / `water_loss_g` removes water from the whole recipe, so a user can mimic meat water loss by hand, but nothing does it by default (the benchmark ran with no cooking).
- It can't remove rendered fat. For a 70/30 patty it captures only about 46% of the true mass loss: 17 g water out of 37 g water + fat.

## 4. Effect estimate (benchmark hamburger: 90 g Hamburger Meat, 5 g sunflower oil, 3 g salt, 2 g pepper)

Panel units ≈ 0.990 + 3.141 × score. That's the frozen benchmark line, and it tops out at about 32.

| Scenario | Umami score | ≈ Panel units |
|---|---|---|
| S0 baseline (as benchmarked) | 1.96 | 7.1 |
| S0b baseline + meat water loss only (15.3 g) | 2.17 | 7.8 |
| **S1 P1 gap-fill (raw)** | **7.64** | **25.0** |
| S1 with nucleotides ×0.5 / ×0.25 / ×0.1 / ×0.05 | 7.64 / 6.65 / 5.30 / 4.51 | 25.0 / 21.9 / 17.6 / 15.2 |
| S1 with glu 10 (if 60.7 is too high) | 5.24 | 17.4 |
| S2 gap-fill + water loss + IMP ×0.94 | 8.02 | 26.2 |
| S3 gap-fill + cooked row (solutes ×1.59, IMP ×0.94), 90 g eaten | 8.24 | 26.9 |
| S3b same, mass-balanced (56.5 g cooked meat) | 8.10 | 26.4 |
| S3c cooked row, IMP ×0.6 | 8.24 | 26.9 |
| **Panel** | — | **31** |
| Croquette: baseline / gap-fill / + pre-cooked beef row | 1.0 / 3.68 / 4.44 | 4.1 / 12.5 / 14.9 (panel 25) |

Exploratory re-score of all 68 benchmark recipes with P1 only. This is not a pre-registered test, so a fresh hold-out is needed before claiming it.
- Umami Spearman goes from 0.567 to 0.612, and calibrated MAE from 8.14 to 7.31.
- Beef recipes, baseline → P1 (≈ panel units → panel):
  - Hamburger: 1.96 → 7.64 (≈25 vs 31)
  - Tartare: 1.70 → 6.68 (≈22 vs 19)
  - Bapao: 2.00 → 6.77 (≈22 vs 25)
  - Bolognese: 2.98 → 4.03 (≈14 vs 25)
  - Croquette: 1.0 → 3.68 (≈13 vs 25)
  - Olvarit beef baby food: 1.0 → 3.44 (≈12 vs **5**, now over-reads)

## 5. Caveats (be skeptical)

- **Which beef values?** The P1 numbers rest on one sibling row (Yamaguchi & Ninomiya Beef: IMP 80). Retail ground beef is aged, and its IMP could be half that. The score doesn't care down to about 50%, but it falls off below 25%.
- **`Hamburger Meat` glutamate 60.7 has no recorded source.** It's 6× the Beef row (10). If it's really about 10, P1 gives 5.2 instead of 7.6. That's worth checking before P1 ships.
- **The residual gap.** It's about 4–6 panel units for the hamburger and about 10 for the croquette. The culprits are plausible but unmodeled:
  - Maillard and roast aroma raising perceived savoriness (aroma–taste interaction)
  - Umami and kokumi peptides
  - The 1–10 scale ceiling (score 10 ≈ 32 panel units)
  - The panel's recipe breakdown (the croquette ragout probably contains stock or bouillon that isn't listed)
- **None of these is a good model target yet.**
- **The cooked data are messy.** Hwang reports units as g/100 g and measures glutamate by acid hydrolysis. Wang's units are off by about 100×. None of the cooked numbers are corrected for yield. The direction is solid; the magnitudes are ±30% at best.
- **Salt and free-acid basis.** Assumed free acid throughout. If the standards were disodium salts, IMP would be about 20% lower, which doesn't change the score (plateau).

## Files

- `literature_table.csv`: per-source raw vs cooked values, method, page/table, quote, OA status, reliability
- `usda_yields.csv` and `scripts/usda_yields.py`: USDA cooking yields, water and fat loss
- `proposals.csv`: rules P1–P7 with values, sources and effects
- `scripts/effect_estimate.py` and `effect_results.json`: model runs (in-memory DB copy only)
