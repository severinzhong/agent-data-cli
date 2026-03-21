from __future__ import annotations

import streamlit as st

from agent_data_cli.dashboard.adapters.sub import list_subscriptions, remove_subscription
from agent_data_cli.dashboard.context import build_dashboard_context
from agent_data_cli.dashboard.state import get_page_state, invalidate_pages, save_page_result
from agent_data_cli.dashboard.widgets.common import render_exception, running_in_streamlit
from agent_data_cli.dashboard.widgets.forms import source_select
from agent_data_cli.dashboard.widgets.tables import render_rows
from agent_data_cli.utils.time import utc_now_iso


def render_page() -> None:
    ctx = build_dashboard_context()
    st.title("Subscriptions")
    selected_source = st.checkbox("Filter by source", key="sub_filter_enabled")
    source_name = source_select(ctx.registry, key="sub_source") if selected_source else None
    page_state = get_page_state(st.session_state, "sub_page_state")

    if st.button("Refresh Subscriptions", key="sub_refresh"):
        rows = list_subscriptions(ctx.store, source_name=source_name)
        save_page_result(
            st.session_state,
            "sub_page_state",
            inputs={"source": source_name},
            result={"rows": rows},
            updated_at=utc_now_iso(),
        )
        page_state = get_page_state(st.session_state, "sub_page_state")

    render_rows(None if page_state["result"] is None else page_state["result"]["rows"], empty_message="No subscriptions yet.")

    channel_key = st.text_input("Channel To Remove", key="sub_remove_channel")
    if st.button("Remove Subscription", key="sub_remove") and source_name is not None and channel_key:
        try:
            rows = remove_subscription(ctx.registry, source_name, channel_key)
            save_page_result(
                st.session_state,
                "sub_page_state",
                inputs={"source": source_name},
                result={"rows": rows},
                updated_at=utc_now_iso(),
            )
            invalidate_pages(st.session_state, "channel_page_state", "content_update_page_state")
        except Exception as exc:  # noqa: BLE001
            render_exception(exc)


if running_in_streamlit():
    render_page()
