import copy
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
runner = importlib.import_module("run")
scorer = importlib.import_module("score")


class ValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = runner.load_json(runner.PROTOCOL_PATH)
        cls.profile = runner.load_json(runner.PROFILE_PATH)
        cls.task_pack = runner.load_json(runner.TASK_PACK_PATH)

    def test_frozen_contract_and_weights(self):
        runner.verify_frozen_inputs(
            self.protocol,
            self.profile,
            self.task_pack,
        )
        changed = copy.deepcopy(self.protocol)
        changed["dimensions"]["A1"]["weight"] = 0.41
        with self.assertRaises(scorer.ValidationError):
            scorer.validate_protocol(changed, self.task_pack)

    def test_diagnostic_projection_preserves_known_groups_order(self):
        values = {"degraded": 0.2, "neutral": 0.6, "improved": 1.0}
        bundles = [
            self.synthetic_bundle(subject, value) for subject, value in values.items()
        ]
        projection = scorer.project_bundles(
            bundles,
            self.protocol,
            self.task_pack,
        )
        self.assertEqual(
            projection["known_groups"]["observed_order"],
            ["degraded", "neutral", "improved"],
        )
        self.assertTrue(projection["known_groups"]["matches"])
        self.assertEqual(projection["score_status"], "unscored")
        self.assertEqual(projection["reconstruction_status"], "pass")
        self.assertNotIn("status", projection)

    def test_qualification_status_requires_valid_trials_and_known_groups(self):
        projection = {"known_groups": {"matches": True}}
        self.assertEqual(
            runner.qualification_status("pass", 9, 9, projection),
            "pass",
        )
        self.assertEqual(
            runner.qualification_status("pass", 8, 9, projection),
            "fail",
        )
        projection["known_groups"]["matches"] = False
        self.assertEqual(
            runner.qualification_status("pass", 9, 9, projection),
            "fail",
        )

    def test_artifact_paths_cannot_escape_the_bundle(self):
        with self.assertRaises(scorer.ValidationError):
            scorer.resolve_uri(
                "../outside",
                runner.PROFILE_PATH,
                runner.REPO_ROOT,
            )

    def test_false_success_still_counts_as_unsupported_guess(self):
        records = [
            {"argv": ["--help"]},
            {"argv": ["resources", "list"], "exit_code": 0, "stdout": "no\n"},
            {"argv": ["lsr"], "exit_code": 0, "stdout": "alpha\n"},
        ]
        self.assertEqual(
            runner.unsupported_guess_count(records, {("lsr",)}),
            1,
        )

    def test_cli_context_excludes_agent_system_tokens(self):
        records = [
            {"stdout": "no\n", "stderr": ""},
            {"stdout": "", "stderr": "hint\n"},
        ]
        self.assertEqual(runner.cli_context_bytes(records), 8)

    def test_shell_chaining_invalidates_blinding(self):
        items = [{"command": ("/bin/zsh -lc './subject --help; cat .subject.json'")}]
        self.assertEqual(runner.prohibited_actor_commands(items), [items[0]["command"]])

    def test_timeout_capture_remains_json_serializable(self):
        task = next(
            task for task in self.task_pack["tasks"] if task["id"] == "list-resources"
        )
        timeout = subprocess.TimeoutExpired(
            ["codex"],
            1,
            output=b'{"type":"turn.started"}\n',
            stderr=b"timed out\n",
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(runner.shutil, "which", return_value="/usr/bin/codex"),
            mock.patch.object(runner.subprocess, "run", side_effect=timeout),
        ):
            capture = runner.execute_actor(task, Path(directory))
        self.assertEqual(capture["termination"], "timeout")
        self.assertIsInstance(capture["stdout"], str)
        self.assertIsInstance(capture["stderr"], str)
        json.dumps(capture)

    def test_trial_classification_separates_integrity_outcome_and_cost(self):
        task = next(
            task for task in self.task_pack["tasks"] if task["id"] == "list-resources"
        )
        capture = {
            "commands": [],
            "records": [],
            "tokens": {
                "input_tokens": self.profile["budgets"]["max_input_tokens"] + 1,
                "output_tokens": 1,
            },
            "termination": "exit",
            "exit_code": 0,
            "response": {
                "completed": True,
                "state_verified": True,
                "error_recovered": False,
                "observed": {},
                "summary": "done",
            },
        }

        token_overage = runner.classify_trial(capture, task, self.profile)
        self.assertTrue(token_overage["valid"])
        self.assertFalse(token_overage["outcome_failed"])

        command_overage = copy.deepcopy(capture)
        command_overage["records"] = [{}] * (task["budget"]["max_commands"] + 1)
        command_classification = runner.classify_trial(
            command_overage,
            task,
            self.profile,
        )
        self.assertTrue(command_classification["valid"])
        self.assertTrue(command_classification["outcome_failed"])

        tool_overage = copy.deepcopy(capture)
        tool_overage["commands"] = [{"command": "/bin/zsh -lc './subject --help'"}] * (
            self.profile["budgets"]["max_tool_calls"] + 1
        )
        tool_classification = runner.classify_trial(
            tool_overage,
            task,
            self.profile,
        )
        self.assertTrue(tool_classification["valid"])
        self.assertTrue(tool_classification["outcome_failed"])

        missing_response = copy.deepcopy(capture)
        missing_response["response"] = None
        response_classification = runner.classify_trial(
            missing_response,
            task,
            self.profile,
        )
        self.assertTrue(response_classification["valid"])
        self.assertTrue(response_classification["outcome_failed"])

        contaminated = copy.deepcopy(capture)
        contaminated["commands"] = [{"command": "/bin/zsh -lc 'cat .subject.json'"}]
        self.assertFalse(
            runner.classify_trial(contaminated, task, self.profile)["valid"]
        )

    def test_budget_failure_remains_in_measurements_as_failed_outcome(self):
        task = next(
            task for task in self.task_pack["tasks"] if task["id"] == "list-resources"
        )
        state = copy.deepcopy(self.task_pack["fixture"]["initial_state"])
        record = {
            "argv": ["resource", "list"],
            "exit_code": 0,
            "stdout": "alpha Alpha active beta Beta paused",
            "stderr": "",
            "before": state,
            "after": state,
        }
        outcome_correct, grader_correct, _, measurements = runner.build_measurements(
            task,
            self.task_pack,
            "improved",
            state,
            state,
            [record],
            None,
            [{"command": "./subject resource list"}],
            1,
            outcome_failed=True,
        )
        self.assertFalse(outcome_correct)
        self.assertTrue(grader_correct)
        a1 = {
            item["measure_id"]: item["normalized_value"]
            for item in measurements
            if item["construct_id"] == "A1"
        }
        self.assertEqual(a1, {"task_completion": 0.0, "result_correctness": 0.0})

    def test_qualification_tasks_require_complete_measure_sets(self):
        registry = scorer.measure_registry(self.protocol)
        task_ids = [task["id"] for task in self.task_pack["tasks"]]
        self.assertEqual(
            len(
                scorer.expected_measure_keys(
                    registry,
                    "list-resources",
                    task_ids,
                )
            ),
            11,
        )
        self.assertEqual(
            len(
                scorer.expected_measure_keys(
                    registry,
                    "recover-invalid-create",
                    task_ids,
                )
            ),
            12,
        )

    def test_state_verification_requires_a_post_change_cli_read(self):
        initial = copy.deepcopy(self.task_pack["fixture"]["initial_state"])
        final = copy.deepcopy(initial)
        final["resources"].append(
            {
                "id": "delta",
                "name": "Delta",
                "status": "active",
                "labels": {"team": "core"},
            }
        )
        mutation = {
            "argv": [
                "resource",
                "create",
                "--id",
                "delta",
                "--name",
                "Delta",
            ],
            "exit_code": 0,
            "stdout": "{}",
            "before": initial,
            "after": final,
        }
        self.assertFalse(
            runner.has_cli_state_verification(
                "recover-invalid-create",
                initial,
                final,
                [mutation],
            )
        )
        verification = {
            "argv": ["resource", "show", "delta"],
            "exit_code": 0,
            "stdout": "delta Delta active team core",
            "before": final,
            "after": final,
        }
        self.assertTrue(
            runner.has_cli_state_verification(
                "recover-invalid-create",
                initial,
                final,
                [mutation, verification],
            )
        )

    def synthetic_bundle(self, subject, value):
        trials = []
        registry = scorer.measure_registry(self.protocol)
        for task in self.task_pack["tasks"]:
            measurements = []
            for measure_id, definition in registry.items():
                if task["id"] not in scorer.applicable_tasks(
                    definition,
                    [item["id"] for item in self.task_pack["tasks"]],
                ):
                    continue
                measurements.append(
                    {
                        "construct_id": definition["construct_id"],
                        "measure_id": measure_id,
                        "normalized_value": value,
                    }
                )
            trials.append(
                {
                    "id": f"{subject}-{task['id']}",
                    "task_id": task["id"],
                    "actor_id": "actor",
                    "valid": True,
                    "measurements": measurements,
                    "critical_events": [],
                }
            )
        return {
            "subject": {"name": subject},
            "method": {"protocol_deviations": []},
            "trials": trials,
        }


if __name__ == "__main__":
    unittest.main()
