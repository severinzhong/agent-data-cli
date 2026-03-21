from __future__ import annotations

import asyncio
import json
from urllib.request import ProxyHandler, build_opener


class BrowserFetcher:
    def __init__(self, *, cdp_url: str = "http://127.0.0.1:9222", wait_ms: int = 1500) -> None:
        self.cdp_url = cdp_url.rstrip("/")
        self.wait_ms = wait_ms
        self._collect_cdp_info()

    def _collect_cdp_info(self) -> None:
        if self.cdp_url.startswith(("ws://", "wss://")):
            self.ws_url = self.cdp_url
            self.user_agent = ""
            return
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"{self.cdp_url}/json/version", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.ws_url = payload["webSocketDebuggerUrl"]
        self.user_agent = payload["User-Agent"]

    def get_text(self, url: str) -> str:
        return asyncio.run(self._get_text_async(url))

    def fetch(self, url: str) -> str:
        return self.get_text(url)

    async def _get_text_async(self, url: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(self.ws_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if self.wait_ms:
                await page.wait_for_timeout(self.wait_ms)
            content = await page.content()
            await page.close()
            await browser.close()
            return content
