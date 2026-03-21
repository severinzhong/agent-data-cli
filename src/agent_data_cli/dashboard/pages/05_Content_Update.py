from __future__ import annotations

import streamlit as st

from agent_data_cli.dashboard.adapters.channel import list_subscribed_channel_options
from agent_data_cli.dashboard.adapters.content import update_content
from agent_data_cli.dashboard.context import build_dashboard_context
from agent_data_cli.dashboard.state import get_page_state, invalidate_pages, save_page_result
from agent_data_cli.dashboard.widgets.common import render_exception, render_object_details, running_in_streamlit
from agent_data_cli.dashboard.widgets.forms import optional_channel_select, optional_group_select, source_select
from agent_data_cli.dashboard.widgets.tables import render_rows
from agent_data_cli.utils.time import utc_now_iso


def build_result_overview(result: dict[str, object]) -> dict[str, object]:
    overview: dict[str, object] = {}
    for key in ("dry_run", "saved_count", "skipped_count"):
        if key in result:
            overview[key] = result[key]
    return overview


def render_page() -> None:
    ctx = build_dashboard_context()
    st.title("Content Update")
    mode = st.radio("Mode", ["source", "group"], horizontal=True, key="content_update_mode")
    row1 = st.columns(2)
    with row1[0]:
        source_name = source_select(ctx.registry, key="content_update_source") if mode == "source" else None
    with row1[1]:
        group_name = optional_group_select(ctx.store, key="content_update_group") if mode == "group" else None
    row2 = st.columns(2)
    with row2[0]:
        channel_key = (
            optional_channel_select(
                [] if source_name is None else list_subscribed_channel_options(ctx.store, source_name),
                key="content_update_channel",
            )
            if mode == "source"
            else None
        )
    with row2[1]:
        since = st.text_input("Since", key="content_update_since")
    row3 = st.columns(2)
    with row3[0]:
        limit = st.number_input("Limit", min_value=1, value=20, key="content_update_limit")
    with row3[1]:
        checkbox_row = st.columns(2)
        with checkbox_row[0]:
            fetch_all = st.checkbox("All", key="content_update_all")
        with checkbox_row[1]:
            dry_run = st.checkbox("Dry Run", key="content_update_dry_run")
    page_state = get_page_state(st.session_state, "content_update_page_state")

    run_clicked = st.button("Run Update", key="content_update_run")
    if run_clicked:
        try:
            result = update_content(
                ctx.registry,
                ctx.store,
                source_name=source_name,
                group_name=group_name,
                channel_key=channel_key or None,
                since=since or None,
                limit=int(limit),
                fetch_all=fetch_all,
                dry_run=dry_run,
            )
            save_page_result(
                st.session_state,
                "content_update_page_state",
                inputs={
                    "mode": mode,
                    "source": source_name,
                    "group": group_name,
                    "channel": channel_key,
                    "since": since,
                    "limit": int(limit),
                    "all": fetch_all,
                    "dry_run": dry_run,
                },
                result=result,
                updated_at=utc_now_iso(),
            )
            invalidate_pages(st.session_state, "content_query_page_state", "source_page_state")
            page_state = get_page_state(st.session_state, "content_update_page_state")
        except Exception as exc:  # noqa: BLE001
            render_exception(exc)

    if page_state["result"] is not None:
        overview = build_result_overview(page_state["result"])
        if overview:
            render_object_details(overview, title="Update Result")
        if "summaries" in page_state["result"]:
            render_rows(page_state["result"]["summaries"], empty_message="No updates.")
        elif "targets" in page_state["result"]:
            render_rows(page_state["result"]["targets"], empty_message="No targets.")
    else:
        st.info("Run an update against one source or one group.")


if running_in_streamlit():
    render_page()
