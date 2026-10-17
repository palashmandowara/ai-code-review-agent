# Six-case review pilot: 17 October 2026

This is a workflow check on **four short adaptations of BugsInPy fixes reversed to reintroduce the bug** and **two synthetic clean controls**. The labels and behavior summaries are visible in the repository. These are not held-out, independently reproduced pull requests. Do not use the percentages below as a claim about performance on arbitrary code reviews.

The runs used Groq `openai/gpt-oss-20b`, prompt `v2`, and the same Windows checkout of `benchmark/datasets/pilot.json` (raw SHA-256 `9eb0f6ffcb322197a305f0ede2c0ed4813749feae0be250e3dba9967b2d40ab1`; canonical JSON SHA-256 `b95d539190ea6d526c1a8feec2379fac9ec0e9e7bfd0ff8ccfcfcb375c434846`). Every run completed all six cases. The reviewer returned findings on added lines only. I manually checked the accepted findings against the intended defect mechanism in each adapted snippet.

| Approach | Intended bugs found | Rejected findings | Comments on clean controls | Provisional location precision / recall / F1 | Median latency | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Plain | 4/4 | 0 | 0/2 | 1.00 / 1.00 / 1.00 | 1.25 s | 3,089 / 3,325 |
| Context | 3/4 | 1 | 0/2 | 0.75 / 0.75 / 0.75 | 1.03 s | 3,249 / 2,861 |
| Tool | 4/4 | 0 | 0/2 | 1.00 / 1.00 / 1.00 | 1.03 s | 3,944 / 2,959 |

The context run's Luigi finding was rejected because the model selected unchanged line 5; the buggy added call is line 4. This counts as one false positive and one missed defect in the strict location score. The accepted explanations for the other cases described the intended defects. A location-only metric can still overcount unrelated findings on the same line, so the manual check matters.

The pilot does **not** show that context or Ruff improves accuracy: plain and tool tied on these cases, and the sample is too small. The extra context is a reconstructed behavior summary; the Ruff input is a short reconstructed source file rather than the full upstream checkout. Output varies between calls, and this experiment has one run per approach. The `estimated_total_usd` field was `0.0` because token prices were not configured; it is not a measured billing amount. The user ran these requests on Groq's free plan.

Next: collect more independent bug-fix commits and real clean changes, preserve the complete before/after file context, verify each label with a reproducing test, freeze a held-out set before tuning, then repeat runs and report uncertainty. Keep the raw JSONL outputs from this pilot locally under `results/` for inspection; that directory is intentionally Git-ignored.
