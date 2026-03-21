from __future__ import annotations

import streamlit as st

from agent_data_cli.dashboard.adapters.group import (
    add_channel_to_group,
    add_source_to_group,
    create_group,
    delete_group,
    list_group_members,
    list_groups,
    remove_channel_from_group,
    remove_source_from_group,
)
from agent_data_cli.dashboard.context import build_dashboard_context
from agent_data_cli.dashboard.state import get_page_state, invalidate_pages, save_page_result
from agent_data_cli.dashboard.widgets.common import render_exception, running_in_streamlit
from agent_data_cli.dashboard.widgets.forms import optional_group_select, source_select
from agent_data_cli.dashboard.widgets.tables import render_rows
from agent_data_cli.utils.time import utc_now_iso


def render_page() -> None:
    ctx = build_dashboard_context()
    st.title("Group")
    page_state = get_page_state(st.session_state, "group_page_state")

    if st.button("Refresh Groups", key="group_refresh"):
        rows = list_groups(ctx.store)
        save_page_result(st.session_state, "group_page_state", inputs={}, result={"rows": rows}, updated_at=utc_now_iso())
        page_state = get_page_state(st.session_state, "group_page_state")

    render_rows(None if page_state["result"] is None else page_state["result"]["rows"], empty_message="No groups yet.")

    input_row1 = st.columns(2)
    with input_row1[0]:
        group_name = st.text_input("Group Name", key="group_name")
    with input_row1[1]:
        selected_group = optional_group_select(ctx.store, key="group_selected")
    input_row2 = st.columns(2)
    with input_row2[0]:
        source_name = source_select(ctx.registry, key="group_source")
    with input_row2[1]:
        channel_key = st.text_input("Channel", key="group_channel")

    row1 = st.columns(2)
    with row1[0]:
        if st.button("Create Group", key="group_create") and group_name:
            try:
                rows = create_group(ctx.store, group_name)
                save_page_result(
                    st.session_state,
                    "group_page_state",
                    inputs={},
                    result={"rows": rows},
                    updated_at=utc_now_iso(),
                )
                invalidate_pages(st.session_state, "content_update_page_state", "content_query_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)
    with row1[1]:
        if st.button("Delete Group", key="group_delete") and selected_group:
            try:
                rows = delete_group(ctx.store, selected_group)
                save_page_result(
                    st.session_state,
                    "group_page_state",
                    inputs={},
                    result={"rows": rows},
                    updated_at=utc_now_iso(),
                )
                invalidate_pages(st.session_state, "content_update_page_state", "content_query_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)

    row2 = st.columns(2)
    with row2[0]:
        if st.button("Show Members", key="group_members_show") and selected_group:
            try:
                st.write(list_group_members(ctx.store, selected_group))
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)
    with row2[1]:
        if st.button("Add Source", key="group_add_source") and selected_group and source_name:
            try:
                st.write(add_source_to_group(ctx.store, selected_group, source_name))
                invalidate_pages(st.session_state, "content_update_page_state", "content_query_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)

    row3 = st.columns(2)
    with row3[0]:
        if st.button("Add Channel", key="group_add_channel") and selected_group and source_name and channel_key:
            try:
                st.write(add_channel_to_group(ctx.store, selected_group, source_name, channel_key))
                invalidate_pages(st.session_state, "content_update_page_state", "content_query_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)
    with row3[1]:
        if st.button("Remove Source", key="group_remove_source") and selected_group and source_name:
            try:
                st.write(remove_source_from_group(ctx.store, selected_group, source_name))
                invalidate_pages(st.session_state, "content_update_page_state", "content_query_page_state")
            except Exception as exc:  # noqa: BLE001
                render_exception(exc)

    if st.button("Remove Channel", key="group_remove_channel") and selected_group and source_name and channel_key:
        try:
            st.write(remove_channel_from_group(ctx.store, selected_group, source_name, channel_key))
            invalidate_pages(st.session_state, "content_update_page_state", "content_query_page_state")
        except Exception as exc:  # noqa: BLE001
            render_exception(exc)


if running_in_streamlit():
    render_page()
