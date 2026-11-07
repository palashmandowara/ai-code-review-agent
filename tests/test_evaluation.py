import pytest

from review_agent.evaluation import adjudicate, template

CASES = [{"id": "auth", "expected": [{"file_path": "a.py", "line_start": 2, "category": "security"}]}]
FINDING = {"file_path": "a.py", "line_start": 2, "explanation": "Unrelated style advice"}


def document(rows, verdict="incorrect"):
    value = template(CASES, rows)
    value["reviewer"] = "test reviewer"
    for item in value["judgments"]:
        item.update(verdict=verdict, rationale="Checked against the fixture contract", expected_index=0)
    return value


def test_same_line_wrong_explanation_is_not_a_true_positive():
    rows = [{"case": "auth", "findings": [FINDING]}]
    result = adjudicate(CASES, rows, document(rows))
    assert (result["tp"], result["fp"], result["fn"]) == (0, 1, 1)


def test_duplicate_correct_findings_count_once():
    rows = [{"case": "auth", "findings": [FINDING, FINDING]}]
    result = adjudicate(CASES, rows, document(rows, "correct"))
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 0)


def test_pending_or_changed_predictions_cannot_be_scored():
    rows = [{"case": "auth", "findings": [FINDING]}]
    with pytest.raises(ValueError):
        adjudicate(CASES, rows, document(rows, "pending"))
    with pytest.raises(ValueError):
        adjudicate(CASES, [{"case": "auth", "findings": []}], document(rows))


def test_failed_case_counts_as_missed_bug():
    rows = [{"case": "auth", "error": "timeout"}]
    result = adjudicate(CASES, rows, document(rows))
    assert result["fn"] == 1 and result["failure_rate"] == 1 and result["complete"] is False
