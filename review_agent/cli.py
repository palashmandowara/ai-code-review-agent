import argparse
import asyncio
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

from .core import review, score, validate_findings


async def case_diagnostics(case: dict) -> str:
    """Run Ruff on the reconstructed changed files, never on benchmark infrastructure."""
    reports = []
    for name, source in case.get("files", {}).items():
        if not name.endswith(".py"):
            continue
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "ruff", "check", "--output-format", "json", "--stdin-filename", name, "-",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, error = await asyncio.wait_for(proc.communicate(source.encode()), 15)
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"Ruff failed for {name}: {error.decode(errors='replace')[:300]}")
        reports.append({"file": name, "findings": json.loads(output)})
    return json.dumps(reports)[:4000]


async def benchmark(path: Path, approach: str, predictions_path: Path | None = None):
    dataset_bytes = path.read_bytes()
    cases = json.loads(dataset_bytes)
    predictions = None
    saved_rejected = {}
    if predictions_path:
        source = predictions_path.read_text()
        try:
            predictions = json.loads(source)
            if isinstance(predictions, dict) and "case" in predictions and "findings" in predictions:
                row = predictions
                predictions = {row["case"]: row["findings"]}
                saved_rejected = {row["case"]: row.get("model", {}).get("rejected_findings", 0)}
        except json.JSONDecodeError:
            rows = [json.loads(line) for line in source.splitlines() if line.strip()]
            predictions = {row["case"]: row["findings"] for row in rows if "case" in row and "findings" in row}
            saved_rejected = {row["case"]: row.get("model", {}).get("rejected_findings", 0)
                              for row in rows if "case" in row and "findings" in row}
    totals = {"tp": 0, "fp": 0, "fn": 0, "category_matches": 0}
    durations = []
    failures = []
    costs = []
    models = set()
    for case in cases:
        start = time.monotonic()
        try:
            metadata = {}
            if predictions is None:
                context = case.get("context", "") if approach != "plain" else ""
                diagnostics = await case_diagnostics(case) if approach == "tool" else ""
                findings = await review(case["diff"], approach, context=context,
                                        diagnostics=diagnostics, metadata=metadata)
                costs.append(metadata.get("estimated_usd", 0))
                if metadata.get("model"):
                    models.add(metadata["model"])
            else:
                if case["id"] not in predictions:
                    raise ValueError("Saved predictions missing this case")
                findings = validate_findings(predictions.get(case["id"], []), case["diff"], metadata)
                metadata["rejected_findings"] += saved_rejected.get(case["id"], 0)
            metrics = score(findings, case["expected"], metadata.get("rejected_findings", 0))
            for key in totals:
                totals[key] += metrics[key]
            print(json.dumps({"case": case["id"], "metrics": metrics, "model": metadata,
                              "findings": [f.model_dump() for f in findings],
                              "seconds": time.monotonic() - start}))
        except Exception as exc:
            failures.append({"case": case["id"], "error": str(exc)})
            print(json.dumps({"case": case["id"], "error": str(exc)}))
            continue
        durations.append(time.monotonic() - start)
    tp, fp, fn = (totals[key] for key in ("tp", "fp", "fn"))
    complete = not failures
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    print(json.dumps({"approach": approach, "cases": len(cases), **totals,
        "scored_cases": len(cases) - len(failures), "complete": complete,
        "precision": precision if complete else None, "recall": recall if complete else None,
        "f1": (2 * precision * recall / (precision + recall) if precision + recall else 0) if complete else None,
        "false_positives_per_case": fp / len(cases) if complete and cases else None,
        "median_seconds": statistics.median(durations) if durations and predictions is None else None,
        "p95_seconds": (sorted(durations)[min(len(durations) - 1, int(len(durations) * .95))]
                        if durations and predictions is None else None),
        "estimated_total_usd": round(sum(costs), 6) if predictions is None else None,
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "dataset_canonical_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest(),
        "review_mode": os.getenv("REVIEW_MODE", "model") if predictions is None else "replay",
        "metric": "provisional_location_match_requires_semantic_review",
        "models": sorted(models),
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
