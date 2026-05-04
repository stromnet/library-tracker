# library-tracker

Tool for logging in to library accounts and normalizing loans/reservations across supported libraries.

## About the code
This codebase was produced with the help of AI-assisted development and should be reviewed, tested, and maintained like any other software project.

## Supported libraries
- Partille
- Alingsås
- Lerum
- Mölnlycke / Härryda

## Supported features
- login for all supported libraries
- normalized snapshot model for:
  - loans
  - reservations / holds
- combined multi-library summary from a YAML config file
- JSON output
- HTML report output
- highlights section for:
  - due loans
  - ready-for-pickup / waiting / in-transit reservations
- per-provider logging with timing for prominent stages
- concurrent fetching across configured accounts/providers
- best-effort pagination support:
  - Partille / Alingsås: normal link-based pagination if present
  - Lerum: normal link-based pagination for checked out / holds pages if present
  - Mölnlycke: best-effort Arena/Wicket next-page traversal

## Current architecture
- common models and abstract base client
- generic Koha parsing layer
- provider adapters for each supported library
- CLI entry point for single-account and config-based runs

## Run

```bash
python3 -m library_tracker.cli partille USERNAME PASSWORD
python3 -m library_tracker.cli alingsas USERNAME PASSWORD
python3 -m library_tracker.cli lerum USERNAME PASSWORD
python3 -m library_tracker.cli molnlycke USERNAME PASSWORD
python3 -m library_tracker.cli --config config/accounts.yaml
```

## Output formats
JSON:

```bash
python3 -m library_tracker.cli partille USERNAME PASSWORD --json
```

HTML report:

```bash
python3 -m library_tracker.cli --config config/accounts.yaml --html report.html
```

Verbose logging:

```bash
python3 -m library_tracker.cli --config config/accounts.yaml --verbose
```

## Windows
Simple Windows helper files are included:
- `requirements.txt`
- `setup.bat`
- `run.ps1`
- `run.bat`

Default files used by the run scripts:
- config: `config/accounts.yaml`
- HTML report: `report.html`

First-time setup:

```bat
setup.bat
```

`setup.bat` will:
- install Python via `winget` if `py` is not available
- install/update dependencies from `requirements.txt`

PowerShell:

```powershell
./run.ps1
```

With custom config/report path:

```powershell
./run.ps1 -Config config/accounts.yaml -Html report.html
```

Batch file:

```bat
run.bat
```

## Linux packaging
A helper script is included to build a distributable zip:

```bash
./build-dist.sh
```

This creates a zip file under `dist/`.

## YAML config
Example files:
- `config/accounts.yaml`
- `config/accounts.example.yaml`

Format:

```yaml
accounts:
  - library: partille
    username: "YOUR_CARD_OR_PERSONNR"
    password: "YOUR_PIN"
    holder_alias: "Förnamn"
```

## Known uncertainties / limitations
- parsing is intentionally simple and may need adjustment if sites change markup
- account name extraction is still incomplete for some providers/pages
- pagination support is best-effort; real paged account examples have not yet been observed for all providers
- Mölnlycke uses Arena/Liferay/Wicket and is the most brittle integration
- some reservation fields vary by status and may not exist for every item
- due dates / expiry dates are currently treated as strings, not fully normalized dates
- credentials are passed on the command line in this tool or in the YAML file; move to env vars or a secrets file later
- if one provider changes markup or auth flow, that adapter may fail independently of the others

## Files of interest
- `library_tracker/cli.py`
- `library_tracker/models.py`
- `library_tracker/partille.py`
- `library_tracker/alingsas.py`
- `library_tracker/lerum.py`
- `library_tracker/molnlycke.py`
- `config/accounts.yaml`
- `config/accounts.example.yaml`
