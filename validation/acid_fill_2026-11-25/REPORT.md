# Acid Fill: Report (2026-11-25)

This is a proposal only. Nothing in `hfp_raw_data.csv`, the model or the website was edited. Every value here was extracted by an agent and hasn't been verified by a person. The build script reads the DB live and refuses to propose for any cell that's already filled (rule R8). A copy is in this folder as `build_acid_fill.py`.

## Files
- `extracted_raw.csv` has all 373 records from the five papers, before mapping. Each record has its page/table, a verbatim quote, units, basis, and whether it's primary or secondary.
- `proposals.csv` has 52 proposed fills across 15 rows. The `recommend` column says `fill` (44) or `hold` (8).
- `disagreements.csv` has 18 comparisons against existing DB values: agreements, conflicts and not-comparable cases.

## Counts
| Confidence | fill | hold |
|---|---|---|
| High | 1 | 0 |
| Medium | 17 | 0 |
| Low | 26 | 8 |

All 15 rows had **no non-ascorbic acid data** before this:
- **Cheeses (Ahmed 2023, primary):** Parmigiano (3 rows), Mozzarella, Emmental, Cheddar 1 yr, Cheddar 3 yr.
- **Ferments:** Doenjang (Shukla 2010, primary), Kimchi (Jeong 2013, primary, read from a figure), Wine Sake and Sauce Soy (Li 2025, secondary).
- **Others (Shi 2022, secondary):** Ham Dry-Cured, Fish Tuna (Fresh), Oyster Generic, Oyster Pacific.

## Notable values (mg/100 g, as eaten)
- **Parmesan:** Lactic 1,890, citric 68, succinic 70. Acetic 410 is on HOLD.
- **Cheddar:** Lactic 1,440 (range 1,440-2,250 across sources), citric 56, acetic 50 (low confidence).
- **Mozzarella:** Lactic 840, citric 47, succinic 0. Acetic 670 is on HOLD.
- **Emmental:** Lactic 270, acetic 300, succinic 50. Swiss also has propionic acid at 630, which has no DB column.
- **Kimchi (ripe, days 40-120, pH 4.0-4.2):** Lactic 274, acetic 58, succinic 38. Converted from mM in kimchi liquid times DB water (94.3%).
- **Doenjang:** Acetic 80 (median of 18; mean 92; range 32-178), the only **high** in this set. Lactic is only 6.7, which is almost certainly too low (see below).
- **Soy sauce:** Lactic 144 and pyroglutamic 292 (low confidence). Acetic, malic, succinic and oxalic are on HOLD.
- **Sake:** Lactic 107, malic 35, succinic 28 (low confidence).

## Biggest uncertainties
- **Ahmed 2023 is a weak paper.** It has one market sample per cheese, and the age is given only as "1-3 months". Its acetic numbers are 5-10x typical, and the authors themselves call Cheddar's 0.23% unexpected. Parmesan butyric at 2.86% is impossible. Lactic and citric look sane, so I kept those at medium and held acetic for Parmesan and Mozzarella. Its "Parmesan" may not be aged PDO Parmigiano, so the Aged 2/4-year rows are low-confidence proxies.
- **Doenjang lactic is probably a big underestimate.** The non-volatile workup has many steps (ethanol reflux, ion exchange, methylation, HPLC-RI). The paper itself cites 1.5-6% total non-volatile acids for other doenjang, against about 0.01% here. The paper's own means also leave out ND samples, so I used medians with ND = 0. Acetic was measured by GC on a simple water extract and is solid.
- **Li 2025 Table 1 units aren't reliable.** Everything is printed as "mg/mL". Cheddar only makes sense read as mg/g, and its yogurt lactic is about 8x too low. The soy sauce and sake ranges are fermentation time-courses (Cantonese and Korean ganjang; one sake source is a kimoto starter paper), not finished Japanese-style products.
- **Kimchi values were read off Fig. 3B.** The reading error is about +/-3%. They're in liquid-phase mM, and converting them to whole kimchi assumes the acids spread through all tissue water. The study was one 30-kg batch.
- **Shi 2022 is all secondary text** (Table S1 isn't on disk). Several of its values are plainly on a dry basis or are errors: radish-kimchi oxalic 10-30%, chicken-soup tartaric up to 8.8%, mushroom lactic 6%. Its "apples" reference is actually **wax apple**, and its "grapes" citation is a grapefruit paper. None of those were proposed.

## Checks against existing DB values (disagreements.csv)
- **Agree:** Onion (all 5 acids match Rodriguez Galdon 2008 exactly), Pork lactic 349 (= the stewed-pork start value), Beef lactic (inside 225-433), and dried vs fresh tuna (consistent once scaled for dry matter).
- **Keep DB:** Yogurt lactic 900 (Li 107 is a likely unit error), Grape tartaric 394.6 (Shi 1,047 is badly cited), and the Wine Generic red set (Li's Cabernet row is uncited).

## Side findings (not proposed; outside the acid columns)
- **Kimchi pH:** The DB cell is blank. Jeong 2013 (p. M765) reports pH "relatively stable at about 4.0 to 4.2" from day 21, so 4.1 is a candidate.
- **Kimchi mannitol:** About 52 mM in the liquid, roughly 890 mg/100 g (Fig. 3B). The DB has a Mannitol column.
- **Cheese sugars (Ahmed Table 1):** The values are in `extracted_raw.csv`. Galactose is 0.14-0.30% in all four cheeses, and lactose is 0.05% (Parmesan) and 0.09% (Cheddar).
- **Wine, Dry Red:** Its acid cells are blank. Copying the DB's own `Wine, Generic` red set (Heras-Roger 2025) would be better than anything in these five papers.

## Still missing (no usable data in these five papers)
1. **Miso and natto.** Gochujang is also missing, and it has pH 4.6 and is flagged. None of the papers measure them, and doenjang is not a fair proxy (different koji and microbes).
2. **A primary soy sauce source (Japanese koikuchi).** It's needed for acetic, succinic and malic, and to confirm lactic and pyroglutamic.
3. **Other cheeses and better cheese data.** Gouda, Manchego, Feta, Cottage (pH 4.88, flagged), Cream cheese (pH 4.45, flagged), American processed (pH 4.98, flagged), Provolone, Monterey Jack, Roquefort and so on have no source at all. A second cheese source is also needed to replace Ahmed's acetic values.
- Also blank: Olives Green (pH 4.1; Li's olive data is naturally black olive *brine*), Sauce Chili (pH 3.24), Prunes, Grapefruit, Blueberry and Orange. These are fruit rows that need a primary fruit-acid table.

## Round 2 (Zeppa, Bevilacqua) - 2026-11-25
This round adds two primary papers: Bevilacqua & Califano 1989 (J Food Sci 54:1076, Table 1 p. 1077) and Zeppa et al. 2001 (JAFC 49:2722, Table 5 p. 2726). The Bevilacqua text layer is garbled OCR, so every value was read from a 300-dpi render of the table. Script: `build_acid_fill_round2.py`. It appends to the three CSVs and adds a `round` column; round-1 rows are kept. There are now 455 extracted records, 72 proposals and 20 disagreement rows.

**New fills (20 values, all in previously blank cells):** 1 high, 11 medium, 8 low.
- **Milk, Cow** (all acids were blank): Citric 161 (**high**; raw milk, n = 12, matches textbook citrate) and lactic 0 (below detection).
- **Yogurt, Plain:** Citric 60, acetic 49, formic 17 (medium).
- **Yogurt, Greek:** The same three acids scaled by the water ratio of 0.925 (low). This is the same rule the DB already uses for Greek lactic.
- **Cheese, Provolone** (newly filled): Lactic 200, acetic 57.5, formic 68 (medium) and citric 293 (low, because the two brands are 114 vs 472).
- **Cheese, Roquefort and Cheese, Cabrales** (newly filled from a generic Argentine blue): Lactic 273 and acetic 96 (medium); formic 102 and citric 399 (low).

**What the new papers do NOT do:**
- Neither paper has Parmesan, Mozzarella, Cheddar or Swiss, so nothing from round 1 was replaced or confirmed directly.
- **The acetic holds stay held** (Parmesan 410, Mozzarella 670), but the case is now stronger. Bevilacqua's measured acetic in three cheeses is 57-96 mg/100 g, which suggests Ahmed's values are 5-10x too high. Cheddar acetic 50 fits that range, but stays low because the cheese is different.
- No confidence was re-ranked, because no stronger source exists yet for the round-1 cheeses.
- Notes were added to those round-1 proposal rows.

**Zeppa 2001 was extracted but not used.**
- The only food is Ossolano cheese (40 d, n = 15), which has no DB row.
- Its Table 5 doesn't look credible on a wet basis. Lactic is 62 g/kg (6.2%, about 3-4x the highest cheese values) and diacetyl is 4.5 g/kg (about 1000x normal). That looks like a dilution-factor error, since the extract was 5 g in 25 mL.

**Bevilacqua caveats:**
- The samples are 1989 Argentine commercial products, and the values aren't corrected for recovery (85-93%).
- Butyric is 0.8-2.9% in the cheeses, which is implausible (likely a co-eluting peak at 214 nm). There's no DB column for it, and it was not used.
- Provolone lactic at 0.2% is low for an aged provolone, but both brands agree.

**New disagreement:** Yogurt lactic. The DB has 900 and Bevilacqua measured 1,960 (n = 3). I kept the DB value, but the range across sources is now 107-1,960. The Greek row follows whatever is decided for plain yogurt.

**Side findings (sugars, not proposed):**
- Zeppa Ossolano: lactose 0.87, glucose 0.42 and galactose 1.01 g/kg (same scaling doubt as the acids).
- Bevilacqua reports no sugars.

**Gaps still open after round 2:**
1. A real Parmesan/Mozzarella/Cheddar/Emmental source, to replace Ahmed and settle the acetic holds.
2. The fresh acid cheeses that are flagged for pH: Cottage (4.88), Cream cheese (4.45) and American processed (4.98). Feta, Gouda, Manchego and Monterey Jack are also missing.
3. Miso, natto, gochujang and a Japanese-style soy sauce are unchanged from round 1.

## Round 3 (soy sauce, miso, bean pastes) - 2026-11-25
This round adds four sources:
- Kaneko et al. 1994 (Nippon Shokuhin Kogyo Gakkaishi 41:148)
- Kanbe et al. 1978 (Nogeikagaku Kaishi 52:329, Kikkoman)
- Ohnishi et al. 2012 (Kagawa ITC Report 12:79)
- Lin et al. 2018 (Molecules 23:1299)

All tables were read from page renders. Kaneko's and Kanbe's tables have English headers; sample identities are quoted in the original Japanese with an English gloss in the CSVs. Script: `build_acid_fill_round3.py`. Round-1 rows that this round replaces are kept but marked `status = superseded by round 3`, and a new `status` column was added. Totals are now 791 extracted records, 96 proposal rows and 35 disagreement/side-finding rows.

**How Kaneko values were converted:** Kaneko gives each acid as % of total organic acid, with the total in mg/100 g of the weighed sample. So value = % x total, and no density conversion is needed. That's a product of group means, so the results are approximate.

**Sauce, Soy (Japanese commercial, n = 6). Round-1 values replaced:**

| Acid | Round 1 | Round 3 | Confidence |
|---|---|---|---|
| Lactic | 143.9 (low) | 658.8 | High |
| Acetic | 699.3 (HOLD) | 205.0 | High |
| Pyroglutamic | 291.9 (low) | 483.1 | Medium |
| Succinic | 863.3 (HOLD) | 62.2 | Medium |
| Malic | 575.6 (HOLD) | 23.8 | Low |
| Citric | none | 117.1 | Medium (new) |
| Oxalic | 123.3 (HOLD) | Withdrawn; leave blank (no Japanese source measures it) | - |
| Formic | none | 4.9 | Low (new; Kanbe mash median) |

- **Kanbe corroborates these values.** Its 20 Kikkoman mashes at 150 days have median lactic 6.96 mg/mL (572 mg/100 g) and acetic 2.57 mg/mL (211 mg/100 g). Pyroglutamic is still rising at 150 days (155 mg/100 g there).
- **Kanbe is used only as a cross-check.** It gives no finished-product values.
- **The round-1 Cantonese and ganjang numbers were 3-14x too high** for acetic, succinic and malic.

**Doenjang (Korean homemade, n = 8; Kaneko Table 3):**

| Acid | Round 1 | Round 3 | Confidence |
|---|---|---|---|
| Lactic | 6.7 (Shukla, low) | 502.4 | Medium |
| Pyroglutamic | none | 204.5 | Medium (new) |
| Citric | 0 (Shukla) | 40.5 | Medium |
| Succinic | 0 (Shukla) | 19.7 | Medium |
| Malic | none | 6.2 | Low (new) |

- **Acetic 80 (Shukla, high) is confirmed:** Kaneko gives 111.
- Oxalic 0 and malonic 0 from Shukla stay as they are.

**Miso, newly filled** (Japanese commercial rice miso, n = 5):
- Pyroglutamic 356, citric 303, lactic 127, acetic 58, succinic 32 (medium).
- Malic 21 (low).

**Miso (Dried), newly filled:** The same acids scaled by dry matter (x1.197, from 58.5% to 70% DM). These are low-confidence proxies, because the paper doesn't report its miso's moisture.

**Not usable:**
- **Ohnishi 2012:** The 27 koikuchi sauces are shown only as PLS plots of CE peak areas, with no concentrations. Qualitative finding: sauces with more pyroglutamic acid had more citric and malic and less lactic and acetic acid (weaker lactic fermentation).
- **Kanbe:** Tables I and III-V are a time course and pure-culture data, so they weren't extracted.

**Broad-bean paste (Lin 2018, 6 Pixian doubanjiang, wet basis):**
- There is **no DB row**, so I propose a **candidate new row, "Paste, Broad Bean (Doubanjiang)"**.
- Medians in mg/100 g: citric 498, malic 277, oxalic 205, succinic 33, tartaric 26, lactic 11, fumaric 0.1. Free Glu is about 259.
- Acetic and pyroglutamic weren't measured. It's not a proxy for gochujang or doenjang: the profile is chili-driven, high in citric and malic.

**Side findings (from Kaneko; not proposed; see disagreements.csv):**
- **Miso sugars look swapped or mis-sourced.** Paper vs DB: glucose 7,719 vs 0, fructose 1,021 vs 6,000, maltose 1,677 vs 200. This one is worth checking, since it affects sweetness.
- **Doenjang sucrose 8,000 in the DB looks wrong.** Homemade doenjang had 0.9% total sugar, and the paper says "韓国味噌には糖がほとんど含まれなかった" (Korean paste contained almost no sugar).
- **Soy sauce:** Total sugar is 2.4% vs DB glucose + sucrose = 400.
- **Free Glu:** Soy sauce 1,262 vs DB 1,050 (+20%), miso 687 vs 450 (+53%), doenjang 851 vs 674 (+26%). Asp runs higher by a similar margin.
- **pH:** Miso 4.97 is a candidate for the blank DB cell. Soy sauce (4.79) and doenjang (5.42) agree with the DB.
- **No DB column:** Levulinic acid makes up 9.7% of Japanese and 32.9% of Korean commercial soy sauce acids. Glucuronic and pyruvic acids are also present.

**Gaps still open after round 3:**
1. **Gochujang** (pH 4.6, flagged) and **natto**: no source yet.
2. **Korean soy sauce (ganjang):** There's no DB row. If one is added, Kaneko has the data: homemade sauce has 781 mg/100 g total acid, 52.9% of it lactic.
3. **Doubanjiang:** It needs a new row plus an acetic and pyroglutamic source.
4. **Japanese soy sauce:** It would be worth a modern n > 6 check (Kaneko's sauces are from 1993, and the style isn't stated).
