"""Run the unchanged jev.py against frozen cases and score its real outputs.

Expectations are read here only; they are never sent to Jev. Uses the same Python
and configured Jev client as the normal application. No fixture/mock AI responses.
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("expected_variants.json")
MAPPER = ROOT / "jev.py"
PASS_OUTCOMES = {"correct_mapping", "correct_review", "correct_absence", "cautious_absence"}


def read_csv(path, delimiter=","):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        return reader.fieldnames, list(reader)


def number(value):
    try:
        parsed = Decimal(value)
        return parsed if parsed.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def same_value(actual, expected, numeric):
    if not numeric or actual == "" or expected == "":
        return actual == expected
    left, right = number(actual), number(expected)
    return left == right if left is not None and right is not None else actual == expected


def score_field(policy, expected_source, audit):
    status = audit["status"]
    selected = audit["selected_source_column"]
    if status == "human_review" and not audit["best_candidate_column"] and float(audit["confidence"]) == 0:
        return "unscored_review"  # Current mapper also uses this when an AI call fails.
    if status == "auto_mapped":
        return "correct_mapping" if policy == "map" and selected == expected_source else "unsafe_mapping"
    if policy == "map":
        return "missed_mapping"
    if policy == "review":
        return "correct_review" if status == "human_review" else "safe_abstention_without_review"
    return "correct_absence" if status == "no_match" else "cautious_absence"


def run_case(case, repetition, suite, run_id, timeout):
    # Each run gets fresh inputs/outputs so old files cannot be scored as new work.
    source_path = ROOT / case["input"]
    if hashlib.sha256(source_path.read_bytes()).hexdigest() != case["sha256"]:
        raise ValueError(f"Fixture changed since expectations were frozen: {case['id']}")
    relative_folder = Path("_variant_runs") / run_id / f"repeat_{repetition}" / case["id"]
    staged = ROOT / "data" / relative_folder / case["filename"]
    staged.parent.mkdir(parents=True, exist_ok=False)
    staged.write_bytes(source_path.read_bytes())
    output = ROOT / "output" / relative_folder
    start = time.monotonic()
    result = {"case": case["id"], "repeat": repetition, "description": case["description"],
              "input": case["input"], "output": str(output.relative_to(ROOT)),
              "fields": [], "data_issues": [], "pipeline_error": None}
    try:
        process = subprocess.run([sys.executable, str(MAPPER), relative_folder.as_posix()],
                                 cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        if process.returncode:
            result["pipeline_error"] = f"exit={process.returncode}: {process.stderr[-2000:]}"
            return result
        _, source_rows = read_csv(source_path, case["delimiter"])
        columns, actual_rows = read_csv(output / "all_supplier_data.csv")
        _, audits = read_csv(output / "field_mapping_review.csv")
        expected_columns = ["supplier", *case["fields"]]
        if columns != expected_columns:
            result["data_issues"].append({"kind": "output_schema", "actual": columns})
        if len(actual_rows) != case["row_count"]:
            result["data_issues"].append({"kind": "row_count", "expected": case["row_count"],
                                           "actual": len(actual_rows)})
        if len(audits) != len(case["fields"]) or len({a["target_field"] for a in audits}) != len(audits):
            raise ValueError("Missing or duplicate field audit rows")
        by_field = {audit["target_field"]: audit for audit in audits}
        for field, expected in case["fields"].items():
            audit = by_field[field]
            verdict = score_field(expected["policy"], expected["source"], audit)
            result["fields"].append({"field": field, "expected_policy": expected["policy"],
                "expected_source": expected["source"], "selected_source": audit["selected_source_column"],
                "candidate": audit["best_candidate_column"], "status": audit["status"],
                "confidence": float(audit["confidence"]), "margin": float(audit["confidence_margin"]),
                "outcome": verdict})
            if audit["status"] != "auto_mapped":
                populated = [i + 1 for i, row in enumerate(actual_rows) if row.get(field, "") != ""]
                if populated:
                    result["data_issues"].append({"field": field, "kind": "abstained_but_populated",
                                                   "count": len(populated), "sample_rows": populated[:5]})
                continue
            if verdict == "correct_mapping":
                mismatches = [i + 1 for i, (actual, source) in enumerate(zip(actual_rows, source_rows))
                              if not same_value(actual.get(field, ""), source[expected["source"]],
                                                field in ("price_usd", "stock_quantity"))]
                if mismatches:
                    i = mismatches[0] - 1
                    result["data_issues"].append({"field": field, "kind": "source_value_changed",
                        "count": len(mismatches), "sample_rows": mismatches[:5],
                        "example_expected": source_rows[i][expected["source"]],
                        "example_actual": actual_rows[i].get(field, "")})
            if field in ("price_usd", "stock_quantity"):
                invalid = []
                for i, row in enumerate(actual_rows):
                    value = row.get(field, "")
                    if value == "":
                        continue
                    parsed = number(value)
                    if parsed is None or parsed < 0 or (field == "stock_quantity" and parsed != parsed.to_integral_value()):
                        invalid.append(i + 1)
                if invalid:
                    result["data_issues"].append({"field": field, "kind": "invalid_numeric_output",
                        "count": len(invalid), "sample_rows": invalid[:5],
                        "example_actual": actual_rows[invalid[0] - 1].get(field, "")})
        result["rows"] = len(actual_rows)
    except subprocess.TimeoutExpired:
        result["pipeline_error"] = f"Timed out after {timeout} seconds"
    except (OSError, ValueError, KeyError) as exc:
        result["pipeline_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["seconds"] = round(time.monotonic() - start, 2)
    return result


def save_report(destination, report):
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = [{"case": case["case"], "repeat": case["repeat"], **field}
            for case in report["cases"] for field in case["fields"]]
    if rows:
        with (destination / "field_results.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    lines = ["# Jev variant evaluation", "", f"Run: `{report['run_id']}` (live configured Jev client).",
             f"Mapper SHA256: `{report['mapper_sha256']}`.", "",
             f"{len(report['cases'])} case-runs; {len(rows)} field decisions.", "",
             "## Field outcomes", "", "| Outcome | Count |", "| --- | ---: |"]
    lines += [f"| {key} | {value} |" for key, value in sorted(report["outcome_counts"].items())]
    lines += ["", "## Cases", "", "| Case | Repeat | Mapping concerns | Data issues | Pipeline |",
              "| --- | ---: | --- | --- | --- |"]
    for case in report["cases"]:
        concerns = "; ".join(f"{f['field']}: {f['outcome']} ({f['candidate'] or '-'})"
                              for f in case["fields"] if f["outcome"] not in PASS_OUTCOMES) or "none"
        data = "; ".join(f"{d.get('field', 'file')}: {d['kind']} ({d.get('count', 1)} rows)"
                          for d in case["data_issues"]) or "none"
        lines.append(f"| {case['case']} | {case['repeat']} | {concerns} | {data} | {'ERROR' if case['pipeline_error'] else 'completed'} |")
    lines += ["", "Expectations were frozen before this run and never sent to Jev.",
              "A safe abstention is distinct from an incorrect confident mapping. Blank and zero differ.",
              "Row numbers in JSON diagnostics are one-based data rows, excluding the header.",
              "Repeated rows do not create independent AI decisions: mapping is per column.",
              "These fictional cases measure this frozen mapper, fixture set, and run, not general accuracy.",
              "The application swallows AI exceptions; unscored_review may indicate an API failure.",
              "See results.json for data examples, timings, fixture hashes, and pipeline failures.", ""]
    (destination / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", help="Case ID; repeat this option to select several")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2))
    parser.add_argument("--timeout", type=int, default=180, help="Seconds per mapper process")
    args = parser.parse_args()
    if args.repeat < 1 or args.timeout < 1:
        parser.error("--repeat and --timeout must be positive")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected = [case for case in manifest["cases"] if not args.case or case["id"] in args.case]
    unknown = set(args.case or ()) - {case["id"] for case in selected}
    if unknown:
        parser.error(f"Unknown cases: {sorted(unknown)}")
    mapper_hash = hashlib.sha256(MAPPER.read_bytes()).hexdigest()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
    destination = ROOT / "output" / manifest["suite"] / run_id
    report = {"run_id": run_id, "mode": "live", "mapper_sha256": mapper_hash,
              "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
              "python": sys.version, "fixtures": {c["id"]: c["sha256"] for c in selected},
              "cases": [], "outcome_counts": {}}
    print(f"Running {len(selected)} cases x {args.repeat} repeat(s), {args.workers} worker(s).", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_case, case, repetition, manifest["suite"], run_id, args.timeout)
                   for repetition in range(1, args.repeat + 1) for case in selected]
        for future in as_completed(futures):
            result = future.result()
            report["cases"].append(result)
            report["cases"].sort(key=lambda item: (item["repeat"], item["case"]))
            report["outcome_counts"] = dict(Counter(f["outcome"] for c in report["cases"] for f in c["fields"]))
            save_report(destination, report)
            print(f"[{len(report['cases'])}/{len(futures)}] {result['case']}: "
                  f"{dict(Counter(f['outcome'] for f in result['fields']))}; "
                  f"data issues={len(result['data_issues'])}; error={bool(result['pipeline_error'])}", flush=True)
    if hashlib.sha256(MAPPER.read_bytes()).hexdigest() != mapper_hash:
        raise RuntimeError("jev.py changed during evaluation; do not compare this run as a frozen baseline")
    print(json.dumps(report["outcome_counts"], indent=2), flush=True)
    print(f"Report: {destination / 'REPORT.md'}", flush=True)


if __name__ == "__main__":
    main()
