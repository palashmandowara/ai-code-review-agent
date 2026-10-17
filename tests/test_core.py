from pathlib import Path

from review_agent.core import Finding, changed_lines, safe_context, score, validate_findings

DIFF = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,3 @@\n a=1\n+b=2\n c=3\n"


def finding(line=2):
    return {"file_path": "a.py", "line_start": line, "line_end": line,
            "title": "Bug", "severity": "medium", "category": "correctness",
            "explanation": "Explanation", "evidence": "Evidence"}


def test_changed_line_validation():
    assert changed_lines(DIFF) == {"a.py": {2}}
    assert len(validate_findings([finding(), finding(), finding(1)], DIFF)) == 1


def test_invalid_location_counts_as_false_positive():
    metadata = {}
    accepted = validate_findings([finding(1)], DIFF, metadata)
    assert score(accepted, [], metadata["rejected_findings"])["fp"] == 1


def test_score_positive_and_negative():
    predicted = [Finding.model_validate(finding())]
    assert score(predicted, [dict(file_path="a.py", line_start=2, category="correctness")])["f1"] == 1
    assert score([], [dict(file_path="a.py", line_start=2, category="correctness")])["fn"] == 1
    assert score([], [])["fp"] == 0


def test_context_cannot_escape_checkout(tmp_path: Path):
    (tmp_path / "safe.py").write_text("pass")
    assert "pass" in safe_context(tmp_path, DIFF.replace("a.py", "safe.py"))
    assert safe_context(tmp_path, DIFF.replace("a.py", "../outside.py")) == ""
