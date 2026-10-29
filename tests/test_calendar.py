"""Regressionen für deterministische deutsche Wochentage und Tool-Übergabe."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from openai.types.chat import ChatCompletion

from agent.calendar import get_calendar_events, get_weekday
from agent.__main__ import run_agent


class WeekdayTests(unittest.TestCase):
    def test_requested_dates(self):
        for date, expected in {
            "2026-10-26": "Montag",
            "2026-10-29": "Donnerstag",
            "2026-10-30": "Freitag",
            "2026-11-01": "Sonntag",
            "2026-11-08": "Sonntag",
        }.items():
            with self.subTest(date=date):
                self.assertEqual(get_weekday(date), expected)

    def test_leap_day_and_invalid_dates(self):
        self.assertEqual(get_weekday("2024-02-29"), "Donnerstag")
        for date in ("2026-02-29", "2026-02-30", "20261026", "26.10.2026", "../secret", None):
            with self.subTest(date=date), patch("agent.calendar.urlopen") as http:
                with self.assertRaises(ValueError):
                    get_weekday(date)
                result = get_calendar_events(date, data_base_url="https://data.invalid")
                self.assertEqual(result["status"], "error")
                self.assertNotIn("weekday_de", result)
                http.assert_not_called()

    def test_weekday_is_independent_of_http_result(self):
        for payload in (b'{"events": []}', b'{"weekday_de": "Freitag", "events": []}'):
            with self.subTest(payload=payload), patch("agent.calendar.urlopen") as http:
                http.return_value.__enter__.return_value = io.BytesIO(payload)
                result = get_calendar_events("2026-10-26", data_base_url="https://data.invalid/")
                self.assertEqual(result["weekday_de"], "Montag")
                self.assertEqual(result["data"], json.loads(payload))
                self.assertEqual(http.call_args.args[0].full_url, "https://data.invalid/calendar/2026-10-26.json")
                self.assertEqual(http.call_args.args[0].method, "GET")
        for exception, status in ((HTTPError("https://data.invalid", 404, "", {}, None), "not_found"),
                                  (HTTPError("https://data.invalid", 500, "", {}, None), "error"),
                                  (URLError("offline"), "error")):
            with self.subTest(status=status), patch("agent.calendar.urlopen", side_effect=exception):
                result = get_calendar_events("2026-10-26", data_base_url="https://data.invalid")
                self.assertEqual(result["weekday_de"], "Montag")
                self.assertEqual(result["status"], status)
        with patch("agent.calendar.urlopen") as http:
            http.return_value.__enter__.return_value = io.BytesIO(b'not json')
            result = get_calendar_events("2026-10-26", data_base_url="https://data.invalid")
            self.assertEqual(result["weekday_de"], "Montag")
            self.assertEqual(result["status"], "error")

    def test_calculated_weekday_reaches_second_model_with_tool_call_id(self):
        first = ChatCompletion.model_validate({
            "id": "first", "object": "chat.completion", "created": 0, "model": "test",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "tool_calls": [{"id": "date-call", "type": "function",
                "function": {"name": "get_calendar_events", "arguments": '{"date":"2026-10-26"}'}}]}}]})
        final = first.model_copy(deep=True)
        final.choices[0].message.tool_calls = None
        final.choices[0].message.content = "Der 26.10.2026 ist ein Montag."
        config = {"MODEL": "test", "OPENAI_API_KEY": "fake", "OPENAI_BASE_URL": "https://model.invalid",
                  "DATA_BASE_URL": "https://data.invalid"}
        with patch("agent.__main__.OpenAI") as cls, patch("agent.calendar.urlopen") as http:
            client = cls.return_value.__enter__.return_value
            client.chat.completions.create.side_effect = [first, final]
            http.return_value.__enter__.return_value = io.BytesIO(b'{"events": []}')
            run_agent("Welcher Wochentag ist der 26.10.2026?", config, MagicMock())
            self.assertEqual(client.chat.completions.create.call_count, 2)
            messages = client.chat.completions.create.call_args.kwargs["messages"]
            self.assertEqual(messages[-1]["tool_call_id"], "date-call")
            result = json.loads(messages[-1]["content"])
            self.assertEqual(result["date"], "2026-10-26")
            self.assertEqual(result["weekday_de"], "Montag")
            self.assertIn("niemals selbst erraten", messages[0]["content"])
            self.assertIn("bei reinen Terminfragen lasse ihn weg", messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
