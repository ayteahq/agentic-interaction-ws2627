"""Offline-Prüfungen für JSONL-Logging; keine echten API-Aufrufe."""

import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from openai.types.chat import ChatCompletion

from agent.__main__ import _run, run_agent
from agent.run_logging import RunLog


class LoggingTests(unittest.TestCase):
    def setUp(self):
        logs = Path(__file__).resolve().parent.parent / "logs"
        logs.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(dir=logs)
        self.addCleanup(self.directory.cleanup)
        self.log = RunLog(Path(self.directory.name))
        self.addCleanup(self.log.close)
        self.log.model = "configured-test-model"

    def records(self):
        return [json.loads(line) for line in self.log.path.read_text(encoding="utf-8").splitlines()]

    def test_schema_unique_files_and_sensitive_arguments(self):
        self.log.write("tool_call", date="Authorization: Bearer secret", tool=True)
        self.log.write("error", ok=False, code="unexpected")
        other = RunLog(Path(self.directory.name))
        other.close()
        self.assertNotEqual(self.log.path, other.path)
        for row in self.records():
            self.assertEqual(row["model"], "configured-test-model")
            self.assertIsNotNone(datetime.fromisoformat(row["ts"]).utcoffset())
            self.assertGreaterEqual(row["duration_ms"], 0)
        self.assertEqual(self.records()[0]["args"], {})
        self.assertNotIn("secret", self.log.path.read_text())

    def test_failed_run_writes_error_without_raw_exception(self):
        with patch("sys.argv", ["agent", "Authorization: Bearer TASK_SECRET"]), \
             patch("agent.__main__.load_config", side_effect=RuntimeError("API_KEY_SECRET")), \
             patch("agent.__main__.load_dotenv"), \
             patch.dict("os.environ", {"MODEL": "configured-test-model"}), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(_run(self.log), 1)
        rows = self.records()
        self.assertEqual([r["event"] for r in rows], ["user_task", "error"])
        self.assertFalse(rows[-1]["ok"])
        self.assertNotIn("SECRET", self.log.path.read_text())

    def test_tool_error_and_final_model_step(self):
        first = ChatCompletion.model_validate({
            "id": "first", "object": "chat.completion", "created": 0, "model": "test",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None, "tool_calls": [{"id": "call1",
                "type": "function", "function": {"name": "get_calendar_events",
                "arguments": '{"date":"2026-10-29"}'}}]}}]})
        final = ChatCompletion.model_validate({
            "id": "final", "object": "chat.completion", "created": 0, "model": "test",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "Abruf fehlgeschlagen. RAW_SECRET"}}]})
        config = {"MODEL": "configured-test-model", "OPENAI_API_KEY": "test-only",
                  "OPENAI_BASE_URL": "https://model.invalid", "DATA_BASE_URL": "https://data.invalid"}
        with patch("agent.__main__.OpenAI") as cls, \
             patch("agent.__main__.execute_tool", return_value={"status": "error", "error": "RAW_SECRET"}):
            client = cls.return_value.__enter__.return_value
            client.chat.completions.create.side_effect = [first, final]
            run_agent("TASK_SECRET", config, self.log)
            self.assertEqual(client.chat.completions.create.call_count, 2)
            messages = client.chat.completions.create.call_args.kwargs["messages"]
            self.assertEqual(messages[-1]["tool_call_id"], "call1")
        rows = self.records()
        self.assertEqual([r["event"] for r in rows], ["tool_call", "tool_result", "error"])
        self.assertFalse(rows[1]["ok"])
        self.assertEqual(rows[1]["args"], {"date": "2026-10-29"})
        self.assertNotIn("SECRET", self.log.path.read_text())


if __name__ == "__main__":
    unittest.main()
