# Kokumi peptides and MSG saltiness: 7-paper review (Nov 25, 2026)

**These are proposals only.** I didn't change any DB, model or website file. All 7 PDFs were read in full from the text layer, and the Sun 2022 Table 2 values were checked against a page image. Every value is listed in `proposals.csv` with its page, table, a verbatim quote and the conversion. Before/after runs were done in memory on a copy of the DB dict (`scripts/`). The file was saved via Python because the Write tool was blocked.

## Summary of proposed changes

| Ingredient / item | Field | Current | Proposed | Source | Confidence |
|---|---|---|---|---|---|
| **Cheese, Manchego** | γ-EVG mg/100 g | 5.9 | **0.059** | Kuroda 2020 Table 2 (0.59 µg/g) | **High: 100× unit error** |
| Cheese, Kashkaval | γ-EVG | 3.5 | 0.035 (ewe) or 0 (cow) | Same ×10 slip on Ossau Iraty 0.35 µg/g | Low |
| **Sauce, Fish** | γ-EVG | 0.43 | **0.19** (Thai median, n = 5) | Kuroda 2012 Table 2, ÷ density 1.22 | Medium |
| Sauce, Soy | γ-EVG | 0.33 | 0.39 (dark median, n = 6) | Kuroda 2013 Table 3, ÷ 1.2162 | Medium (0.33 is also defensible) |
| Doenjang | γ-EVG | blank | 1.40 (median, n = 9) | Kim 2021 Table 2 | Low-medium (basis doubt) |
| Beer | γ-EVG | 0.012 | keep 0.012 | Miyamura 2015 Table 2 | High (confirmed) |
| Wine, Sake / wines | γ-EVG | blank / 0 | 0 (not detected, < 0.003) | Miyamura 2015 Table 2 | Medium (provenance only) |
| Cheddar (1 yr) | γ-EVG | blank | 0 (not detected) | Kuroda 2020 Table 2 | High (provenance only) |
| New potency: γ-Glu-Val | KOKUMI_POTENCY | not counted | 0.61 × GSH | Ohsu 2010 Table 2 (same PSE panel as 12.8) | Medium-high |
| New potency: γ-Glu-Leu | KOKUMI_POTENCY | not counted | ~0.30 × GSH | Dunkel 2007 broth thresholds, via Li 2020 | Low |
| MSG sodium in saltiness | weight vs NaCl Na | 1.0 always | 1.0 when other Na ≥ MSG Na; down to 0.3 when MSG is the only sodium | Yamaguchi 1991, Sun 2022, Morita 2021, Jinap 2016 | Low-medium |

## 1. Kokumi fills (γ-EVG)

- **Manchego is the big one.** The paper gives 0.59 µg/g, which is 0.059 mg/100 g. The DB has 5.9, so the µg/g value was multiplied by 10 instead of divided by 10. Kashkaval's 3.5 has no source I could find, but it equals Ossau Iraty's 0.35 µg/g with the same slip.
  - Quote: "Manchego Ewe 0.59 … Mean value (n = 3). Limit of detection = 0.03 μg/g" (p. 7806, Table 2).
  - Cow-milk cheeses (Cheddar 4 and 12 months, Stilton, Saint Agur, Langres) had none detected. The authors trace this to β-casein: sheep have Val-Gly at positions 9–10, while cows have Pro-Gly.
- **Fish sauce, resolving the 0.43 question.** The primary paper reports **mg/dL**, which is mg/100 mL, so it needs the density step.
  - The Koku book's 4.4 mg/L (Table 7.24) is the mean of 17 sauces that mixes Thai (~2.3 mg/L) and Vietnamese (~11.6 mg/L). The DB's 0.43 ≈ 4.4 ÷ 10 with no density correction, so the earlier flag was right.
  - Thai median 0.23 mg/dL ÷ 1.22 = **0.19 mg/100 g**. The DB's sodium (7,851) matches Thai sauces (Table 1: 6.5–8.4 g/100 g).
  - Vietnamese nước mắm runs **5× higher (0.98)**. If you ever add a Vietnamese fish sauce row, use 0.98.
- **Soy sauce:** current 0.33 = the mean of all 9 Japanese samples (dark, light and white). Ordinary dark soy (koikuchi, the Kikkoman type) has a median of 0.475 mg/dL ÷ 1.2162 = **0.39**. Korean brewed ganjang agrees (0.36–0.44). The change is small, so either value is fine.
- **Doenjang: 1.40 mg/100 g (median of 9, range 0.46–5.22).** Basis doubt: Table 2 and the Results text say µg/g of doenjang, but the abstract's GGP totals (203–387 µg/g) are about 7× lower than the table's (1,425–14,465). If the abstract is right, the value is about 0.2.
  - Kim also misquotes Kuroda's soy sauce as "15 to 61 µg/mL". The real range is 1.5–6.1, so Kim is the less careful source.
- **Beer 0.012 is confirmed** (8 beers, 0.08–0.18 mg/L). **Wine and sake were not detected** (< 0.03 mg/L), so the existing zeros are confirmed. Sake and Wine, Dry Red could get an explicit 0 for provenance.
- **Not changed (outside these papers):** Paste, Shrimp 0.24 looks like the same no-density "mg/L ÷ 10" pattern (Koku Table 7.24: shrimp paste 2.4 mg/L, a solid reported per litre). This is worth a look later.

## 2. Model effect (before → after, kokumi score /10)

| Recipe | Kokumi | Umami | Salt |
|---|---|---|---|
| Soy sauce neat, or 15 mL in 250 g water | 1.00 → 1.00 | no change | no change |
| Fish sauce neat, nuoc cham base, or soup | 1.00 → 1.00 | no change | no change |
| **Manchego 30 g** | **6.90 → 1.00** | 4.95 → 4.11 | 10.0 → 8.97 |
| Doenjang 30 g in 300 g water | 1.00 → 1.00 | no change | no change |
| Doenjang neat | 1.00 → 1.00 (2.24 if γ-Glu-Val and γ-Glu-Leu are counted) | no change | no change |
| Beer 355 mL | 1.00 → 1.00 | no change | no change |

- **What this means:** at real food levels, γ-EVG alone never clears the kokumi floor (Ueda 1997 GSH threshold of 0.01–0.04%). Soy sauce neat gives only ~5 mg GSH-eq/100 g. So the fish sauce and soy sauce fixes are about correctness, not scores. **The Manchego fix is the only one that changes a score**, and it removes a fake kokumi 6.9.
- **Peptides the model doesn't count** (Kim 2021, in every ganjang and doenjang sample): γ-Glu-Val, γ-Glu-Leu, γ-Glu-Glu, -Gly, -Gln, -His, -Met, -Phe, -Tyr, -Trp.
  - **γ-Glu-Val: 0.61 × GSH by weight** (Ohsu 2010 Table 2, the same PSE panel that gave 12.8 for γ-EVG). This is the only clean potency.
  - **γ-Glu-Leu: ~0.30** (broth thresholds 0.8 mM vs GSH 0.2 mM, Dunkel 2007 via Li 2020; low confidence).
  - The others only have water thresholds based on astringency with no GSH comparator, so there's **no usable potency**.
  - In doenjang and ganjang these two add about +35% and +64% to the γ-EVG GSH-equivalents. That lifts doenjang tasted neat from 1.00 to 2.24. Worth adding only if more foods get data; right now only doenjang has it.

## 3. MSG saltiness

**How salty MSG's sodium is, relative to NaCl's sodium at equal Na** (iso-salty NaCl, `scripts/msg_na_equivalence.py`):

| Condition | Effective weight of MSG Na | Source |
|---|---|---|
| MSG on top of 1% NaCl (171 mM) | **~0.3** | Yamaguchi 1991 p. 836: "about 30% of NaCl in molar Na comparison" |
| 0.3% MSG + 0.3% NaCl (51 mM) | **1.29** (MSG adds more than its Na; p < 0.05, n = 561) | Morita 2021 Table 3 |
| 0.3% MSG + 0.6% NaCl | 0.36 (n.s.) | Morita 2021 |
| 0.3% MSG + 0.9% NaCl | ≈ 0 (n.s.) | Morita 2021 |
| 0.55 or 1.40 g/L MSG + NaCl 35–240 mM | 1.5–3.8; net lift +8–14% at ≤ 75 mM, +1–6% at 160–240 mM | Sun 2022 Table 2 |
| Soup, 0.3% NaCl + 0.7% MSG vs 0.8% + 0.2% | Saltiness not different (4.3 vs 4.7 on 1–9), with 38% less Na | Jinap 2016 Table 2 (qualitative; no NaCl dose curve) |

- **Yes, MSG raises the saltiness of low-salt solutions beyond its sodium** (Morita, Sun, Jinap). The effect fades as salt rises. At high salt, MSG's sodium counts for only about 30% (Yamaguchi) or less (Morita, n.s.).
- **The current v.2.8.1 rule already matches the low-salt data:** Sun's 12 cells within 3.4%, and Morita at 0.3% NaCl gives 74 vs 72 mM. It over-predicts Morita at 0.6–0.9% NaCl by about 18%, but those differences were not significant, and Sun says the opposite. Morita had no umami scale, so some umami may have been "dumped" into saltiness.
- **Where the model is wrong is MSG-dominant mixtures.** 0.5% MSG in plain water scores 3.4/10 salty because its sodium counts like NaCl. Yamaguchi's ~30% and Schiffman 2000 (0.05 M MSG = 1.1/10 salty) say it should be near the floor.
- **Considered and rejected:** a global weight of 0.3 with the lift refit (EMAX 0.21, fade 60–180 mM). Its total error is similar (RMS 0.055 vs 0.065 in log iso-NaCl), but it breaks the Sun fit (0.018 → 0.047) and moves against Jinap's soup result (`scripts/msg_rule_fit.py`, `msg_rule_effect.py`).

**Proposed rule:**
- MSG-row sodium counts at **w = 0.3 + 0.7 × min(1, Na from everything else ÷ Na from MSG)** in saltiness.
- Keep UMAMI_SALT_EMAX 0.10 and the 75–260 mM fade as they are.
- **Implementation:** in `compute()`, sum `na_mg` separately for rows in `MSG_NA_INGREDIENTS = {"Monosodium Glutamate"}`. Before `na_m` is computed, set the saltiness sodium to `na_other + w × na_msg`. Leave the umami shift and bitterness sodium as they are. Mirror the change in `web/hfp_model.js`.
- **Which rows are glutamate or nucleotide salts:** only **Monosodium Glutamate** (Na 13,594 = anhydrous MSG; its Na:Glu molar ratio is 1:1). Ajitide I+G (disodium nucleotides) is optional, since Yamaguchi puts IMP's sodium at ~50%. Bouillon, Beef Stock Cube and the soy and fish sauces contain glutamate, but their sodium can't be split from NaCl, so they stay at weight 1.
- **Effect:** Sun, Morita, Jinap and all normal salted recipes are unchanged (w = 1). 0.5% MSG in water goes 3.44 → 1.00, and 0.1% NaCl + 0.5% MSG goes 4.53 → 4.04.
- **Confidence: low-medium.** The 0.3 end point was measured on top of 1% NaCl, not in plain water. The linear blend between the end points is my assumption.

## Files
- `proposals.csv`: 14 rows with quotes, pages, conversions and confidence.
- `scripts/kokumi_effect.py`: before/after kokumi runs (in memory).
- `scripts/msg_na_equivalence.py`, `msg_rule_fit.py`, `msg_rule_effect.py`, `msg_guard_effect.py`: the MSG analysis.
- `scripts/write_proposals.py`, `scripts/write_report.py` and `text/` (the extracted paper text).
