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

## Deployment

Docker Compose supplies PostgreSQL and Redis for local development. Production needs managed database/queue, HTTPS reverse proxy, secret management, backups, and monitoring. No AWS resources are provisioned by this repository.

See [`docs/evaluation.md`](docs/evaluation.md) for the experiment protocol and [`docs/security.md`](docs/security.md) for operational limits. This repository creates tables on first startup and does not yet include migrations; for an existing development database created by an earlier version, back it up and recreate it before running the new schema.
