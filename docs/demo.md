# Five-minute portfolio demo

1. Explain the product: a PR reviewer that reports supported defects, plus a benchmark that
   measures review quality. It does not merge or execute submitted code.
2. Show the architecture: signed webhook, SQL outbox, Redis/RQ worker, structured findings,
   validation, GitHub comment, and stored dashboard result.
3. Start the Docker demo. Submit the provided authorization diff and point out the **demo**
   label. Explain that this deterministic rule proves plumbing, not AI performance.
4. With model credentials configured, review a separate diff and inspect the evidence.
   For an end-to-end GitHub demonstration, open a PR in the test repository and show the
   corresponding App bot comment and dashboard record. Do not claim a live run until it happened.
5. Show tests, verified development cases, the six-case pilot, and the human adjudication
   workflow. Explain the small sample, reconstructed context, and need for held-out data.

## Accurate resume wording

- Built a GitHub-integrated code review service with signed webhooks, background processing,
  structured LLM findings, and inline PR comments.
- Developed a React/TypeScript dashboard for review history, evidence inspection, and queued
  manual reviews, with authenticated APIs and durable SQL-to-Redis job delivery.
- Implemented three review configurations and an evaluation harness with reproducible
  fixtures, failure reporting, and human-adjudicated precision/recall scoring.

Only add deployment or accuracy figures after collecting the corresponding evidence.
Both repositories are currently private; making them public is a separate visibility
change requiring an owner decision and a full secret/history check. A private video demo
or selected screenshots can be used without publishing the repository.
