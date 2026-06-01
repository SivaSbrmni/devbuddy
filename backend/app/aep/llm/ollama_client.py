"""Async HTTP client for the Ollama API.

Targets the native Ollama wire format (``/api/generate``, ``/api/chat``,
``/api/embeddings``, ``/api/tags``) so the gateway can speak to either
a local ``ollama serve`` instance **or** Ollama Cloud — the only
difference is the base URL and the presence of an ``Authorization``
header (handled in :mod:`app.aep.llm.config`).

Key design points
-----------------

* **One client per process.** The module exposes a lazily constructed
  singleton with a shared ``httpx.AsyncClient`` so we get connection
  pooling for free. Tests can construct their own instance with an
  injected ``transport``.
* **Retries with exponential backoff** for network errors and 5xx
  responses. Caps at :attr:`AepLlmConfig.max_retries`.
* **Strict error translation.** Every failure mode is mapped to a
  :class:`app.aep.llm.errors.LlmGatewayError` subclass so the HTTP
  layer can render a stable envelope.
* **Streaming support** for ``generate`` / ``chat``. The client yields
  parsed JSON chunks as they arrive. The HTTP route layer wraps that
  iterator in a ``text/event-stream`` ``StreamingResponse``.
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import httpx

from app.aep.llm.config import AepLlmConfig, get_aep_llm_config
from app.aep.llm.errors import (
    InvalidRequest,
    ModelNotFound,
    UpstreamHttpError,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.aep.observability import aep_logger


_logger = aep_logger("aep.llm.ollama_client")


class OllamaClient:
    """Thin async wrapper over the Ollama HTTP API.

    Construct with no arguments for the default singleton-friendly
    behaviour. Tests should pass ``transport`` to inject a mock.
    """

    def __init__(
        self,
        *,
        config: Optional[AepLlmConfig] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._config = config or get_aep_llm_config()
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    # ─────────────────────────────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────────────────────────────

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            timeout = httpx.Timeout(
                self._config.request_timeout_seconds,
                connect=self._config.connect_timeout_seconds,
            )
            self._client = httpx.AsyncClient(
                base_url=self._config.base_url,
                headers=self._config.auth_headers(),
                timeout=timeout,
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @asynccontextmanager
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> AsyncIterator[httpx.Response]:
        client = await self._ensure_client()
        attempt = 0
        backoff = self._config.backoff_initial_seconds
        last_exc: Optional[Exception] = None
        while True:
            attempt += 1
            try:
                req = client.build_request(method, path, json=json_body)
                resp = await client.send(req, stream=stream)
                # Retry transient upstream failures (502/503/504) but not
                # client errors. ``response.raise_for_status`` is deferred
                # to the caller so streaming bodies aren't consumed here.
                if resp.status_code in (502, 503, 504) and attempt <= self._config.max_retries:
                    await resp.aclose()
                    await self._sleep_backoff(attempt, backoff)
                    backoff = min(backoff * 2, self._config.backoff_max_seconds)
                    continue
                try:
                    yield resp
                finally:
                    if not stream:
                        await resp.aclose()
                return
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt > self._config.max_retries:
                    raise UpstreamTimeout(
                        f"Ollama timed out after {self._config.request_timeout_seconds}s",
                        details={"path": path, "attempt": attempt},
                    ) from exc
                await self._sleep_backoff(attempt, backoff)
                backoff = min(backoff * 2, self._config.backoff_max_seconds)
            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt > self._config.max_retries:
                    raise UpstreamUnavailable(
                        f"Cannot reach Ollama at {self._config.base_url}: {exc}",
                        details={"path": path, "attempt": attempt},
                    ) from exc
                await self._sleep_backoff(attempt, backoff)
                backoff = min(backoff * 2, self._config.backoff_max_seconds)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt > self._config.max_retries:
                    raise UpstreamUnavailable(
                        f"Ollama HTTP error: {exc}",
                        details={"path": path, "attempt": attempt},
                    ) from exc
                await self._sleep_backoff(attempt, backoff)
                backoff = min(backoff * 2, self._config.backoff_max_seconds)

        # Unreachable, but keeps type-checkers happy.
        raise UpstreamUnavailable(  # pragma: no cover
            f"Ollama request failed: {last_exc!r}",
            details={"path": path},
        )

    async def _sleep_backoff(self, attempt: int, base: float) -> None:
        delay = min(base * (2 ** (attempt - 1)), self._config.backoff_max_seconds)
        await asyncio.sleep(delay)

    # ─────────────────────────────────────────────────────────────────
    # Public methods
    # ─────────────────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Lightweight upstream probe.

        Calls ``GET /api/tags`` because Ollama doesn't expose a
        dedicated health endpoint. A 2xx response means the server is
        reachable; we surface the model count as a soft readiness
        signal.
        """
        start = time.monotonic()
        async with self._request("GET", "/api/tags") as resp:
            self._raise_for_status(resp, body=None)
            payload = resp.json()
            elapsed_ms = int((time.monotonic() - start) * 1000)
            models = payload.get("models") or []
            _logger.info(
                "aep.llm.health",
                base_url=self._config.base_url,
                model_count=len(models),
                elapsed_ms=elapsed_ms,
            )
            return {
                "status": "ok",
                "base_url": self._config.base_url,
                "model_count": len(models),
                "elapsed_ms": elapsed_ms,
                "cloud": self._config.is_cloud,
            }

    async def list_models(self) -> list[dict[str, Any]]:
        async with self._request("GET", "/api/tags") as resp:
            self._raise_for_status(resp, body=None)
            payload = resp.json()
            return list(payload.get("models") or [])

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
        options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise InvalidRequest("`prompt` must not be empty")
        body = self._generate_body(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            options=options,
        )
        return await self._post_json("/api/generate", body)

    async def generate_stream(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
        options: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        if not prompt.strip():
            raise InvalidRequest("`prompt` must not be empty")
        body = self._generate_body(
            model=model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            options=options,
        )
        async for chunk in self._post_jsonl("/api/generate", body):
            yield chunk

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not messages:
            raise InvalidRequest("`messages` must contain at least one entry")
        body = self._chat_body(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            options=options,
        )
        return await self._post_json("/api/chat", body)

    async def chat_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 512,
        options: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        if not messages:
            raise InvalidRequest("`messages` must contain at least one entry")
        body = self._chat_body(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            options=options,
        )
        async for chunk in self._post_jsonl("/api/chat", body):
            yield chunk

    async def embed(
        self,
        *,
        model: str,
        inputs: list[str],
    ) -> list[list[float]]:
        if not inputs:
            raise InvalidRequest("`input` must contain at least one string")

        embeddings: list[list[float]] = []
        # Ollama's ``/api/embeddings`` accepts a single ``prompt`` per
        # call; we fan-out sequentially to preserve order and keep the
        # implementation portable to Ollama Cloud, which currently
        # mirrors the local surface.
        for text in inputs:
            if not text.strip():
                raise InvalidRequest("embedding inputs must be non-empty strings")
            payload = await self._post_json(
                "/api/embeddings",
                {"model": model, "prompt": text},
            )
            vec = payload.get("embedding")
            if not isinstance(vec, list):
                raise UpstreamHttpError(
                    "Ollama response missing `embedding` array",
                    details={"payload_keys": list(payload.keys())},
                )
            embeddings.append([float(x) for x in vec])
        return embeddings

    # ─────────────────────────────────────────────────────────────────
    # Body builders
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_body(
        *,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
        options: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        opts: dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
        if options:
            opts.update(options)
        return {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": opts,
        }

    @staticmethod
    def _chat_body(
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        stream: bool,
        options: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        opts: dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
        if options:
            opts.update(options)
        return {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": opts,
        }

    # ─────────────────────────────────────────────────────────────────
    # HTTP helpers
    # ─────────────────────────────────────────────────────────────────

    async def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        async with self._request("POST", path, json_body=body) as resp:
            self._raise_for_status(resp, body=body)
            return resp.json()

    async def _post_jsonl(
        self,
        path: str,
        body: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        async with self._request("POST", path, json_body=body, stream=True) as resp:
            if resp.status_code >= 400:
                # Need to read the body to surface the error message.
                content = await resp.aread()
                self._raise_for_status(resp, body=body, payload_bytes=content)
                return
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                yield chunk

    def _raise_for_status(
        self,
        resp: httpx.Response,
        *,
        body: Optional[dict[str, Any]],
        payload_bytes: Optional[bytes] = None,
    ) -> None:
        if resp.status_code < 400:
            return

        try:
            if payload_bytes is not None:
                upstream_payload = json.loads(payload_bytes.decode("utf-8"))
            else:
                upstream_payload = resp.json()
        except (ValueError, UnicodeDecodeError):
            upstream_payload = {
                "raw": (payload_bytes or b"").decode("utf-8", errors="replace")[:512]
                if payload_bytes is not None
                else None
            }

        message = (
            (upstream_payload or {}).get("error")
            if isinstance(upstream_payload, dict)
            else None
        )
        message = message or f"Ollama returned HTTP {resp.status_code}"

        details: dict[str, Any] = {"path": str(resp.request.url.path)}
        if body and "model" in body:
            details["model"] = body["model"]
        if isinstance(upstream_payload, dict):
            details["upstream"] = upstream_payload

        if resp.status_code == 404:
            raise ModelNotFound(
                message, upstream_status=resp.status_code, details=details
            )
        if resp.status_code == 400:
            raise InvalidRequest(
                message, upstream_status=resp.status_code, details=details
            )
        raise UpstreamHttpError(
            message, upstream_status=resp.status_code, details=details
        )


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────


_singleton: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Process-wide :class:`OllamaClient` singleton."""
    global _singleton
    if _singleton is None:
        _singleton = OllamaClient()
    return _singleton


def reset_ollama_client() -> None:
    """Test hook — drop the cached client (without closing it!)."""
    global _singleton
    _singleton = None


__all__ = ["OllamaClient", "get_ollama_client", "reset_ollama_client"]
