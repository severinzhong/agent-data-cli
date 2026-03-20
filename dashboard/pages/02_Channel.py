from __future__ import annotations

import streamlit as st

from dashboard.adapters.channel import list_channel_options, list_channels, search_channels
from dashboard.adapters.group import add_channel_to_group
from dashboard.adapters.sub import add_subscription, remove_subscription
from dashboard.context import build_dashboard_context
from dashboard.state import get_page_state, invalidate_pages, save_page_result
from dashboard.widgets.common import render_exception, running_in_streamlit
from dashboard.widgets.forms import optional_channel_select, optional_group_select, source_select
from dashboard.widgets.tables import render_rows
from utils.time import utc_now_iso


def render_page() -> None:
    ctx = build_dashboard_context()
    st.title("Channel")
    form_row1 = st.columns(2)
    with form_row1[0]:
        source_name = source_select(ctx.registry, key="channel_source")
    with form_row1[1]:
        query = st.text_input("Query", key="channel_query")
    form_row2 = st.columns(2)
    with form_row2[0]:
        limit = st.number_input("Limit", min_value=1, value=20, key="channel_limit")
    page_state = get_page_state(st.session_state, "channel_page_state")

    with form_row2[1]:
        action_row = st.columns(2)
        with action_row[0]:
            list_clicked = st.button("List Channels", key="channel_list", width="stretch")
        with action_row[1]:
            search_clicked = st.button("Search Channels", key="channel_search", width="stretch")

    if list_clicked and source_name is not None:
        try:
            rows = list_channels(ctx.registry, ctx.store, source_name)
            save_page_result(
                st.session_state,
                "channel_page_state",
                inputs={"source": source_name, "mode": "list"},
                result={"rows": rows},
                updated_at=utc_now_iso(),
            )
            page_state = get_page_state(st.session_state, "channel_page_state")
        except Exception as exc:  # noqa: BLE001
            render_exception(exc)
    if search_clicked and source_name is not None:
        try:
            rows = search_channels(ctx.registry, ctx.store, source_name, query=query, limit=int(limit))
            save_page_result(
                st.session_state,
                "channel_page_state",
                inputs={"source": source_name, "query": query, "limit": int(limit)},
                result={"rows": rows},
                updated_at=utc_now_iso(),
            )
            page_state = get_page_state(st.session_state, "channel_page_state")
        except Exception as exc:  # noqa: BLE001
            render_exception(exc)

    render_rows(None if page_state["result"] is None else page_state["result"]["rows"], empty_message="Search or list channels.")

    action_inputs = st.columns(2)
    with action_inputs[0]:
        selected_channel = optional_channel_select(
            [] if source_name is None else list_channel_options(ctx.registry, ctx.store, source_name),
            key="channel_selected",
            label="Selected Channel",
        )
    with action_inputs[1]:
        selected_group = optional_group_select(ctx.store, key="channel_group")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Subscribe", key="channel_sub") and source_name is not None and selected_channel:
            try:
                add_subscription(ctx.registry, source_name, selected_channel)
                invalidate_pages(st.session_state, "sub_page_state", "channel_page_state", "content_update_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)
    with col2:
        if st.button("Unsubscribe", key="channel_unsub") and source_name is not None and selected_channel:
            try:
                remove_subscription(ctx.registry, source_name, selected_channel)
                invalidate_pages(st.session_state, "sub_page_state", "channel_page_state", "content_update_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)
    with col3:
        if st.button("Add To Group", key="channel_group_add") and source_name is not None and selected_channel and selected_group:
            try:
                add_channel_to_group(ctx.store, selected_group, source_name, selected_channel)
                invalidate_pages(st.session_state, "group_page_state", "content_update_page_state", "content_query_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)


if running_in_streamlit():
    render_page()
