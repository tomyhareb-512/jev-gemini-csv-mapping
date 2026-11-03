"""Explicit recovery of unfinished tasks, retaining failed attempts and completed work."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import statistics
import time

import compare_models as benchmark


def pending_tasks(records, tasks, models, repeats):
    done = {(r["model_id"], r["task_id"], r["repeat"]) for r in records if not r.get("error")}
    return [(model, task, repetition) for repetition in range(1, repeats + 1)
            for task in tasks for model in models
            if (model["id"], task["id"], repetition) not in done]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_folder", type=Path)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    folder = args.run_folder.resolve()
    permitted = (benchmark.ROOT / "output/model_comparison").resolve()
    if not folder.is_relative_to(permitted) or args.timeout < 1:
        parser.error("Select a comparison run inside this project and a positive timeout")
    report = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    tasks = json.loads((folder / "tasks_and_expectations.json").read_text(encoding="utf-8"))
    catalog = json.loads((folder / "catalog_snapshot.json").read_text(encoding="utf-8"))
    if report["runner_sha256"] != benchmark.digest(Path(benchmark.__file__)):
        raise SystemExit("Comparison runner changed; do not combine results across implementations")
    if report["mapper_sha256"] != benchmark.digest(benchmark.ROOT / "jev.py"):
        raise SystemExit("Mapper changed; use a new benchmark run")
    models = report["models"]
    repeats = max(r["repeat"] for r in report["records"])
    remaining = pending_tasks(report["records"], tasks, models, repeats)
    if not remaining:
        print("No unfinished tasks; no inference calls made.")
        return
    for task in tasks:
        if benchmark.digest(benchmark.ROOT / task["input"]) != task["fixture_sha256"]:
            raise SystemExit("Fixture changed; do not combine results")
    benchmark.load_environment()
    config = json.loads((benchmark.HERE / "models.json").read_text(encoding="utf-8"))
    config["timeout_seconds"] = args.timeout
    model_lookup = {m["id"]: m for m in models}
    task_lookup = {t["id"]: t for t in tasks}
    used = sum(r["cost_usd"] if r.get("cost_usd") is not None else
               benchmark.reserve_cost(model_lookup[r["model_id"]], task_lookup[r["task_id"]], catalog, config["max_output_tokens"])
               for r in report["records"])
    reserved = sum(benchmark.reserve_cost(m, t, catalog, config["max_output_tokens"]) for m, t, _ in remaining)
    if used + reserved > report["budget_usd"]:
        raise SystemExit("Remaining work exceeds the original budget guard; no inference calls made")
    if any(m["adapter"] == "openrouter" for m, _, _ in remaining) and not benchmark.os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OpenRouter key unavailable; no inference calls made")
    history = folder / "attempt_history"
    history.mkdir(exist_ok=True)
    event_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    for name in ("results.json", "REPORT.md", "summary.csv"):
        shutil.copy2(folder / name, history / f"{event_id}_{name}")
    report.setdefault("recoveries", []).append({"started_utc": datetime.now(timezone.utc).isoformat(),
        "pending_tasks": len(remaining), "timeout_seconds": args.timeout,
        "recovery_script_sha256": benchmark.digest(Path(__file__)), "reservation_usd": reserved})
    report["status"] = "resuming_unfinished_tasks"
    import httpx
    benchmark.ROUTER_CLIENT = httpx.Client(timeout=args.timeout)
    jev_client = None
    if any(m["adapter"] == "jev" for m, _, _ in remaining):
        from jev_lite import TypeSafe
        jev_client = TypeSafe(max_retries=0, timeout=args.timeout, cache=None)
    print(f"Resuming {len(remaining)} unfinished tasks; original attempts retained; reservation ${reserved:.4f}.", flush=True)
    try:
        for index, (model, task, repetition) in enumerate(remaining, 1):
            start = time.perf_counter()
            try:
                result = benchmark.jev_call(model, task, jev_client) if model["adapter"] == "jev" else benchmark.openrouter_call(model, task, catalog, config)
                if not result.get("error"):
                    result.update(benchmark.score_answer(result["scores"], task))
            except Exception as exc:
                result = {"error": str(exc) if isinstance(exc, benchmark.RequestFailure) else type(exc).__name__,
                          "seconds": time.perf_counter() - start, "cost_usd": None, "cost_kind": "unknown"}
            result.update(model_id=model["id"], task_id=task["id"], expected=task["expected"],
                          repeat=repetition, explicit_recovery=event_id)
            report["records"].append(result)
            report["summary"] = benchmark.summarize(report["records"], models, tasks, repeats)
            benchmark.save_results(folder, report)
            print(f"[{index}/{len(remaining)}] {model['label']}: {task['id']} — {'ERROR' if result.get('error') else 'recorded'}", flush=True)
            if result.get("error") or result.get("cost_usd") is None:
                report["status"] = "incomplete_recovery_error"
                break
        else:
            report["status"] = "completed_with_recovered_attempts"
        report["summary"] = benchmark.summarize(report["records"], models, tasks, repeats)
        for summary in report["summary"]:
            successes = [r for r in report["records"] if r["model_id"] == summary["model_id"] and not r.get("error")]
            times = [r["seconds"] for r in successes]
            summary["median_successful_seconds"] = statistics.median(times) if times else None
            summary["p95_successful_seconds"] = benchmark.percentile95(times)
            summary["unknown_cost_attempts"] = sum(r.get("cost_usd") is None for r in report["records"] if r["model_id"] == summary["model_id"])
        benchmark.save_results(folder, report)
        # Keep the initial partial CSV exports too, rather than overwriting them.
        mapped = folder / "mapped_outputs"
        if mapped.exists():
            mapped.rename(history / f"{event_id}_partial_mapped_outputs")
        benchmark.export_mapped_outputs(folder, report["records"], tasks)
        print("Updated report:", folder / "REPORT.md", flush=True)
    finally:
        benchmark.ROUTER_CLIENT.close()
        benchmark.ROUTER_CLIENT = None
        if jev_client:
            jev_client.close()


if __name__ == "__main__":
    main()
