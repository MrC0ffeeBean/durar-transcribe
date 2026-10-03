"""Guard: final\\bNN.md must validate AND equal keyer A + the logged decisions exactly (no silent rewrites).

Usage: python check_final.py b17 [--json]      exit 0 = PASS
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply import ApplyError, build_final
from common import ROOT, canonical, read_text
from validate import validate


def check(k):
    name = f"b{k:02d}"
    path = ROOT / "final" / f"{name}.md"
    res = {"batch": name, "pass": False, "problems": []}
    if not path.exists():
        res["problems"].append("final file missing")
        return res
    errs, warns = validate(path)
    res["errors"], res["warnings"] = errs, len(warns)
    if errs:
        res["problems"].append(f"{len(errs)} validation error(s): {errs[:3]}")
    try:
        expected, info, D = build_final(k)
    except ApplyError as e:
        res["problems"].append(f"cannot rebuild from decisions: {e}")
        return res
    actual = canonical(read_text(path))
    if actual != expected:
        a, b = actual.splitlines(), expected.splitlines()
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                res["problems"].append(f"final differs from A+decisions at line {i + 1}: {x[:60]!r} vs {y[:60]!r}")
                break
        else:
            res["problems"].append("final differs from A+decisions (length)")
    if not (ROOT / "reports" / f"{name}.json").exists():
        res["problems"].append("report missing")
    res["agreement"] = D["agreement"]
    res["n_decisions"] = len(info["decisions"])
    res["n_extra_edits"] = len(info["extra_edits"])
    res["pass"] = not res["problems"]
    return res


def main():
    k = int(sys.argv[1].lstrip("b"))
    res = check(k)
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(("PASS " if res["pass"] else "FAIL ") + res["batch"], *res["problems"], sep="\n  ")
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
