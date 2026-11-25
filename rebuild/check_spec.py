"""check_spec.py: checks that REBUILD.md documents every constant in the live Taste Check model.

Standard-library Python 3.8+. Run from this folder:
    python check_spec.py                      # uses ../index.html (the Taste Check page in this repo)
    python check_spec.py path/to/index.html   # or a page you downloaded from the live site

What it checks (exit code 0 = PASS, 1 = FAIL):
 1. Every numeric literal in the page's HFP_MODEL block (comments and strings excluded) appears in a row of
    the constant register in REBUILD.md (the tables under "## 12. Constant register"), and that row has a
    non-empty Source cell. Numbers are compared as values, so 0.50 and 0.5 match.
 2. Every UPPER_CASE constant declared in the model block (const NAME = ...) is named in a register row
    with a non-empty Source cell.
 3. Every ingredient name hard-coded in the model block (string literals inside the name sets and tables)
    appears in REBUILD.md.
 4. The SHA-256 of the ingredient CSV matches the value printed in REBUILD.md, and the CSV matches a fresh
    export of the page's HFP_DB block (tools/export_db.py).
 5. The SHA-256 of each embedded block printed in test_recipes.json matches the page.
"""
import csv
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRIVIAL = {0.0, 1.0}          # loop starts, "1 -" complements and boolean-like flags
CSV_NAME = "hfp_ingredients_v2.8.3.csv"


def block(text, tag):
    m = re.search(r"/\*%s:BEGIN\*/(.*?)/\*%s:END\*/" % (tag, tag), text, re.S)
    if not m:
        raise SystemExit(f"FAIL: {tag} block not found in the page")
    return m.group(1)


def lex(js):
    """Minimal JavaScript lexer: returns (numbers, strings, code_without_comments_and_strings)."""
    nums, strs, out = [], [], []
    i, n = 0, len(js)
    prev = ""                                   # last significant character, to tell regex from division
    while i < n:
        c = js[i]
        if js.startswith("//", i):
            j = js.find("\n", i)
            i = n if j < 0 else j
            continue
        if js.startswith("/*", i):
            j = js.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "\"'`":
            j, buf = i + 1, []
            while j < n and js[j] != c:
                if js[j] == "\\":
                    buf.append(js[j:j + 2]); j += 2; continue
                buf.append(js[j]); j += 1
            strs.append("".join(buf))
            out.append(" ")
            i = j + 1
            prev = "a"
            continue
        if c == "/" and (prev in "(,=:[!&|?{};+-*%<>~^" or prev == ""):
            j, cls = i + 1, False                # regex literal
            while j < n:
                if js[j] == "\\":
                    j += 2; continue
                if js[j] == "[":
                    cls = True
                elif js[j] == "]":
                    cls = False
                elif js[j] == "/" and not cls:
                    break
                j += 1
            j += 1
            while j < n and js[j].isalpha():
                j += 1
            out.append(" ")
            i = j
            prev = "a"
            continue
        m = re.match(r"(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", js[i:])
        if m and not (i > 0 and (js[i - 1].isalnum() or js[i - 1] == "_")):
            nums.append(m.group(0))
            out.append(m.group(0))
            i += len(m.group(0))
            prev = "a"
            continue
        out.append(c)
        if not c.isspace():
            prev = "a" if (c.isalnum() or c in "_$)]") else c
        i += 1
    return nums, strs, "".join(out)


def register_rows(md):
    """Rows of the markdown tables inside section 12 (the constant register)."""
    m = re.search(r"^## 12\. Constant register.*?(?=^## 13\.)", md, re.S | re.M)
    if not m:
        raise SystemExit("FAIL: '## 12. Constant register' section not found in REBUILD.md")
    rows, header = [], None
    for line in m.group(0).splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", x) for x in cells):
            continue
        if header is None:
            header = [h.lower() for h in cells]
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def numbers_in(s):
    vals = set()
    for t in re.findall(r"(?<![\w.])[-−]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", s.replace(",", " ")):
        try:
            vals.add(abs(float(t.replace("−", "-"))))
        except ValueError:
            pass
    return vals


def main():
    page_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "index.html")
    page = open(page_path, encoding="utf-8").read()
    md = open(os.path.join(HERE, "REBUILD.md"), encoding="utf-8").read()
    model = block(page, "HFP_MODEL")
    nums, strs, code = lex(model)
    rows = register_rows(md)
    sourced = [r for r in rows if r.get("source", "").strip() not in ("", "-", "—")]
    unsourced = [r for r in rows if r not in sourced]
    fails = []
    if unsourced:
        fails += [f"register row without a source: {r}" for r in unsourced]

    # 1. numeric literals
    reg_vals = set()
    for r in sourced:
        for v in r.values():
            reg_vals |= numbers_in(v)
    lits = sorted({float(x) for x in nums} - TRIVIAL)
    missing_nums = [x for x in lits if not any(abs(x - v) <= 1e-12 * max(1.0, abs(x)) for v in reg_vals)]
    fails += [f"numeric literal {x!r} not in a sourced register row" for x in missing_nums]

    # 2. upper-case constants
    names = sorted(set(re.findall(r"\b([A-Z][A-Z0-9_]{1,})\s*=(?!=)", code)) - {"G"})
    reg_text = " ".join(" ".join(r.values()) for r in sourced)
    missing_ids = [x for x in names if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(x) + r"(?![A-Za-z0-9_])", reg_text)]
    fails += [f"constant {x} not named in a sourced register row" for x in missing_ids]

    # 3. hard-coded ingredient names (string literals with a capital letter that are not messages)
    name_like = sorted({s for s in strs if re.fullmatch(r"[A-Z][A-Za-z ,()%'&-]{2,60}", s) and not s.endswith(".")})
    missing_names = [s for s in name_like if s not in md]
    fails += [f"hard-coded name {s!r} not in REBUILD.md" for s in missing_names]

    # 4. CSV hash and content
    csv_path = os.path.join(HERE, CSV_NAME)
    data = open(csv_path, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    if sha not in md:
        fails.append(f"SHA-256 of {CSV_NAME} ({sha}) is not printed in REBUILD.md")
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import export_db                                    # noqa: E402
    buf = io.StringIO()
    dbj = export_db.load(page_path)
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ingredient"] + dbj["fields"] + ["ph_ref", "blank_fields", "tiers"])
    for name, vals, ph, blank, tier in dbj["items"]:
        w.writerow([name] + [export_db.fmt(v) for v in vals]
                   + ["" if ph is None else export_db.fmt(ph), ";".join(sorted(blank or [])),
                      ";".join(f"{k}:{v}" for k, v in sorted((tier or {}).items()))])
    if buf.getvalue().encode("utf-8") != data:
        fails.append(f"{CSV_NAME} differs from a fresh export of the page's HFP_DB block")

    # 5. block hashes recorded with the test recipes
    tr = json.load(open(os.path.join(HERE, "test_recipes.json"), encoding="utf-8"))
    for tag in ("HFP_DB", "HFP_MODEL", "HFP_PASTE"):
        h = hashlib.sha256(block(page, tag).encode("utf-8")).hexdigest()
        if tr["block_sha256"].get(tag) != h:
            fails.append(f"test_recipes.json block_sha256[{tag}] does not match this page")

    print(f"model block: {len(set(nums))} distinct numeric literals ({len(lits)} non-trivial), "
          f"{len(names)} upper-case constants, {len(name_like)} hard-coded names")
    print(f"register: {len(rows)} rows ({len(sourced)} with a source)")
    print(f"{CSV_NAME}: sha256 {sha}")
    if fails:
        print(f"FAIL ({len(fails)} problems)")
        for f in fails:
            print("  - " + f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
