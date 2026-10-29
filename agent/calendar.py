"""Nur lesender Zugriff auf die simulierten HTTP-Kalenderdaten."""

import json
import re
from datetime import date as calendar_date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOOL = {
    "type": "function",
    "function": {
        "name": "get_calendar_events",
        "description": "Liest simulierte Kalenderdaten für einen bestimmten Tag. Verändert keine Termine.",
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
        if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError
        calendar_date.fromisoformat(date)
    except ValueError:
        return {"status": "error", "error": "Ungültiges Datum; erwartet wird YYYY-MM-DD."}

    url = f"{data_base_url.rstrip('/')}/calendar/{date}.json"
    try:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
        return {"status": "ok", "date": date, "data": data}
    except HTTPError as exc:
        if exc.code == 404:
            return {"status": "not_found", "date": date,
                    "message": "Für diesen Tag sind keine Kalenderdaten vorhanden."}
        return {"status": "error", "date": date, "error": f"Kalenderabruf: HTTP {exc.code}."}
    except (json.JSONDecodeError, UnicodeError):
        return {"status": "error", "date": date, "error": "Die Kalenderantwort enthält kein gültiges JSON."}
    except (URLError, OSError, ValueError):
        return {"status": "error", "date": date, "error": "Die Kalenderdaten konnten nicht abgerufen werden."}
