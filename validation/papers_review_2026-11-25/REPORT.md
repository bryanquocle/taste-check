# Papers review against Taste Check open questions (Nov 25, 2026)

PROPOSAL ONLY. No model, data or website file was changed. Saved via Python (the Write tool was blocked). All 10 PDFs were read in full (text extraction plus page images for every table and figure used). Figure values marked "read" were read off the plot by eye (about ±1 scale unit). `cook_evap.py` was imported unchanged and run on the Snitkjær conditions.

Molecular weights: Glu 147.13; MSG·H2O 187.13; Asp 133.10; Na-Asp·H2O 173.10; Na-Asp (anhydrous) 155.09; IMP 348.21; Na2IMP·7.5H2O 527.28; Na2IMP 392.17; GMP 363.22; Na2GMP·7H2O 533.29; Na2GMP 407.18.

## Summary of recommendations

| # | Item | Current | Proposed | Source | Confidence |
|---|---|---|---|---|---|
| 1 | SALT_SHIFT_MAX (NaCl → umami) | 2.0 (dog nerve) | **1.0** (no salt effect on umami intensity) | Wang 2022 Fig. 1; Yamaguchi 1991 p. 833 and Table 4; Schiffman 1991 Table 4a | **High** that 2.0 is wrong; medium that 1.0 beats a mild suppression |
| 1b | Legacy SALT_THRESHOLD_RULE (off) | ×4 Glu > 150 mM Na; ×4/×8 nucleotides > 20/170 mM Na, "no source" | Keep off for glutamate. Optional: nucleotide-alone thresholds ×2 at ≥ 20 mM NaCl, ×4 at ≥ 170 mM | Yamaguchi 1991 Table 4 (the likely origin; the multipliers were doubled and the glutamate one is not supported) | Medium; low impact |
| 2 | Aspartate threshold | 0.0166 g/100 mL ("unsourced") | **Keep 0.0166; add the source**: 1.25 mM Na-aspartate × 133.10 = 0.01664 | Yamaguchi 1991 Table 1, p. 834 | Medium-high (exact 3-digit match) |
| 2b | (alternative) | | Kirimura gives 100 mg/dL Asp·Na = 0.077 (hydrate) or 0.086 (anhydrous) as free Asp | Kirimura 1969 Table I, p. 690 | Not recommended (method mismatch, see Q2) |
| 3 | NUC_THR_ALONE IMP / GMP | 0.0135 / 0.0075 (Kuninaka 1980) | **Keep** | Maga's figures confirmed as printed but are secondhand company data; three primary human studies agree with Kuninaka | Medium-high |
| 4 | Glu threshold divisor D | Linear in IMP-eq, ×63 at 5 mM | **Keep the ×63 cap.** Optional: saturating shape (fits 2× better) | Amado 2024, Tanaka 2025, Schiffman 1991 | Cap: medium. Shape change: low-medium |
| 4b | Suprathreshold synergy (flag only) | IMP/GMP fold capped at 63; AMP fold 26.7 at 3 mM | No change here. Tanaka shows ~24–39× (IMP/GMP) and ~6–7× (AMP) at 1–3 mM MPG, shrinking at higher MPG | Tanaka 2025 Fig. 5 | Flag for a separate synergy review |
| 5 | Cooking: kitchen factor K | 1.3 | **Keep 1.3** (blind steady-state check gives 1.16–1.3) | Snitkjær 2017 Figs. 2–3 | Medium |
| 5b | Cooking: boil path at "mid" throttle | 0.75 × burner | Over-predicts a gentle boil 1.6–2.6×. Consider defaulting a "simmer at 212 °F" to the low setting or to the surface term | Snitkjær 2017 | Medium-low (one study) |
| 5c | Cooking: lid on at a boil | factor 0.01 | Wrong at a boil: a lidded pot lost ~85% as much as an open one. Apply 0.01 only below a boil | Snitkjær 2017 Fig. 3b | Medium-low (one pot and lid) |

## Q1. Salt → umami (decides the held change)

**Answer: in humans, NaCl does not raise perceived umami. The only direct suprathreshold test shows mild suppression, and threshold data show no effect on glutamate. Recommendation: set SALT_SHIFT_MAX = 1.0.**

### Suprathreshold intensity

- **Wang et al. 2022** (Food Qual Pref 98:104503; 12 trained UK panelists, gLMS, swallowed):
  - Design (Table 1, p. 3): MSG 0.015 M with NaCl 0.08 M (Exp. 1 and 2), MPG 0.01 M with NaCl 0.05 M (Exp. 3, no sodium from the glutamate).
  - Fig. 1 (p. 4, read): umami alone → umami + NaCl was 32.2 → 23.5 (Exp. 1), 31.1 → 22.4 (Exp. 2, sodium-balanced), 27.2 → 19.0 (Exp. 3, MPG). That is **×0.73, ×0.72, ×0.70**, all significant (p < 0.05).
  - "all the taste mixtures containing MSG were significantly (p < 0.05) lower in perceived umami intensity compared to MSG alone" (p. 5).
  - NaCl was the *weakest* suppressor: "The main exceptions were where the binary mixture was with sodium chloride (U + N), this led to a lower reduction in umami" (p. 5). Sucrose roughly halved umami (U+S ≈ 14).
  - Abstract: "Where glutamate and sodium chloride were used together, both umami and salty taste were maintained."
- **What the model predicts for Wang's samples:** at 0.08 M NaCl + 0.015 M MSG, the dog curve gives effect ≈ 0.574, so the shift is **×1.98 on concentration** (umami raw 7.9 → 10.4 on the Yamaguchi scale, +32%). With MPG + 0.05 M NaCl the shift is ×1.71. Humans went **down ~28%** in exactly these conditions.
- **Yamaguchi 1991** (Physiol Behav 49:833, review of Ajinomoto data): "Umami does not enhance the four basic tastes nor is it enhanced by them" (p. 833). Wang (p. 2) cites Yamaguchi 1998 the same way: "NaCl had no substantial influence on the perception of umami, while all other tastes did suppress umami."
- **Kemp & Beauchamp 1994** (J Food Sci 59:682): **NaCl was never tested on umami.** The four taste exemplars were sucrose, citric acid, quinine and NaCl (p. 683). Its general findings: "No true potentiation was found. Suprathreshold sodium chloride or monosodium glutamate additions generally suppressed pure tastes and flavors" (abstract, p. 682). Indirect support only.
- **Animal note (Maga 1983, p. 260):** in rats the MSG + IMP/GMP synergistic response "is decreased in the presence of salt"; cats differ. So even the animal evidence is split, and the dog data are not a safe stand-in.

### Thresholds (separate from intensity)

- **Yamaguchi 1991 Table 4 (p. 835), triangle tests:**
  - MSG threshold: 0.625 mM in water, **0.625 mM in 150 mM NaCl, 0.625 mM in 370 mM NaCl. No change.** "the threshold of MSG was not different from that in its aqueous solution nor in 370 mM NaCl solution" (p. 836).
  - IMP threshold: 0.313 mM in water, **0.625 mM in 20 mM NaCl (×2), 1.25 mM in 170 mM NaCl (×4)**, because IMP's threshold in water is really its sodium. IMP anion threshold "between 0.6 and 1.2 mM" (p. 836).
- **Schiffman 1991 Table 4a (p. 852), 16 young subjects:** MSG detection 0.902 mM alone; 1.35 mM in 0.5 mM NaCl, 1.11 mM in 3 mM NaCl (not significant). Recognition 2.55 → 2.27 → 1.75 mM (not significant). With L-Glu (Table 4b) NaCl also had no significant effect (1.72 → 1.49 / 1.48 mM). Only tiny salt levels (0.5–3 mM) were tested, far below food levels.
- **Bottom line on thresholds:** NaCl does not move the glutamate threshold. It raises the IMP-alone threshold (×2 to ×4) because IMP's threshold in water is a sodium signal.

### Recommendation

- **Set SALT_SHIFT_MAX = 1.0. Confidence: high** that the ×2 enhancement is wrong (no human study shows NaCl raising umami, and the one direct test shows the opposite at food-like levels). **Medium** that 1.0 is better than modeling suppression.
- **Why not model suppression?** Wang is one 12-person UK panel in water. Yamaguchi's data say no effect. Sweet, sour and bitter suppress umami *more* than salt does, so a salt-only suppression term would be lopsided (the model already handles acid suppression through Miranda). If you ever want it as a sensitivity scenario, Wang's ×0.72 on intensity corresponds to roughly **×0.5–0.7 on concentration** at 50–80 mM NaCl (using Schiffman 1991's MSG magnitude slope 0.87, Table 5b, or the model's own log curve).
- **Side effect to decide:** `SCORE_REF["umami"]` contains `log(5.0 * SALT_SHIFT_MAX)`. At 1.0 the 10/10 reference drops from 29.61 to 26.03, so unsalted dishes score a bit higher and salted ones lower. Either let it recompute (it follows the stated rule "5 g/dL with both boosts at max") or freeze it at 29.61. Rerun the Sauce, Soup, Dish and Bake map fits either way.
- **Legacy rule origin found (1b):** the breakpoints in the switched-off SALT_THRESHOLD_RULE (glutamate at 150 mM; nucleotides at 20 and 170 mM Na) match Yamaguchi 1991 Table 4 exactly. The multipliers don't: the table shows glutamate ×1 (not ×4) and nucleotides ×2 / ×4 (not ×4 / ×8). Keep it off. If you want salt in the nucleotide-alone path, ×2 / ×4 on IMP (GMP by analogy) is the sourced version. Low impact, since nucleotide thresholds now only apply when there's no glutamate.

## Q2. Aspartate threshold

- **Kirimura 1969** (J Agric Food Chem 17:689), Table I, p. 690, "Threshold Values and Organoleptic Characteristics of Amino Acids":
  - **Asp·Na: 100 mg/dL** (salty \*\*, MSG-like \*\*). Glu·Na: 30 mg/dL. Asp (free acid): 3 mg/dL, mainly sour (sour \*\*\*, MSG \*). Glu: 5 mg/dL.
  - Salt form: written "Asp·Na"; the hydrate isn't stated. Method isn't stated beyond a 100-person Ajinomoto panel "chosen by screening approximately 1000 employees" (p. 689).
  - As free Asp: Na-Asp·H2O → 0.100 × 133.10/173.10 = **0.077 g/100 mL** (5.78 mM); anhydrous Na-Asp → **0.086**.
  - Kirimura's own MSG value (30 mg/dL) is 2.5× Yamaguchi's 12 mg/dL, so his thresholds run high. Scaled to the model's glutamate basis (Asp:Glu molar ratio 3.6 × 0.68 mM), it gives 0.033.
- **Where 0.0166 comes from (new):** Yamaguchi 1991 Table 1 (p. 834; triangle test, n = 30): AspNa is significant down to **1.25 mM** (20/30 correct; 0.625 mM gives 11/30, not significant). 1.25 mM × 133.10 / 10⁴ = **0.01664 g/100 mL**, matching the model's 0.0166 to three digits. The same table gives MSG 0.625 mM = 0.0092 g/100 mL Glu, consistent with the model's glutamate 0.01. So both cells look like they came from this table.
- Caveat (p. 835): "Though AspNa is an umami substance, its taste threshold is equal to that of Na because its umami taste is weak." It's a detection threshold, not an umami one. Same is true of the glutamate threshold.
- **Recommendation: keep 0.0166 and replace "unsourced" with "Yamaguchi 1991 Table 1, 1.25 mM AspNa as free acid".** Medium-high confidence. It barely matters anyway (Asp umami weight 0.077; Yamaguchi 1991 p. 836 says aspartate "has an umami taste about 1/10 that of MSG").

## Q3. Nucleotide thresholds (Maga 1983)

- **Confirmed as printed.** Maga 1983 (Crit Rev Food Sci Nutr 18:231):
  - p. 251: "In comparing the taste thresholds of MSG, IMP, and GMP using the same panel, values of 0.014, 0.012, and 0.0035% have been reported" (ref. 134 = Takeda, *Ribotide product data No. 2*, "Comparison of the flavor enhancing effects of disodium 5′-inosinate and disodium 5′-guanylate"). That is a company bulletin, not a paper.
  - Table 15 (p. 260), "Water": MSG 0.03, **IMP 0.012, GMP 0.0035%** (refs 9, 15, 151, 152: Kuninaka 1964/1967 reviews and two Japanese meeting abstracts, 1960–61). In MSG solution: IMP 0.0001, GMP 0.00003; MSG in IMP solution: 0.002 (background levels not given).
  - Same section, p. 250: Kuninaka (1967) range "0.01 to 0.025% for 5′-IMP and 0.0035 to 0.02% for 5′-GMP". The Ajinomoto bulletin (ref. 135) gives 0.03, 0.025 and 0.0125 g/dL. Maga: "threshold values should only be considered approximate indicators."
  - Salt form: disodium salts; the hydrate isn't stated.
- **Conversion to free acid:**
  - IMP 0.012%: Na2IMP·7.5H2O → 0.228 mM = 0.0079 g/100 mL; anhydrous Na2IMP → 0.306 mM = **0.0107** (the old model value 0.011 = this reading).
  - GMP 0.0035%: Na2GMP·7H2O → 0.066 mM = 0.0024; anhydrous → 0.086 mM = 0.0031. The old 0.0056 matches neither.
- **Compared with Kuninaka 1980 (IMP 0.387 mM, GMP 0.206 mM):** Maga's IMP is 0.6–0.8× and GMP 0.3–0.4×. The primary human studies sit with Kuninaka:
  - Yamaguchi 1991 Table 1: IMP 0.313 mM, GMP 0.156 mM.
  - Schiffman 1991 Table 2b: IMP 0.43 mM (young detection), 1.99 mM (elderly); recognition 1.07 mM (Table 3b).
  - Tanaka 2025 (Table 2, Fig. 2): at 3 mM, 72–78% of panelists named IMP and GMP as umami; at 0.5 mM, 72–89% couldn't tell them from water.
- **Recommendation: keep Kuninaka 1980.** Medium-high confidence. Optional, low priority: Yamaguchi 1991 puts the true IMP anion threshold at 0.6–1.2 mM, and the IMP-alone threshold doubles or quadruples in salted food (see Q1, item 1b).

## Q4. Glutamate threshold drop with nucleotides

### Data (all detection thresholds; nucleotides at a constant 3 mM background, also present in the blank)

| Condition | Amado 2024 (US, n = 17; IMP/GMP/AMP n = 11) | Tanaka 2025 (Japanese young women, trained, n = 18) |
|---|---|---|
| MPG alone | 2.08 mM | 1.55 mM |
| + IMP 3 mM | 0.04603 mM (**÷45.2**) | 0.0161 mM (**÷96.3**) |
| + GMP 3 mM | 0.0698 mM (**÷29.8**) | 0.0144 mM (**÷107.6**) |
| + AMP 3 mM | 0.2329 mM (**÷8.9**) | 0.0760 mM (**÷20.4**) |
| + UMP 3 mM | 2.03 mM (÷1.0, ns) | 0.88 mM (÷1.76, p < 0.01) |
| + CMP 3 mM | ×2.59 higher on average (P = 0.20); 10/17 people inhibited, mean 8.75 mM | 1.40 mM (÷1.11, ns) |

Sources: Amado, Chem Senses 49:bjad049, Results pp. 2–4, Fig. 1. Tanaka, Chem Senses 50:bjaf043, Table 3, p. 6 (stimuli were disodium nucleotide salts, p. 2). Same staircase method (4-down, 1-up, ¼-log steps).

### Model vs data (D = min(63.16, 1 + 62.16 × IMPeq / 5), IMPeq = IMP + 0.18 AMP + 2.3 GMP in mM)

| Condition | Observed fold | Model D | Model/observed |
|---|---|---|---|
| IMP 3 mM | 45.2 (Amado) / 96.3 (Tanaka) | 38.3 | 0.85 / 0.40 |
| GMP 3 mM (IMPeq 6.9 → capped) | 29.8 / 107.6 | 63.2 | 2.12 / 0.59 |
| AMP 3 mM (IMPeq 0.54) | 8.9 / 20.4 | 7.7 | 0.86 / 0.38 |
| Schiffman 1991 young, MSG, IMP 0.1 mM (0.902 → 0.113 mM; Table 2b, p. 847) | 8.0 | 2.2 | 0.28 |
| Schiffman 1991 young, MSG, IMP 1 mM (→ 0.048 mM) | 18.8 | 13.4 | 0.71 |
| Schiffman 1991 young, K-glutamate, IMP 0.1 / 1 mM | 8.5 / 83.5 | 2.2 / 13.4 | 0.26 / 0.16 |
| Schiffman 1991 elderly, MSG, IMP 0.1 / 1 mM | 3.2 / 19.5 | 2.2 / 13.4 | 0.70 / 0.69 |
| Yamaguchi & Kimizuka 1979, IMP 5 mM (anchor) | 63.2 | 63.2 | 1.00 |

- **Agreement:** the model sits inside the human spread at 3–5 mM. US (Amado) is ~15% above the model, Japanese trained women (Tanaka) ~2.5× below it. The ×63 cap falls between Amado and Tanaka, so it's a fair middle. The AMP weight of 0.18 matches Amado well (0.86).
- **Misses:**
  - At low IMP (0.1 mM) the linear ramp under-predicts 3–4× (2.2× vs 8×). Real thresholds drop fast and then level off.
  - GMP: the 2.3× weight isn't supported at threshold (GMP/IMP fold ratio 0.66 in Amado, 1.12 in Tanaka). But at 3 mM both may already be near saturation, so these data can't pin the weight. Flag only.
- **Optional shape change (low-medium confidence):** a saturating curve D = 1 + 85 × IMPeq / (1.65 + IMPeq) fits the five IMP points with half the log error of the linear ramp (RMS 0.17 vs 0.31 log10 units). It gives 5.9× at 0.1 mM, 33× at 1 mM, 56× at 3 mM and 65× at 5 mM. Keep a cap if adopted. This mostly matters for foods with 0.1–1 mM nucleotides (vegetables, most cooked meats).
- **Absolute glutamate threshold (flag only):** model 0.01 g/100 mL = 0.68 mM. Human detection values: Yamaguchi 1991 0.625 mM MSG (Table 1), Kemp & Beauchamp ~0.98 mM ("about at detection threshold", p. 683), Schiffman 0.90 mM, Tanaka 1.55 mM, Amado 2.08 mM MPG. The model sits at the sensitive end, which is consistent with its Yamaguchi method. No change.

### Suprathreshold umami (Tanaka 2025 Fig. 5, p. 8; LMS, read from plot)

- MPG alone: 1, 3, 10, 30, 100 mM ≈ 0.8, 2.6, 6.4, 13.2, 24.0% LMS. With 3 mM IMP: 15.5, 21.0, 25.5, 29.8, 35.7%. GMP is similar; AMP gives 5.3, 10.9, 19.1, 25.8, 32.6%.
- Iso-intensity concentration shift (MPG needed alone to match the mixture):
  - **IMP ~39× at 1 mM MPG, ~24× at 3 mM**, ~12× at 10 mM, falling to ~4× at 100 mM.
  - GMP: 27×, 23×, ~15×.
  - **AMP: ~6–7×** at 1–10 mM.
  - (Values beyond 100 mM MPG are extrapolated.)
- Nucleotides alone at 3 mM (Table 4, p. 8): IMP 4.51%, GMP 4.16% (above "barely detectable" 1.4%); AMP 1.03%, CMP 0.80%, UMP 1.12% (not above it).
- "Umami synergy was observed especially at concentrations where MPG alone induced weak to moderate umami intensity (i.e. 3 to 30 mM MPG)" (p. 6). Tanaka also notes (p. 9) that Kochem & Breslin 2017 found 3 mM IMP or GMP did *not* enhance 100 mM MPG in US subjects.
- **Flag for the model:** at 3 mM nucleotide the model's synergy fold is 63 (IMP and GMP, capped; uncapped 194 and 449) and **26.7 for AMP**. Even this most-sensitive panel shows ~24–39× for IMP/GMP at low glutamate, and only ~6–7× for AMP. The fold also shrinks as glutamate rises, which Yamaguchi's constant-fold equation doesn't do. Suggest a separate review of the AMP coefficient (219) and the cap. No change proposed here.

## Q5. Cooking estimator blind check (Snitkjær 2017)

### What the paper reports

- Food Chem 230:234. 47 veal stock reductions: 900 mL stock + 150 mL beer or wine = **1,050 mL**, 30 min. The pot was brought to the boil lid-on at max power (time 0), then reduced "at a lower energy input without lid" (p. 235).
- Table 1 (p. 235) conditions:
  - Base: 20 cm × 12 cm steel pot, 100 °C, no lid.
  - Temperature series: 59, 65 and 84 °C.
  - Pot diameter: 16 cm and 30 cm (IKEA).
  - Pot height: 7 cm (sauté pan) and 17 cm.
  - Lid on.
- Temperature was read with a kitchen thermometer. About 60 mL was sampled at 0, 3, 7, 14, 21 and 30 min, and the pot was weighed throughout.
- Volume over time is "results not shown" (p. 237), but each Fig. 3a point (remaining "corrected" volume fraction, p. 238) pairs with a Fig. 2 time point. That lets the 30-min loss be recovered.
- "Corrected volume" (p. 236) removes the sampling. Read as a product of per-step evaporation ratios, Base-e evaporates at a constant 11.3–12.2 g/min across all five intervals. Read as an additive fraction of V0, the rate climbs from 13 to 17 g/min at constant heat, which is implausible. So the multiplicative reading is used, with the additive one as an upper bound.

### Results (30 min, lid off; observed = multiplicative / additive reading)

| Run | Observed loss | Model (`loss_in_pot`, mid; low–high) | K the data imply on the Shah term |
|---|---|---|---|
| Base-e: 20 cm, 100 °C | 349 / 453 g (11.6 g/min) | 550 g (367–734), burner-limited | 1.02 |
| d16-a: 16 cm, 100 °C | 223 / 286 g | 550 g (367–734) | 1.02 |
| d30-a: 30 cm, 100 °C | 402 / 525 g | 1,053 g (769–1,071) | 0.52 |
| h7-a: 20 cm sauté, 100 °C | 216 / 276 g | 550 g | 0.63 |
| h17-a: 20 cm, 17 cm tall, 100 °C | 265 / 341 g | 550 g | 0.78 |
| T84-a: 20 cm, 84 °C (183 °F) | 198 / 253 g | **215 g** (166–248) | 1.19 whole run; **1.16 for 14–30 min** |
| T59-a: 20 cm, 59 °C (138 °F) | 89 / 112 g | 57 g (44–66) | 2.0 whole run; **~1.3 for 14–30 min** |
| Lid-a: 20 cm, 100 °C, **lid on** | 297 / 383 g | **6 g** (lid factor 0.01) | n/a |

(`estimate(1050 g, 30 min, 212 °F)` with its own pot list: central 630 g, capped at 60% of the water; range 367–630 g.)

- **K = 1.3 holds up below a boil.** At 84 °C the model is within +9% for the whole run. The steady-state segment (14–30 min, after the pot cooled from its starting boil) implies K = 1.16. At 59 °C the late segment implies about 1.3, but this volume comes from the concentrations via β = 3.9, so it's less direct. The whole-run 2.0 at 59 °C is inflated by the cool-down from 100 °C at time 0. **Keep 1.3.**
- **At a boil the model runs high.** The boil path at mid throttle (0.75 × 0.92 kW) predicts 18 g/min; the 16–20 cm pots did 7–12 g/min at "lower energy input". For 16–20 cm pots the Shah surface term at 100 °C with K ≈ 1 nailed it (K needed 1.02 for both). The 30 cm pot and the sauté pan fell further below, probably heat-limited. The low setting (367 g) is within 5% for Base-e only.
- **Lid on at a boil is badly wrong.** Lidded Lid-a lost ~85% as much as open Base-e (297 vs 349 g). The model's 0.01 factor comes from sub-boil simmering (Opadokun at 90 °C), where a lid does stop evaporation. At a boil the steam escapes under the lid. One lid and pot only.
- **Proposals (medium-low confidence, one study):**
  1. Keep K = 1.3.
  2. When the user says "boil/simmer at 212 °F" with no heat level, default to the low throttle (or the Shah term at 100 °C × area) instead of mid.
  3. Apply the lid-on factor only below ~205 °F. At a boil, use something like 0.6–1.0 until better data exist.
- Bonus finding: ethanol falls as a power of the remaining volume, C/C0 = (V/V0)^β, with **β ≈ 3.9 lid off** (mean of Base series, Fig. 4) and **~8–10.5 lid on** (Fig. 3b), independent of pot size and temperature (p. 238). That's a ready-made rule if the model ever tracks wine or beer in cooking.

## Q6. Schiffman 2000 (Physiol Behav 69:147)

Mostly a theory paper (across-fiber coding), with one useful table. In Table 1a/1b (p. 149; 12 young and 12 elderly subjects, 10 points spread over sweet/salty/sour/bitter/other):
- **0.05 M Na glutamate** is rated salty only 1.1 (young) / 0.5 (elderly), with "other" (umami) 6.6 / 7.7.
- **0.2 M NaCl** is salty 7.8 / 6.8.
- **0.3 M KCl** is salty 5.5 / 6.1, sour 2.0 / 0.8, bitter 1.4 / 2.7.

Two leads, no change proposed:
- (a) MSG's sodium tastes much less salty than NaCl's. Yamaguchi 1991 (p. 836, Table 6) puts MSG at ~30% of NaCl per mole of Na (IMP ~50%, AspNa 40–60%), and says MSG + IMP saltiness is "estimated as zero". The model now counts glutamate-salt sodium as full sodium saltiness. Worth checking against the Sun 2022 fit behind UMAMI_SALT_EMAX.
- (b) KCl carries a bitter/sour side taste, more so in older people. That's relevant to the open "K citrate/malate may be bitter" question.
