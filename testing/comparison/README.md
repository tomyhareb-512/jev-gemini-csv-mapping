# Jev versus OpenRouter models

Prepared November 2, 2026. This runner compares the same supplier-column tasks
through Jev's typed API and selected OpenRouter chat models. `jev.py` and all old
results stay unchanged. No paid comparison has been run during setup.

## Enter your key locally

From the Jev project folder:

```powershell
python testing/comparison/set_key.py
```

This prompts for a hidden key and saves it to the project's `.env.openrouter`.
Alternatively, edit `OPENROUTER_API_KEY=` in that file yourself. Do not paste a
key into chat. The file is covered by `.gitignore`. A non-empty key in this local
file takes precedence over an inherited environment variable, so the key you
enter here selects the intended account. A blank entry leaves any existing
environment configuration available.

Jev uses the same installed `jev_lite` client and existing TypeSafe credentials as
the project. If needed, set `TYPESAFE_API_KEY` locally too. Do not use
`typesafe/jev-router` as the Jev baseline: that service selects other models and
bills their prices, rather than measuring the standalone Jev decision model.

## Preview, then run

For the first **Gemini versus Jev** trial, process all seven mapping targets in
each of two CSVs (28 calls total):

```powershell
python testing/comparison/compare_models.py --model jev-1.14.0 --model google/gemini-3.8-flash --case 01_clean_synonyms --case 02_shuffled_distractors
```

Add `--run` to that command only after entering your key and deciding to start.
Repeated `--case` options always select all seven fields for each specified CSV,
instead of the default mixed 14-task sample below. Full-case runs also export
eight-column supplier CSVs and mapping-review CSVs under each run's
`mapped_outputs/<model>/repeat_<n>/<case>/` folder. Python fills `supplier` and
copies accepted source values. Each model only supplies the column scores.
Unaccepted or unrun mappings are left blank and identified in the review file.

```powershell
# Shows model prices, credential-presence status, and the reservation estimate.
# No inference calls. Public model metadata may be fetched without a key.
python testing/comparison/compare_models.py

# Makes the actual paid comparison calls.
python testing/comparison/compare_models.py --run
```

The default is **14 tasks per model, 7 models, 98 calls, one repetition**, with a
**$1 local estimated budget guard**. The November 2 price snapshot produced a
  conservative reservation estimate below the **$1 guard** for that entire plan. This is an
estimate based on prompt byte lengths plus overhead and maximum output tokens,
not an actual charge or a guaranteed provider ceiling. Normal token counts may
cost less. Put a credit limit on your OpenRouter key for an account-side cap;
the local guard cannot cancel a completed request retroactively. Jev is billed
separately through TypeSafe and is included in the local estimate.

To start even smaller, explicitly select a few models:

```powershell
python testing/comparison/compare_models.py --model jev-1.14.0 --model anthropic/claude-haiku-5.5 --model google/gemini-3.8-flash
python testing/comparison/compare_models.py --run --model jev-1.14.0 --model anthropic/claude-haiku-5.5 --model google/gemini-3.8-flash
```

To repeat the same comparisons, use `--repeat 3`. The preview will show the larger
reservation; a live run refuses before inference if the total plan exceeds the
local guard. Raise it explicitly with `--max-usd` only when you intend that spend.
No retries are enabled, and remaining calls to an unhealthy model are skipped
after its first error or missing cost record. Incomplete results remain labelled
incomplete, and skipped tasks stay in accuracy denominators.

## Configured models and prices

Base list USD per **one million tokens**, checked against the public catalog on
November 2, 2026. Input and output are priced separately. These are not measured
task costs, speed rankings, or provider quotes guaranteed for every route.

| Model | Input | Output | Default |
| --- | ---: | ---: | --- |
| Jev 1.14 | 0.042 | 0 | Yes, TypeSafe direct |
| Claude Haiku 5.5 | 0.10 | 0.50 | Yes |
| Gemini 3.8 Flash | 0.825 | 4.125 | Yes |
| Qwen3.8 Flash | 0.15 | 0.47 | Yes |
| DeepSeek V4.1 Flash | 0.045 | 0.50 | Yes |
| Claude Sonnet 5.5 | 2.00 | 10.00 | Yes |
| GPT-6.1 Terra | 1.00 | 5.00 | Yes |
| GPT-6.1 Sol | 2.00 | 10.00 | Optional |
| GPT-6 Luna | 0.10 | 0.50 | Optional |
| Jev 1.13 | 0.042 | 0 | Optional, TypeSafe direct |

Edit `models.json` to enable/disable entries, or select exact configured IDs with
`--model`. The runner verifies OpenRouter IDs against the live catalog before
paid execution and never silently substitutes another model. No Opus model is
included. GPT-6.1 Terra is the lower-cost 6.1 option; Sol remains optional.

OpenRouter prices are refreshed from its public catalog before every live run.
Jev's configured list rate comes from its official model reference and should be
updated when that reference changes. Schedule/context overrides and caching can
change billed costs. OpenRouter's reported `usage.cost` is used where available;
Jev's cost is calculated from billable input tokens at its list rate. These cost
sources are labelled separately in the saved records. Unknown cost is not zero.

## Fair comparison protocol

- Read CSVs as strings with their known fixture delimiter, preserving identifiers.
- Freeze 14 tasks before any new answers: 10 with a known source column, 2 absent
  fields, and 2 requiring review. Cover all seven target fields.
- Mirror the current application's state and question text: filename, target
  definition, all source headings, then one scored question per source column
  with up to eight non-empty sample values. Both adapters receive those same
  state/questions. Expected answers are never sent. Definitions, including the
  existing filename-specific price wording, are preserved for this comparison.
  This measures the existing mapping method, rather than a revised prompt.
- Ask Jev its native Noul questions. Ask chat models for the corresponding numeric
  scores through a strict JSON schema; validate every returned key and score.
  The chat adapter adds output-format instructions, not extra supplier facts.
- Pin Jev to a version and record the actual model/version returned by each API.
- Use supported low/no reasoning settings, log them, and cap generated tokens at
  1,024. Temperature is not forced because several selected endpoints do not
  support it. Routing fallback is disabled and required schema parameters are
  enforced. Provider choices and actual token usage are saved when returned.
- Run sequentially in a reproducibly shuffled/interleaved schedule. Both adapters
  use persistent HTTP clients. Record end-to-end API time, including networking
  and decoding, rather than claiming to measure model-only inference or TTFT.

This comparison mirrors the **current per-column scoring prompt**, with raw CSV
values preserved as strings. Jev uses native Noul outputs; chat models require
additional JSON output instructions and can attend to the question bundle as a
whole. These API differences are recorded rather than assumed away. The original
application and CSV export code are not modified. Do not put these numbers beside
the historical 85.7% workflow score and interpret the difference as a model
improvement: that run used a different task set and mapper version. Every model,
including Jev, needs a fresh run under this same protocol. The small suite reuses development
fixtures, so it is not an unseen generalization benchmark. Add a frozen holdout
set before drawing broad conclusions or tuning models against it.

## What the results measure

Each live run creates a fresh directory under `output/model_comparison/`:

- `REPORT.md`: model comparison table.
- `summary.csv`: numbers suitable for opening in Excel.
- `results.json`: per-task scores, model/provider, errors, usage, costs, and timings.
- `tasks_and_expectations.json`: the frozen evidence and evaluator labels.
- `catalog_snapshot.json`: public model metadata used for this run.

The separate metrics are:

1. **Top-column ranking accuracy:** did the expected source rank uniquely first?
   Only the 10 known-source tasks belong in this denominator. A low score can
   still rank correctly. Ties do not count as correct.
2. **Mapping decision accuracy:** with the same 0.85 confidence and 0.15 margin
   rule, did the final mapping/review/absence decision meet the expected policy?
   All 14 tasks belong in this denominator. Absent fields may safely request
   review; ambiguous fields specifically need a review signal.
3. **False accepted mappings:** wrong sources or unjustified acceptance of an
   absent/ambiguous source, shown beside the number of accepted mappings.
4. **Latency:** median and nearest-rank p95 seconds per complete API response.
5. **Cost:** known total USD, number of accounted calls, and cost-source labels.

Scores generated by chat models are self-reported and are not assumed to have
the same calibration as Jev's probabilities. No metric here is automatically a
general "hallucination rate." No single best model is announced before actual
results exist; weigh valid answers, ranking, false acceptances, speed, and cost.
With only 14 tasks and one repetition, small accuracy differences and p95 timings
are preliminary. Use repeat runs and a larger holdout set for a stronger claim.

## Offline verification

### Explicit recovery after a network failure

The normal runner never automatically retries. If a transient timeout stops a
model, `resume_comparison.py` can explicitly finish only the failed or unrun
tasks in an existing run:

```powershell
python testing/comparison/resume_comparison.py output/model_comparison/<run-folder> --timeout 90
```

This checks the mapper, comparison runner, and fixture hashes, retains all failed
attempts, and archives the initial reports and partial CSVs under
`attempt_history/`. A completed task is never sent again. The original budget
guard remains in effect, with a reservation for unknown-cost failed attempts.
Recovery stops on its next request/accounting error; it is not an unlimited retry
loop. Reports record successful answers separately from attempted requests, so a
recovered timeout does not become a content/mapping error. Cost for a timed-out
request remains unknown unless the provider supplied accounting. The final JSON
also gives median/p95 times for successful responses separately from all attempts.

```powershell
python -m unittest discover -s testing/comparison -p test_compare_models.py -v
```

These tests use explicit mock responses to test the evaluator and adapters.
They do not make model calls, establish model accuracy, or generate benchmark
results. The default CLI preview also makes no inference calls.

## Sources

- [OpenRouter public model catalog](https://openrouter.ai/api/v1/models)
- [OpenRouter structured output schema](https://openrouter.ai/docs/guides/features/structured-outputs)
- [OpenRouter usage and billed costs](https://openrouter.ai/docs/cookbook/administration/usage-accounting)
- [TypeSafe model versions and pricing](https://docs.typesafe.ai/models)
- [TypeSafe typed API and billable usage](https://docs.typesafe.ai/api/system-one)
- [Official GPT-6.1 Terra model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-terra)
