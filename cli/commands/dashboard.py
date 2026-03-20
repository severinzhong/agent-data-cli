from __future__ import annotations

from cli.commands.specs import CommandArgSpec, CommandContext, CommandNodeSpec
from dashboard.runtime import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DashboardRuntimeStatus,
    get_dashboard_status,
    run_dashboard_foreground,
    start_dashboard,
    stop_dashboard,
)


def start_dashboard_command(*, host: str, port: int, daemon: bool) -> int:
    if daemon:
        status = start_dashboard(host=host, port=port)
        _print_status(status, title="dashboard started")
        return 0
    return run_dashboard_foreground(host=host, port=port)


def _run_dashboard_start(args, extras: list[str], ctx: CommandContext) -> int:
    _ = extras, ctx
    return start_dashboard_command(
        host=DEFAULT_HOST if args.host is None else args.host,
        port=DEFAULT_PORT if args.port is None else args.port,
        daemon=args.daemon,
    )


def _run_dashboard_status(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras, ctx
    _print_status(get_dashboard_status(), title="dashboard status")
    return 0


def _run_dashboard_stop(args, extras: list[str], ctx: CommandContext) -> int:
    _ = args, extras, ctx
    _print_status(stop_dashboard(), title="dashboard stopped")
    return 0


def _print_status(status: DashboardRuntimeStatus, *, title: str) -> None:
    print(title)
    print(f"running: {int(status.running)}")
    if status.pid is not None:
        print(f"pid: {status.pid}")
    if status.host is not None:
        print(f"host: {status.host}")
    if status.port is not None:
        print(f"port: {status.port}")
    if status.url is not None:
        print(f"url: {status.url}")
    if status.started_at is not None:
        print(f"started_at: {status.started_at}")
    if status.log_path is not None:
        print(f"log_path: {status.log_path}")


DASHBOARD_COMMAND = CommandNodeSpec(
    name="dashboard",
    summary="Run the local Streamlit dashboard.",
    child_dest="dashboard_command",
    children=(
        CommandNodeSpec(
            name="start",
            summary="Start the Streamlit dashboard.",
            arg_specs=(
                CommandArgSpec(names=("--host",), value_name="host"),
                CommandArgSpec(names=("--port",), value_name="port", type=int),
                CommandArgSpec(names=("--daemon",), action="store_true"),
            ),
            run=_run_dashboard_start,
        ),
        CommandNodeSpec(
            name="status",
            summary="Show dashboard runtime status.",
            run=_run_dashboard_status,
        ),
        CommandNodeSpec(
            name="stop",
            summary="Stop the running dashboard.",
            run=_run_dashboard_stop,
        ),
    ),
)
