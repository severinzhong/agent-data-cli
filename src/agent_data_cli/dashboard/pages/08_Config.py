from __future__ import annotations

import streamlit as st

from agent_data_cli.dashboard.adapters.config import (
    check_source_config,
    explain_cli_config,
    explain_source_config,
    list_cli_configs,
    list_source_configs,
    set_cli_config,
    set_source_config,
    unset_cli_config,
    unset_source_config,
)
from agent_data_cli.dashboard.context import build_dashboard_context
from agent_data_cli.dashboard.state import get_page_state, invalidate_pages, save_page_result
from agent_data_cli.dashboard.widgets.common import render_exception, running_in_streamlit
from agent_data_cli.dashboard.widgets.forms import source_select
from agent_data_cli.dashboard.widgets.tables import render_rows
from agent_data_cli.utils.time import utc_now_iso


def render_page() -> None:
    with build_dashboard_context() as ctx:
        st.title("Config")
        scope = st.radio("Scope", ["cli", "source"], horizontal=True, key="config_scope")
        row1 = st.columns(2)
        with row1[0]:
            source_name = source_select(ctx.registry, key="config_source") if scope == "source" else None
        with row1[1]:
            key = st.text_input("Key", key="config_key")
        row2 = st.columns(2)
        with row2[0]:
            value = st.text_input("Value", key="config_value")
        page_state = get_page_state(st.session_state, "config_page_state")

        with row2[1]:
            list_clicked = st.button("List Config", key="config_list", width="stretch")

        if list_clicked:
            try:
                rows = (
                    list_cli_configs(ctx.registry, ctx.store)
                    if scope == "cli"
                    else list_source_configs(ctx.registry, ctx.store, source_name)
                )
                save_page_result(
                    st.session_state,
                    "config_page_state",
                    inputs={"scope": scope, "source": source_name},
                    result={"rows": rows},
                    updated_at=utc_now_iso(),
                )
                page_state = get_page_state(st.session_state, "config_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)

        render_rows(None if page_state["result"] is None else page_state["result"]["rows"], empty_message="List config entries.")

        row1 = st.columns(3)
        with row1[0]:
            if st.button("Set", key="config_set") and key and value:
                try:
                    rows = (
                        set_cli_config(ctx.registry, ctx.store, key, value)
                        if scope == "cli"
                        else set_source_config(ctx.registry, ctx.store, source_name, key, value)
                    )
                    save_page_result(
                        st.session_state,
                        "config_page_state",
                        inputs={"scope": scope, "source": source_name},
                        result={"rows": rows},
                        updated_at=utc_now_iso(),
                    )
                    invalidate_pages(st.session_state, "source_page_state", "channel_page_state", "content_search_page_state", "content_update_page_state")
                except Exception as exc:  # noqa: BLE001
                    render_exception(exc)
        with row1[1]:
            if st.button("Unset", key="config_unset") and key:
                try:
                    rows = (
                        unset_cli_config(ctx.registry, ctx.store, key)
                        if scope == "cli"
                        else unset_source_config(ctx.registry, ctx.store, source_name, key)
                    )
                    save_page_result(
                        st.session_state,
                        "config_page_state",
                        inputs={"scope": scope, "source": source_name},
                        result={"rows": rows},
                        updated_at=utc_now_iso(),
                    )
                    invalidate_pages(st.session_state, "source_page_state", "channel_page_state", "content_search_page_state", "content_update_page_state")
                except Exception as exc:  # noqa: BLE001
                    render_exception(exc)
        with row1[2]:
            if st.button("Explain", key="config_explain") and key:
                try:
                    details = explain_cli_config(ctx.registry, key) if scope == "cli" else explain_source_config(ctx.registry, source_name, key)
                    st.write(details)
                except Exception as exc:  # noqa: BLE001
                    render_exception(exc)

        if st.button("Check Source Config", key="config_check") and source_name is not None:
            try:
                st.write(check_source_config(ctx.registry, source_name))
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)


if running_in_streamlit():
    render_page()
