# Local acceptance on Windows

Use PowerShell with Git and Docker Desktop installed and Docker Desktop running in Linux
containers mode. This procedure has not yet been executed on the owner's computer.
The repository is private: authenticate Git as an account with access. Do not paste tokens
or model keys into chat, screenshots, or git commits.

## 1. Get the review branch

For a new checkout:

```powershell
git clone --branch feature/review-dashboard https://github.com/palashmandowara/ai-code-review-agent.git
cd ai-code-review-agent
docker version
docker compose version
```

If you already have a checkout, run `git status` first. Preserve local changes before
switching branches; then fetch and switch to `feature/review-dashboard`.

## 2. Configure a private demo token

The following creates `.env` only if it does not exist, and fills a blank dashboard token.
Existing configuration is preserved. No Python installation is required.

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
$config = [IO.File]::ReadAllText((Join-Path $PWD '.env'))
if ($config -match '(?m)^DASHBOARD_TOKEN=\s*$') {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $demoToken = [Convert]::ToBase64String($bytes)
    $config = [regex]::Replace($config, '(?m)^DASHBOARD_TOKEN=[ \t]*\r?$', "DASHBOARD_TOKEN=$demoToken")
    [IO.File]::WriteAllText((Join-Path $PWD '.env'), $config)
}
notepad .env
```

Keep `REVIEW_MODE=demo` for this first check. Copy the dashboard token from the file for
the login screen and keep it private.

## 3. Start and verify

```powershell
docker compose config --quiet
docker compose up --build -d --wait
Invoke-RestMethod http://localhost:8000/ready
Start-Process http://localhost:8000
```

Sign in, select **New review → Load example → Run review**, and wait for the queued run
to complete. Inspect the authorization finding and the demo label. This proves the local
pipeline, not model accuracy.

```powershell
docker compose restart api worker dispatcher
```

Refresh after services restart and verify that the run and finding still appear in history.
If startup or review fails, inspect:

```powershell
docker compose ps
docker compose logs --tail=100 api worker dispatcher init
```

Share the error text after removing secrets and source code. To stop without deleting data:

```powershell
docker compose down
```

Do not add `-v` unless you intend to delete database and queue volumes.

## 4. Run a real model review

In `.env`, set `REVIEW_MODE=model` and your provider's `LLM_API_KEY`, endpoint, and model.
The sample endpoint/model must be available to your provider account. Set token prices
only from your provider's actual pricing if you want cost estimates.

```powershell
docker compose up -d --force-recreate api worker dispatcher
```

Submit a separate small diff and inspect its findings and model metadata. An empty result
is not proof that the code is correct. Preserve the observed result for the demo.

## 5. Connect GitHub and finish release verification

A local model review does not establish live GitHub integration. Follow the README's GitHub
App setup with Contents read and Pull requests read/write permissions. Webhook delivery
needs a reachable HTTPS endpoint; localhost alone cannot receive GitHub deliveries. Choose
a host or authenticated development tunnel before configuring the callback. Store the
App key and webhook secret locally, and install the App on the test repository.

Open/update a test PR and confirm both the bot's inline comment and matching dashboard
record. Record the commit, review approach, and actual result. Do not publish credentials
in a recording. Finally resolve the Actions startup annotation and get remote backend,
browser, and container checks green before merging PR #7.

A broader accuracy claim also requires an independent test set and human-adjudicated model
runs. It is optional for listing the implemented project on a resume, not evidence supplied
by the deterministic demo.
