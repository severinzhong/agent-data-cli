from __future__ import annotations

import streamlit as st

from dashboard.adapters.help import build_help_doc_for_topic, list_help_topics
from dashboard.context import build_dashboard_context
from dashboard.state import get_page_state, save_page_result
from dashboard.widgets.common import running_in_streamlit
from utils.time import utc_now_iso


def render_page() -> None:
    ctx = build_dashboard_context()
    st.title("Help")
    topics = list_help_topics(ctx.registry)
    topic = st.selectbox(
        "Topic",
        ["global", *topics["commands"], *topics["sources"]],
        key="help_topic",
    )
    page_state = get_page_state(st.session_state, "help_page_state")

    if st.button("Load Help", key="help_load"):
        doc = build_help_doc_for_topic(ctx.registry, topic)
        save_page_result(
            st.session_state,
            "help_page_state",
            inputs={"topic": topic},
            result={"doc": doc},
            updated_at=utc_now_iso(),
        )
        page_state = get_page_state(st.session_state, "help_page_state")

    if page_state["result"] is None:
        st.info("Load global, command, or source help.")
        return

    doc = page_state["result"]["doc"]
    st.subheader(doc.title)
    st.caption(doc.summary)
    for section in doc.sections:
        st.markdown(f"### {section.title}")
        for line in section.lines:
            st.markdown(f"- {line}")


if running_in_streamlit():
    render_page()
