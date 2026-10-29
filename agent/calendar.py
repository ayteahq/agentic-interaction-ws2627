"""Nur lesender Zugriff auf die simulierten HTTP-Kalenderdaten."""

import json
import re
from datetime import date as calendar_date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WEEKDAYS_DE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


def get_weekday(date: str) -> str:
    """Berechnet den deutschen Wochentag unabhängig von System-Locale und LLM."""
    if not isinstance(date, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date):
        raise ValueError("Datum muss das Format YYYY-MM-DD haben.")
    return WEEKDAYS_DE[calendar_date.fromisoformat(date).weekday()]


TOOL = {
    "type": "function",
    "function": {
        "name": "get_calendar_events",
        "description": "Liest simulierte Kalenderdaten für einen bestimmten Tag und liefert den mit Python berechneten deutschen Wochentag weekday_de. Verändert keine Termine.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Kalendertag im Format YYYY-MM-DD, z. B. 2026-10-29.",
                    "pattern": r"^\d{4}-\d{2}-\d{2}$",
                }
            },
            "required": ["date"],
            "additionalProperties": False,
        },
    },
}


def get_calendar_events(date: str, *, data_base_url: str) -> dict:
    """Liefert JSON-Daten oder einen strukturierten Fehler ohne sensible Details."""
    try:
        weekday = get_weekday(date)
    except ValueError:
        return {"status": "error", "error": "Ungültiges Datum; erwartet wird YYYY-MM-DD."}

    date_info = {"date": date, "weekday_de": weekday}
    url = f"{data_base_url.rstrip('/')}/calendar/{date}.json"
    try:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
        return {"status": "ok", **date_info, "data": data}
    except HTTPError as exc:
        if exc.code == 404:
            return {"status": "not_found", **date_info,
                    "message": "Für diesen Tag sind keine Kalenderdaten vorhanden."}
        return {"status": "error", **date_info, "error": f"Kalenderabruf: HTTP {exc.code}."}
    except (json.JSONDecodeError, UnicodeError):
        return {"status": "error", **date_info, "error": "Die Kalenderantwort enthält kein gültiges JSON."}
    except (URLError, OSError, ValueError):
        return {"status": "error", **date_info, "error": "Die Kalenderdaten konnten nicht abgerufen werden."}
