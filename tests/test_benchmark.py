import asyncio
import json
from pathlib import Path

from review_agent.cli import benchmark, case_diagnostics


def test_oracle_replay(capsys):
    root = Path(__file__).resolve().parents[1] / "benchmark" / "datasets"
    asyncio.run(benchmark(root / "dev.json", "plain", root / "oracle_predictions.json"))
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["cases"] == 8
    assert result["f1"] == 1
    assert result["failures"] == []
    assert result["estimated_total_usd"] is None


def test_failure_does_not_publish_partial_score(tmp_path, capsys, monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("review_agent.cli.review", fail)
    dataset = tmp_path / "broken.json"
    dataset.write_text(json.dumps([{"id": "broken", "diff": "", "expected": []}]))
    asyncio.run(benchmark(dataset, "plain"))
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["complete"] is False
    assert result["scored_cases"] == 0
    assert result["f1"] is None
    assert result["failures"][0]["case"] == "broken"


def test_tool_diagnostics_use_case_source():
    result = asyncio.run(case_diagnostics({"files": {"example.py": "def f():\n    return missing\n"}}))
    findings = json.loads(result)[0]["findings"]
    assert any(item["code"] == "F821" for item in findings)
