from __future__ import annotations

import streamlit as st

from dashboard.adapters.channel import list_channel_options
from dashboard.adapters.content import search_content
from dashboard.context import build_dashboard_context
from dashboard.state import get_page_state, save_page_result
from dashboard.widgets.common import render_exception, running_in_streamlit
from dashboard.widgets.forms import optional_channel_select, source_select
from dashboard.widgets.tables import render_rows
from utils.time import utc_now_iso


def render_page() -> None:
    ctx = build_dashboard_context()
    st.title("Content Search")
    row1 = st.columns(2)
    with row1[0]:
        source_name = source_select(ctx.registry, key="content_search_source")
    with row1[1]:
        channel = optional_channel_select(
            [] if source_name is None else list_channel_options(ctx.registry, ctx.store, source_name),
            key="content_search_channel",
        )
    row2 = st.columns(2)
    with row2[0]:
        query = st.text_input("Query", key="content_search_query")
    with row2[1]:
        since = st.text_input("Since", key="content_search_since")
    row3 = st.columns(2)
    with row3[0]:
        limit = st.number_input("Limit", min_value=1, value=20, key="content_search_limit")
    page_state = get_page_state(st.session_state, "content_search_page_state")

    with row3[1]:
        run_clicked = st.button("Run Search", key="content_search_run", use_container_width=True)

    if run_clicked and source_name is not None:
        try:
            rows = search_content(
                ctx.registry,
                source_name,
                channel=channel or None,
                query=query or None,
                since=since or None,
                limit=int(limit),
            )
            save_page_result(
                st.session_state,
                "content_search_page_state",
                inputs={"source": source_name, "channel": channel, "query": query, "since": since, "limit": int(limit)},
                result={"rows": rows},
                updated_at=utc_now_iso(),
            )
            page_state = get_page_state(st.session_state, "content_search_page_state")
        except Exception as exc:  # noqa: BLE001
            render_exception(exc)

    render_rows(None if page_state["result"] is None else page_state["result"]["rows"], empty_message="Run a remote content search.")


if running_in_streamlit():
    render_page()
