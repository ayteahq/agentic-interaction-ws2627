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

from agent.__main__ import AgentError, _run, load_config, main, run_agent
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
        self.log.write("tool_call", date="Authorization: Bearer secret", tool="get_calendar_events")
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


    def test_help_writes_nonempty_log_without_model_call(self):
        output = io.StringIO()
        with patch("sys.argv", ["agent", "--help"]), \
             patch("agent.__main__.RunLog", return_value=self.log), \
             patch("agent.__main__.load_config") as config, \
             patch("agent.__main__.OpenAI") as client, \
             contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertIn("prompt", output.getvalue())
        config.assert_not_called()
        client.assert_not_called()
        self.assertEqual(self.records()[0]["event"], "final")
        self.assertEqual(self.records()[0]["code"], "help")
        self.assertTrue(self.records()[0]["ok"])

    def test_configuration_validation_and_environment_priority(self):
        config = {"MODEL": "environment-model", "OPENAI_API_KEY": "fake-local-test",
                  "OPENAI_BASE_URL": "https://model.invalid", "DATA_BASE_URL": "https://data.invalid"}
        with patch.dict("os.environ", config), patch("agent.__main__.load_dotenv"):
            self.assertEqual(load_config(), config)
            for invalid in ("", "https://[", "file:///tmp/model"):
                with patch.dict("os.environ", {"OPENAI_BASE_URL": invalid}):
                    with self.assertRaises(AgentError) as error:
                        load_config()
                    self.assertEqual(error.exception.code, "configuration")

    def test_error_categories(self):
        for category in ("configuration", "model_response", "tool_error"):
            with self.subTest(category=category), \
                 patch("sys.argv", ["agent", "Frage"]), \
                 patch("agent.__main__.load_config", return_value={"MODEL": "test"}), \
                 patch("agent.__main__.run_agent", side_effect=AgentError("RAW_SECRET", code=category)), \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(_run(self.log), 1)
                self.assertEqual(self.records()[-1]["code"], category)
        self.assertNotIn("RAW_SECRET", self.log.path.read_text())

    def test_actual_unknown_tool_name_and_model_response_error(self):
        first = ChatCompletion.model_validate({
            "id": "first", "object": "chat.completion", "created": 0, "model": "test",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "tool_calls": [{"id": "unknown1", "type": "function",
                "function": {"name": "unknown_calendar_tool", "arguments": '{"date":"2026-10-29"}'}}]}}]})
        final = first.model_copy(deep=True)
        final.choices[0].message.tool_calls = None
        final.choices[0].message.content = "Unbekanntes Tool."
        config = {"MODEL": "test", "OPENAI_API_KEY": "fake", "OPENAI_BASE_URL": "https://model.invalid",
                  "DATA_BASE_URL": "https://data.invalid"}
        with patch("agent.__main__.OpenAI") as cls:
            client = cls.return_value.__enter__.return_value
            client.chat.completions.create.side_effect = [first, final]
            with patch("agent.__main__.get_calendar_events") as calendar:
                run_agent("Frage", config, self.log)
                calendar.assert_not_called()
            self.assertEqual(client.chat.completions.create.call_args.kwargs["messages"][-1]["tool_call_id"], "unknown1")
            for row in self.records():
                self.assertEqual(row["tool"], "unknown_calendar_tool")
            self.assertEqual(self.records()[-1]["code"], "tool_error")
            client.chat.completions.create.side_effect = [final]
            with self.assertRaises(AgentError) as error:
                run_agent("Frage", config, self.log)
            self.assertEqual(error.exception.code, "model_response")

    def test_tool_exception_is_classified(self):
        first = ChatCompletion.model_validate({
            "id": "first", "object": "chat.completion", "created": 0, "model": "test",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "tool_calls": [{"id": "call1", "type": "function",
                "function": {"name": "get_calendar_events", "arguments": '{"date":"2026-10-29"}'}}]}}]})
        config = {"MODEL": "test", "OPENAI_API_KEY": "fake", "OPENAI_BASE_URL": "https://model.invalid",
                  "DATA_BASE_URL": "https://data.invalid"}
        with patch("agent.__main__.OpenAI") as cls, \
             patch("agent.__main__.execute_tool", side_effect=RuntimeError("RAW_SECRET")):
            cls.return_value.__enter__.return_value.chat.completions.create.return_value = first
            with self.assertRaises(AgentError) as error:
                run_agent("Frage", config, self.log)
            self.assertEqual(error.exception.code, "tool_error")
            self.assertEqual(error.exception.tool, "get_calendar_events")
            self.assertEqual(self.records()[-1]["event"], "tool_result")
            self.assertFalse(self.records()[-1]["ok"])

    def test_tool_and_model_names_redact_known_secrets(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "credential_canary"}):
            self.log.model = "model-credential_canary"
            self.log.write("tool_call", tool="credential_canary")
            self.log.write("error", tool="Authorization: Bearer credential_canary", ok=False)
        self.assertNotIn("credential_canary", self.log.path.read_text())
        self.assertNotIn("Authorization", self.log.path.read_text())


if __name__ == "__main__":
    unittest.main()
