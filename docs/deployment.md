# Deployment and recovery

## Local acceptance checklist

1. Copy `.env.example` to `.env`, set a random `DASHBOARD_TOKEN`, and keep demo mode.
2. `docker compose config --quiet`
3. `docker compose up --build -d --wait`
4. Visit `/ready`, sign in, and submit the example diff.
5. Verify the review moves from queued to completed and has one demo finding.
6. `docker compose restart api worker dispatcher` and verify the history remains.
7. Inspect `docker compose logs --tail=100 api worker dispatcher` for failures.

## Private server deployment

Use a server you control with Docker Compose. Keep the API bound to loopback as supplied;
terminate HTTPS at a reverse proxy forwarding to `127.0.0.1:8000`. Expose only the HTTPS
port and necessary administration access. Never expose Redis/PostgreSQL ports. Supply
secrets through your host's secret mechanism. Configure the GitHub App webhook to the HTTPS
URL. Confirm readiness, a manual model review, then a fresh GitHub test PR.

This repository does not create a paid host, domain, managed database, or TLS certificate.
Choose those separately. Shared-token access is appropriate for a private single-owner
portfolio demo, not a multi-tenant public service. Do not post the access token publicly.

## Database backup

```sh
docker compose exec -T db pg_dump -U review review > review-backup.sql
```

Store backups privately because they contain source code. Restore into a separate database
first and verify before replacing any active database. Do not use `docker compose down -v`
on a deployment you want to keep; that removes persistent volumes.

## Troubleshooting

- **Queued for a long time:** check dispatcher/worker and Redis readiness. The SQL outbox
  retains undelivered work during queue outages.
- **Failed:** check worker logs and model/GitHub configuration. Fix the cause, then retry
  from the dashboard. Retries can cause additional model usage.
- **Skipped:** split a diff exceeding 30,000 characters into smaller PRs.
- **Stale:** the PR changed or closed before publication; open/update it to trigger a new run.
- **No dashboard record from Actions:** the standalone Actions reviewer has no connection
  to the App database. Use the GitHub App path for a unified dashboard demo.
- **GitHub CI startup_failure with no jobs:** inspect the run page's workflow annotations
  and account/repository Actions settings. Do not interpret this as a failing pytest run.
  For run `42368390146`, the owner reported an account billing issue. Billing remains
  an owner-controlled blocker.

## Upgrade

Back up the database. Build the new image, then recreate API, dispatcher, and worker together.
This update adds tables using SQLAlchemy create_all; it does not alter existing columns.
Future column changes need a real migration, not recreation of a live database.
