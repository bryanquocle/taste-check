// Runs web/hfp_model.js under Node for tests/web_parity.py. Reads a JSON list of cases from the file given
// as the first argument, prints a JSON list of results. Loads only the two project files below.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const web = path.join(__dirname, "..", "web");
const sandbox = { console: console };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const f of ["hfp_db.js", "hfp_model.js"]) {
  vm.runInContext(fs.readFileSync(path.join(web, f), "utf8"), sandbox, { filename: f });
}
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = cases.map((c) => {
  const r = sandbox.HFP.compute(c.recipe, c.opt);
  return { name: c.name, results: r.results, scores: r.scores, pH: r.acidity ? r.acidity.pH : null, totals: r.totals };
});
process.stdout.write(JSON.stringify(out));
