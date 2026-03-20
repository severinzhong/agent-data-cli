from __future__ import annotations

from collections.abc import MutableMapping
from copy import deepcopy


DEFAULT_PAGE_STATE = {
    "inputs": {},
    "result": None,
    "ran": False,
    "updated_at": None,
}


def get_page_state(session_state: MutableMapping[str, object], page_key: str) -> dict[str, object]:
    state = session_state.get(page_key)
    if isinstance(state, dict):
        return state
    initialized = deepcopy(DEFAULT_PAGE_STATE)
    session_state[page_key] = initialized
    return initialized


def save_page_result(
    session_state: MutableMapping[str, object],
    page_key: str,
    *,
    inputs: dict[str, object],
    result: object,
    updated_at: str | None,
) -> dict[str, object]:
    state = get_page_state(session_state, page_key)
    state["inputs"] = dict(inputs)
    state["result"] = result
    state["ran"] = True
    state["updated_at"] = updated_at
    session_state[page_key] = state
    return state


def ensure_page_result(
    session_state: MutableMapping[str, object],
    page_key: str,
    *,
    loader,
    updated_at: str | None,
) -> dict[str, object]:
    state = get_page_state(session_state, page_key)
    if state["ran"]:
        return state
    state["result"] = loader()
    state["ran"] = True
    state["updated_at"] = updated_at
    session_state[page_key] = state
    return state


def invalidate_pages(session_state: MutableMapping[str, object], *page_keys: str) -> None:
    for page_key in page_keys:
        session_state[page_key] = deepcopy(DEFAULT_PAGE_STATE)
