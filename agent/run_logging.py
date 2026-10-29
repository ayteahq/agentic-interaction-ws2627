"""JSONL-Laufprotokolle mit bewusst begrenzten, nicht sensitiven Feldern."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4


def redact_credentials(value):
    """Bekannte Geheimnisse auch in Modell- und Toolnamen entfernen."""
    if not isinstance(value, str):
        return None
    for key, secret in os.environ.items():
        if secret and any(part in key.upper() for part in
                          ("KEY", "SECRET", "TOKEN", "PASSWORD", "AUTHORIZATION")):
            value = value.replace(secret, "[REDACTED]")
    return value


class RunLog:
    """Ein exklusiv erstelltes Protokoll pro Aufruf; keine Rohtexte oder Header."""

    def __init__(self, directory: Path):
        self.run_id = str(uuid4())
        self.started = perf_counter()
        self.model = None
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{self.run_id}.jsonl"
        self.stream = self.path.open("x", encoding="utf-8")

    def write(self, event: str, *, started=None, ok=None, date=None,
              status=None, code=None, tool=None):
        if event not in {"user_task", "tool_call", "tool_result", "final", "error"}:
            raise ValueError("Unbekanntes Logereignis")
        # Keine frei formulierten Prompts, Antworten, JSON-Daten, URLs,
        # Exceptions oder Header übernehmen. Nur das Datumsformat ist erlaubt.
        args = {"date": date} if isinstance(date, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date) else {}
        safe_tool = redact_credentials(tool)
        if safe_tool is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", safe_tool):
            safe_tool = "[REDACTED_TOOL_NAME]"
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": self.run_id, "event": event,
            "tool": safe_tool,
            "args": args, "ok": ok, "model": redact_credentials(self.model),
            "duration_ms": round((perf_counter() - (self.started if started is None else started)) * 1000, 3),
        }
        if status in {"ok", "not_found", "error"}:
            record["status"] = status
        if code in {"configuration", "arguments", "model_http", "model_connection",
                    "model_response", "unexpected", "interrupted", "tool_error", "help"}:
            record["code"] = code
        self.stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        self.stream.flush()

    def close(self):
        self.stream.close()
