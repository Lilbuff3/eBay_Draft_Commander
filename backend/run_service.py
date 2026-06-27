"""
Supervisor wrapper for eBay Draft Commander.

Launches the backend (``backend/wsgi_service.py``) as a disposable child
process and relaunches it on request. This is the robust fix for the
Windows restart bug: ``os.execv`` does not reliably rebind port 5000 because
Windows has no real fork/exec and eventlet's monkey-patched listener socket
is not released before the replacement tries to bind.

With this supervisor, only ONE process ever binds port 5000. When the child
exits, the OS closes every file descriptor (including the port-5000 listener)
*before* the supervisor respawns — eliminating the bind race entirely.

Exit-code contract (set by the child via os._exit):
    42    -> restart requested; supervisor relaunches the child
    0     -> clean stop; supervisor stops too
    other -> crash; supervisor relaunches (with a crash-loop guard)

Launch:
    Detached / prod:  Start-Process pythonw backend\\run_service.py
    Dev (restartable): python backend/run_service.py

The child stays ``wsgi_service.py`` unchanged (it keeps its own stdout/stderr
redirection to data/backend_service.log).
"""
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

CHILD_SCRIPT = ROOT_DIR / "backend" / "wsgi_service.py"

# Exit-code contract
RESTART_CODE = 42
CLEAN_STOP_CODE = 0

# Crash-loop guard: give up if the child crashes too often in a short window
CRASH_WINDOW_SECONDS = 60
CRASH_MAX = 3
RESTART_BACKOFF_SECONDS = 2


def _get_logger() -> logging.Logger:
    """File logger for the supervisor itself (works headless under pythonw)."""
    log_dir = ROOT_DIR / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("supervisor")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_dir / "supervisor.log", mode="a", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        logger.addHandler(handler)
    return logger


def main() -> int:
    log = _get_logger()
    log.info("Supervisor starting. Child: %s", CHILD_SCRIPT)

    child_env = dict(os.environ)
    child_env["DC_SUPERVISED"] = "1"

    current_child: "subprocess.Popen | None" = None
    stopping = False
    crash_times: list[float] = []

    def _shutdown(signum, _frame):
        nonlocal stopping
        stopping = True
        log.info("Supervisor received signal %s; terminating child and exiting.", signum)
        if current_child and current_child.poll() is None:
            current_child.terminate()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    if hasattr(signal, "SIGBREAK"):  # Windows Ctrl-Break
        signal.signal(signal.SIGBREAK, _shutdown)

    while not stopping:
        current_child = subprocess.Popen(
            [sys.executable, str(CHILD_SCRIPT)],
            cwd=str(ROOT_DIR),
            env=child_env,
        )
        log.info("Child started (pid=%s).", current_child.pid)
        code = current_child.wait()

        if stopping:
            break

        if code == RESTART_CODE:
            log.info("Restart requested (exit 42). Relaunching child.")
            continue

        if code == CLEAN_STOP_CODE:
            log.info("Child exited cleanly (exit 0). Supervisor stopping.")
            break

        # Unexpected exit -> crash path with loop guard
        now = time.monotonic()
        crash_times.append(now)
        crash_times = [t for t in crash_times if now - t <= CRASH_WINDOW_SECONDS]
        log.warning(
            "Child crashed (exit %s). %d crash(es) in the last %ss.",
            code, len(crash_times), CRASH_WINDOW_SECONDS,
        )
        if len(crash_times) > CRASH_MAX:
            log.error(
                "Crash-loop guard tripped (>%d crashes/%ss). Supervisor giving up.",
                CRASH_MAX, CRASH_WINDOW_SECONDS,
            )
            return 1
        time.sleep(RESTART_BACKOFF_SECONDS)

    return 0


if __name__ == "__main__":
    sys.exit(main())
