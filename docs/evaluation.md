# Evaluation protocol

## Cases and labels

Each case has a unique ID, source, diff, expected defect location, category, and a human-readable rationale. The current fixtures are synthetic smoke tests. The `dev` and `heldout` files are separated for workflow testing; their labels are public and their small size makes them unsuitable for a published performance claim.

Before a real experiment, gather independently verified bug-fix commits, retain commit URLs and licenses, reconstruct the bug-introducing diff, and confirm with a reproducing test or documented behavior. Include clean changes and suspicious-but-correct cases. Keep near duplicates in one split. Freeze the held-out set before prompt tuning.

## Matching

A finding provisionally matches one expected defect if its file path and added line fall within the expected line range. One expected defect can match at most one prediction. Category wording is recorded as a separate exact-match count, since providers use different labels for the same bug. Invalid locations, malformed findings, and duplicates count as false positives; a failed model call counts as a failed case, not a clean review. Location matching alone can count an unrelated issue on the same line, so inspect the semantic rationale manually before treating numerical matches as true defects in any published results.

## Comparison

Run `plain`, `context`, and `tool` on identical cases with the same model version and prompt version. Record the dataset checksum, application Git SHA, model name, provider, token prices, token usage, failures, and timestamps. Repeat selected cases to estimate variability. Report precision, recall, F1, false positives per PR, localization accuracy, median and p95 latency, estimated cost per review, and failure rate. Report raw counts beside percentages and inspect false positives and misses.

The CLI computes numerical precision/recall/F1, latency, and configured token cost; it does not currently automate semantic adjudication, repeated runs, or dataset provenance review. Oracle predictions only test the scoring code.

## Sourced pilot

`benchmark/datasets/pilot.json` contains four short adaptations of documented BugsInPy fixes, reversed to reintroduce the bugs, plus two synthetic clean controls. Each positive case links to its upstream patch and records the fixed commit and test file. These snippets preserve the defect mechanism but are not the original upstream pull request diffs. The context strings summarize the intended behavior from the fix; they are reconstructed evaluation material, not retrieved repository files. The dataset is visible alongside the prompts, so it is not a held-out benchmark. Do not present its scores as general performance or as independent real-world PR results.

The harness passes a case's behavior context only to `context` and `tool`. For `tool`, it runs Ruff on that case's reconstructed Python source. These two modes thus receive extra information, and differences cannot be attributed solely to the prompting strategy. A failed call appears as a failure and causes aggregate precision, recall, and F1 to be `null`. A complete run includes one JSON line per case and a final summary with a raw-file SHA-256 and a canonical JSON SHA-256. The canonical checksum is stable across Windows and Unix line endings.

Prompt v2 requests a single added line per finding and, for Groq GPT-OSS 20B/120B, uses Groq's strict JSON Schema output mode. Other OpenAI-compatible endpoints retain JSON object mode. Rejected finding locations are reported with a reason. Compare approaches only when dataset checksum, prompt version, and model match; earlier v1 runs are diagnostic history, not part of the v2 comparison.

On Windows, from the project directory with `.env` set to `REVIEW_MODE=model` and the Groq settings, run the pilot in Docker. Each run makes six model calls. Keep the result files locally because they include model output and case text; do not commit them.

```powershell
$projectPath = (Get-Location).Path
New-Item -ItemType Directory results -Force | Out-Null
foreach ($approach in 'plain','context','tool') {
    docker compose run --rm -v "${projectPath}/benchmark:/app/benchmark:ro" worker `
        python -m review_agent.cli benchmark /app/benchmark/datasets/pilot.json `
        --approach $approach | Tee-Object "results/pilot-$approach.jsonl"
}
```

Check each final JSON line for `"complete": true` before comparing scores. Inspect individual findings and failures manually. To rescore a saved JSONL run after a scoring change without model calls, use `--predictions results/pilot-plain.jsonl`; the replay preserves rejected-finding counts but has no original latency or token-cost measurement. Never count the deterministic `REVIEW_MODE=demo` as an AI result. For a defensible future evaluation, curate more upstream patches and clean real changes, review licenses and labels independently, freeze a separate held-out set, and rerun with a fixed model version.


## Verified development fixtures and semantic adjudication

`verified-dev.json` contains eight injected bugs and four clean controls generated from
project-authored sources in `tests/fixtures/verified_cases.py`. Pytest checks the original
behavior, demonstrates each regression, and checks clean alternatives. The dataset must
match the generator byte-for-byte after JSON parsing. These cases are development data;
none are presented as a new held-out benchmark or new model results.

Use `python -m review_agent.evaluation DATASET RESULTS JUDGMENTS --template` to create a
pending worksheet. A reviewer must fill their name and each verdict/rationale; correct
findings also identify `expected_index`. Run the same command without `--template` to
calculate semantic metrics. Dataset/prediction hashes reject stale worksheets. Duplicate
findings cannot count twice. Failed cases count as missed expected defects and are reported
in failure rate. Location-only results remain clearly labeled provisional.

A future final experiment must freeze an independent dataset before tuning, verify upstream
licenses and reproducing tests, preserve raw outputs, repeat each approach, and report
uncertainty. Additional development fixtures do not substitute for that experiment.
