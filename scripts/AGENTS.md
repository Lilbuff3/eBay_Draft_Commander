<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-30 | Updated: 2026-03-30 -->

# scripts

## Purpose
Development automation and utility scripts for testing, health checks, migrations, and batch operations. One-off executables and helpers used during development and deployment, not part of the core Flask/React application.

## Key Files
| File | Description |
|------|-------------|
| `run_all_tests.py` | Master test runner: orchestrates backend (pytest) and frontend (vitest) in parallel, reports aggregated summary |
| `run_tests_backend.py` | Backend test runner wrapper (pytest with standard flags) |
| `check_health.py` | Health check: validates .env credentials, tests Gemini API, eBay token refresh, server connectivity |
| `migrate_to_sqlite.py` | One-time migration script from old data format to SQLite database (backend/app/core/database.py) |
| `Start_Production.bat` | Windows batch script: starts production Flask server on port 5000 |
| `Start_Selling_Session.bat` | Windows batch script: starts full dev stack (Flask backend + Vite frontend) |

## Subdirectories
(None — all scripts are in root of scripts/ directory)

## For AI Agents

### Working In This Directory
- Scripts are ad-hoc utilities, **not** part of the main application
- Use absolute paths for imports: `Path(__file__).parent.parent / "backend" / ...`
- Load .env via `load_dotenv()` from `python-dotenv` (handles parent directory walk)
- Test scripts spawn subprocess calls: `subprocess.run(["pytest", ...])` for backend, `subprocess.run(["npm", "run", "test"])` for frontend
- Health checks import and call backend services directly to verify runtime state
- Windows batch scripts assume `python` command is in PATH
- Log output to console with clear section headers and status indicators

### Dependencies
- `check_health.py` imports: `backend.app.services.ai_analyzer`, `backend.app.services.ebay_service`
- `migrate_to_sqlite.py` imports: database models from `backend.app.core.database`, migration utilities
- `run_all_tests.py` calls: `run_tests_backend.py` (subprocess), `npm run test` in frontend/ (subprocess)
- Backend expects Flask on `localhost:5000`, Vite frontend on `localhost:5175` (dev mode)
- All scripts assume project root as CWD when running

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
