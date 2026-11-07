"""Auditable human adjudication; a matching line alone never establishes a true positive."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_rows(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    cases = [row for row in rows if "case" in row]
    if len({row["case"] for row in cases}) != len(cases):
        raise ValueError("Use one run per adjudication file; duplicate case IDs found")
    return cases


def template(cases, rows):
    return {"dataset_sha256": digest(cases), "predictions_sha256": digest(rows),
            "reviewer": "", "judgments": [
                {"case": row["case"], "finding": i, "finding_sha256": digest(finding),
                 "expected_index": None, "verdict": "pending", "rationale": ""}
                for row in rows for i, finding in enumerate(row.get("findings", []))]}


def adjudicate(cases, rows, document):
    if document.get("dataset_sha256") != digest(cases) or document.get("predictions_sha256") != digest(rows):
        raise ValueError("Adjudication does not match the dataset and predictions")
    if not document.get("reviewer", "").strip():
        raise ValueError("A named reviewer is required")
    expected = {case["id"]: case["expected"] for case in cases}
    if len(expected) != len(cases) or {r["case"] for r in rows} != set(expected):
        raise ValueError("Require unique dataset IDs and exactly one result for every case")
    if len(rows) != len(expected):
        raise ValueError("Duplicate result cases")
    judgments = {}
    for item in document["judgments"]:
        key = (item["case"], item["finding"])
        if key in judgments:
            raise ValueError("Duplicate judgment")
        judgments[key] = item
    tp = fp = fn = failures = 0
    visited = set()
    for row in rows:
        targets = expected[row["case"]]
        matched = set()
        if "error" in row:
            failures += 1
            fn += len(targets)
            continue
        if not isinstance(row.get("findings"), list):
            raise ValueError("Successful rows must contain a findings array")
        fp += row.get("model", {}).get("rejected_findings", 0)
        for index, finding in enumerate(row.get("findings", [])):
            key = (row["case"], index)
            judgment = judgments.get(key)
            if not judgment or judgment.get("finding_sha256") != digest(finding):
                raise ValueError("Every finding needs a matching judgment")
            if judgment.get("verdict") not in {"correct", "incorrect"} or not judgment.get("rationale", "").strip():
                raise ValueError("Every finding needs a final verdict and evidence-based rationale")
            visited.add(key)
            if judgment["verdict"] == "incorrect":
                fp += 1
                continue
            target_index = judgment.get("expected_index")
            if type(target_index) is not int or target_index not in range(len(targets)):
                raise ValueError("Correct findings must identify a labeled defect")
            target = targets[target_index]
            if (finding["file_path"] != target["file_path"] or
                not target["line_start"] <= finding["line_start"] <= target.get("line_end", target["line_start"])):
                raise ValueError("Correct finding is outside its expected defect location")
            if target_index in matched:
                fp += 1  # duplicate explanation does not detect a second bug
            else:
                matched.add(target_index)
                tp += 1
        fn += len(targets) - len(matched)
    if visited != set(judgments):
        raise ValueError("Judgments contain unknown findings")
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"metric": "human_adjudicated", "reviewer": document["reviewer"], "cases": len(cases),
            "dataset_sha256": digest(cases), "predictions_sha256": digest(rows),
            "tp": tp, "fp": fp, "fn": fn, "failures": failures, "complete": failures == 0,
            "precision": precision, "recall": recall,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "false_positives_per_case": fp / len(cases) if cases else None,
            "failure_rate": failures / len(cases) if cases else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("judgments", type=Path)
    parser.add_argument("--template", action="store_true", help="Create a pending judgment file; refuse overwrite")
    args = parser.parse_args()
    cases = json.loads(args.dataset.read_text())
    rows = load_rows(args.predictions)
    if args.template:
        with args.judgments.open("x") as handle:
            json.dump(template(cases, rows), handle, indent=2)
    else:
        print(json.dumps(adjudicate(cases, rows, json.loads(args.judgments.read_text())), indent=2))


if __name__ == "__main__":
    main()
