import asyncio

from review_agent.core import review


def test_offline_demo_reports_only_known_fixture(monkeypatch):
    monkeypatch.setenv("REVIEW_MODE", "demo")
    diff = ("diff --git a/access.py b/access.py\n--- a/access.py\n+++ b/access.py\n"
            "@@ -1,2 +1,2 @@\n def can_delete(actor, owner):\n"
            "-    return actor.id == owner.id\n+    return True\n")
    metadata = {}
    findings = asyncio.run(review(diff, metadata=metadata))
    assert len(findings) == 1
    assert findings[0].line_start == 2
    assert metadata["model"] == "offline-demo-rule"
    assert asyncio.run(review(diff.replace("can_delete", "can_view"))) == []
