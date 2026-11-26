# Umami gap: sourcing free glutamate for savory processed foods (Nov 25, 2026)

**This is a proposal only.** Nothing in `hfp_raw_data.csv` or the model files was changed. Every row is in `proposals.csv`, with its quote, conversion and DOI.

## Summary

| DB row | Field | Now | Proposed | Confidence | Source |
|---|---|---|---|---|---|
| Bouillon | Glutamate | 6827 (copied from Beef Stock Cube) | **9,270** | Medium | Median of 16 analyzed cubes and powders (Soyseven 2021; Martinez-Tome 2015; Krishna 2010) |
| Bouillon | IMP / GMP | blank | **80 / 80** | Low | Derived from the industry MSG:I+G ratio of 50-100:1 (Archer 2022, Front Nutr); below the measured Vietnamese seasoning range |
| Beef Stock Cube | Glutamate | 6827 (no source) | **8,970** (or use 9,270) | Medium | Median of 6 meat cubes (Soyseven 2021 + Martinez-Tome 2015) |
| Beef Stock Cube | IMP / GMP | blank | 80 / 80 | Low | Same derivation as Bouillon |
| **New:** Yeast Extract (Spread, e.g. Marmite) | Glutamate | n/a | **1,700** | Medium | FSANZ 2003 Tech Report 20, Table 2: Vegemite 1431, Marmite 1960 |
| New: Yeast Extract (Spread) | Na / K / water / protein / density | n/a | 3380 / 2100 / 40.9% / 23.88% / 1.22 g/mL | High (density medium) | USDA SR Legacy FDC 167717 |
| Yeast Extract (existing row, powder) | Glutamate | 1020 (no source) | **5,000** | Medium | Tome 2021 review: "about 5% ... w/w free ... glutamate" |
| Olives, Black | Glutamate | blank | **leave blank** | n/a | Nothing open found. USDA total Glu is 93 mg/100 g, so free Glu must be below that |
| Olives, Green | Glu / Asp | 4 / 3 | no change | n/a | Nothing better found |
| Soup Mix, Onion (Dry) | Glutamate | blank | **leave blank** | n/a | No brand-specific data |
| Generic instant soup row | Glutamate | n/a | **don't add** | Low | Measured values run 177 to 1,933 mg/100 g; too wide to use |

## What this means for the benchmark misses

- **Stock cube (panel 41):** Bouillon goes up about 36% (6827 to 9270) and gains nucleotides. That should lift the score clearly. Test it before adopting, because the synergy term is very sensitive to IMP/GMP.
- **Packet soup and cup-a-soup (31, 21):** There's no defensible generic soup-mix value. Better fix: the recipe breakdown should include a Bouillon or Yeast Extract line at a dose taken from the label. The breakdowns in the benchmark (Tagkopoulos) leave these out.
- **Tapenade (32):** Still stuck, because black olives have no free-glutamate value. Its umami has to come from the anchovy (630) and from capers (blank).
- **Croquette (25):** Not addressed. It's a meat and roux matrix; see the cooked-meat free-glutamate idea in the benchmark REPORT.

## Notes by item

### 3. Bouillon / stock cubes
- **Values (MSG, g/kg):**
  - Soyseven 2021, Table 5: 11 Turkish cubes, 63-151 (median 106).
  - Martinez-Tome 2015, Table 7: 4 Spanish dehydrated "soups", 109-132. These are bouillon-type powders with 23-26 g Na/100 g.
  - Krishna 2010, Table 1: one Indian cube, 133.5.
  - Conacher 1979 (JAOAC 62:604, abstract): up to 13.1% in bouillon cubes, which agrees.
- **Pooled median:** 11.8% MSG, which is 9,274 mg glutamic acid/100 g, assuming MSG.H2O (x 147.13/187.13).
  - Why monohydrate: Martinez-Tome give the MSG ingredient a theoretical 12.3% Na, which is the monohydrate figure.
  - If the papers meant anhydrous MSG, the value would be about 10% higher (10,262).
- **Conflict flagged:** Demirhan 2015 (122 Turkish cubes, abstract only) reports 7-15 g/kg, ten times lower. I didn't pool it, since it's probably a basis or reporting issue, but I can't confirm that.
- **Nucleotides:** No open paper gives measured IMP/GMP values for bouillon.
  - The 80/80 comes from Archer 2022's ratio rule. Mid-ratio 75:1 gives 0.177% I+G, split 50:50 and converted from the Na2 salts to free acids.
  - Le 2021 (Vietnam, 10 sauces and seasonings) measured 1,129-6,158 mg/kg IMP. The 80 sits below that range, so it's conservative.
  - Many cubes contain no I+G at all.

### 2. Yeast extract
- **The DB already has a "Yeast Extract" row** (Glu 1020, water 2%, protein 64%). That's a powder, and its sources aren't on file. The benchmark mapping probably just didn't use it.
- **Spread (new row):** Composition is from USDA SR "Yeast extract spread", which looks like Vegemite (Na 3,380).
  - Glutamate 1,700 is the mean of FSANZ's Vegemite and Marmite values.
  - FSANZ cites Nicholas & Jones 1991 and Yoshida 1998, not the UIC database. **Bryan to confirm that this meets the licensing rule.**
  - Alternative: use 1,431 to match the Vegemite-like composition.
- **Powder:** Tome 2021 gives about 5% free glutamate (abstract checked via OpenAlex). Recommend changing 1020 to 5000.
  - Nucleotides aren't proposed: ribonucleotide-enriched grades range from about 0% to 25% I+G.

### 1. Table olives
- **No measured free glutamate found for any style**, in open or abstract-visible sources.
- **Paywalled papers that probably have it:**
  - Casado & Montano 2008, J Agric Food Chem 56:2021 (free amino acids in olives before sterilization).
  - Casado et al. 2007, J Agric Food Chem 55:3503 (free amino acids in commercial ripe olives; total D-amino acids 18.6-38.2 mg/100 g).
- **Context:**
  - USDA total glutamic acid in ripe canned olives is 93 mg/100 g, which caps free Glu.
  - Olive microbes convert added MSG to GABA (Bonatsou 2017; de Castro 2014). That suggests fermented olives carry little free glutamate.
- **Recommendation:** Keep black olives blank. Add Casado 2008 to the paper wishlist (needs a browser or library download).

### 4. Dehydrated soup mix
- **Instant soups:**
  - Soyseven 2021 (15 Turkish instant soups): median 2.25 g MSG/kg, which is 177 mg Glu/100 g. Four soups had none detected.
  - Krishna 2010 (one Indian soup): 24.6 mg/g, which is 1,933 mg Glu/100 g.
  - Neither paper says whether the soups were tested dry or prepared.
- **Recommendation:** Don't add a generic row, and don't fill Onion Soup Mix. I couldn't verify whether the Lipton mix contains MSG.
- Malaysia label survey (J Nutr Sci 2025): 91% of soup and broth mixes declare MSG. This supports the parser flag, but it gives no amounts.

### 5. Tapenade
- Skipped. It's a recipe of rows already in the DB (olives, capers, anchovy, oil), and its gap is the olive glutamate above.

## Couldn't source
- Free glutamate and aspartate for black (ripe or Kalamata) and green olives, and olive nucleotides.
- Measured IMP/GMP in bouillon cubes (Acebal 2008, Food Chem 106:811, has them but is paywalled).
- Nucleotides and aspartate in Marmite and Vegemite.
- Glutamate in onion soup mix and Dutch-style packet soups.
- The primary Rhodes et al. 1991 UK MSG survey (Food Addit Contam 8:663; stock cubes, soups, yeast extract) is paywalled and worth getting.

## Sources (DOIs)
- Soyseven et al. 2021, IJFST: https://doi.org/10.1111/ijfs.14661 (paywalled; Table 5 values read from the publisher page)
- Martinez-Tome et al. 2015, J Food Sci Technol: https://doi.org/10.1007/s13197-015-1940-y (free full text in PMC: PMC4648876)
- Krishna Veni et al. 2010, J Young Pharm: https://doi.org/10.4103/0975-1483.66795 (open access, PMC2964770)
- Archer et al. 2022, Front Nutr: https://doi.org/10.3389/fnut.2022.746018 (open access)
- Le Dinh Hai et al. 2021, Vietnamese J Food Control: https://doi.org/10.47866/2615-9252/vjfc.3852 (open access)
- Demirhan et al. 2015, Food Addit Contam B: https://doi.org/10.1080/19393210.2014.991355 (abstract only)
- FSANZ 2003, MSG Technical Report 20: https://www.foodstandards.gov.au/sites/default/files/publications/Documents/MSG%20Technical%20Report.pdf
- Tome 2021, ACS Food Sci Technol: https://doi.org/10.1021/acsfoodscitech.0c00131 (abstract)
- USDA FDC 167717 (yeast extract spread), 169094 (ripe olives): local SR Legacy copy in `data_sources/`
- Bonatsou 2017 https://doi.org/10.1016/j.fm.2016.11.001; de Castro 2014 https://doi.org/10.1080/19440049.2014.913320; Casado 2007 https://doi.org/10.1021/jf0701685
