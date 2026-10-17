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


def test_replay_jsonl_preserves_rejected_findings(tmp_path, capsys):
    dataset = tmp_path / "cases.json"
    dataset.write_text(json.dumps([{"id": "one", "diff": "diff --git a/a.py b/a.py\n+++ b/a.py\n@@ -0,0 +1 @@\n+bad\n",
                                    "expected": [{"file_path": "a.py", "line_start": 1, "category": "correctness"}]}]))
    replay = tmp_path / "saved.jsonl"
    replay.write_text(json.dumps({"case": "one", "findings": [{"file_path": "a.py", "line_start": 1,
        "line_end": 1, "title": "Defect", "severity": "high", "category": "API misuse",
        "explanation": "wrong", "evidence": "bad"}], "model": {"rejected_findings": 1}}) + "\n")
    asyncio.run(benchmark(dataset, "plain", replay))
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 0)
    assert result["category_matches"] == 0
    assert result["complete"] is True
