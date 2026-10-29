# agentic-interaction-ws2627

Agentic Human-AI Interaction - Universität Ulm - WS 2026/27

## Exercise 1 - First Tool Call

Der Kalender-Agent verwendet die OpenAI-kompatible Chat-Completions-API und
liest ausschließlich simulierte Kalenderdaten per HTTP GET. Python 3.11 oder
neuer ist erforderlich.

### Einrichtung unter Windows (PowerShell)

```powershell
cd C:\Users\erasl\agentic-interaction-ws2627
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Bei einer neueren Python-Version `-3.11` entsprechend ersetzen. Die bereits
vorhandene virtuelle Umgebung kann weiterverwendet werden.

In der lokalen `.env` müssen die vier Variablen `OPENAI_BASE_URL`, `MODEL`,
`OPENAI_API_KEY` und `DATA_BASE_URL` mit den von der Übung bereitgestellten
Werten gesetzt sein. Modell und Basisadressen haben keine Standardwerte.
Bereits gesetzte Umgebungsvariablen haben Vorrang vor `.env`.
Die `.env` und API-Schlüssel niemals veröffentlichen oder committen.

### Start

```powershell
.\.venv\Scripts\Activate.ps1
python -m agent "Was steht am 29.10.2026 im Kalender?"
```

Ohne Aktivierung:

```powershell
.\.venv\Scripts\python.exe -m agent "Was steht am 29.10.2026 im Kalender?"
```

### Ablauf und Funktionen

1. `load_config()` lädt `.env` aus dem Repository mit `override=False` und prüft
   die erforderlichen Einstellungen, ohne deren Werte auszugeben.
2. `run_agent()` übergibt Anfrage und Toolbeschreibung an das Modell. Das Modell
   bestimmt das Datum und erzeugt einen Aufruf von `get_calendar_events`.
3. `execute_tool()` prüft Toolname und JSON-Argumente.
4. `get_calendar_events()` validiert das Datum und liest per GET
   `{DATA_BASE_URL}/calendar/{YYYY-MM-DD}.json`. JSON-Daten werden unter `data`
   zurückgegeben. HTTP 404 liefert `not_found`, andere Abruffehler `error`.
5. Die Assistant-Nachricht mit den Tool-Aufrufen und je eine Tool-Nachricht mit
   passender `tool_call_id` werden dem Modell übergeben. Der zweite Modellaufruf
   erzeugt die deutsche Antwort; weitere Tool-Aufrufe sind dabei deaktiviert.

Die endgültige Antwort steht auf stdout, bei erfolgreichem Ablauf ist der
Exit-Code 0. Technische Fehler des Modellzugriffs oder der Konfiguration stehen
auf stderr und führen zu Exit-Code 1. Fehlende Kalenderdaten und Kalenderabruffehler
werden als Tool-Ergebnis vom Modell erklärt; sie beenden den Ablauf nicht vorzeitig.
Es werden keine Kalender verändert und keine Logs geschrieben. Die Kalenderabfrage
verwendet keinen API-Schlüssel; dieser wird nur dem Modell-Client übergeben.

### JSONL-Logging

Jeder Programmaufruf erstellt `logs/<run_id>.jsonl` mit einer neuen UUID. Jede
Zeile ist ein JSON-Objekt mit `ts` (UTC mit Zeitzone), `run_id`, `event`, `tool`,
`args`, `ok`, `model` und `duration_ms`. `model` ist der konfigurierte Modellname;
ist die Konfiguration unvollständig, kann das Feld `null` sein. `tool` ist bei
Tool-Ereignissen `get_calendar_events`, sonst `null`. `args` enthält ausschließlich
das Datum im Format YYYY-MM-DD. `ok: null` bedeutet, dass das Ergebnis beim
Tool-Aufruf noch aussteht.

Ereignisse: `user_task`, `tool_call`, `tool_result`, `final` und bei Fehlern
`error`. HTTP 404 ist ein reguläres Ergebnis (`status: not_found`, `ok: true`),
kein technischer Fehler. Andere Tool-Fehler ergeben `ok: false` und zusätzlich
ein `error`-Ereignis; der zweite Modellaufruf erklärt sie weiterhin auf Deutsch.
`final` bestätigt die Ausgabe der Antwort, nicht den Erfolg aller Datenabrufe.

Die Dauer wird mit dem monotonen Timer `time.perf_counter()` gemessen: bei
Tool-Ereignissen ab Beginn der Tool-Verarbeitung, sonst ab Beginn des Runs.
Nach jeder Zeile wird der Dateipuffer geleert, und die Datei wird auch bei Fehlern
geschlossen. Falls das Dateisystem keine Logdatei anlegen oder schreiben kann,
ist eine vollständige Protokollierung technisch nicht möglich.

Aus Sicherheitsgründen protokollieren wir keine Rohtexte der Anfrage oder Antwort,
Kalenderinhalte, `.env`-Inhalte, URLs, HTTP-Header oder Exception-Texte. Fehlercodes
und Statuswerte stammen aus einer festen Auswahlliste. So können auch über Prompts,
Tool-Antworten oder Fehlermeldungen eingeschleuste Zugangsdaten nicht in Logs gelangen.
`logs/` und `.env` werden weiterhin durch `.gitignore` ausgeschlossen.
