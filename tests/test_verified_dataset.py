import copy
import importlib.util
import json
from pathlib import Path

import pytest

from review_agent.core import changed_lines

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verified_cases", ROOT / "tests/fixtures/verified_cases.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def behavior(source, args, name):
    # Only the fixed, project-authored fixtures above execute here, never incoming PRs/datasets.
    namespace = {}
    exec(compile(source, "<trusted-regression-fixture>", "exec"), namespace)
    values = copy.deepcopy(args)
    try:
        result = namespace["check"](*values)
        if name == "input_mutation" and values != args:
            return "input-mutated"
        if name == "clean_copy" and result is values[0]:
            return "aliased-input"
        return result
    except (KeyError, ZeroDivisionError) as exc:
        return type(exc).__name__


@pytest.mark.parametrize("case", module.CASES, ids=[row[0] for row in module.CASES])
def test_fixture_contracts(case):
    name, _, before, after, args, answer, category = case
    assert behavior(before, args, name) == answer
    if category:
        assert behavior(after, args, name) != answer
    else:
        assert behavior(after, args, name) == answer


def test_dataset_matches_verified_sources():
    spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts/build_verified_dataset.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    saved = json.loads((ROOT / "benchmark/datasets/verified-dev.json").read_text())
    assert saved == builder.build()
    for case in saved:
        for label in case["expected"]:
            assert label["line_start"] in changed_lines(case["diff"])[label["file_path"]]
