from __future__ import annotations

import streamlit as st


def render_rows(rows: list[dict[str, object]] | None, *, empty_message: str = "No rows.") -> None:
    if not rows:
        st.info(empty_message)
        return
    st.dataframe(rows, width="stretch", hide_index=True)
