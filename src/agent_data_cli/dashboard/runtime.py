from __future__ import annotations

import json
import os
import socket
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from agent_data_cli.runtime_paths import resolve_runtime_paths
from agent_data_cli.utils.time import utc_now_iso


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8501
STATE_FILE_NAME = "server.json"
LOG_FILE_NAME = "server.log"


@dataclass(frozen=True, slots=True)
class DashboardRuntimeStatus:
    running: bool
    pid: int | None = None
    host: str | None = None
    port: int | None = None
    url: str | None = None
    started_at: str | None = None
    cwd: str | None = None
    log_path: str | None = None


def start_dashboard(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    daemon: bool = True,
    runtime_dir: Path | None = None,
) -> DashboardRuntimeStatus:
    runtime_dir = _resolve_runtime_dir(runtime_dir)
    if not daemon:
        raise RuntimeError("start_dashboard only supports daemon mode")
    _assert_not_running(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_path = runtime_dir / LOG_FILE_NAME
    process = _spawn_process(_streamlit_command(host, port), daemon=True, log_path=log_path)
    try:
        state = _write_state(runtime_dir, pid=process.pid, host=host, port=port, log_path=log_path)
        _wait_until_ready(process.pid, host, port)
        return _status_from_state(state, running=True)
    except Exception:
        _clear_state(runtime_dir)
        raise


def run_dashboard_foreground(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    runtime_dir: Path | None = None,
) -> int:
    runtime_dir = _resolve_runtime_dir(runtime_dir)
    _assert_not_running(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_path = runtime_dir / LOG_FILE_NAME
    process = _spawn_process(_streamlit_command(host, port), daemon=False, log_path=log_path)
    _write_state(runtime_dir, pid=process.pid, host=host, port=port, log_path=log_path)
    try:
        return process.wait()
    finally:
        _clear_state(runtime_dir)


def get_dashboard_status(*, runtime_dir: Path | None = None) -> DashboardRuntimeStatus:
    runtime_dir = _resolve_runtime_dir(runtime_dir)
    state = _read_state(runtime_dir)
    if state is None:
        return DashboardRuntimeStatus(running=False)
    if not _is_process_alive(state["pid"]):
        _clear_state(runtime_dir)
        return DashboardRuntimeStatus(running=False)
    if not _port_is_listening(str(state["host"]), int(state["port"])):
        return _status_from_state(state, running=False)
    return _status_from_state(state, running=True)


def stop_dashboard(
    *,
    runtime_dir: Path | None = None,
    term_timeout_seconds: float = 1.0,
) -> DashboardRuntimeStatus:
    runtime_dir = _resolve_runtime_dir(runtime_dir)
    state = _read_state(runtime_dir)
    if state is None:
        return DashboardRuntimeStatus(running=False)
    pid = int(state["pid"])
    if not _is_process_alive(pid):
        _clear_state(runtime_dir)
        return DashboardRuntimeStatus(running=False)
    _send_signal(pid, signal.SIGTERM)
    host = str(state["host"])
    port = int(state["port"])
    if _wait_until_stopped(pid, host, port, timeout_seconds=term_timeout_seconds):
        _clear_state(runtime_dir)
        return DashboardRuntimeStatus(running=False)
    if _is_process_alive(pid):
        _send_signal(pid, signal.SIGKILL)
    if _wait_until_stopped(pid, host, port, timeout_seconds=term_timeout_seconds):
        _clear_state(runtime_dir)
        return DashboardRuntimeStatus(running=False)
    raise RuntimeError(f"dashboard failed to stop: pid={pid}")


def _assert_not_running(runtime_dir: Path) -> None:
    state = _read_state(runtime_dir)
    if state is None:
        return
    if _is_process_alive(state["pid"]):
        raise RuntimeError(f"dashboard already running: pid={state['pid']}")
    _clear_state(runtime_dir)


def _streamlit_command(host: str, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(__file__).resolve().parent / "index.py"),
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]


def _spawn_process(command: list[str], *, daemon: bool, log_path: Path) -> subprocess.Popen[bytes]:
    if daemon:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("ab")
        try:
            return subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=log_handle,
                start_new_session=True,
            )
        finally:
            log_handle.close()
    return subprocess.Popen(command)


def _write_state(runtime_dir: Path, *, pid: int, host: str, port: int, log_path: Path) -> dict[str, object]:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "pid": pid,
        "host": host,
        "port": port,
        "started_at": utc_now_iso(),
        "cwd": str(Path.cwd()),
        "log_path": str(log_path),
    }
    (runtime_dir / STATE_FILE_NAME).write_text(json.dumps(state, ensure_ascii=True, indent=2))
    return state


def _read_state(runtime_dir: Path) -> dict[str, object] | None:
    path = runtime_dir / STATE_FILE_NAME
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _clear_state(runtime_dir: Path) -> None:
    path = runtime_dir / STATE_FILE_NAME
    if path.exists():
        path.unlink()


def _status_from_state(state: dict[str, object], *, running: bool) -> DashboardRuntimeStatus:
    host = str(state["host"])
    port = int(state["port"])
    return DashboardRuntimeStatus(
        running=running,
        pid=int(state["pid"]),
        host=host,
        port=port,
        url=f"http://{host}:{port}",
        started_at=str(state["started_at"]),
        cwd=str(state["cwd"]),
        log_path=str(state["log_path"]),
    )


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _send_signal(pid: int, sig: int) -> None:
    os.kill(pid, sig)


def _port_is_listening(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _wait_until_ready(pid: int, host: str, port: int, timeout_seconds: float = 5.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _is_process_alive(pid):
            raise RuntimeError("dashboard failed to start: process exited before ready")
        if _port_is_listening(host, port):
            return
        time.sleep(0.05)
    raise RuntimeError(f"dashboard failed to start within {timeout_seconds:.1f}s")


def _wait_until_stopped(pid: int, host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        alive = _is_process_alive(pid)
        listening = _port_is_listening(host, port)
        if not alive and not listening:
            return True
        time.sleep(0.05)
    return False


def _resolve_runtime_dir(runtime_dir: Path | None) -> Path:
    if runtime_dir is not None:
        return runtime_dir
    return resolve_runtime_paths().runtime_dir
