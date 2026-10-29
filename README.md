# agentic-interaction-ws2627
Agentic Human-AI Interaction - University of Ulm - WS 2026/27

## Exercise 1 – First Tool Call

Dieses Projekt gehört zum Modul Agentic Human-AI Interaction der Universität Ulm.
Die Grundstruktur liest zunächst nur eine Anfrage als Kommandozeilenargument ein
und gibt sie zur Kontrolle aus. Es findet noch kein API-Aufruf statt.

### Voraussetzungen

- Python 3.11 oder neuer (mit dem Windows Python Launcher `py`)
- Windows PowerShell

### Einrichtung und Start unter Windows

Im lokalen Repository eine virtuelle Umgebung erstellen und die Abhängigkeiten installieren:

```powershell
cd C:\Users\erasl\agentic-interaction-ws2627
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Bei einer neueren Python-Version die Versionsauswahl `-3.11` entsprechend ersetzen.
Die virtuelle Umgebung lässt sich direkt ohne Aktivierung verwenden:

```powershell
.\.venv\Scripts\python.exe -m agent "Was steht am 29.10.2026 im Kalender?"
```

Alternativ die Umgebung aktivieren und den vorgesehenen Einstiegspunkt verwenden:

```powershell
.\.venv\Scripts\Activate.ps1
python -m agent "Was steht am 29.10.2026 im Kalender?"
```

Erwartete Ausgabe:

```text
Testeingabe: Was steht am 29.10.2026 im Kalender?
```

Für diesen Test sind keine API-Schlüssel und keine `.env`-Datei erforderlich.
`openai` und `python-dotenv` sind für die späteren Übungsschritte vorgesehen;
der aktuelle Test verwendet ausschließlich die Python-Standardbibliothek.
