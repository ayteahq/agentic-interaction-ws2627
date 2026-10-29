# Exercise 1 - First Tool Call

Agentic Human-AI Interaction - Universität Ulm - WS 2026/27.
Der Python-Agent beantwortet Kalenderfragen mit einer OpenAI-kompatiblen
Chat-Completions-API und ausschließlich simulierten HTTP-Kalenderdaten.

## Voraussetzungen auf einem neuen Windows-Computer

- Python 3.11 oder neuer von https://www.python.org/downloads/ installieren,
  einschließlich Python Launcher (`py`).
- Git von https://git-scm.com/downloads installieren.
- PowerShell sowie Zugang zum Übungsrepository und den Modell-/Datendiensten.

Installation prüfen:

```powershell
py --version
git --version
```

## Repository klonen

Die Beispieladresse durch die URL des eigenen GitHub-Repositorys ersetzen.
In einem vorhandenen Checkout diesen Schritt überspringen.

```powershell
cd $HOME
git clone https://github.com/DEIN-GITHUB-NAME/agentic-interaction-ws2627.git
cd agentic-interaction-ws2627
```

## Virtuelle Umgebung und Abhängigkeiten

Im Repository ausführen. Bei einer neueren Python-Version `-3.11` entsprechend
ersetzen. Eine bereits eingerichtete Umgebung kann weiterverwendet werden.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Lokale Konfiguration

Eine Datei namens `.env` im Repository-Hauptverzeichnis anlegen, beispielsweise
mit `notepad .env`. Folgendes Schema eintragen und alle Platzhalter durch die
von der Übung bereitgestellten Werte ersetzen:

```dotenv
OPENAI_BASE_URL=https://MODELLDIENST.example/API-BASISPFAD
MODEL=MODELLNAME_AUS_DER_UEBUNG
OPENAI_API_KEY=DEIN_LOKALER_API_SCHLUESSEL
DATA_BASE_URL=https://DATENDIENST.example/BASISPFAD
```

Dies sind ausschließlich Platzhalter, keine funktionierende Konfiguration.
Die vollständige Basisadresse des OpenAI-kompatiblen Dienstes verwenden;
`/chat/completions` ergänzt das SDK. Der Datendienst muss die simulierten Dateien
unter `{DATA_BASE_URL}/calendar/{YYYY-MM-DD}.json` bereitstellen.
Es gibt keine festgelegten Modellnamen oder Dienstadressen im Anwendungscode.
Bereits gesetzte Umgebungsvariablen haben Vorrang vor `.env` (`override=False`),
auch leere Variablen; erforderliche leere Werte werden als Fehler behandelt.
`.env` niemals veröffentlichen oder committen. Schlüssel nicht in Quellcode,
Screenshots oder Konsolenausgaben übernehmen.

## Start

Ohne Aktivierung der virtuellen Umgebung:

```powershell
.\.venv\Scripts\python.exe -m agent "Was steht am 29.10.2026 im Kalender?"
.\.venv\Scripts\python.exe -m agent --help
```

Alternativ aktivieren und den vorgesehenen Einstiegspunkt verwenden:

```powershell
.\.venv\Scripts\Activate.ps1
python -m agent "Was steht am 29.10.2026 im Kalender?"
```

Falls PowerShell die Aktivierung blockiert, den Aufruf ohne Aktivierung verwenden.

## Ablauf und Fehler

1. `load_config()` lädt die Repository-Konfiguration und prüft die Pflichtwerte.
2. `run_agent()` übergibt Anfrage und Function-Calling-Beschreibung an das Modell.
   Das Modell wählt das Datum und ruft `get_calendar_events` auf.
3. `execute_tool()` validiert Name und JSON-Argumente. `get_calendar_events()`
   liest die simulierten Daten per HTTP GET und verarbeitet das JSON. Zusätzlich
   berechnet `get_weekday()` mit `datetime.date.weekday()` und einer festen deutschen
   Wochentagstabelle das Feld `weekday_de`. Dieses steht für jedes gültige Datum
   auch bei fehlenden Kalenderdaten oder Abruffehlern im Tool-Ergebnis.
   Das Modell soll Wochentage ausschließlich aus diesem Feld übernehmen und nur
   bei ausdrücklichen Wochentagsfragen erwähnen. Angaben innerhalb der abgerufenen
   Kalenderdaten sind für die Wochentagsberechnung nicht maßgeblich.
4. Das Modell erhält seine Tool-Aufrufe sowie die Ergebnisse als Tool-Nachrichten
   mit passender `tool_call_id`. Ein zweiter Modellaufruf erzeugt die deutsche Antwort.

HTTP 404 bedeutet fehlende Daten (`not_found`), nicht einen nachweislich leeren
Kalender. Erfolgreich gelesene Daten mit leerer Terminliste sind dagegen ein
leerer Kalender. Andere Toolfehler werden dem Modell zur Erklärung übergeben.
Die Antwort steht auf stdout, erfolgreiche Abläufe liefern Exit-Code 0.
Konfigurations-, Modell- und nicht behandelte Ausführungsfehler liefern Exit-Code 1
mit einer sicheren Meldung auf stderr. Fehlerhafte CLI-Argumente liefern Exit-Code 2.
Es werden keine echten Kalender oder externen Konten verändert.

## JSONL-Logging

Jeder Aufruf erstellt `logs/<UUID>.jsonl`, auch bei fehlgeschlagenen Runs.
Jede Zeile ist ein JSON-Objekt mit `ts`, `run_id`, `event`, `tool`, `args`, `ok`,
`model` und `duration_ms`. Zeitstempel sind ISO-8601 in UTC mit Zeitzone.
Dauern werden mit dem monotonen Timer `time.perf_counter()` gemessen: bei
Tool-Ereignissen ab Beginn der Toolverarbeitung, sonst ab Beginn des Runs.
Nach jeder Zeile wird der Dateipuffer geleert; am Ende wird die Datei geschlossen.

Normale erfolgreiche Runs enthalten `user_task`, `tool_call`, `tool_result`, `final`.
`--help` zeigt die Hilfe, liefert Exit-Code 0 und schreibt ein `final`-Ereignis
mit `code: help`, ohne die API aufzurufen. Fehler erzeugen `error` mit einem
klassifizierten Code: `configuration`, `model_response`, `tool_error` oder einem
spezifischen Verbindungs-/HTTP-/CLI-Fehlercode.

`tool` enthält den tatsächlich angeforderten Function-Toolnamen, sonst `null`.
`args` enthält ausschließlich das Datum im Format YYYY-MM-DD. `ok: null`
beim Toolaufruf bedeutet, dass dessen Ergebnis noch aussteht. HTTP 404 ist ein
reguläres Ergebnis (`status: not_found`, `ok: true`). Andere Toolfehler ergeben
`ok: false` und ein `error`-Ereignis. Ein anschließendes `final` bestätigt die
Antwortausgabe, nicht den Erfolg aller Datenabrufe.

`model` ist der konfigurierte Modellname, bei fehlender Konfiguration gegebenenfalls
`null`. Rohtexte von Prompts/Antworten, Kalenderinhalte, URLs, Header und fremde
Exception-Texte werden nicht geloggt. Bekannte Geheimnisse aus der Umgebung werden
auch in Modell- und Toolnamen redigiert. Ungültige oder sensitive Toolnamen werden
durch einen Marker ersetzt; gültige unbekannte Toolnamen bleiben zur Diagnose erhalten.
`.env`, `.venv/` und `logs/` sind durch `.gitignore` ausgeschlossen.
Falls das Dateisystem keine Datei anlegen oder schreiben kann, ist vollständiges
Logging technisch nicht möglich.

## Automatisierte Tests

Offline-Regressionsprüfungen ohne echte API-Aufrufe:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```
