# Model comparison

Status: **completed_with_recovered_attempts**. Protocol: `original-first8-mapping-v1`.
Ranking and decision denominators include all planned tasks; missing/error answers are not silently removed.

| Model | Answers / planned | Top column correct | Decisions correct | False accepted / accepted | Median s | P95 s | Known cost USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Jev 1.14 | 70/70 | 65/65 (100.0%) | 69/70 (98.6%) | 0/64 | 0.224 | 0.519 | 0.003770 (70/70 calls) |
| Gemini 3.8 Flash | 70/70 | 65/65 (100.0%) | 70/70 (100.0%) | 0/65 | 3.515 | 8.599 | 0.103378 (70/71 calls) |

Cost: OpenRouter-reported charges where provided; Jev costs calculated from billable input tokens and its configured list rate.
Unknown costs are never treated as free. Local budget reservations are estimates; an OpenRouter key credit limit is the account-side cap.
Table latency includes all API attempts, including the failed timeout. Successful-response-only median/p95 and recovery details are in FINDINGS.md and results.json. These are end-to-end network times, not model-only inference or time to first token.
This is a small, previously seen development suite, not an unseen accuracy or general hallucination-rate measurement.
Generated scores from chat models are self-reported and may not be calibrated like Jev probabilities.
This uses current application state/questions and fresh calls; chat models additionally need JSON output instructions. Raw strings are preserved.
The historical 85.7% used a different task set/version; compare models inside this report only.
No overall winner is declared automatically; inspect ranking, unsafe acceptances, completion, latency, and cost together.

[Read the completed ten-file comparison and recovery notes](FINDINGS.md)

Publication note: service request/generation identifiers were removed from the published JSON. The timeout remains recorded; local attempt-history archives are not included.
