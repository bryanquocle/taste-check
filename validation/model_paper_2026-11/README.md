# Model-description paper analyses (November 2026)

Analyses behind *Taste Check: Predicting Six Taste Intensities from Food Composition* (technical report, `report/technical-report.pdf`; also at https://tools.mendocinofoodconsulting.com/taste-check/technical-report.pdf). Model version 2.17.0 (report revised November 27, 2026; first edition described v2.16.2).

| Script | What it does | Output |
|---|---|---|
| `analyses.py tally` | Counts evidence levels in the constant register (`rebuild/REBUILD.md` section 12) | `results/tally.json` |
| `analyses.py coverage` | Ingredient-database field coverage, and recipe mass resting on missing or estimated data | `results/coverage.json` |
| `analyses.py validate` | Spearman rho per taste on the SVT held-out test half, 2,000 bootstrap resamples (seed 20261126) | `results/validate.json` |
| `analyses.py morris` | Morris elementary-effects screening of 13 uncertain constants (r = 20, 4 levels, 281 runs) | `results/morris.json` |
| `worked_examples.py` | Three recipes computed by hand from the printed equations and compared with the model | `results/worked_examples.json` |
| `figures.py` | Validation scatter and sensitivity bars | `figures/` |

Run from the repository root layout of the author's working folder (the scripts import `hfp_model.py` two levels up). Standard-library Python except `figures.py` (matplotlib).

**Data notes.**
- `svt_units.csv` maps 89 SVT foods to model ingredients with a seeded dev/test split. It is derived from Mars et al. (2020), Taste, Fat and Texture Database (SVT), DANS doi:10.17026/dans-xst-ughm, and is shared under **CC BY-SA 4.0**, like `tests/svt_panel.json`.
- The `coverage` step reads parsed Food.com recipes (RecipeNLG ingredient text) that are not redistributed here; its aggregate results are in `results/coverage.json`.
