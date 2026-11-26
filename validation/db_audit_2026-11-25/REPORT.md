# Taste Check ingredient DB audit: proposal only

Nov 25, 2026. Nothing in `hfp_raw_data.csv`, `hfp_data_quality.csv` or any model file was changed. Every proposed value below needs Bryan's OK before entry.

## Files

| File | What it is |
|---|---|
| `flags.csv` | All 534 flags. Reviewed items first (`review_rank` 1-40, with `verdict`, `proposed`, evidence), then the unreviewed automatic flags by score |
| `flags_raw.csv` | Raw output of `audit.py` (529 ingredient-field flags, all checks and evidence merged) |
| `impact_test.csv` | Score before/after for 14 proposals, run on a temp copy of the DB |
| `copy_pairs.csv` | Rows with identical sugar or Na/K/protein/sugar vectors (copy-paste detector) |
| `scripts/audit.py` | The 6 checks (re-runnable; standard library only) |
| `scripts/build_outputs.py` | Merges the manual review into `flags.csv` |
| `scripts/impact_test.py`, `copy_check.py`, `show_rows.py`, `usda_lookup.py` | Helpers |

Run order: `audit.py` -> `build_outputs.py` -> `impact_test.py` (Anaconda Python, `-X utf8`, `PYTHONIOENCODING=utf-8`).

## How the checks work

USDA linkage:
- 365 rows link through `staging_rows.csv`.
- 38 link through "SR Legacy NNNNNN" in their source text.
- 189 more link by an exact Na + K + protein fingerprint. This found that several "unsourced" rows are verbatim USDA foods.
- 38 link by a strict name match, which gets low confidence.
- 198 rows have no link.

| Check | What it tests | Unique flags* |
|---|---|---|
| 1 Physical | Negatives; >100 g/100 g; density 0.02-2.5; pH 1-10; Na >40 g outside salts; caffeine/theobromine where impossible; mass balance (water + protein + sugars + acids + NaCl-eq + USDA fat >103 g); free Glu >30% of protein and free Asp >15%; **free Glu/Asp > USDA total (bound + free) Glu/Asp**; gamma-EVG >1 mg/100 g; K = 0 in protein foods; caffeine blank in caffeine sources | 35 |
| 2 Unit slips | Each value against the category median and the linked USDA food; flags ratios within 0.15 log of 10x, 100x or 1000x. **Liquid density vs water %** (1 + 0.0039 x solids) | 99 |
| 3 Swaps | Glucose:fructose, Na:K, AMP/IMP/GMP, citric:malic, Glu:Asp and sucrose:glucose ratios inverted against a sibling row; Na > K in unsalted plant foods; IMP in plants; GMP > IMP in muscle | 33 |
| 4 Siblings | Dry-basis mismatch >=5x between rows with the same base name, with a protein dry-ratio control | 36 |
| 5 Totals | Sum of sugars vs USDA total sugars; acids vs pH (pH < 4 with almost no acid; >1.5 g acid at pH > 6.5) | 12 |
| 6 Outliers | Robust z (median/MAD of log10) per category and field, n >= 5, abs(z) >= 3.5 | 340 |

*A flag can hit several checks. There are 529 unique ingredient-field flags across 315 ingredients. Before review, 16 were high, 78 medium and 435 low confidence.

Ranking: each flag's score = the field's impact weight on Taste Check x confidence x size of the deviation. Flags hit by more than one check get a bonus. The impact weights are:
- Glu, IMP, GMP and Na: 1.0
- Sugars, the main acids, gamma-EVG and caffeine: 0.8
- pH: 0.7
- Density: 0.5
- Water and K: 0.35 (K is low because Python counts chloride K only)
- Protein: 0.15

**What the impact test showed:** Water % and density do not move single-ingredient scores on the v.2.8.5 whole-food basis. Water only sets the pH-phase concentration, and density only matters when a recipe enters an ingredient by volume. So the water and density errors below are real but low-impact, unless the recipe uses cups or tablespoons.

## Top 40 (manual review)

Verdict key:
- **ERROR**: likely real error, with a proposed value.
- **NEEDS SOURCE**: wrong or inconsistent, but no fix value yet.
- **GAP**: blank where a value must exist (blank loads as 0).
- **NAMING**: the values are right for a different product than the name says.
- **OK**: checked against the source; false positive.

| # | Ingredient | Field | Now | Verdict | Proposed | Evidence (short) | Conf. | Score impact |
|---|---|---|---|---|---|---|---|---|
| 1 | Juice, Grape | Glutamate | 258 | ERROR | 3.6 | Free Glu exceeds USDA 168207 *total* Glu (110 mg). The Grape row was already fixed to must 37.8 mg/L; the juice was missed. 37.8 / 1.054 = 3.6 | high | umami 3.93 -> 1.0 |
| 2 | Ketchup | Sucrose / Glucose / Fructose | 21340 / 3650 / 3650 | ERROR | 2300 / 10250 / 8720 | Row = USDA 168556. USDA's total 21.27 g was entered as sucrose, then glucose and fructose were added on top (28.6 g; mass balance 103.5 g) | high | sour 8.31 -> 8.69, umami 1.91 -> 1.80 |
| 3 | Grape | Sucrose | 1460 | ERROR | 150 | Rest of row = USDA 174683; USDA sucrose 0.15 g; ~10x | high | sweet 7.49 -> 6.57 |
| 4 | Burdock Root | Glucose + Fructose | 145 + 145 | ERROR | total 2900 (split needs source) | Row = USDA 169974 (total sugars 2.90 g); /10 slip | high | sweet 1.06 -> 2.18 |
| 5 | Vinegar, Balsamic | Density (Acetic) | 1.34 (4478) | ERROR | 1.08 (5556) | USDA 172241 water and sugars; 255 g/cup = 1.08. 1.34 is traditional DOP balsamic. The acetic value was derived by dividing by 1.34 | high | sour 8.53 -> 8.82 (15 g in 85 g water) |
| 6 | Beef Extract | Water | 32.5 | ERROR | 3.27 (re-source or rename) | Identical to Bouillon = USDA 171560 bouillon powder; water x10. Not real beef extract | high | none on food basis; naming -> salt |
| 7 | Maltose Syrup | Water | 77.5 | ERROR | ~22.5 (needs label) | Density 1.36 and mass balance 111.6 g. 100 - 77.5 = dry solids entered as water | high | none on food basis |
| 8 | Carob Syrup | Water / sugars | 85 / 13.4 g | NEEDS SOURCE | water ~25-30%, sugars ~5x | Density 1.275 and K 827 point to a concentrate; water and sugars look diluted | high | sweetness likely understated several-fold |
| 9 | Juice, Apple | Density | 1.33 | ERROR | 1.048 | USDA 173933: 248 g/cup. 1.33 = concentrate | high | volume recipes +27% juice |
| 10 | Coffee Bean | Ascorbic (+ whole row) | 213 | NEEDS SOURCE | 0; re-source the row | Coffee has no vitamin C. Water 50, protein 2.35 and K 82 fit no coffee product; caffeine is blank | high | bitter (no caffeine) |
| 11 | Cacao Nib | Theobromine, Caffeine | blank | GAP | needs source (~1,000-1,500 / 100-250) | Blank loads as 0; the cocoa powder row has 2057 / 230 | high | bitter |
| 12 | Green Tea (leaf) | Caffeine | blank | GAP | MEXT 16036 (verify; ~2,300 from memory) | Brewed rows have caffeine; the leaf row does not | high | bitter |
| 13 | Coconut Milk | Na/K/protein/water/sorbitol | 19 / 19 / 0.21 / 75.2 / 1500 | NEEDS SOURCE | choose canned USDA 170173 (Na 13 / K 220 / protein 2.02 / water 72.88) | Hybrid of the carton beverage (174116) and canned water; sorbitol unsourced | medium | sweet (sorbitol); K Excel only |
| 14 | Corn (Fresh) | Sucrose / Glucose | 890 / 3430 | NEEDS SOURCE | 3430 / 890 if confirmed | Copies USDA 169998. But every USDA canned corn is sucrose-dominant and sweet corn stores sucrose, so the USDA raw split is likely inverted | medium | sweet 4.19 -> 5.29 if swapped |
| 15 | Juice, Peach | Density | 1.163 | NEEDS SOURCE | ~1.05 | USDA peach nectar water is 87.3%. Asp 212 likely includes asparagine | medium | volume recipes +11% |
| 16 | Edamame | Na; sugars | 128; 4282 / 3170 / 1051 | NEEDS SOURCE | Na 6; 1130 / 0 / 210 (+ maltose 1140) | No source; USDA 168410/168411 | medium | salt, sweet |
| 17 | Nectarine | Na / K | 13 / 131 | NEEDS SOURCE | 0 / 201 | USDA 169914 (protein matches) | low | K (Excel) |
| 18 | Tortilla, Corn | Sugars (maltose) | 4020 (3150) | NEEDS SOURCE | ~880 total | USDA 175036; maltose is unlikely in masa | medium | sweet |
| 19 | Beef Stock Cube | K | 0 | ERROR | ~403 or blank | Missing coded as 0 (USDA cubes 309-446) | medium | K (Excel total-K) |
| 20 | Cheese, Manchego | K | 0 | ERROR | blank (~100) | K = 0 is impossible in cheese | medium | K (Excel) |
| 21 | Fish, Flying (Fresh) | K | 0 | ERROR | blank (~300-400) | K = 0 with 21 g protein | medium | K (Excel) |
| 22 | Black-Eyed Peas (+ Butter Bean, Great Northern, Navy Bean, Hominy) | Na | 267-370 | NAMING | add "(Canned)" or a cooked-from-dry row | Canned-with-salt USDA values under unqualified names | medium | salt (+0.3 g Na/100 g) |
| 23 | Spice, Onion (Dried Flakes) | Sucrose | 37410 | NEEDS SOURCE | split by raw-onion ratio: ~8,700 / 17,400 / 11,400 | Documented tier 3 (total entered as sucrose); onion is glucose/fructose-rich | medium | sweet (small) |
| 24 | Barley Malt Syrup | Sugars / water | 79.9 g / 20 | NEEDS SOURCE | check basis | Mass balance 104.7 g | low | sweet |
| 25 | Asparagus (Canned) | Citric | 900 | NEEDS SOURCE | needs source | 11.6x fresh on a dry basis; neither row has source text; sugars copied from fresh | medium | sour |
| 26 | Spinach | Glutamate | 9.9 | NEEDS SOURCE | consider 67 (Horie 2012) | Open from the earlier check; no source for 9.9 | medium | umami |
| 27 | Sauce, Tomato | Na | 11 | NAMING | "(No Salt Added)" | No-salt sibling of the canned row (474) | low | salt |
| 28 | Wasabi | Na | 3390 | NAMING | "(Prepared Paste)"; optional root row (USDA 168583) | = USDA 171831 paste | low | salt |
| 29 | Honey | Acids | all 0 | GAP | blank, or gluconic if ever modeled | pH 3.95 comes from gluconic acid (no column) | low | sour |
| 30 | Celery (+ Lettuce, Butterhead; Lettuce) | Glutathione | 0.07 (0.13, 0.51) | NEEDS SOURCE | needs source | 10-70x below the vegetable median; no source | low | kokumi |
| 31 | Vinegar, Rice | Density / water | 0.989 / 80 | NEEDS SOURCE | check water (plain ~94%) | The pair is inconsistent | low | sour |
| 32 | Sugar Beet Molasses | Water / protein | 22.4 / 13.5 | NEEDS SOURCE | check | Mass balance 104.3 g | low | none |
| 33 | Tomato Flesh/Pulp rows (17) | Glu / AMP / GMP | e.g. Piccolo pulp Glu 1650 | OK | - | Match Oruna-Concha 2007 Table 2 exactly (Piccolo pulp 16.5 g/kg; Elegance UK AMP 38/437 mg/kg) | high | - |
| 34 | Fish, Anchovy (Canned) | Glutamate | 630 | OK | - | Salt-ripened fillets; 600-1,400 is typical | medium | - |
| 35 | Ajitide I+G | IMP / GMP / Na | 44,395 / 44,601 / 11,505 | OK | - | Consistent with anhydrous disodium salts expressed as free acid | high | - |
| 36 | Saccharin (Sodium) | Na | 11,205 | OK | - | 23/205 of Na saccharin | high | - |
| 37 | Baking Powder | Na | 10,600 | OK | - | USDA double-acting | high | - |
| 38 | Broth, Chicken (+ low-Na broth, reduced-Na cream soups) | K | 18 | OK | - | USDA 174536; the low-Na versions use KCl | high | - |
| 39 | Oreo, Nutella, Snickers, Butterfinger | Caffeine / theobromine | 1-8 / 36-230 | OK | - | Cocoa products (USDA) | high | - |
| 40 | Kefir (Plain) | Galactose | 910 | OK | - | USDA 170904 | high | - |

**This week's known errors are all already corrected in the DB.** Manchego gamma-EVG 0.059, Kashkaval 0.035, fish sauce 0.189, doenjang sucrose 0, apple malic 427, green tea K 2,200 and mint density 0.108 are all in place. Miso is still open as known (glucose 7,719 vs USDA's odd fructose-only split).

## Patterns found

1. **Decimal slips against USDA (x10 and /10).** Grape sucrose (x10), burdock sugars (/10) and Beef Extract water (x10). They are the same family as green tea K, and all three rows are otherwise verbatim USDA.
2. **"Total sugars entered as sucrose", double-counted.** Ketchup got the USDA total as sucrose *plus* glucose and fructose (28.6 g vs 21.3 g). Onion flakes and doenjang (now fixed) entered the total as sucrose without double counting. Tier-3 "total as sucrose" rows (tofu, chocolate milk, onion flakes, wild rice and others) are fine for total sweetness, but they misstate the sugar mix.
3. **A fix applied to the parent row but not its derivative.** Grape Glu was corrected (184 -> 3.8), but Juice, Grape still carries 258 from the same unsourced family. Worth a sweep: whenever a row is corrected, grep for its siblings (`Juice, X`, `X (Dried)`, `X (Canned)`).
4. **Density borrowed from a different product than the composition.** Balsamic got DOP density with commercial composition, which also skewed the derived acetic value. Apple juice got concentrate density. Coconut milk mixes beverage and canned values.
5. **Water/solids confusion in syrups.** Maltose syrup (77.5 = 100 - 22.5) and carob syrup. The liquid-density check catches this class.
6. **Missing values coded as 0.** K = 0 in Manchego, flying fish and beef stock cube; all acids 0 in honey; sugars 0 in cacao nib. The model treats blank and 0 the same, but a 0 hides the gap from the tier warnings.
7. **Name ambiguity with big salt consequences.** Canned beans and hominy, wasabi paste, no-salt tomato sauce, and "Beef Extract" (really bouillon). Each row's values match its USDA food, but the name invites the wrong pick.
8. **Bitter actives missing where they must exist.** Cacao nib, coffee bean and green tea leaf.
9. **Free "Asp" in stone fruits probably includes asparagine.** Peach juice, nectarine and prunes sit at or near the total-protein ceiling. Umami impact is low because Asp is weighted 0.077.

## False-positive notes

- **The free-Glu-vs-protein rule misfires on tomato pulp.** The pulp rows carry whole-tomato protein (0.83-0.88 g). All Flesh/Pulp rows were verified against Oruna-Concha 2007 Table 2 and marked OK in `flags.csv`.
- **The category robust-z check (340 flags) mostly reflects real diversity.** Herbs mix fresh (~90% water) and dried (~10%); pickled vegetables carry salt; caviar has little IMP; unsweetened chocolate and cocoa sit in "Sweeteners". Treat check 6 as a search aid, not evidence. Only items confirmed by a second check or a source made the top 40.
- **Na > K in plant foods:** almost all hits are canned, pickled or salted products whose names don't say so (their USDA values are correct). They belong to pattern 7, not to swaps.
- **Name matching to USDA was noisy** (Mint -> After Eight; Sugar -> sugar-apple). The script now requires the USDA description's head to equal the ingredient's head, and also links by fingerprint. The 8 remaining name-match flags are low confidence.
- **Sibling dry-basis checks fire on real processing changes:** salt-ripened anchovy and squid, glutathione loss in dried shiitake, and reduced-sodium soups using KCl. These stay "low" unless the protein dry ratio says the matrix is the same.
- **USDA is not always right.** Chicken broth K 18 and raw sweet corn's sugar split are USDA's own values. Corn is flagged NEEDS SOURCE for that reason, not as a transcription error.
