"""Parity: web/cook_evap.js vs validation/cook_evaporation/cook_evap.py on a grid of cases (v.2.10.0).
Python rounds its outputs to whole grams, so the pass mark is 0.6 g."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "validation", "cook_evaporation"))
import cook_evap as ce  # noqa: E402

cases = []
for mass in (150, 400, 1200, 3000, 8000):
    for minutes in (5, 30, 120):
        for tF in (150, 195, 205, 211, 212):
            for pot in (None, "saucepan", "skillet", "dutch", "stockpot", "wok", "saute"):
                for lid in ("off", "ajar", "on"):
                    cases.append([mass, minutes, tF, pot, lid, mass * 0.85])
js = r"""
const fs=require('fs'); require(process.argv[1]);
const cs=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(cs.map(c=>{const r=globalThis.HFP_COOK.estimate(...c);return [r.central_g,r.low_g,r.high_g,r.capped];})));"""
p = subprocess.run(["node", "-e", js, os.path.join(ROOT, "web", "cook_evap.js")], input=json.dumps(cases),
                   capture_output=True, text=True, encoding="utf-8")
if p.returncode:
    sys.exit(p.stderr)
got = json.loads(p.stdout)
worst, bad = 0.0, 0
for c, g in zip(cases, got):
    e = ce.estimate(c[0], c[1], c[2], c[3], c[4], c[5])
    d = max(abs(e["central_g"] - g[0]), abs(e["low_g"] - g[1]), abs(e["high_g"] - g[2]))
    worst = max(worst, d)
    if d > 0.6 or e["capped"] != g[3]:
        bad += 1
        if bad <= 5:
            print("MISMATCH", c, e["central_g"], e["low_g"], e["high_g"], g)
print(("COOK PARITY PASS" if not bad else "COOK PARITY FAIL") + f": {len(cases)} cases, worst difference {worst:.2f} g")
sys.exit(1 if bad else 0)
