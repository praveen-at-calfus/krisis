"""Single-command launcher: starts the FastAPI backend and the Streamlit UI together.

Run from v1.1/:  ../.venv/bin/python run.py
Ctrl-C stops both. Ports are configurable via API_PORT / UI_PORT env vars.
"""
import os
import pathlib
import signal
import subprocess
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
BIN = HERE.parent / ".venv" / "bin"           # shared venv at the project root
API_PORT = os.getenv("API_PORT", "8000")
UI_PORT = os.getenv("UI_PORT", "8501")
API_BASE = f"http://localhost:{API_PORT}"


def _wait_healthy(timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{API_BASE}/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001 — not up yet
            time.sleep(0.5)
    return False


def _stop(name: str, proc) -> None:
    if proc is None or proc.poll() is not None:
        return
    print(f"Stopping {name} ...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt


def main() -> int:
    # Handle both Ctrl-C (SIGINT) and `kill` (SIGTERM) as a graceful shutdown, so the
    # finally-block stops both children regardless of how we're asked to stop.
    signal.signal(signal.SIGINT, _raise_keyboard_interrupt)
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)

    print(f"Starting KRISIS API on {API_BASE} (docs at {API_BASE}/docs) ...")
    api = subprocess.Popen(
        [str(BIN / "uvicorn"), "app.api:app", "--port", API_PORT, "--log-level", "warning"],
        cwd=str(HERE),
    )
    ui = None
    try:
        if not _wait_healthy():
            print("API did not become healthy in time - is Postgres running? Shutting down.")
            return 1
        print(f"API ready. Launching Streamlit UI on http://localhost:{UI_PORT} ...\n")
        env = dict(os.environ, API_BASE=API_BASE)   # point the UI at this API
        ui = subprocess.Popen(
            [str(BIN / "streamlit"), "run", "streamlit_app.py", "--server.port", UI_PORT],
            cwd=str(HERE), env=env,
        )
        ui.wait()
    except KeyboardInterrupt:
        print()
    finally:
        _stop("UI", ui)
        _stop("API", api)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
