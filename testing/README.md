# Supplier CSV stress cases

25 isolated fictional supplier files, with 2,400 product rows total. Each full file
has 100 rows; the header-only case has zero. These are controlled variants of the
same fictional catalog so a change in behavior can be tied to a specific change
in headings, values, or file structure.

`jev.py` and the original `data/18-10-2026` examples are unchanged by this suite.
The expectations in `expected_variants.json` were written before the first live
run. They are evaluator inputs, never model inputs. Do not put this manifest in a
supplier input folder.

## Run

From the Jev project folder, using the Python environment that already runs Jev:

```powershell
python testing/run_variants.py
```

This makes real calls through the existing configured Jev client. Two isolated
mapper processes run at a time; use `--workers 1` for sequential execution. Each
case gets its own process, fresh staged inputs, output directory, and timeout.
Original fixture files remain intact. A failed case does not stop other cases.

To inspect one case through the normal application:

```powershell
python jev.py 26-10-2026-variants/13_zero_and_blank_stock
```

To repeat selected probes and see whether decisions change:

```powershell
python testing/run_variants.py --case 18_bad_prices_after_sample --case 19_same_rows_bad_values_first --repeat 3
```

Each evaluation has a fresh timestamped folder under
`output/26-10-2026-variants/` containing `REPORT.md`, `results.json`, and
`field_results.csv`. The JSON records fixture hashes, the mapper hash, timings,
field decisions, changed-value examples, and invalid numeric output. Staged raw
application outputs live under `output/_variant_runs/<run>/`.

## Cases and expectations

| Case | What it probes |
| --- | --- |
| 01 clean synonyms | Clear alternative headings should map all fields. |
| 02 shuffled distractors | Ignore column order, order IDs, units sold, and box prices. |
| 03 missing fields | Leave absent supplier ID and specifications blank. |
| 04 description has specs | A description can legitimately supply two target fields. |
| 05 unknown currency | Bare Price requires review, not a USD assumption. |
| 06 EUR only | No USD field and no automatic currency conversion. |
| 07 USD box prices | Do not map or divide a box price into a unit price. |
| 08 quantity traps | Sold units, ordered units, and boxes are not available units. |
| 09 two valid prices | Require a human choice between two different USD unit prices. |
| 10 two supplier IDs | Require a human choice between two valid internal references. |
| 11 opaque headings | Names/groups/features can be recognized; code roles and units need review. |
| 12 misleading headings | Judge values together with headings, even when headings mislead. |
| 13 zero and blank stock | Preserve zero versus unknown; do not fill blanks. |
| 14 leading-zero IDs | Preserve exact identifier spelling, including initial zeros. |
| 15 mixed currency | One column with mixed currencies cannot wholly become price_usd. |
| 16 contextual currency | USD and per-item evidence is in separate columns. |
| 17 multilingual headings | French and Arabic headings; UTF-8 input. |
| 18 bad prices after sample | Eight good samples hide 92 explicitly EUR prices. |
| 19 reordered price case | Exactly the same rows as 18, but conflicting values appear first. |
| 20 text numeric values | Correct semantic mapping still needs number normalization. |
| 21 bad stock after sample | Eight valid samples hide 92 negative or fractional counts. |
| 22 header only | Empty catalog should produce zero output rows without a crash. |
| 23 semicolon CSV | Probe the current comma-delimiter assumption. |
| 24 instruction in a cell | Supplier text must remain data, even when phrased as an instruction. |
| 25 familiar filename | A supplier_a filename must not establish per-item meaning when values/context say boxes. |

The two-price and two-ID cases use a deliberate evaluation policy: without a
stated business preference, equally valid competing sources require review.
This policy is visible here so it can be discussed rather than hidden in a score.
Missing fields may safely produce either `no_match` or a cautious review. An
uncertain field marked `no_match` is a safe abstention, but it loses the requested
human-review signal and is counted separately.

## Interpreting results

- `correct_mapping`: accepted the expected source column.
- `unsafe_mapping`: accepted a wrong source, or mapped a field requiring review/absence.
- `missed_mapping`: left a clearly supported field blank.
- `correct_review`: held an ambiguous field for human review.
- `safe_abstention_without_review`: left ambiguity blank but did not request review.
- `correct_absence` / `cautious_absence`: did not invent a missing field.
- `unscored_review`: no candidate and zero scores; the current application's swallowed
  API exceptions can produce this, so this is not evidence of successful reasoning.

Data checks are separate from mapping checks. For example, Jev can correctly pick
an ID column while pandas strips its leading zeros. Prices must be finite
nonnegative numbers, and stock must be finite nonnegative whole units. A blank is
allowed and differs from zero. Numeric formatting such as `12.50` versus `12.5`
is equivalent; identifier strings are compared exactly. Invalid source values are
intentional probes; copying them through is a pipeline limitation, not necessarily
a wrong column choice by Jev.

The application samples only eight non-empty values per column. 100 rows do not
mean 100 independent AI trials: there are seven field decisions per case. A
single run describes this case set and mapper version, not general model accuracy.
Do not tune prompts against these cases and then call the same set an unseen test.
Add a separately frozen case set when measuring improvements.

`generate_variants.py` documents and reproduces the fixture design. It refuses to
overwrite an existing suite or manifest; choose a new suite name before generating
a different version. The test runner never modifies `jev.py`.
