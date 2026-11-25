// Exports every rule table of the Taste Check paste parser (HFP_PASTE block of the live page) to CSV.
// The tables are read from the running code, not retyped: the script adds one export line to the block's
// source before running it in a sandbox, so the CSV always matches the page it was given.
//
// Usage: node export_paste_rules.js <taste-check/index.html> <paste_rules.csv>
"use strict";
const fs = require("fs");
const vm = require("vm");

const [pagePath, outPath] = process.argv.slice(2);
if (!outPath) { console.error("usage: node export_paste_rules.js index.html paste_rules.csv"); process.exit(2); }
const page = fs.readFileSync(pagePath, "utf8");
const m = page.match(/\/\*HFP_PASTE:BEGIN\*\/([\s\S]*?)\/\*HFP_PASTE:END\*\//);
if (!m) throw new Error("HFP_PASTE block not found");
let src = m[1];
const HOOK = "G.HFP_PASTE = { parse, parseLine };";
if (!src.includes(HOOK)) throw new Error("export line not found; the parser changed, update this script");
src = src.replace(HOOK, HOOK + " G.__RULES = { FRAC, OZ, LB, NUM, QTY, SIZE, UNITS, MAP, SKIP_FIRST, SKIP, EACH_G, UNIT_G, CAN_G, VOL, HEADER, DESCRIPT, APPROX_NOTE, GUARDED };");
const sb = {}; sb.window = sb; sb.globalThis = sb;
vm.createContext(sb);
vm.runInContext(src, sb, { filename: "HFP_PASTE" });
const R = sb.__RULES;

// Messages (status notes) are string literals inside parse() and toItem(); collect them from the source text.
function fnBody(name) {
  const i = src.indexOf("function " + name + "(");
  if (i < 0) throw new Error("function not found: " + name);
  let depth = 0, j = src.indexOf("{", i);
  for (let k = j; k < src.length; k++) {
    if (src[k] === "{") depth++;
    else if (src[k] === "}") { depth--; if (depth === 0) return src.slice(j, k + 1); }
  }
  throw new Error("unbalanced " + name);
}
const messages = [];
for (const fn of ["toItem", "parse"]) {
  const body = fnBody(fn);
  const LIT = String.raw`("(?:\\.|[^"\\])*"|` + "`(?:\\\\.|[^`\\\\])*`)";
  const re = new RegExp(String.raw`status:\s*"(\w+)",\s*item:\s*null,\s*note:\s*` + LIT
    + String.raw`|\[\s*null\s*,\s*"(\w+)"\s*,\s*` + LIT + String.raw`\s*\]`
    + String.raw`|status = "(\w+)"; note = ` + LIT, "g");
  let mm;
  while ((mm = re.exec(body))) {
    const st = mm[1] || mm[3] || mm[5], lit = mm[2] || mm[4] || mm[6];
    messages.push([fn, st, lit.slice(1, -1).replace(/\\"/g, '"')]);
  }
}

const rows = [];
const add = (table, order, pattern, flags, value, note) => rows.push([table, order, pattern, flags, value, note]);
Object.entries(R.FRAC).forEach(([k, v], i) => add("FRAC", i + 1, k, "", v, "unicode fraction replaced before parsing"));
add("NUMBER", 1, R.NUM, "", "", "number: mixed number, fraction or decimal");
add("QTY", 1, R.QTY.source, R.QTY.flags, "", "leading quantity; optional range with -, en dash or 'to' (midpoint used)");
add("SIZE", 1, R.SIZE.source, R.SIZE.flags, `oz/fl oz=${R.OZ} g; lb=${R.LB} g; g and ml=1`, "package size in parentheses after the quantity; multiplies the quantity");
R.UNITS.forEach(([rx, unit], i) => add("UNITS", i + 1, rx.source, rx.flags, unit, "unit words; first match wins; matched against the text after the quantity plus a trailing space"));
R.MAP.forEach(([rx, name], i) => {
  let kind = "map";
  if (name.startsWith("!")) kind = "refuse";
  else if (name === "BLEND") kind = "refuse-blend";
  else if (name.includes("|")) kind = "map-conditional";
  else if (name.endsWith("*")) kind = "map-approx";
  add("MAP", i + 1, rx.source, rx.flags, name, kind);
});
add("SKIP_FIRST", 1, R.SKIP_FIRST.source, R.SKIP_FIRST.flags, "skip", "checked on the bare first choice before mapping");
add("SKIP", 1, R.SKIP.source, R.SKIP.flags, "skip", "checked after mapping fails");
add("HEADER", 1, R.HEADER.source, R.HEADER.flags, "ignore line", "section headers");
add("DESCRIPT", 1, R.DESCRIPT.source, R.DESCRIPT.flags, "removed", "descriptive words removed before the search fallback");
add("GUARDED", 1, R.GUARDED.source, R.GUARDED.flags, "guess rejected", "a search guess matching this is rejected unless the line shares a word of 4+ letters with it (excluding fruit, salt, extract)");
Object.entries(R.EACH_G).forEach(([k, v], i) => add("EACH_G", i + 1, k, "", v, "grams per piece when no unit"));
Object.entries(R.UNIT_G).forEach(([k, v], i) => add("UNIT_G", i + 1, k, "", v, "grams per unit"));
Object.entries(R.CAN_G).forEach(([k, v], i) => add("CAN_G", i + 1, k, "", v, "grams per can, jar or package"));
Object.entries(R.VOL).forEach(([k, v], i) => add("VOL", i + 1, k, "", `${v[0]} x ${v[1]}`, "volume unit passed to the model (unit x multiplier)"));
Object.entries(R.APPROX_NOTE).forEach(([k, v], i) => add("APPROX_NOTE", i + 1, k, "", v, "note shown for an approximate (*) match"));
messages.forEach(([fn, st, text], i) => add("MESSAGE", i + 1, fn, "", st, text));

const q = s => { s = String(s); return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const out = ["table,order,pattern_or_key,regex_flags,value,note"].concat(rows.map(r => r.map(q).join(","))).join("\n") + "\n";
fs.writeFileSync(outPath, out);
const counts = {};
rows.forEach(r => (counts[r[0]] = (counts[r[0]] || 0) + 1));
console.log(`wrote ${rows.length} rows`, JSON.stringify(counts));
