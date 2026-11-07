# Release status — 7 November 2026

This is an evidence ledger, not a production-readiness claim.

| Area | Evidence | Status |
| --- | --- | --- |
| Backend | Ruff and 55 pytest tests pass locally | Verified locally |
| Browser | Login rejection, queued demo review/history, mobile layout | 3 checks pass locally |
| Frontend | TypeScript + Vite production build | Pass |
| Queue | SQL outbox recovery, deduplication, RQ worker, retry behavior | Covered by tests |
| GitHub integration | Existing bot comments on test repository PR #1 | Historical live evidence |
| New complete workflow | Signed webhook → outbox → worker → comment → dashboard | Integration test uses mocked GitHub |
| Fixtures | 8 injected defects + 4 clean controls with executable checks | Development cases, not held-out |
| Evaluation | Hash-bound, human-adjudicated semantic scoring | Implemented and tested |
| Model experiment | Existing six-case pilot only | No new model results claimed |
| Docker | Compose health gates, init, persistent volumes, non-root image, CI smoke job | Engine unavailable locally; remote verification required |
| Remote CI | Latest checked branch run `42368390146` failed at startup with no jobs; GitHub rejected retry with HTTP 403 | Diagnostic unavailable through connector; remote CI remains blocked |
| Deployment | Local/private-server instructions and recovery guide | No public host provisioned |
| Visibility | Repositories remain private | Owner decision and secret/history audit needed before publication |

Local model credentials and GitHub App private-key configuration were unavailable during
this work. No secret was extracted from GitHub Actions. Therefore a new live model/GitHub
run and a held-out comparison could not honestly be performed in this environment.

## Remaining release gates

1. Resolve the GitHub Actions startup diagnostic and get backend/browser/container jobs green.
2. Configure the App and model on the intended host; demonstrate a fresh PR through to the dashboard.
3. Review and merge the PR after those checks, then record a short demo.
4. Decide whether to publish sanitized code or provide a private demo. Do not change visibility blindly.
5. For accuracy claims, freeze an independent test set, run repeated model experiments, retain raw
   outputs, and complete human adjudication. More synthetic development data is not a substitute.
