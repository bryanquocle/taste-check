# Taste Check model (Human Flavorome Project)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24540783.svg)](https://doi.org/10.5281/zenodo.24540783)
[![tests](https://github.com/bryanquocle/taste-check/actions/workflows/tests.yml/badge.svg)](https://github.com/bryanquocle/taste-check/actions/workflows/tests.yml)

The model behind [Taste Check](https://tools.mendocinofoodconsulting.com/taste-check/). It predicts how salty, savory (umami), sweet, sour, bitter and rich (kokumi) a recipe should taste from its chemistry, using published dose-response curves and a sourced ingredient database.

Built by Dr. Bryan Quoc Le, food scientist, [Mendocino Food Consulting](https://www.mendocinofoodconsulting.com/).

**Version 2.15.0** (November 25, 2026). The full specification, with every constant, its source and its verification status, is in [`rebuild/REBUILD.md`](rebuild/REBUILD.md).

## What's here

| Path | What it is |
|---|---|
| `hfp_model.py` | The reference model (standard-library Python 3.8+, no extra packages). Also `hfp_acidbase.py` (pH, sourness), `hfp_sweet.py` (sweetness), `hfp_bitter.py` (bitterness), `hfp_ranges.py` (uncertainty ranges), `hfp_formulate.py` (reformulation helper). |
| `hfp_raw_data.csv` | The ingredient database: glutamate, nucleotides, sodium, potassium, sugars, organic acids, glutathione, caffeine and more, per 100 g. |
| `hfp_data_quality.csv`, `hfp_categories.csv` | Data-quality tiers for individual values, and ingredient categories used for uncertainty ranges. |
| `web/` | The browser port that runs on the live page (`hfp_model.js`, `hfp_db.js`, `recipe_paste.js`). |
| `tests/` | Golden recipes, published sensory panels and the parity tests that keep Python and JavaScript identical. |
| `rebuild/` | Rebuild package: the specification, 53 test recipes with expected outputs, references, the paste parser rules and a checker. |
| `MODEL_NOTES.md` | Developer notes and change history. |

## Quick start

```
python hfp_model.py "Tomato (Canned)=200 g" "Sauce, Soy=15 mL" "Water=100 g"
python hfp_model.py --search miso          # find exact ingredient names
python hfp_model.py --detail "Garlic=10 g" "Water=300 g"
```

## Tests

```
python tests/run_tests.py          # 38 golden recipes + 19 published panel sets
python tests/svt_panel_test.py     # 85 foods rated by a trained Dutch panel (SVT, DANS doi:10.17026/dans-xst-ughm)
python tests/ranges_test.py
python tests/web_parity.py         # needs Node.js; checks the browser port matches Python
```

To check the specification against the live page, save https://tools.mendocinofoodconsulting.com/taste-check/ as `index.html` and run `python rebuild/check_spec.py index.html`.

## How well it works, and its limits

Rank agreement (Spearman rho) with the 81-food SVT panel: umami 0.73, saltiness 0.84, sweetness 0.80, sourness 0.75. On a pre-registered hold-out of 43 low-water foods, saltiness 0.77 and sweetness 0.84. Aroma, fat, texture and heat are not modelled, bitterness covers five compounds only, and several constants are labelled assumptions in the specification. The predicted pH is an estimate and must not be used for food safety decisions.

## License

- **Code** (`*.py`, `*.js`): MIT, see [`LICENSE`](LICENSE).
- **Data and documentation** (`*.csv`, `*.json`, `*.md`): Creative Commons Attribution 4.0, see [`LICENSE-DATA.md`](LICENSE-DATA.md), except `tests/svt_panel*.json`, which is derived from the SVT sensory database and shared under CC BY-SA 4.0.

## Cite

Le, B. Q. (2026). *Taste Check model (Human Flavorome Project)* (Version 2.15.0). Mendocino Food Consulting. https://doi.org/10.5281/zenodo.24540783

That DOI always resolves to the latest version; v2.15.0 itself is https://doi.org/10.5281/zenodo.24548959. See [`CITATION.cff`](CITATION.cff).
