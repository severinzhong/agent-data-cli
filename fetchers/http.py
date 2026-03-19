from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from .base import FetchResponse, RequestPolicy, RiskMarkers, RiskSignal, default_headers


DIRECT_PROXY_VALUE = "direct"

REQUEST_POLICIES = {
    "default": RequestPolicy(name="default", max_retries=1),
    "search": RequestPolicy(name="search", max_retries=1, retry_statuses=(429, 500, 502, 503, 504)),
    "update": RequestPolicy(name="update", max_retries=2, retry_statuses=(429, 500, 502, 503, 504)),
    "interact": RequestPolicy(name="interact", max_retries=0),
}


class HttpFetcher:
    def __init__(
        self,
        proxy_url: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        client_kwargs: dict[str, object] = {
            "follow_redirects": True,
        }
        if transport is not None:
            client_kwargs["transport"] = transport
        if proxy_url is None:
            client_kwargs["trust_env"] = True
        elif proxy_url == DIRECT_PROXY_VALUE:
            client_kwargs["trust_env"] = False
            client_kwargs["proxy"] = None
        else:
            client_kwargs["trust_env"] = False
            client_kwargs["proxy"] = proxy_url
        self._client = httpx.Client(**client_kwargs)
        self._cookies: dict[str, str] = {}
        self._last_request_at_by_scope: dict[str, float] = {}

    def close(self) -> None:
        self._client.close()

    def cookies(self) -> dict[str, str]:
        return dict(self._cookies)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, object] | None = None,
        content: bytes | str | None = None,
        json_body: object | None = None,
        cookies: dict[str, str] | None = None,
        policy: str | RequestPolicy | dict[str, object] | None = None,
        risk_markers: RiskMarkers | None = None,
    ) -> FetchResponse:
        resolved_policy = resolve_request_policy(policy)
        self._sleep_for_policy(resolved_policy, url)
        merged_cookies = dict(self._cookies)
        if cookies:
            merged_cookies.update(cookies)
        last_error: Exception | None = None
        response: httpx.Response | None = None
        attempts = max(1, resolved_policy.max_retries + 1)
        for attempt in range(attempts):
            try:
                response = self._client.request(
                    method,
                    url,
                    headers=default_headers(headers),
                    params=params,
                    content=content,
                    json=json_body,
                    cookies=merged_cookies or None,
                    timeout=resolved_policy.timeout_s,
                )
                self._merge_response_cookies(response)
                self._record_request_time(resolved_policy, url)
                if response.status_code in resolved_policy.retry_statuses and attempt + 1 < attempts:
                    self._sleep_for_retry(resolved_policy, attempt)
                    continue
                break
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise
                self._sleep_for_retry(resolved_policy, attempt)
        if response is None:
            raise last_error or RuntimeError("request failed before response")
        return FetchResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
            cookies=dict(response.cookies.items()),
            encoding=response.encoding,
            risk_signal=detect_risk_signal(response, risk_markers),
        )

    def get_bytes(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        policy: str | RequestPolicy | dict[str, object] | None = None,
    ) -> bytes:
        resolved_policy = _merge_timeout_into_policy(policy, timeout)
        return self.request(
            "GET",
            url,
            headers=headers,
            policy=resolved_policy,
        ).body

    def get_text(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        encoding: str = "utf-8",
        errors: str = "replace",
        policy: str | RequestPolicy | dict[str, object] | None = None,
    ) -> str:
        resolved_policy = _merge_timeout_into_policy(policy, timeout)
        return self.request(
            "GET",
            url,
            headers=headers,
            policy=resolved_policy,
        ).text(
            encoding=encoding,
            errors=errors,
        )

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        encoding: str = "utf-8",
        policy: str | RequestPolicy | dict[str, object] | None = None,
    ):
        resolved_policy = _merge_timeout_into_policy(policy, timeout)
        return self.request(
            "GET",
            url,
            headers=headers,
            policy=resolved_policy,
        ).json(encoding=encoding)


def resolve_request_policy(
    policy: str | RequestPolicy | dict[str, Any] | None,
) -> RequestPolicy:
    if policy is None:
        return REQUEST_POLICIES["default"]
    if isinstance(policy, RequestPolicy):
        return policy
    if isinstance(policy, str):
        try:
            return REQUEST_POLICIES[policy]
        except KeyError as exc:
            raise ValueError(f"unknown request policy: {policy}") from exc
    if isinstance(policy, dict):
        base_name = str(policy.get("base", "default"))
        base_policy = resolve_request_policy(base_name)
        return RequestPolicy(
            name=base_policy.name,
            timeout_s=float(policy.get("timeout_s", base_policy.timeout_s)),
            min_interval_ms=int(policy.get("min_interval_ms", base_policy.min_interval_ms)),
            jitter_ms=int(policy.get("jitter_ms", base_policy.jitter_ms)),
            max_retries=int(policy.get("max_retries", base_policy.max_retries)),
            backoff_ms=int(policy.get("backoff_ms", base_policy.backoff_ms)),
            retry_statuses=tuple(policy.get("retry_statuses", base_policy.retry_statuses)),
            risk_statuses=tuple(policy.get("risk_statuses", base_policy.risk_statuses)),
            cooldown_scope=str(policy.get("cooldown_scope", base_policy.cooldown_scope)),
        )
    raise TypeError(f"unsupported request policy value: {policy!r}")


def _merge_timeout_into_policy(
    policy: str | RequestPolicy | dict[str, object] | None,
    timeout: int | float,
) -> dict[str, object]:
    if policy is None:
        return {"base": "default", "timeout_s": float(timeout)}
    if isinstance(policy, str):
        return {"base": policy, "timeout_s": float(timeout)}
    if isinstance(policy, RequestPolicy):
        return {
            "base": policy.name,
            "timeout_s": float(timeout),
            "min_interval_ms": policy.min_interval_ms,
            "jitter_ms": policy.jitter_ms,
            "max_retries": policy.max_retries,
            "backoff_ms": policy.backoff_ms,
            "retry_statuses": policy.retry_statuses,
            "risk_statuses": policy.risk_statuses,
            "cooldown_scope": policy.cooldown_scope,
        }
    merged_policy = dict(policy)
    merged_policy["timeout_s"] = float(timeout)
    return merged_policy


def detect_risk_signal(response: httpx.Response, markers: RiskMarkers | None) -> RiskSignal | None:
    if markers is None:
        return None
    if response.status_code in markers.status_codes:
        return RiskSignal(kind="status_code", reason=f"matched status code {response.status_code}", status_code=response.status_code)
    normalized_headers = {key.lower(): value for key, value in response.headers.items()}
    for key in markers.header_keys:
        if key.lower() in normalized_headers:
            return RiskSignal(
                kind="header_marker",
                reason=f"matched header {key}",
                status_code=response.status_code,
                details={key.lower(): normalized_headers[key.lower()]},
            )
    if markers.body_contains:
        body_text = response.text
        for marker in markers.body_contains:
            if marker in body_text:
                return RiskSignal(
                    kind="body_marker",
                    reason=f"matched body marker {marker}",
                    status_code=response.status_code,
                )
    return None


def _cooldown_key(scope: str, url: str) -> str:
    if scope == "host":
        return httpx.URL(url).host or url
    return "shared"


def _sleep_seconds(duration_s: float) -> None:
    if duration_s > 0:
        time.sleep(duration_s)


def _compute_retry_delay_s(policy: RequestPolicy, attempt: int) -> float:
    base_delay_s = policy.backoff_ms / 1000
    if base_delay_s <= 0:
        return 0
    return base_delay_s * (2**attempt) + (random.uniform(0, policy.jitter_ms) / 1000 if policy.jitter_ms > 0 else 0)


def _compute_interval_delay_s(policy: RequestPolicy) -> float:
    delay_s = policy.min_interval_ms / 1000
    if policy.jitter_ms > 0:
        delay_s += random.uniform(0, policy.jitter_ms) / 1000
    return delay_s


def _now_s() -> float:
    return time.time()


def _request_scope_key(policy: RequestPolicy, url: str) -> str:
    return _cooldown_key(policy.cooldown_scope, url)


def _record_last_request(mapping: dict[str, float], key: str, value: float) -> None:
    mapping[key] = value


def _read_last_request(mapping: dict[str, float], key: str) -> float | None:
    return mapping.get(key)


def _merge_cookie_dict(target: dict[str, str], response: httpx.Response) -> None:
    for key, value in response.cookies.items():
        if value:
            target[key] = value


def _sleep_until_policy_window(policy: RequestPolicy, url: str, last_request_at_by_scope: dict[str, float]) -> None:
    if policy.min_interval_ms <= 0 and policy.jitter_ms <= 0:
        return
    scope_key = _request_scope_key(policy, url)
    last_request_at = _read_last_request(last_request_at_by_scope, scope_key)
    if last_request_at is None:
        return
    target_delay_s = _compute_interval_delay_s(policy)
    elapsed_s = _now_s() - last_request_at
    _sleep_seconds(target_delay_s - elapsed_s)


def _record_policy_request(policy: RequestPolicy, url: str, last_request_at_by_scope: dict[str, float]) -> None:
    _record_last_request(last_request_at_by_scope, _request_scope_key(policy, url), _now_s())


def _sleep_retry_backoff(policy: RequestPolicy, attempt: int) -> None:
    _sleep_seconds(_compute_retry_delay_s(policy, attempt))


HttpFetcher._sleep_for_policy = lambda self, policy, url: _sleep_until_policy_window(policy, url, self._last_request_at_by_scope)
HttpFetcher._record_request_time = lambda self, policy, url: _record_policy_request(policy, url, self._last_request_at_by_scope)
HttpFetcher._sleep_for_retry = lambda self, policy, attempt: _sleep_retry_backoff(policy, attempt)
HttpFetcher._merge_response_cookies = lambda self, response: _merge_cookie_dict(self._cookies, response)
