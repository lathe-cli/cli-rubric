import importlib.util
import unittest
from pathlib import Path
from unittest import mock

RUNNER_PATH = Path(__file__).with_name("run.py")
SPEC = importlib.util.spec_from_file_location("three_cli_runner", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class AwireStateTest(unittest.TestCase):
    def test_known_channel_uses_get_and_accepts_not_found_as_absent(self):
        channel_id = "fixture-id"
        result = {
            "argv": [
                "awirectl",
                "channels",
                "get",
                "--id",
                channel_id,
                "-o",
                "json",
            ],
            "started_at": "2026-08-04T00:00:00Z",
            "duration_ms": 1,
            "termination": "exit",
            "exit_code": 3,
            "stdout": "",
            "stderr": '{"error":{"message":"HTTP 404: channel not found"}}',
        }

        with mock.patch.object(RUNNER, "invoke", return_value=result) as invoke:
            state = RUNNER.awire_channel_state(
                [],
                "fixture-name",
                channel_id,
                "task",
                "state",
                expected_exists=False,
            )

        self.assertEqual(state, {"matching_channels": []})
        invoke.assert_called_once_with(result["argv"])


if __name__ == "__main__":
    unittest.main()
