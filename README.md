# AI Code Review Agent

GitHub App webhook service that reviews changed lines, validates structured findings, and posts inline comments. Includes a CLI benchmark for comparing three review configurations.

## Local setup

1. Use Python 3.11+; run `pip install -e '.[dev]'`.
2. Copy `.env.example` to `.env` and set the values. Never commit `.env`.
3. Run `pytest -q` and `ruff check .`.
4. Review a diff with `review-agent review change.diff --approach plain`.
5. Run the example benchmark with `review-agent benchmark benchmark/datasets/smoke.json --approach plain`.

Model requests use `LLM_API_URL` (OpenAI-compatible chat completions), `LLM_MODEL`, and `LLM_API_KEY`. Set `INPUT_USD_PER_MILLION` and `OUTPUT_USD_PER_MILLION` to the provider's current token prices for cost estimates; the defaults of zero mean cost is unconfigured.

For a no-cost end-to-end test, set `REVIEW_MODE=demo` in `.env` and restart the API and worker. The demo reviewer has one deterministic fixture rule: it flags `return True` inside a changed `can_delete` function. It is not an AI model and its results must never be presented as model performance. Leave `LLM_API_KEY` blank in demo mode.

## GitHub App

Create a GitHub App with Pull requests read/write and Contents read permissions. Subscribe to pull request events. Configure its webhook URL as `https://YOUR_HOST/webhooks/github`, set `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_ID`, and the PEM key in `GITHUB_PRIVATE_KEY` (escaped newlines supported). Install on a test repository. Run `docker compose up --build` behind HTTPS. The API verifies signatures, queues valid pull request events, and the worker checks the head SHA before publishing comments.

The diff, source files, and comments are untrusted data. No PR code is executed by the app. For `context` and `tool`, the worker fetches up to 12 changed source files and six related files, including tests with matching names, pinned to the head SHA. `tool` also parses changed Python files with Ruff via stdin; this is static analysis, not execution. Related-file retrieval is a simple filename heuristic, not a full caller graph.

## Benchmark

Dataset JSON items contain `id`, `diff`, and `expected` findings with `file_path`, `line_start`, and `category`. Matching is one-to-one using file, expected line range, and category. Run each approach against the same versioned dataset. The included 12 synthetic cases are smoke fixtures, split into `dev.json` and `heldout.json`; they are not a defensible final benchmark. Build a larger independently verified set with public bug provenance and negative controls before publishing performance claims. The CLI prints case results and aggregate precision, recall, F1, median/p95 latency, configured token-cost estimates, and failures. The model identifier and token usage appear per case.

Check the evaluation code offline with `review-agent benchmark benchmark/datasets/dev.json --predictions benchmark/datasets/oracle_predictions.json`. The oracle file is a scoring test, never a measured model result. For real experiments, run each approach on `dev.json`, freeze prompts and matching rules, then run each on `heldout.json`. Save full terminal output and configuration for reproducibility.

A six-case sourced pilot is in `benchmark/datasets/pilot.json`: four adapted regressions from documented BugsInPy fixes and two synthetic clean controls. It is a workflow demonstration, not a held-out performance benchmark. See [`docs/evaluation.md`](docs/evaluation.md) for provenance, limitations, and Windows commands to run all three approaches with a configured model.

The first Groq pilot results, including the rejected-location case and interpretation limits, are in [`docs/pilot-results.md`](docs/pilot-results.md).

## Deployment

### Free hosted review on this repository

The `Live AI review` GitHub Actions workflow runs the existing `plain` reviewer on owner/collaborator pull requests. It needs no always-on machine, Redis, database, Smee tunnel, or GitHub App private key. In this repository, create an Actions repository secret named `GROQ_API_KEY` containing your Groq API key (Settings → Secrets and variables → Actions → New repository secret). The workflow provides its own short-lived `GITHUB_TOKEN` and posts a review to each new PR commit. It reads PR diffs through GitHub's API and installs code from the trusted default branch; it never checks out or runs submitted PR code. A large diff (>30,000 characters) is skipped. Review the Actions log for errors or skipped PRs. The workflow is intentionally restricted to owner, member, or collaborator PRs to limit free-tier usage. Never commit API keys or paste them into issue/PR text.

GitHub-hosted standard runners are free for public repositories; private repositories have included free minutes subject to the account's quota. Groq's free plan has rate limits. A GitHub Actions run is the hosted review deployment, not a continuously running HTTP endpoint. The original GitHub App integration still runs with Docker Compose locally; it is not hosted by this workflow.

Docker Compose supplies PostgreSQL and Redis for local development. Hosting that webhook service continuously requires a VM or managed database/queue, HTTPS reverse proxy, secret management, backups, and monitoring. No AWS resources are provisioned by this repository.

See [`docs/evaluation.md`](docs/evaluation.md) for the experiment protocol and [`docs/security.md`](docs/security.md) for operational limits. This repository creates tables on first startup and does not yet include migrations; for an existing development database created by an earlier version, back it up and recreate it before running the new schema.


## Review dashboard

The React + TypeScript dashboard is served by FastAPI at `/` after the frontend is built.
It includes searchable review history (latest 100), findings with evidence, manual diff reviews,
and a clearly labeled view of the published six-case pilot. GitHub history reads the same
review/finding tables as the worker. The GitHub Actions-only reviewer does not write to this database.

### Run with Docker

Set a long random `DASHBOARD_TOKEN` in `.env` (for example, generate one with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`), then run:

```sh
docker compose up --build
```

Open `http://localhost:8000` and enter that token. The UI keeps it in memory only.
Use HTTPS when hosting beyond localhost. Dashboard endpoints are disabled if the token is missing;
this is a single-workspace shared-token dashboard, not a multi-user authentication system.

### Frontend development

```sh
cd frontend
npm ci
npm run dev
```

Run `uvicorn review_agent.api:app --reload` separately at port 8000 with
`DASHBOARD_TOKEN`, `DATABASE_URL`, and model variables exported in its environment.
Vite proxies `/api` to port 8000. For a single-server build, run `npm run build` in
`frontend`, then start/restart FastAPI. Python package data includes the generated assets.
Docker builds the frontend automatically; generated bundles and node_modules are not committed.

Manual reviews accept unified diffs up to 30,000 characters with optional supplied context
(up to 12,000 characters). They call the configured model provider, persist the diff and findings
in a new `manual_review_runs` table, and **never post to GitHub**. Tool-assisted manual reviews
are intentionally unavailable without source files; use the existing GitHub App or benchmark CLI.
Requests run synchronously with the existing provider timeout; keep the page open until completion.
A process crash can leave a manual run marked running. This version does not include recovery or deletion UI.
Existing GitHub runs do not store a diff, so their detail screen links back to the PR.
Set `REVIEW_MODE=demo` for the deterministic authorization fixture; the UI explicitly labels demo output.
Pilot cards are a static transcription of `docs/pilot-results.md`, not live benchmark execution.

Dashboard API (all require `Authorization: Bearer <DASHBOARD_TOKEN>`):

- `GET /api/dashboard/runs`: latest review summaries.
- `GET /api/dashboard/runs/{github-N|manual-N}`: findings and available diff.
- `POST /api/dashboard/reviews`: `{title, diff, approach: "plain" | "context", context}`.
