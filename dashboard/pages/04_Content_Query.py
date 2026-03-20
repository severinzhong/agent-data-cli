from __future__ import annotations

import streamlit as st

from dashboard.adapters.channel import list_channel_options
from dashboard.adapters.content import query_content
from dashboard.context import build_dashboard_context
from dashboard.state import get_page_state, save_page_result
from dashboard.widgets.common import render_exception, running_in_streamlit
from dashboard.widgets.forms import optional_channel_select, optional_group_select, source_select
from dashboard.widgets.tables import render_rows
from utils.time import utc_now_iso


def render_page() -> None:
    ctx = build_dashboard_context()
    st.title("Content Query")
    mode = st.radio("Mode", ["source", "group"], horizontal=True, key="content_query_mode")
    row1 = st.columns(2)
    with row1[0]:
        source_name = source_select(ctx.registry, key="content_query_source") if mode == "source" else None
    with row1[1]:
        group_name = optional_group_select(ctx.store, key="content_query_group") if mode == "group" else None
    row2 = st.columns(2)
    with row2[0]:
        channel_key = (
            optional_channel_select(
                [] if source_name is None else list_channel_options(ctx.registry, ctx.store, source_name),
                key="content_query_channel",
            )
            if mode == "source"
            else None
        )
    with row2[1]:
        keywords = st.text_input("Keywords", key="content_query_keywords")
    row3 = st.columns(2)
    with row3[0]:
        since = st.text_input("Since", key="content_query_since")
    with row3[1]:
        limit = st.number_input("Limit", min_value=1, value=20, key="content_query_limit")
    page_state = get_page_state(st.session_state, "content_query_page_state")

    run_clicked = st.button("Run Query", key="content_query_run")
    if run_clicked:
        try:
            result = query_content(
                ctx.registry,
                ctx.store,
                source_name=source_name,
                group_name=group_name,
                channel_key=channel_key or None,
                keywords=keywords or None,
                since=since or None,
                limit=int(limit),
            )
            save_page_result(
                st.session_state,
                "content_query_page_state",
                inputs={
                    "mode": mode,
                    "source": source_name,
                    "group": group_name,
                    "channel": channel_key,
                    "keywords": keywords,
                    "since": since,
                    "limit": int(limit),
                },
                result=result,
                updated_at=utc_now_iso(),
            )
            page_state = get_page_state(st.session_state, "content_query_page_state")
        except Exception as exc:  # noqa: BLE001
            render_exception(exc)

    render_rows(None if page_state["result"] is None else page_state["result"]["rows"], empty_message="Query the local database.")


if running_in_streamlit():
    render_page()
