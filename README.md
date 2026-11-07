# AI Code Review Agent

A GitHub-integrated reviewer that checks pull request diffs for concrete bugs, validates
structured findings, and posts inline comments. A React dashboard shows review history,
findings, and queued manual diff reviews. An evaluation harness measures results without
pretending that a correct line number proves a correct bug report.

**Status:** working portfolio MVP under active hardening. The six-case model pilot is
exploratory, not a general accuracy benchmark. Public hosting and current remote CI must
be verified separately. See [release status](docs/release-status.md).

## What it does

- Reviews changed lines using plain prompting, repository context, or context plus Ruff.
- Receives signed GitHub App webhooks, persists jobs before acknowledging, and processes
  them with Redis/RQ outside the HTTP request.
- Rechecks the PR head before publishing and uses review markers to reduce duplicates.
- Shows history, evidence, severity, and available diffs in a responsive dashboard.
- Accepts manual diffs without writing anything to GitHub; failed runs can be retried.
- Provides reproducible fixture checks and a separate human-adjudicated evaluation step.

It does not autonomously fix code, merge PRs, or guarantee bug detection. Repository
retrieval is a bounded filename heuristic, not semantic search or a caller graph.

## Quick start: local demo

Requires Docker with Compose. Copy `.env.example` to `.env`, generate a random token with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`, and set it as `DASHBOARD_TOKEN`.
Then:

```sh
docker compose up --build
```

Open **http://localhost:8000**, enter your token, select **New review → Load example → Run
review**. The review is queued and the page updates when it finishes. `REVIEW_MODE=demo`
uses a deterministic authorization fixture rule; the UI labels this output as demo data.
It is not an AI result and needs no model API key.

Compose starts the API/dashboard, dispatcher, RQ worker, PostgreSQL, and persistent Redis.
The API port is bound to localhost. PostgreSQL and Redis are not exposed to the host.
`/health` checks the HTTP process; `/ready` checks database and Redis connectivity.

## Use a real model

Set these in `.env`, then recreate the app services:

```dotenv
REVIEW_MODE=model
LLM_API_URL=https://api.groq.com/openai/v1/chat/completions
LLM_MODEL=openai/gpt-oss-20b
LLM_API_KEY=your-provider-key
```

```sh
docker compose up -d --force-recreate api worker dispatcher
```

An OpenAI-compatible Chat Completions endpoint is supported. Provider access, limits,
and charges are your responsibility. Configure both token prices for meaningful cost
estimates. Empty prices mean **unconfigured**, not free inference.

## Connect a GitHub App

1. Create an App with **Contents: read** and **Pull requests: read/write** permissions.
2. Subscribe to pull request events and install it on your test repository.
3. Host the API behind HTTPS; set the webhook URL to `/webhooks/github`.
4. Set `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, and `GITHUB_PRIVATE_KEY` in the server
   environment. PEM keys may use escaped newlines.
5. Open/update a PR, inspect the bot's inline comments, then inspect the same run in the
   dashboard. Set `REVIEW_APPROACH` to `plain`, `context`, or `tool`.

New App runs retain bounded diffs for dashboard inspection. Historical runs without saved
diffs link back to GitHub. The optional `Live AI review` Actions workflow runs independently
and does **not** populate the dashboard database. It uses trusted base-branch code and
never checks out submitted PR code.

## Development

```sh
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -e '.[dev]'
python -m ruff check .
python -m pytest -q
cd frontend
npm ci
npm run build
npx playwright install chromium --only-shell
npm run test:e2e
```

The browser test launcher uses a disposable SQLite database, in-memory fake Redis,
real RQ SimpleWorker/dispatcher, and demo mode. It makes no GitHub/model calls. Integration tests
exercise signed webhook → SQL outbox → queue → worker → mocked GitHub comment → dashboard.
Container CI separately checks real PostgreSQL and Redis when GitHub Actions can start.

For frontend hot reload use `npm run dev`. Run FastAPI at port 8000 with environment
variables exported; Vite proxies `/api` there. Local Python does not automatically read
`.env`. Start `python -m review_agent.jobs` and `rq worker reviews --with-scheduler`
against the same database/Redis for queued work.

## Evaluation

- `smoke.json` / `dev.json` / `heldout.json`: original tiny synthetic workflow fixtures.
  Their split names do not establish a defensible held-out experiment.
- `verified-dev.json`: 12 project-authored cases with executable behavior checks: eight
  injected defects and four clean controls. Regenerate with
  `python scripts/build_verified_dataset.py`. This is **development data**.
- `pilot.json`: four adapted BugsInPy defects and two synthetic clean controls.
  [Pilot report](docs/pilot-results.md) records the existing model results and limitations.

```sh
review-agent benchmark benchmark/datasets/verified-dev.json --approach plain > results.jsonl
python -m review_agent.evaluation benchmark/datasets/verified-dev.json results.jsonl judgments.json --template
# Inspect each finding and fill reviewer, verdict, rationale, and expected_index.
python -m review_agent.evaluation benchmark/datasets/verified-dev.json results.jsonl judgments.json
```

Repeat runs for each approach with a fixed model, prompt, dataset, and `APP_GIT_SHA`.
The numerical harness uses provisional location matching; the separate adjudicator
requires recorded human judgments and binds them to dataset/prediction hashes. Failed
cases are visible; the CLI exits nonzero for incomplete runs. Never report demo/oracle
output as model performance. See [evaluation protocol](docs/evaluation.md).

## Architecture and operations

See [architecture](docs/architecture.md), [deployment](docs/deployment.md),
[security](docs/security.md), and [demo guide](docs/demo.md).

The dashboard uses a shared token, not multi-user accounts. Tokens remain in browser memory.
Source code is stored in the database and sent to the configured model provider in model
mode. Use trusted repositories, HTTPS, and restricted network access. Keep keys out of git.

Tables are created additively; this release adds `manual_review_runs` and `review_outbox`
without changing existing columns. It does not provide a general schema migration engine.
Back up existing databases before upgrades. No cloud resources are provisioned automatically.
