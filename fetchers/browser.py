import json
import asyncio
from typing import Callable
from urllib.request import ProxyHandler, build_opener

from .base import Fetcher


class BrowserFetcher(Fetcher):
    def __init__(
        self,
        *,
        cdp_url: str  = "http://127.0.0.1:9222",
        wait_ms: int = 1500,
        renderer: Callable[[str], str] | None = None,
    ) -> None:
        self.cdp_url = cdp_url.rstrip("/")
        self.collect_cdp_info(self.cdp_url)
        self.wait_ms = wait_ms
        self.renderer = renderer
        
    def collect_cdp_info(self, cdp_url: str):
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"{cdp_url}/json/version", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.ws_url = payload.get("webSocketDebuggerUrl")
        self.user_agent = payload.get("User-Agent")
        self.user_ganet = self.user_agent

    def fetch(self, target: str) -> str:
        return asyncio.run(self._fetch_async(target))

    async def _fetch_async(self, target: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            await page.goto(target, wait_until="domcontentloaded", timeout=45000)
            if self.wait_ms:
                await page.wait_for_timeout(self.wait_ms)
            content = await page.content()
            await page.close()
            await browser.close()
            return content
