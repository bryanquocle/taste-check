"""Export the HFP ingredient database (hfp_raw_data.csv + hfp_data_quality.csv) to a compact JS file
for the browser version of the model. Re-run after any Raw Data change, then rebuild the page."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hfp_model as m
import hfp_acidbase as ab
import hfp_sweet as sw

db = m.load_db()
FIELDS = (list(m.COL) + ["acid_" + a for a in ab.ORGANIC_ACIDS] + ["sugar_" + s for s in sw.SUGAR_COLUMNS])
out = {"fields": FIELDS, "items": []}
for name, d in db.items():
    out["items"].append([name, [d[f] if d[f] else 0 for f in FIELDS], d["ph_ref"],
                         sorted(d["_blank"]), {k: v for k, v in d["_tier"].items()}])
js = "window.HFP_DB = " + json.dumps(out, separators=(",", ":"), ensure_ascii=False) + ";\n"
path = os.path.join(HERE, "hfp_db.js")
open(path, "w", encoding="utf-8").write(js)
print(f"wrote {path}: {len(out['items'])} ingredients, {len(js) // 1024} KB")
