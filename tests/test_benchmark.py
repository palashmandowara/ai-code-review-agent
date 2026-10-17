import asyncio
import json
from pathlib import Path

from review_agent.cli import benchmark


def test_oracle_replay(capsys):
    root = Path(__file__).resolve().parents[1] / "benchmark" / "datasets"
    asyncio.run(benchmark(root / "dev.json", "plain", root / "oracle_predictions.json"))
    result = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result["cases"] == 8
    assert result["f1"] == 1
    assert result["failures"] == []
    assert result["estimated_total_usd"] is None
