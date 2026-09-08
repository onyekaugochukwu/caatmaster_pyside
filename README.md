# CAATmaster

**A desktop computer-assisted audit techniques (CAAT) tool for auditors, internal control specialists, and compliance officers** — data transformation and cleaning, a library of audit-specific analytical tests, financial-statement and XBRL analysis, and AI-assisted review, all in one native application with no server and no coding required.

> **Status: v0.1.0-beta.** Downloads for Windows, Linux, and macOS (Apple Silicon) are on the [Releases page](https://github.com/onyekaugochukwu/caatmaster_pyside/releases), along with the companion book below.

## The Companion Book

*Audit Analytics with CaatMaster* is a full practitioner's guide to this application: 32 chapters across 8 parts, plus 3 reference appendices, covering every technique from data import through IFRS-specific analytics to AI-assisted review — each with real worked examples against a running fictional company. Read it online at [`docs/book/index.html`](docs/book/index.html) or download the PDF from the [latest release](https://github.com/onyekaugochukwu/caatmaster_pyside/releases/latest).

## What CAATmaster Does

CAATmaster combines three kinds of capability that are usually found in separate tools:

- **General-purpose data transformation and cleaning** — the kind of work found in a spreadsheet or BI product, applied to a complete population rather than a sample.
- **A library of audit-specific analytical tests** — from long-established techniques like Benford's Law and gap analysis, to statistical estimates required by specific accounting standards.
- **AI-assisted features for narrative text and unstructured documents** — under a strict rule that the AI is never asked to count, sum, or estimate a figure that the underlying data engine can compute exactly.

### Feature Highlights

| Area | What's included |
|------|------------------|
| **Data import & cleaning** | CSV, Excel (`.xlsx`/`.xls`), JSON, Parquet; a cleaning wizard for messy multi-row headers and merged cells; 100+ transformation operations reachable by right-clicking any column |
| **Classic CAATs** | Data profiling, completeness/integrity checks, cross-tabulation, Benford's Law, ratio & trend analysis, outlier/anomaly detection (Isolation Forest, Z-score, IQR, LOF), Monetary Unit and other sampling methods |
| **Internal controls** | Segregation of duties analysis, access review, COSO risk heatmaps, deterministic rule libraries |
| **Financial statement analytics** | Financial ratios, statement-to-concept reshaping, direct XBRL/inline-XBRL (iXBRL) import via Arelle |
| **IFRS/IAS-specific tests** | Revenue recognition (IFRS 15), expected credit losses (IFRS 9), lease liability & IBR checks (IFRS 16), impairment reverse-DCF (IAS 36), provision trend breaks (IAS 37), inventory NRV write-downs (IAS 2), deferred tax recoverability (IAS 12), FX rate consistency (IAS 21) |
| **SQL workflow** | A DuckDB-backed SQL editor with syntax highlighting, cross-dataset joins ("Model Query"), reusable query parameters, and AI-assisted query drafting |
| **Machine learning** | Anomaly detection, classification, clustering, and ARIMA/ETS forecasting, with a full model inventory (save/load/export/import) |
| **AI-assisted review** | Grounded, tool-calling AI chat scoped to the current project's data; document/PDF analysis; numeric disclosure reconciliation against source figures; every AI-drafted figure remains traceable to a deterministic computation |
| **Reporting & programs** | Interactive visualizations (8 chart types), HTML report builder with drag-and-drop sections, and reusable audit programs that replay a full pipeline against a new period's data |
| **Projects & sessions** | Self-contained `.caat` project files carry every dataset, transformation pipeline, and setting — no server, no separate session state to lose |

See the companion book's table of contents for the full, chapter-by-chapter breakdown.

## Technology Stack

| Component | Technology |
|-----------|-----------|
| GUI Framework | PySide 6 (Qt 6), Power Query-inspired light theme |
| Data Processing | Polars |
| SQL Engine | DuckDB |
| Database (auth only) | SQLite via SQLAlchemy 2.0 — see [Data & Storage](#data--storage) |
| XBRL/iXBRL | Arelle |
| ML | scikit-learn, XGBoost, LightGBM, statsmodels |
| AI Providers (optional) | OpenAI, Anthropic, Google Gemini, Hugging Face, Ollama/local via `httpx` |
| Credential Storage | OS-native keyring where available, Fernet-encrypted file otherwise |
| Auth | Argon2 password hashing (via `passlib`), JWT sessions |
| Packaging | PyInstaller — portable directory or single-file EXE (Windows), portable directory or AppImage (Linux), `.app` bundle (macOS) |

## Getting Started

### Download a Build

The simplest way to try CAATmaster is to grab a portable build from the [Releases page](https://github.com/onyekaugochukwu/caatmaster_pyside/releases) — no installation, no Python required. Extract (or mount, for the Linux AppImage) and run.

### Run From Source

Requires Python 3.11+.

```bash
git clone https://github.com/onyekaugochukwu/caatmaster_pyside.git
cd caatmaster_pyside
pip install -r requirements.txt
python main.py
```

### Run the Tests

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -v
```

CI (`.github/workflows/tests.yml`) runs the full suite on every push and pull request to `main`.

## Project Structure

```
caatmaster_pyside/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── caatmaster.spec             # PyInstaller spec (shared by every build script below)
├── build.py                    # Universal build script (auto-detects platform)
├── build_windows.py            # Windows: portable directory or single .exe
├── build_linux.py              # Linux: portable directory
├── build_appimage.py           # Linux: single-file AppImage
├── build_macos.py              # macOS: .app bundle
├── src/
│   ├── core/                   # Business logic: database, data_processor (Polars ops),
│   │                           # models, project/session management, financial concepts,
│   │                           # cleaning wizard, audit programs, XBRL/report building
│   ├── services/                # AI, auth, financial ratios, ML, SQL, IFRS/IAS-specific
│   │                           # analytics, SOX/COSO, XBRL import, visualization
│   └── gui/
│       ├── main_window.py      # Main application window
│       ├── views/               # Dashboard, Data, Transform, SQL, Analyze,
│       │                        # Visualizations, Reports, Projects, Settings, ML Models
│       ├── dialogs/             # Operation-specific dialogs (60+)
│       └── components/          # Sidebar, AI panel, shared modal base classes
├── resources/                   # Bundled fonts and config
├── docs/book/                   # The companion book (index.html + PDF)
└── tests/                       # pytest suite (core, services, gui)
```

## Building for Distribution

Every build script shares a single PyInstaller spec (`caatmaster.spec`), so the dependency list can't drift between platforms.

```bash
# Auto-detects platform and builds the recommended format
python build.py

# Or force a specific platform/format:
python build.py --type=portable    # Portable directory (Windows/Linux)
python build.py --type=onefile     # Single .exe (Windows only)
python build.py --type=appimage    # AppImage (Linux only)
```

| Platform | Script | Output |
|----------|--------|--------|
| Windows | `build_windows.py` | Portable directory (default) or single `.exe` |
| Linux | `build_linux.py` | Portable directory |
| Linux | `build_appimage.py` | Single-file `.AppImage` |
| macOS | `build_macos.py` | `.app` bundle (Apple Silicon only — see below) |

**Cross-compilation isn't possible for PyInstaller apps** — build on the platform you're targeting. `.github/workflows/release.yml` does exactly this on tagged releases, building all three platforms in parallel and publishing the results as release assets.

**macOS note:** GitHub's hosted macOS runners are Apple Silicon (arm64) only, so the published macOS build won't run on an Intel Mac. The build is also unsigned/unnotarized; the bundled README explains the one-time Gatekeeper workaround.

## Data & Storage

CAATmaster is local-first: everything for a given engagement lives in one `.caat` project file, portable and shareable without a server.

- **Projects, datasets, and transformation pipelines** are stored in the project's `.caat` file (`src/core/caat_format.py`), not in a database.
- **User accounts and saved ML models** are the only things backed by a real SQLite database, at `~/.caatmaster/data/caatmaster.db`.
- **AI provider credentials** are stored via the OS-native keyring when one is available (Windows Credential Manager, macOS Keychain, Linux Secret Service), falling back to a Fernet-encrypted file when it isn't.
- **Recent-projects list, session state, and AI audit logs** live under `~/.caatmaster/` and `~/.config/caatmaster/`.

### Default Login

On first launch, a default administrator account is created:

- Username: `admin`
- Password: `admin123`

**Change this password immediately after first login** (Settings → User Account → Change Password). Passwords are hashed with Argon2; sessions use JWT tokens.

## Known Limitations

- No PDF financial-statement import — PDF support (via `pypdf`) reads narrative text for AI-assisted analysis, not structured figures for ratio calculation.
- Every configurable threshold (IFRS 16's 50bps, IAS 36's 2 percentage points, etc.) is a documented starting point for audit judgment, not a standard-defined bright line — see Appendix C of the companion book for the full reference.
- Multi-user collaboration requires sharing the `.caat` project file directly; there is no server-side concurrent access.
- AI features require an API key from a supported provider (OpenAI, Anthropic, Google, Hugging Face) or a local Ollama endpoint.

## Contributing

Issues and pull requests are welcome. Before submitting a change, run the test suite and, if you touched a packaging script, actually build and launch the result — none of `build.py`, `build_windows.py`, `build_linux.py`, `build_appimage.py`, or `build_macos.py` are covered by CI on every commit, only on tagged releases.

## License

No license file is currently published in this repository. Contact the repository owner before reusing or redistributing this code.
