"""Browser Agent — Playwright-based browser automation for UI validation.

Capabilities:
- Open pages, click, type, submit forms
- Inspect DOM, capture screenshots
- Inspect network traffic
- Validate UI behavior
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

log = structlog.get_logger()


@dataclass
class BrowserAction:
    action_type: str  # navigate, click, type, screenshot, evaluate, wait
    selector: str = ""
    value: str = ""
    url: str = ""
    script: str = ""
    timeout_ms: int = 30000


@dataclass
class BrowserResult:
    success: bool
    action: str
    data: dict[str, Any]
    screenshot_path: str | None = None
    error: str | None = None


class BrowserAgent:
    """Wraps Playwright for autonomous browser-based testing and validation."""

    def __init__(self) -> None:
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._network_log: list[dict[str, Any]] = []

    async def startup(self) -> None:
        try:
            from playwright.async_api import async_playwright
            pw = await async_playwright().start()
            self._browser = await pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            self._page = await self._context.new_page()
            self._page.on("request", self._on_request)
            self._page.on("response", self._on_response)
            log.info("browser_agent.started")
        except Exception as exc:
            log.warning("browser_agent.startup_failed", error=str(exc))

    async def shutdown(self) -> None:
        if self._browser:
            await self._browser.close()
            log.info("browser_agent.stopped")

    async def execute_action(self, action: BrowserAction) -> BrowserResult:
        if not self._page:
            return BrowserResult(success=False, action=action.action_type, data={}, error="Browser not initialized")

        try:
            if action.action_type == "navigate":
                await self._page.goto(action.url, timeout=action.timeout_ms)
                return BrowserResult(success=True, action="navigate", data={"url": action.url})

            elif action.action_type == "click":
                await self._page.click(action.selector, timeout=action.timeout_ms)
                return BrowserResult(success=True, action="click", data={"selector": action.selector})

            elif action.action_type == "type":
                await self._page.fill(action.selector, action.value, timeout=action.timeout_ms)
                return BrowserResult(success=True, action="type", data={"selector": action.selector})

            elif action.action_type == "screenshot":
                path = action.value or "/tmp/screenshot.png"
                await self._page.screenshot(path=path, full_page=True)
                return BrowserResult(success=True, action="screenshot", data={}, screenshot_path=path)

            elif action.action_type == "evaluate":
                result = await self._page.evaluate(action.script)
                return BrowserResult(success=True, action="evaluate", data={"result": result})

            elif action.action_type == "wait":
                await self._page.wait_for_selector(action.selector, timeout=action.timeout_ms)
                return BrowserResult(success=True, action="wait", data={"selector": action.selector})

            elif action.action_type == "get_text":
                text = await self._page.text_content(action.selector)
                return BrowserResult(success=True, action="get_text", data={"text": text})

            elif action.action_type == "get_html":
                html = await self._page.content()
                return BrowserResult(success=True, action="get_html", data={"html": html[:50000]})

            else:
                return BrowserResult(
                    success=False, action=action.action_type, data={},
                    error=f"Unknown action: {action.action_type}",
                )

        except Exception as exc:
            log.error("browser_agent.action_failed", action=action.action_type, error=str(exc))
            return BrowserResult(success=False, action=action.action_type, data={}, error=str(exc))

    def get_network_log(self) -> list[dict[str, Any]]:
        return self._network_log[-100:]  # last 100 entries

    def _on_request(self, request: Any) -> None:
        self._network_log.append({
            "type": "request",
            "url": request.url,
            "method": request.method,
        })

    def _on_response(self, response: Any) -> None:
        self._network_log.append({
            "type": "response",
            "url": response.url,
            "status": response.status,
        })


# Singleton
browser_agent = BrowserAgent()
