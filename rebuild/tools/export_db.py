"""Export the ingredient database embedded in the Taste Check page (HFP_DB block) to CSV.

Usage (Python 3.8+, standard library only):
    python export_db.py <path to taste-check/index.html> <output.csv>

One row per ingredient, columns in the page's own field order. Values are exactly the numbers in the page
(0 where the page stores 0 or null). Extra columns:
    ph_ref         reference pH used to calibrate the ingredient (blank = none)
    blank_fields   fields recorded as blank (no data) in the source workbook, ";"-separated
    tiers          data-quality tiers for fields that have one, "field:tier" ";"-separated
"""
import csv
import json
import re
import sys


def load(page_path):
    text = open(page_path, encoding="utf-8").read()
    m = re.search(r"/\*HFP_DB:BEGIN\*/\s*window\.HFP_DB\s*=\s*(.*?);?\s*/\*HFP_DB:END\*/", text, re.S)
    if not m:
        raise SystemExit("HFP_DB block not found")
    return json.loads(m.group(1).strip().rstrip(";"))


def fmt(v):
    if v is None:
        return "0"
    if float(v).is_integer():
        return str(int(v))
    return repr(float(v))


def main(page_path, out_path):
    db = load(page_path)
    fields = db["fields"]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["ingredient"] + fields + ["ph_ref", "blank_fields", "tiers"])
        for name, vals, ph, blank, tier in db["items"]:
            w.writerow([name] + [fmt(v) for v in vals]
                       + ["" if ph is None else fmt(ph), ";".join(sorted(blank or [])),
                          ";".join(f"{k}:{v}" for k, v in sorted((tier or {}).items()))])
    print(f"{len(db['items'])} ingredients, {len(fields)} fields -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
