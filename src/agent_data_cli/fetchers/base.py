from __future__ import annotations

from dataclasses import dataclass, field
import json


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


@dataclass(slots=True)
class FetchResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes
    cookies: dict[str, str] = field(default_factory=dict)
    encoding: str | None = None
    risk_signal: RiskSignal | None = None

    def text(self, encoding: str = "utf-8", errors: str = "replace") -> str:
        return self.body.decode(self.encoding or encoding, errors=errors)

    def json(self, encoding: str = "utf-8"):
        return json.loads(self.text(encoding=encoding))


@dataclass(frozen=True, slots=True)
class RequestPolicy:
    name: str
    timeout_s: float = 30.0
    min_interval_ms: int = 0
    jitter_ms: int = 0
    max_retries: int = 0
    backoff_ms: int = 0
    retry_statuses: tuple[int, ...] = ()
    risk_statuses: tuple[int, ...] = ()
    cooldown_scope: str = "source"


@dataclass(frozen=True, slots=True)
class RiskMarkers:
    status_codes: tuple[int, ...] = ()
    header_keys: tuple[str, ...] = ()
    body_contains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RiskSignal:
    kind: str
    reason: str
    status_code: int | None = None
    details: dict[str, str] = field(default_factory=dict)


def default_headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    return headers
