from __future__ import annotations

import streamlit as st


def source_select(registry, *, key: str, label: str = "Source") -> str | None:
    names = registry.list_names()
    if not names:
        st.warning("No sources discovered.")
        return None
    return st.selectbox(label, names, key=key)


def optional_group_select(store, *, key: str, label: str = "Group") -> str | None:
    groups = [item.group_name for item in store.list_groups()]
    options = [""] + groups
    selected = st.selectbox(label, options, key=key)
    return None if selected == "" else selected


def optional_channel_select(options: list[dict[str, str]], *, key: str, label: str = "Channel") -> str | None:
    labels_by_value = {item["value"]: item["label"] for item in options}
    selected = st.selectbox(
        label,
        ["", *labels_by_value.keys()],
        format_func=lambda value: "All" if value == "" else labels_by_value[value],
        key=key,
    )
    return None if selected == "" else selected
