# experiments/ — springboard lab (z-lab Phase 2)

Live-oracle studies against the fleet's typed models. Every experiment is
witness-booked; REFUSED rows are kept, never retried away.

## S1 — triagedesk vs live jev-1.13.0 (`s1-triagedesk-live.mjs`)

Run: `TYPESAFEAI_KEY=… node experiments/s1-triagedesk-live.mjs` (12 live calls, ~3¢ total).

**Result (2026-09-25 09:1x CST): 12/12 live, 5/5 pins green.** Heuristic-vs-live
agreement: action 9/12, page-gate 10/12, score ±10 only 5/12 (mean |Δ| 24.3).

Boundary segments (drift is data):
- **auto-close class dissolves live** — model never picks `auto-close` (t05/t06
  → `reply-only`): "cosmetic" tickets get an answer, not a dismissal. The naive
  keyword gate invents a disposition the oracle doesn't believe in.
- **page-gate under-fires on heuristics** — t10 (billing+down mix) and t11
  (blocked-team urgency) scored `no` offline but p=0.67/0.76 live. Deadline
  pressure is invisible to keyword counting.
- **score calibration lives at the top of the scale** — jev saturates 100 on
  production-loss cases where the heuristic compresses to 40-60; scores are
  ordinal ranks, not a shared interval scale. SLA-by-band policies keyed on
  absolute numbers will mis-fire across decision-makers.

Wire truth (verified this run): `POST https://api.typesafe.ai/v1/systemone`,
Bearer auth, `questions` need `question`+`criteria`+`scale`; score answers are
normalized floats with per-index `probabilities`; noul answers carry ONLY a
probability (threshold yes/no yourself). Host-only `typesafe.ai/v1` = 404.

Receipt: `out/s1-triagedesk-live.receipt.json` (hash-chained, verify with the
toolkit's `verifyChain`).
