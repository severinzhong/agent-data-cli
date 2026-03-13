from __future__ import annotations

import json
import random
import time
from typing import Any

import httpx

from core.protocol import AuthRequiredError, RemoteExecutionError

from .constants import CREATOR_HOST, EDITH_HOST, HOME_URL, USER_AGENT
from .signing import build_get_uri, sign_creator, sign_main_api


DIRECT_PROXY_VALUE = "direct"


class XiaohongshuClient:
    def __init__(
        self,
        *,
        cookies: dict[str, str],
        timeout: float = 30.0,
        request_delay: float = 0.5,
        max_retries: int = 3,
        proxy_url: str | None = None,
    ) -> None:
        self.cookies = dict(cookies)
        client_kwargs: dict[str, object] = {
            "timeout": timeout,
            "follow_redirects": True,
        }
        if proxy_url is None:
            client_kwargs["trust_env"] = True
        elif proxy_url == DIRECT_PROXY_VALUE:
            client_kwargs["trust_env"] = False
            client_kwargs["proxy"] = None
        else:
            client_kwargs["trust_env"] = False
            client_kwargs["proxy"] = proxy_url
        self._http = httpx.Client(**client_kwargs)
        self._request_delay = request_delay
        self._max_retries = max_retries
        self._last_request_time = 0.0

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> XiaohongshuClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def get_self_info(self) -> dict[str, Any]:
        data = self._main_api_get("/api/sns/web/v2/user/me")
        if not isinstance(data, dict):
            raise RemoteExecutionError("xiaohongshu returned invalid self info payload")
        return data

    def search_users(self, keyword: str) -> dict[str, Any]:
        data = self._creator_post(
            "/web_api/sns/v1/search/user_info",
            {
                "keyword": keyword,
                "search_id": str(int(time.time() * 1000)),
                "page": {"page_size": 20, "page": 1},
            },
        )
        if not isinstance(data, dict):
            raise RemoteExecutionError("xiaohongshu returned invalid user search payload")
        return data

    def search_notes(
        self,
        keyword: str,
        *,
        page: int = 1,
        page_size: int = 20,
        sort: str = "general",
        note_type: int = 0,
    ) -> dict[str, Any]:
        data = self._main_api_post(
            "/api/sns/web/v1/search/notes",
            {
                "keyword": keyword,
                "page": page,
                "page_size": page_size,
                "search_id": self._search_id(),
                "sort": sort,
                "note_type": note_type,
                "ext_flags": [],
                "filters": [],
                "geo": "",
                "image_formats": ["jpg", "webp", "avif"],
            },
        )
        if not isinstance(data, dict):
            raise RemoteExecutionError("xiaohongshu returned invalid note search payload")
        return data

    def get_user_notes(self, user_id: str, *, cursor: str = "") -> dict[str, Any]:
        data = self._main_api_get(
            "/api/sns/web/v1/user_posted",
            {
                "num": 30,
                "cursor": cursor,
                "user_id": user_id,
                "image_scenes": "FD_WM_WEBP",
            },
        )
        if not isinstance(data, dict):
            raise RemoteExecutionError("xiaohongshu returned invalid user notes payload")
        return data

    def get_note_detail(self, note_id: str, *, xsec_token: str = "", xsec_source: str = "pc_feed") -> dict[str, Any]:
        data = self._main_api_post(
            "/api/sns/web/v1/feed",
            {
                "source_note_id": note_id,
                "image_formats": ["jpg", "webp", "avif"],
                "extra": {"need_body_topic": "1"},
                "xsec_source": xsec_source,
                "xsec_token": xsec_token,
            },
        )
        if not isinstance(data, dict):
            raise RemoteExecutionError("xiaohongshu returned invalid note detail payload")
        return data

    def like_note(self, note_id: str) -> dict[str, Any]:
        return self._expect_dict(self._main_api_post("/api/sns/web/v1/note/like", {"note_oid": note_id}))

    def unlike_note(self, note_id: str) -> dict[str, Any]:
        return self._expect_dict(self._main_api_post("/api/sns/web/v1/note/dislike", {"note_oid": note_id}))

    def favorite_note(self, note_id: str) -> dict[str, Any]:
        return self._expect_dict(self._main_api_post("/api/sns/web/v1/note/collect", {"note_id": note_id}))

    def unfavorite_note(self, note_id: str) -> dict[str, Any]:
        return self._expect_dict(self._main_api_post("/api/sns/web/v1/note/uncollect", {"note_ids": note_id}))

    def post_comment(self, note_id: str, content: str) -> dict[str, Any]:
        return self._expect_dict(
            self._main_api_post(
                "/api/sns/web/v1/comment/post",
                {
                    "note_id": note_id,
                    "content": content,
                    "at_users": [],
                },
            )
        )

    def _expect_dict(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise RemoteExecutionError("xiaohongshu returned invalid payload")
        return value

    def _main_api_get(self, uri: str, params: dict[str, str | int | list[str]] | None = None) -> Any:
        headers = {
            **self._base_headers(),
            **sign_main_api("GET", uri, self.cookies, params=params),
        }
        url = f"{EDITH_HOST}{build_get_uri(uri, params)}"
        response = self._request_with_retry("GET", url, headers=headers)
        return self._handle_response(response)

    def _main_api_post(self, uri: str, data: dict[str, Any]) -> Any:
        headers = {
            **self._base_headers(),
            **sign_main_api("POST", uri, self.cookies, payload=data),
        }
        response = self._request_with_retry(
            "POST",
            f"{EDITH_HOST}{uri}",
            headers=headers,
            content=json.dumps(data, separators=(",", ":")),
        )
        return self._handle_response(response)

    def _creator_post(self, uri: str, data: dict[str, Any]) -> Any:
        host = self._creator_host(uri)
        headers = {
            **self._base_headers(),
            **sign_creator(f"url={uri}", data, self.cookies["a1"]),
            "origin": CREATOR_HOST,
            "referer": f"{CREATOR_HOST}/",
        }
        response = self._request_with_retry(
            "POST",
            f"{host}{uri}",
            headers=headers,
            content=json.dumps(data, separators=(",", ":")),
        )
        return self._handle_response(response)

    def _creator_host(self, uri: str) -> str:
        if uri.startswith("/api/galaxy/"):
            return CREATOR_HOST
        return EDITH_HOST

    def _base_headers(self) -> dict[str, str]:
        return {
            "user-agent": USER_AGENT,
            "content-type": "application/json;charset=UTF-8",
            "cookie": self._cookie_header(),
            "origin": HOME_URL,
            "referer": f"{HOME_URL}/",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "dnt": "1",
            "priority": "u=1, i",
        }

    def _cookie_header(self) -> str:
        return "; ".join(f"{key}={value}" for key, value in self.cookies.items())

    def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        self._sleep_if_needed()
        last_error: Exception | None = None
        response: httpx.Response | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._http.request(method, url, **kwargs)
                self._merge_response_cookies(response)
                self._last_request_time = time.time()
                if response.status_code in (429, 500, 502, 503, 504):
                    wait_seconds = (2**attempt) + random.uniform(0, 1)
                    time.sleep(wait_seconds)
                    continue
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                wait_seconds = (2**attempt) + random.uniform(0, 1)
                time.sleep(wait_seconds)
        if last_error is not None:
            raise RemoteExecutionError(f"xiaohongshu request failed: {last_error}") from last_error
        if response is None:
            raise RemoteExecutionError("xiaohongshu request failed before response")
        raise RemoteExecutionError(f"xiaohongshu request failed: HTTP {response.status_code}")

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code in (461, 471):
            raise RemoteExecutionError(
                f"xiaohongshu requires verification: type={response.headers.get('verifytype', 'unknown')}, "
                f"uuid={response.headers.get('verifyuuid', 'unknown')}"
            )

        text = response.text
        if not text:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RemoteExecutionError(f"xiaohongshu returned non-JSON response: {text[:200]}") from exc

        if payload.get("success"):
            return payload.get("data", payload.get("success"))

        code = payload.get("code")
        if code == -100:
            raise AuthRequiredError("xiaohongshu cookie is invalid or expired; please update xiaohongshu.cookie")
        if code == 300015:
            raise RemoteExecutionError("xiaohongshu signature verification failed")
        if code == 300012:
            raise RemoteExecutionError("xiaohongshu IP was blocked")
        raise RemoteExecutionError(f"xiaohongshu API error: {json.dumps(payload, ensure_ascii=False)[:300]}")

    def _merge_response_cookies(self, response: httpx.Response) -> None:
        for key, value in response.cookies.items():
            if value:
                self.cookies[key] = value

    def _search_id(self) -> str:
        return f"{int(time.time() * 1000)}{random.randint(1000, 9999)}"

    def _sleep_if_needed(self) -> None:
        if self._request_delay <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)
