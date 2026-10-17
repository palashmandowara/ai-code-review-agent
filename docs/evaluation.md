# Evaluation protocol

## Cases and labels

Each case has a unique ID, source, diff, expected defect location, category, and a human-readable rationale. The current fixtures are synthetic smoke tests. The `dev` and `heldout` files are separated for workflow testing; their labels are public and their small size makes them unsuitable for a published performance claim.

Before a real experiment, gather independently verified bug-fix commits, retain commit URLs and licenses, reconstruct the bug-introducing diff, and confirm with a reproducing test or documented behavior. Include clean changes and suspicious-but-correct cases. Keep near duplicates in one split. Freeze the held-out set before prompt tuning.

## Matching

A finding matches one expected defect only if its file path, category, and added line fall within the expected line range. One expected defect can match at most one prediction. Invalid locations, malformed findings, and duplicates count as false positives; a failed model call counts as a failed case, not a clean review. Review the semantic rationale manually before treating numerical matches as true defects in any published results.

## Comparison

Run `plain`, `context`, and `tool` on identical cases with the same model version and prompt version. Record the dataset checksum, application Git SHA, model name, provider, token prices, token usage, failures, and timestamps. Repeat selected cases to estimate variability. Report precision, recall, F1, false positives per PR, localization accuracy, median and p95 latency, estimated cost per review, and failure rate. Report raw counts beside percentages and inspect false positives and misses.

The CLI computes numerical precision/recall/F1, latency, and configured token cost; it does not currently automate semantic adjudication, repeated runs, or dataset provenance review. Oracle predictions only test the scoring code.
