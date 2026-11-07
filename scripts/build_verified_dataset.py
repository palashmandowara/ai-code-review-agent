"""Build development fixtures from checked-in test definitions. No model calls."""
import difflib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    spec = importlib.util.spec_from_file_location("verified_cases", ROOT / "tests/fixtures/verified_cases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cases = []
    for name, contract, before, after, args, answer, category in module.CASES:
        path = f"{name}.py"
        diff = f"diff --git a/{path} b/{path}\n" + "".join(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True), fromfile=f"a/{path}", tofile=f"b/{path}"))
        # Line 2 is the changed defective expression in every positive fixture.
        cases.append({"id": name, "source": "project-authored synthetic development fixture",
                      "split": "development", "verification": "tests/test_verified_dataset.py",
                      "diff": diff, "files": {path: after}, "context": contract,
                      "expected": [{"file_path": path, "line_start": 2, "category": category,
                                    "rationale": contract}] if category else []})
    return cases


if __name__ == "__main__":
    target = ROOT / "benchmark/datasets/verified-dev.json"
    target.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"Wrote {len(build())} verified development cases to {target}")
