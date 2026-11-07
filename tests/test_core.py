from pathlib import Path

from review_agent.core import Finding, changed_lines, response_format_for, safe_context, score, validate_findings

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
    assert metadata["rejected_details"][0]["reason"] == "start_not_added_line"


def test_groq_strict_schema_and_generic_fallback():
    strict = response_format_for("https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-20b")
    schema = strict["json_schema"]["schema"]
    assert strict["json_schema"]["strict"] is True
    assert schema["required"] == ["findings"]
    assert schema["properties"]["findings"]["items"]["additionalProperties"] is False
    assert response_format_for("https://example.com/v1/chat/completions", "other") == {"type": "json_object"}


def test_score_positive_and_negative():
    predicted = [Finding.model_validate(finding())]
    assert score(predicted, [dict(file_path="a.py", line_start=2, category="correctness")])["f1"] == 1
    assert score([], [dict(file_path="a.py", line_start=2, category="correctness")])["fn"] == 1
    assert score([], [])["fp"] == 0


def test_context_cannot_escape_checkout(tmp_path: Path):
    (tmp_path / "safe.py").write_text("pass")
    assert "pass" in safe_context(tmp_path, DIFF.replace("a.py", "safe.py"))
    assert safe_context(tmp_path, DIFF.replace("a.py", "../outside.py")) == ""



def test_added_content_that_looks_like_a_file_header():
    diff = 'diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,2 @@\n+++ counter\n+next\n'
    assert changed_lines(diff) == {"a.py": {1, 2}}


def test_multiple_hunks_and_deleted_file():
    diff = ('diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n'
            '@@ -1 +1 @@\n-old\n+new\n@@ -9 +9 @@\n-old\n+new\n'
            'diff --git a/b.py b/b.py\n--- a/b.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n')
    assert changed_lines(diff) == {"a.py": {1, 9}}
