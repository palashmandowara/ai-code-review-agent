# Release status — 7 November 2026

This is an evidence ledger, not a production-readiness claim.

## Windows Compose acceptance update

On 7 November 2026, the ZIP checkout was run locally with Docker Desktop. Compose
built and became ready; an authenticated manual demo was queued, completed with the
authorization finding, and remained in history after restarting API, worker, and
dispatcher. A wrong dashboard token returned HTTP 401. This was deterministic demo
output, not a model review. The frontend build, Ruff, and 55 backend tests passed in
containers. The backend test run emitted a Starlette TestClient deprecation warning.

A real-model retry completed using `openai/gpt-oss-20b`, returning one finding about
the unconditional authorization check in the same small diff. It recorded 478 input
and 304 output tokens; pricing was not configured. This is one observed review, not
an accuracy measurement. Three Playwright checks passed using installed Chrome after
the bundled Chromium installer stalled. A fresh GitHub App test on private test repository
PR #2 completed with a real-model inline authorization finding and a matching completed
dashboard record. The PR remains an unmerged draft. The temporary HTTPS tunnel was closed
after the test.

The owner reported an account billing issue preventing GitHub Actions jobs from starting.
This remains unresolved; no billing settings were changed and remote CI is not green.

| Area | Evidence | Status |
| --- | --- | --- |
| Backend | Ruff and 55 pytest tests pass locally | Verified locally |
| Browser | Login rejection, queued demo review/history, mobile layout | 3 checks pass locally |
| Frontend | TypeScript + Vite production build | Pass |
| Queue | SQL outbox recovery, deduplication, RQ worker, retry behavior | Covered by tests |
| GitHub integration | Existing bot comments on test repository PR #1 | Historical live evidence |
| New complete workflow | Private test PR #2: GitHub webhook → queue → model → inline comment and matching dashboard record | Verified locally through temporary HTTPS tunnel |
| Fixtures | 8 injected defects + 4 clean controls with executable checks | Development cases, not held-out |
| Evaluation | Hash-bound, human-adjudicated semantic scoring | Implemented and tested |
| Model experiment | Existing six-case pilot; one additional local model review | Exploratory; no new accuracy claim |
| Docker | Compose built, readiness and demo review verified; history survived service restart | Verified locally; remote verification required |
| Remote CI | Run `42368390146` created no jobs; owner reported an account billing issue | Blocked by account billing; not verified green |
| Deployment | Local/private-server instructions and recovery guide | No public host provisioned |
| Visibility | Project repository is public; test repository is private | Continue to keep test data and credentials private |

The live App test used a temporary tunnel and local services, not a persistent deployment.
No secret was extracted from GitHub Actions. A held-out model comparison has not been performed.

## Remaining release gates

1. Resolve the account billing blocker separately and get backend/browser/container jobs green.
2. Configure the App and model on any intended persistent host and repeat the live check there.
3. Review and merge the PR after those checks, then record a short demo.
4. Review public documentation and recorded demo material for sensitive information.
5. For accuracy claims, freeze an independent test set, run repeated model experiments, retain raw
   outputs, and complete human adjudication. More synthetic development data is not a substitute.
