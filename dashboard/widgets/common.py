from __future__ import annotations

import streamlit as st


def format_object_value(value: object) -> str:
    if value is None:
        return "unset"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(format_object_value(item) for item in value)
    return str(value)


def build_object_sections(data: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    rows: list[dict[str, object]] = []
    sections: list[dict[str, object]] = []
    for key, value in data.items():
        if isinstance(value, dict):
            sections.append(
                {
                    "title": key,
                    "kind": "object",
                    "rows": build_object_sections(value)["rows"],
                    "sections": build_object_sections(value)["sections"],
                }
            )
            continue
        if _is_table_like_list(value):
            sections.append(
                {
                    "title": key,
                    "kind": "table",
                    "rows": value,
                }
            )
            continue
        rows.append({"key": key, "value": format_object_value(value)})
    return {"rows": rows, "sections": sections}


def render_object_details(data: dict[str, object], *, title: str | None = None) -> None:
    sections = build_object_sections(data)
    if title is not None:
        st.subheader(title)
    _render_kv_rows(sections["rows"])
    for section in sections["sections"]:
        st.markdown(f"##### {section['title']}")
        if section["kind"] == "table":
            st.dataframe(section["rows"], width="stretch", hide_index=True)
            continue
        with st.container(border=True):
            _render_kv_rows(section["rows"])
            for nested in section["sections"]:
                st.markdown(f"###### {nested['title']}")
                if nested["kind"] == "table":
                    st.dataframe(nested["rows"], width="stretch", hide_index=True)
                else:
                    _render_kv_rows(nested["rows"])


def render_exception(exc: Exception) -> None:
    st.error(str(exc))


def render_notice(message: str) -> None:
    st.info(message)


def running_in_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except Exception:  # noqa: BLE001
        return False
    return get_script_run_ctx() is not None


def _is_table_like_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, dict) for item in value)


def _render_kv_rows(rows: list[dict[str, object]]) -> None:
    with st.container(border=True):
        for row in rows:
            left, right = st.columns([1, 2])
            with left:
                st.caption(str(row["key"]))
            with right:
                st.markdown(str(row["value"]))
