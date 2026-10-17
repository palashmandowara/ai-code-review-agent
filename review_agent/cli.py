import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from .core import review, score, validate_findings


async def benchmark(path: Path, approach: str, predictions_path: Path | None = None):
    cases = json.loads(path.read_text())
    predictions = json.loads(predictions_path.read_text()) if predictions_path else None
    totals = {"tp": 0, "fp": 0, "fn": 0}
    durations = []
    failures = []
    costs = []
    for case in cases:
        start = time.monotonic()
        try:
            metadata = {}
            if predictions is None:
                findings = await review(case["diff"], approach, path.parent, metadata=metadata)
                costs.append(metadata.get("estimated_usd", 0))
            else:
                findings = validate_findings(predictions.get(case["id"], []), case["diff"], metadata)
            metrics = score(findings, case["expected"], metadata.get("rejected_findings", 0))
            for key in totals:
                totals[key] += metrics[key]
            print(json.dumps({"case": case["id"], "metrics": metrics, "model": metadata,
                              "findings": [f.model_dump() for f in findings]}))
        except Exception as exc:
            failures.append({"case": case["id"], "error": str(exc)})
        durations.append(time.monotonic() - start)
    tp, fp, fn = (totals[key] for key in ("tp", "fp", "fn"))
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    print(json.dumps({"approach": approach, "cases": len(cases), **totals,
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0,
        "median_seconds": statistics.median(durations),
        "p95_seconds": sorted(durations)[min(len(durations) - 1, int(len(durations) * .95))],
        "estimated_total_usd": round(sum(costs), 6) if predictions is None else None,
        "failures": failures}))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("review")
    one.add_argument("diff", type=Path)
    one.add_argument("--approach", choices=["plain", "context", "tool"], default="plain")
    one.add_argument("--root", type=Path)
    bench = sub.add_parser("benchmark")
    bench.add_argument("dataset", type=Path)
    bench.add_argument("--approach", choices=["plain", "context", "tool"], default="plain")
    bench.add_argument("--predictions", type=Path, help="Replay saved predictions without model calls")
    args = parser.parse_args()
    if args.command == "review":
        findings = asyncio.run(review(args.diff.read_text(), args.approach, args.root))
        print(json.dumps([f.model_dump() for f in findings], indent=2))
    else:
        asyncio.run(benchmark(args.dataset, args.approach, args.predictions))


if __name__ == "__main__":
    main()
