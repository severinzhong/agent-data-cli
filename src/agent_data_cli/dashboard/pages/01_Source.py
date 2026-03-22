from __future__ import annotations

import streamlit as st

from agent_data_cli.dashboard.adapters.source import check_source_config, check_source_health, list_sources
from agent_data_cli.dashboard.context import build_dashboard_context
from agent_data_cli.dashboard.state import ensure_page_result, get_page_state, save_page_result
from agent_data_cli.dashboard.widgets.common import render_exception, render_object_details, running_in_streamlit
from agent_data_cli.dashboard.widgets.forms import source_select
from agent_data_cli.dashboard.widgets.tables import render_rows
from agent_data_cli.utils.time import utc_now_iso


def render_page() -> None:
    with build_dashboard_context() as ctx:
        page_state = ensure_page_result(
            st.session_state,
            "source_page_state",
            loader=lambda: {"rows": list_sources(ctx.registry)},
            updated_at=utc_now_iso(),
        )
        st.title("Source")

        if st.button("Refresh Sources", key="source_refresh"):
            rows = list_sources(ctx.registry)
            save_page_result(st.session_state, "source_page_state", inputs={}, result={"rows": rows}, updated_at=utc_now_iso())
            page_state = get_page_state(st.session_state, "source_page_state")
        render_rows(None if page_state["result"] is None else page_state["result"]["rows"], empty_message="No source data yet.")

        selected_source = source_select(ctx.registry, key="source_page_source")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Check Health", key="source_health") and selected_source is not None:
                try:
                    result = check_source_health(ctx.registry, ctx.store, selected_source)
                    page_state["health_result"] = result
                    st.session_state["source_page_state"] = page_state
                except Exception as exc:  # noqa: BLE001
                    render_exception(exc)

            if page_state.get("health_result") is not None:
                render_object_details(page_state["health_result"], title="Health")

        with col2:
            if st.button("Config Check", key="source_config_check") and selected_source is not None:
                try:
                    page_state["config_check_result"] = check_source_config(ctx.registry, selected_source)
                    st.session_state["source_page_state"] = page_state
                except Exception as exc:  # noqa: BLE001
                    render_exception(exc)

            if page_state.get("config_check_result") is not None:
                render_object_details(page_state["config_check_result"], title="Config Check")


if running_in_streamlit():
    render_page()
