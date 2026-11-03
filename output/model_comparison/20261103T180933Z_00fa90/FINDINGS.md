# Ten-file Gemini versus Jev comparison

Completed November 3, 2026. Ten existing CSVs, 100 rows each; all seven mapping targets tested in each file. Python supplied the supplier column and copied accepted source values. Original inputs and the earlier two-file run were preserved.

| Metric | Jev 1.14 | Gemini 3.8 Flash |
| --- | ---: | ---: |
| Correct top-ranked source, where a matching column exists | 65/65 (100%) | 65/65 (100%) |
| Expected mapping/review/absence decisions | 69/70 (98.6%) | 70/70 (100%) |
| Incorrect accepted mappings | 0 | 0 |
| Median successful API response | 0.224 s | 3.514 s |
| P95 successful API response | 0.519 s | 7.536 s |
| Known cost for the entire 10-file trial | $0.003770424 | $0.10337775 |
| Valid responses / attempted requests | 70/70 | 70/71 |

The ranking denominator is 65 because five target fields are absent in the selected inputs. No general hallucination rate is inferred from this development set.

## The one held mapping

In 04_description_has_specs, Jev correctly ranked Description first for specifications but assigned 0.75, below the unchanged 0.85 acceptance threshold. Python left specifications blank and requested review. Gemini accepted Description. This is an acceptance/uncertainty difference, not a wrong top-ranked source or invented value.

## Network recovery and cost

Gemini had one network timeout after 45 seconds. The initial attempt is retained in results.json and attempt_history/. Explicit recovery completed only the 57 failed or unrun tasks, using a 90-second network timeout; completed Jev or Gemini tasks were not repeated. No prompt or output-token settings changed. There were 141 actual attempts for 140 unique successful task answers.

Known combined cost: $0.107148174 (about 10.71 US cents), plus any charge for the timed-out Gemini request, which could not be confirmed. Gemini costs are provider-reported; Jev costs are calculated from billable input tokens at its configured published list rate. The local budget guard was $1.

The latency table above uses successful responses only. Failed-attempt durations remain in the raw report and records. A recovered timeout is not counted as a mapping/content mistake. The recovered batch was sequential, so timing comparisons remain preliminary and may reflect provider/network conditions.

## Verification

Checked all 20 mapped CSVs: 1,000 rows per model, eight output columns, every accepted value copied exactly, blanks retained for unaccepted/absent fields, and seven audit rows per file. The original mapper and comparison runner hashes still match the start of this run.

## Input and output files

| Case | Input | Gemini output | Jev output |
| --- | --- | --- | --- |
| 01_clean_synonyms | [CSV](../../../data/26-10-2026-variants/01_clean_synonyms/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/01_clean_synonyms/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/01_clean_synonyms/all_supplier_data.csv) |
| 02_shuffled_distractors | [CSV](../../../data/26-10-2026-variants/02_shuffled_distractors/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/02_shuffled_distractors/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/02_shuffled_distractors/all_supplier_data.csv) |
| 03_missing_fields | [CSV](../../../data/26-10-2026-variants/03_missing_fields/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/03_missing_fields/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/03_missing_fields/all_supplier_data.csv) |
| 04_description_has_specs | [CSV](../../../data/26-10-2026-variants/04_description_has_specs/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/04_description_has_specs/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/04_description_has_specs/all_supplier_data.csv) |
| 06_eur_only | [CSV](../../../data/26-10-2026-variants/06_eur_only/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/06_eur_only/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/06_eur_only/all_supplier_data.csv) |
| 07_usd_box_prices | [CSV](../../../data/26-10-2026-variants/07_usd_box_prices/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/07_usd_box_prices/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/07_usd_box_prices/all_supplier_data.csv) |
| 08_quantity_traps | [CSV](../../../data/26-10-2026-variants/08_quantity_traps/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/08_quantity_traps/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/08_quantity_traps/all_supplier_data.csv) |
| 13_zero_and_blank_stock | [CSV](../../../data/26-10-2026-variants/13_zero_and_blank_stock/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/13_zero_and_blank_stock/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/13_zero_and_blank_stock/all_supplier_data.csv) |
| 14_leading_zero_ids | [CSV](../../../data/26-10-2026-variants/14_leading_zero_ids/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/14_leading_zero_ids/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/14_leading_zero_ids/all_supplier_data.csv) |
| 17_multilingual_headings | [CSV](../../../data/26-10-2026-variants/17_multilingual_headings/supplier_variant.csv) | [CSV](mapped_outputs/google_gemini-3.8-flash/repeat_1/17_multilingual_headings/all_supplier_data.csv) | [CSV](mapped_outputs/jev-1.14.0/repeat_1/17_multilingual_headings/all_supplier_data.csv) |

[Raw report](REPORT.md) | [Summary for Excel](summary.csv) | [All task-level evidence](results.json)

Each output folder also contains field_mapping_review.csv. Earlier partial exports are archived under attempt_history/.

Publication note: service request/generation identifiers were removed from the published JSON. The timeout remains recorded; local attempt-history archives are not included.
