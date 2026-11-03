"""Offline tests for the evaluator and adapters. These are NOT model benchmark results."""
import json
import csv
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import compare_models as benchmark
import resume_comparison as recovery


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tasks = benchmark.build_tasks()
        self.task = self.tasks[0]

    def scores(self, task=None, high=.96):
        task = task or self.task
        result = {key: .01 for key in task["questions"]}
        expected = task["expected"]["source"]
        result[f"candidate_{task['columns'].index(expected)}"] = high
        return result

    def test_coverage_and_no_answers_in_model_payload(self):
        self.assertEqual(len(self.tasks), 14)
        self.assertEqual(sum(t["expected"]["policy"] == "map" for t in self.tasks), 10)
        self.assertEqual({t["field"] for t in self.tasks}, set(benchmark.definitions()))
        for task in self.tasks:
            payload = json.dumps({"state": task["state"], "questions": task["questions"]})
            for key in ('"expected"', '"policy"', '"source":'):
                self.assertNotIn(key, payload)
        self.assertIn("supplier_a.csv", benchmark.definitions()["price_usd"])
        self.assertIn("All source headings:", self.task["state"])
        self.assertIn("Sample values:", self.task["questions"]["candidate_0"]["instructions"])

    def test_full_case_selection_maps_all_seven_fields_per_file(self):
        tasks = benchmark.build_tasks(["01_clean_synonyms", "02_shuffled_distractors"])
        self.assertEqual(len(tasks), 14)
        for case in {task["case"] for task in tasks}:
            self.assertEqual({task["field"] for task in tasks if task["case"] == case}, set(benchmark.definitions()))
        with self.assertRaises(ValueError):
            benchmark.build_tasks(["not-a-fixture"])

    def test_recovery_only_selects_failed_or_unrun_tasks(self):
        tasks = self.tasks[:3]
        models = [{"id": "offline"}]
        records = [{"model_id": "offline", "task_id": tasks[0]["id"], "repeat": 1},
                   {"model_id": "offline", "task_id": tasks[1]["id"], "repeat": 1, "error": "timeout"}]
        pending = recovery.pending_tasks(records, tasks, models, 1)
        self.assertEqual([task["id"] for _, task, _ in pending], [tasks[1]["id"], tasks[2]["id"]])
        self.assertEqual(len(records), 2)
        records += [{"model_id": "offline", "task_id": task["id"], "repeat": 1} for task in tasks[1:]]
        self.assertEqual(recovery.pending_tasks(records, tasks, models, 1), [])

    def test_full_case_output_copies_only_accepted_sources(self):
        tasks = benchmark.build_tasks(["01_clean_synonyms"])
        records = []
        for task in tasks:
            scores = self.scores(task)
            if task["field"] == "price_usd":
                scores = self.scores(task, high=.83)
            records.append({"model_id": "offline/dummy", "repeat": 1, "task_id": task["id"],
                            **benchmark.score_answer(scores, task)})
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            benchmark.export_mapped_outputs(folder, records, tasks)
            output = folder / "mapped_outputs/offline_dummy/repeat_1/01_clean_synonyms"
            with (output / "all_supplier_data.csv").open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                self.assertEqual(reader.fieldnames, ["supplier", *benchmark.definitions()])
            self.assertEqual(len(rows), 100)
            self.assertEqual(rows[0]["supplier"], "VARIANT")
            self.assertEqual(rows[0]["supplier_product_id"], "V-00001")
            self.assertEqual(rows[0]["stock_quantity"], "0")
            self.assertEqual(rows[0]["price_usd"], "")
            self.assertTrue((output / "field_mapping_review.csv").exists())

    def test_explicit_local_key_overrides_inherited_key_without_printing(self):
        with patch.dict(benchmark.os.environ, {"OPENROUTER_API_KEY": "offline-inherited-dummy"}):
            with patch.object(Path, "exists", return_value=True), patch.object(Path, "read_text", return_value="OPENROUTER_API_KEY=offline-local-dummy\nTYPESAFE_API_KEY=\n"):
                benchmark.load_environment()
            self.assertEqual(benchmark.os.environ["OPENROUTER_API_KEY"], "offline-local-dummy")

    def test_low_confidence_correct_rank_is_not_wrong_rank(self):
        result = benchmark.score_answer(self.scores(high=.83), self.task)
        self.assertTrue(result["rank_correct"])
        self.assertFalse(result["decision_correct"])
        self.assertEqual(result["status"], "human_review")
        self.assertFalse(result["false_accepted_mapping"])

    def test_wrong_confident_mapping_is_caught(self):
        scores = self.scores()
        expected = f"candidate_{self.task['columns'].index(self.task['expected']['source'])}"
        other = next(key for key in scores if key != expected)
        scores[expected], scores[other] = .02, .99
        result = benchmark.score_answer(scores, self.task)
        self.assertFalse(result["rank_correct"])
        self.assertTrue(result["false_accepted_mapping"])

    def test_tie_is_not_counted_as_correct_rank(self):
        scores = self.scores()
        other = next(key for key, value in scores.items() if value == .01)
        scores[other] = .96
        result = benchmark.score_answer(scores, self.task)
        self.assertFalse(result["rank_correct"])
        self.assertEqual(result["status"], "human_review")

    def test_no_match_and_review_are_distinct(self):
        task = next(t for t in self.tasks if t["expected"]["policy"] == "review")
        scores = {key: .01 for key in task["questions"]}
        self.assertFalse(benchmark.score_answer(scores, task)["decision_correct"])
        scores["candidate_0"] = .7
        self.assertTrue(benchmark.score_answer(scores, task)["decision_correct"])
        scores["candidate_0"] = .99
        self.assertTrue(benchmark.score_answer(scores, task)["false_accepted_mapping"])

    def test_missing_invalid_and_nonfinite_scores_fail(self):
        for bad in [True, float('nan'), float('inf'), -.1, 1.1, '0.9']:
            scores = self.scores()
            scores["candidate_0"] = bad
            with self.assertRaises(ValueError):
                benchmark.validate_scores(scores, self.task)
        with self.assertRaises(ValueError):
            benchmark.validate_scores({}, self.task)

    def test_missing_answers_stay_in_denominators(self):
        model = {"id": "offline", "label": "Offline mock"}
        summary = benchmark.summarize([], [model], self.tasks, 1)[0]
        self.assertEqual(summary["ranking_total"], 10)
        self.assertEqual(summary["planned"], 14)
        self.assertEqual(summary["ranking_accuracy_pct"], 0)
        self.assertIsNone(summary["known_cost_usd"])

    def test_raw_string_identifiers_preserve_leading_zeros(self):
        path = benchmark.ROOT / "data/26-10-2026-variants/14_leading_zero_ids/supplier_variant.csv"
        import csv
        with path.open(newline="", encoding="utf-8") as stream:
            self.assertEqual(next(csv.DictReader(stream))["Supplier_item_ID"], "0000001")

    def test_public_catalog_and_reservations(self):
        config = json.loads((benchmark.HERE / "models.json").read_text())
        catalog = json.loads((benchmark.HERE / "catalog_snapshot.json").read_text(encoding="utf-8"))
        total = 0
        for model in config["models"]:
            if model["enabled"]:
                for task in self.tasks:
                    cost = benchmark.reserve_cost(model, task, catalog, config["max_output_tokens"])
                    self.assertGreater(cost, 0)
                    total += cost
        self.assertLess(total, config["max_total_usd"])

    def test_openrouter_adapter_sends_same_evidence_and_keeps_cost_on_bad_json(self):
        model = {"id": "offline", "adapter": "openrouter"}
        catalog = {"models": {"offline": {"supported_parameters": [], "reasoning": {}}}}
        raw = {"model": "offline", "usage": {"cost": .001},
               "choices": [{"finish_reason": "stop", "message": {"content": "not JSON"}}]}
        config = {"max_output_tokens": 1024, "timeout_seconds": 1}
        with patch.dict(benchmark.os.environ, {"OPENROUTER_API_KEY": "offline-dummy-not-a-key"}):
            with patch.object(benchmark, "json_request", return_value=raw) as mocked:
                result = benchmark.openrouter_call(model, self.task, catalog, config)
        body = mocked.call_args.args[1]
        content = json.loads(body["messages"][1]["content"])
        self.assertEqual(content["state"], self.task["state"])
        self.assertEqual(content["questions"], self.task["questions"])
        self.assertNotIn("expected", content)
        self.assertFalse(body["provider"]["allow_fallbacks"])
        self.assertEqual(result["cost_usd"], .001)
        self.assertIn("error", result)

    def test_jev_adapter_passes_explicit_model_and_same_state(self):
        answers = {key: SimpleNamespace(noul=value) for key, value in self.scores().items()}
        raw = SimpleNamespace(model="jev-offline", nouls=answers,
                              usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 100, "output_tokens": 10}))
        from unittest.mock import Mock
        client = Mock()
        client.system_one.create.return_value = raw
        model = {"id": "jev-offline", "input_per_million": .042}
        result = benchmark.jev_call(model, self.task, client)
        self.assertEqual(client.system_one.create.call_args.kwargs["state"], self.task["state"])
        self.assertEqual(client.system_one.create.call_args.kwargs["model"], "jev-offline")
        self.assertAlmostEqual(result["cost_usd"], .0000042)


if __name__ == "__main__":
    unittest.main()
