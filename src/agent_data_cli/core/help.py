from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HelpSection:
    title: str
    lines: list[str]


@dataclass(slots=True)
class HelpDoc:
    title: str
    summary: str
    sections: list[HelpSection]
