// Reference oracle for the Taste Check rebuild package.
// Runs the model JavaScript exactly as embedded in the live Taste Check page and writes the expected values
// for every test recipe. The page is the source of truth; this script only loads it.
//
// Usage (Node 18+, no packages needed):
//   node oracle.js <path to taste-check/index.html> <test_recipe_inputs.json> <output test_recipes.json>
// Get the page with e.g.: curl -L -o index.html https://tools.mendocinofoodconsulting.com/taste-check/
"use strict";
const fs = require("fs");
const vm = require("vm");
const crypto = require("crypto");

const [pagePath, inputPath, outPath] = process.argv.slice(2);
if (!outPath) { console.error("usage: node oracle.js index.html test_recipe_inputs.json test_recipes.json"); process.exit(2); }
const page = fs.readFileSync(pagePath, "utf8");

function block(tag) {
  const m = page.match(new RegExp("/\\*" + tag + ":BEGIN\\*/([\\s\\S]*?)/\\*" + tag + ":END\\*/"));
  if (!m) throw new Error("marker not found: " + tag);
  return m[1];
}
// The page's taste-neutral helper rows ("Oil or fat", "Dried spices & herbs") live in their own <script>
// between the DB block and the model block.
function helperScript() {
  const m = page.match(/<script>\s*(\/\/ Taste-neutral helpers[\s\S]*?)<\/script>/);
  if (!m) throw new Error("helper script not found");
  return m[1];
}
const DB = block("HFP_DB"), MODEL = block("HFP_MODEL"), PASTE = block("HFP_PASTE"), HELP = helperScript();

const sb = { console };
sb.window = sb; sb.globalThis = sb;
vm.createContext(sb);
vm.runInContext(DB, sb, { filename: "HFP_DB" });
vm.runInContext(HELP, sb, { filename: "helpers" });
vm.runInContext(MODEL, sb, { filename: "HFP_MODEL" });
vm.runInContext(PASTE, sb, { filename: "HFP_PASTE" });
const HFP = sb.HFP, PASTE_API = sb.HFP_PASTE;

const sha = s => crypto.createHash("sha256").update(s, "utf8").digest("hex");
const inputs = JSON.parse(fs.readFileSync(inputPath, "utf8"));

function toRecipe(items) {
  return items.map(it => Array.isArray(it) ? { ingredient: it[0], amount: it[1], unit: it[2] } : Object.assign({}, it));
}
const RAW_KEYS = ["umami_intensity", "saltiness_intensity", "sweetness_intensity", "sourness_intensity",
  "kokumi_intensity_pct", "bitterness_intensity"];
const SCORE_KEYS = ["umami", "saltiness", "sweetness", "sourness", "kokumi", "bitterness"];

const recipes = inputs.filter(x => x.items).map(x => {
  const recipe = toRecipe(x.items);
  const opt = Object.assign({}, x.opt || {});
  let page_note = null;
  if (typeof opt.water_loss_g === "string" && opt.water_loss_g.startsWith("PAGE_PCT:")) {
    // The page converts "cooked down by P %" to grams of water: P% of the recipe's total mass (computed with no options).
    const pct = +opt.water_loss_g.split(":")[1];
    opt.water_loss_g = HFP.compute(recipe, {}).totals.mass_g * pct / 100;
    page_note = `water_loss_g = ${pct}% of total mass, as the page does`;
  }
  const r = HFP.compute(recipe, opt);
  const exp = { raw: {}, score: {} };
  RAW_KEYS.forEach(k => (exp.raw[k] = r.results[k]));
  SCORE_KEYS.forEach(k => (exp.score[k] = r.scores[k]));
  exp.pH = r.acidity.pH;
  exp.intermediate = {
    total_mass_g: r.totals.mass_g, total_water_g: r.totals.water_g, salt_pct_water: r.totals.salt_pct_water,
    sucrose_eq_pct: r.totals.sucrose_eq_pct, umami_eq_msg_pct: r.totals.umami_eq_msg_pct,
    sour_stimulus_mM: r.acidity.sour_stimulus_mM, citric_equiv_mM: r.acidity.citric_equiv_mM,
    umami_remaining: r.acidity.umami_remaining, synergy_pH_factor: r.acidity.synergy_pH_factor,
  };
  exp.note_keys = r.notes.map(n => n.key).sort();
  exp.missing = r.missing.map(m => ({ name: m.name, fields: m.fields.slice() }));
  exp.estimated = r.estimated.map(m => ({ name: m.name, fields: m.fields.slice().sort() }));
  const out = { id: x.id, name: x.name, origin: x.origin, recipe, opt, expected: exp };
  if (x.covers) out.covers = x.covers;
  if (page_note) out.page_note = page_note;
  return out;
});

const paste = inputs.filter(x => x.paste).map(x => ({ id: x.id, name: x.name, text: x.paste,
  expected: PASTE_API.parse(x.paste, Object.keys(HFP.db), HFP.search, HFP.db) }));

const out = {
  about: "Expected outputs computed by executing the model JavaScript embedded in the live Taste Check page (tools/oracle.js).",
  model_version: "2.8.3", source_page: "https://tools.mendocinofoodconsulting.com/taste-check/",
  block_sha256: { HFP_DB: sha(DB), HFP_MODEL: sha(MODEL), HFP_PASTE: sha(PASTE), helpers: sha(HELP) },
  derived_constants: { score_reference: HFP.SCORE_REF, miranda_fit_S50_mM_and_hill: HFP._fit() },
  tolerances: {
    raw: "abs(got - expected) <= max(1e-6, 1e-6 * abs(expected))",
    score: "abs(got - expected) <= 0.05 (1-10 scale)",
    pH: "abs(got - expected) <= 1e-4",
    intermediate: "abs(got - expected) <= max(1e-6, 1e-6 * abs(expected)); informative, for debugging",
    note_keys: "set of keys should match exactly (conditions in REBUILD.md section 11); note wording is not tested",
    missing_estimated: "exact match (data-gap flags, REBUILD.md section 11.2); 'estimated' field lists are sorted",
    null: "sourness is null (not a number) when the acidity model is switched off",
  },
  recipes, paste_cases: paste,
};
fs.writeFileSync(outPath, JSON.stringify(out, null, 1) + "\n");
console.log(`wrote ${recipes.length} recipes, ${paste.length} paste cases`);
