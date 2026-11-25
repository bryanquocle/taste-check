"""Tests for hfp_formulate.py (Stage 3): compare and solve.

  python tests/formulate_test.py        (about a minute)

Pass conditions from the rebuild plan: compare says "no real difference" when there is none and calls a
clear difference; solve lands within 0.2 score points of the target on a re-run (it is held to 0.02 here).
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hfp_model as m  # noqa: E402
import hfp_formulate as hf  # noqa: E402

db = m.load_db()
problems = []


def R(*items):
    return [{"ingredient": n, "amount": a, "unit": "g"} for n, a in items]


def check(label, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + label + ("" if ok else "  " + detail))
    if not ok:
        problems.append(label)


def rerun(recipe, taste, opt=None):
    return hf._scores(recipe, db, opt or {})[taste]


A = R(("Salt", 8), ("Water", 1000))
B = R(("Salt", 6), ("Water", 1000))
TOM = R(("Tomato (Canned)", 200), ("Water", 100))
STEW = R(("Beef", 1000), ("Ginger", 40), ("Garlic", 20), ("Onion", 350), ("Paste, Tomato", 66), ("Butter, Salted", 35),
         ("Wine, Generic", 60), ("Carrot", 250), ("Broth, Beef", 946), ("Sauce, Fish", 58), ("Water", 318), ("Sugar", 37))
STEW_OPT = {"water_loss_g": 300, "cook_min": 120, "cook_temp_c": 95}

# ---- compare ----
c = hf.compare(TOM, TOM, n=30, db=db)
check("compare: a recipe against itself is 'no real difference' on every taste",
      all(v is None or (v["verdict"] == "same" and v["diff"] == 0) for v in c.values()), repr(c))
c = hf.compare(A, B, n=30, db=db)
check("compare: 6 g/L salt is called lower in saltiness than 8 g/L",
      c["saltiness"]["verdict"] == "lower" and -0.9 < c["saltiness"]["diff"] < -0.5, repr(c["saltiness"]))
check("compare: tastes neither recipe has are not called different",
      all(c[t]["verdict"] == "same" for t in ("umami", "sweetness", "kokumi", "sourness")))
tiny = hf.compare(A, R(("Salt", 8.1), ("Water", 1000)), n=30, db=db)
check("compare: a 1% salt change is 'no real difference' (under the 0.25 floor)",
      tiny["saltiness"]["verdict"] == "same", repr(tiny["saltiness"]))
c2 = hf.compare(B, A, n=30, db=db)
check("compare: swapping A and B flips the sign", abs(c2["saltiness"]["diff"] + c["saltiness"]["diff"]) < 1e-12)

# ---- solve ----
target = rerun(A, "saltiness")
s = hf.solve(R(("Water", 1000)), "Salt", "saltiness", target, db=db)
check("solve: salt for the saltiness of 8 g/L comes back as 8 g",
      s["status"] == "solved" and abs(s["grams"] - 8.0) < 0.02, "%s %.4f" % (s["status"], s["grams"]))
check("solve: the re-run lands on the target (plan allows 0.2; held to 0.02)",
      abs(rerun(s["recipe"], "saltiness") - target) < 0.02)
s = hf.solve(TOM, "Salt", "saltiness", 7.0, db=db)
check("solve: salt in diluted canned tomato reaches saltiness 7.0",
      s["status"] == "solved" and abs(rerun(s["recipe"], "saltiness") - 7.0) < 0.02, "%s %.3f g" % (s["status"], s["grams"]))
s = hf.solve(R(("Water", 1000)), "Salt", "umami", 9.0, db=db)
check("solve: salt cannot move umami in plain water ('no_effect')", s["status"] == "no_effect", s["status"])
s = hf.solve(R(("Water", 1000)), "Sugar", "sweetness", 10.0, db=db, max_grams=10)
check("solve: an unreachable target is reported, not faked ('too_low' at the maximum)",
      s["status"] == "too_low" and s["grams"] == 10, "%s %r" % (s["status"], s["grams"]))
s = hf.solve(A, "Salt", "saltiness", 0.5, db=db)
check("solve: a target below what zero gives is reported ('too_high' at zero)",
      s["status"] == "too_high" and s["grams"] == 0, "%s %r" % (s["status"], s["grams"]))
no_fs = [it for it in STEW if it["ingredient"] != "Sauce, Fish"]
target = rerun(STEW, "saltiness", STEW_OPT)
s = hf.solve(no_fs, "Salt", "saltiness", target, STEW_OPT, db=db)
check("solve: salt replaces the fish sauce's saltiness in the stew (re-run within 0.02)",
      s["status"] == "solved" and abs(rerun(s["recipe"], "saltiness", STEW_OPT) - target) < 0.02,
      "%s %.2f g" % (s["status"], s["grams"]))
print("        stew: %.1f g salt stands in for 58 g fish sauce; umami %.2f -> %.2f"
      % (s["grams"], rerun(STEW, "umami", STEW_OPT), s["after"]["umami"]))

print("\n" + ("FORMULATE TEST PASS" if not problems else "FORMULATE TEST FAIL: %d" % len(problems)))
sys.exit(1 if problems else 0)
