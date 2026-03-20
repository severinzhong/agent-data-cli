from __future__ import annotations

import streamlit as st

from dashboard.runtime import get_dashboard_status
from dashboard.widgets.common import render_object_details, running_in_streamlit


def render_page() -> None:
    st.set_page_config(page_title="Agent-Data-Cli Dashboard", layout="wide")
    st.title("Agent-Data-Cli Dashboard")
    st.caption("Streamlit Dashboard for Human to Understand the Projetc")

    status = get_dashboard_status()
    st.subheader("Runtime")
    render_object_details(
        {
            "running": status.running,
            "pid": status.pid,
            "host": status.host,
            "port": status.port,
            "url": status.url,
            "started_at": status.started_at,
            "log_path": status.log_path,
        }
    )


if running_in_streamlit():
    render_page()
