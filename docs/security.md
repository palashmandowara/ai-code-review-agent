# Security and operations

- Verify `X-Hub-Signature-256` before processing a webhook and keep its secret out of version control.
- Store GitHub App private keys and model credentials as environment secrets; never include them in benchmark output.
- Treat repository text and model output as untrusted. Source is supplied as data to the model. Validate schemas and changed line locations before posting.
- GitHub source is fetched at the PR head SHA. The worker rechecks that SHA before publication, and a review marker reduces duplicate posts on retries.
- Ruff parses changed Python content through stdin. The worker does not run repository code or fetch executable artifacts into its container.
- The context fetch has file count, file size, and prompt size limits. Diffs exceeding 30,000 characters are explicitly skipped or rejected; this avoids silently reviewing only part of a change.
- Docker Compose is a local setup. A public deployment needs HTTPS, network restrictions for PostgreSQL and Redis, managed secrets, backups, logs, and alerts. Rotate keys after accidental disclosure.

Residual risks: a crash between GitHub accepting a review and its marker appearing in the list endpoint can still cause a duplicate; model prompt injection may still influence output despite instructions; provider policies govern private-code transfer; database schema changes currently require a fresh development database or a planned migration.



Dashboard APIs require DASHBOARD_TOKEN and do not persist it in browser storage. Manual
reviews are queued and never publish to GitHub. Their source/context/results are retained
in PostgreSQL, so backups are sensitive. A shared token is not multi-user authorization.
The supplied Compose API is loopback-only; use HTTPS and network restrictions on a host.
The container runs as a non-root user. Redis uses a persistent AOF volume. Job publication
uses a SQL outbox and per-run locks, but remote GitHub effects are still at-least-once.
