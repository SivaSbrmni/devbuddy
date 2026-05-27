"""High-level service backing the ``/LLM`` HTTP gateway.

Sits between the FastAPI route handlers and :class:`OllamaClient`. The
service owns:

* model resolution (delegated to :class:`ModelRouter`)
* token accounting + structured logging
* envelope shaping so route handlers stay thin
* a single place to plug in the compatibility adapter LLM hooks when
  Phase 2+ work needs to observe every call
"""
from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Optional

from app.aep.compat import LlmCallPayload, get_compatibility_adapter
from app.aep.llm.config import AepLlmConfig, get_aep_llm_config
from app.aep.llm.errors import InvalidRequest
from app.aep.llm.ollama_client import OllamaClient, get_ollama_client
from app.aep.llm.router import ModelRouter, RouteDecision, get_model_router
from app.aep.observability import aep_logger


_logger = aep_logger("aep.llm.gateway")

PROVIDER_LABEL = "aep-ollama"
_PREVIEW_CHARS = 160


def _preview(text: str) -> str:
    text = text or ""
    if len(text) <= _PREVIEW_CHARS:
        return text
    return text[:_PREVIEW_CHARS] + "…"


def _chat_preview(messages: list[dict[str, Any]]) -> str:
    try:
        last = next(
            (m for m in reversed(messages) if m.get("role") == "user"),
            messages[-1] if messages else None,
        )
        if last is None:
            return ""
        content = last.get("content") or ""
        if isinstance(content, list):
            content = json.dumps(content)[:200]
        return _preview(str(content))
    except Exception:
        return ""


class LlmGatewayService:
    """Façade over :class:`OllamaClient` for the HTTP layer."""

    def __init__(
        self,
        *,
        client: Optional[OllamaClient] = None,
        router: Optional[ModelRouter] = None,
        config: Optional[AepLlmConfig] = None,
    ) -> None:
        self._client = client or get_ollama_client()
        self._router = router or get_model_router()
        self._config = config or get_aep_llm_config()
        self._adapter = get_compatibility_adapter()

    # ─────────────────────────────────────────────────────────────────
    # Diagnostics
    # ─────────────────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        upstream = await self._client.health()
        return {
            "status": "ok",
            "upstream": upstream,
            "default_model": self._config.default_model,
            "embedding_model": self._config.embedding_model,
        }

    async def list_models(self) -> dict[str, Any]:
        models = await self._client.list_models()
        return {
            "models": models,
            "default_model": self._config.default_model,
            "embedding_model": self._config.embedding_model,
            "routing": self._router.as_mapping(),
        }

    def route(self, task_type: str, *, override: Optional[str] = None) -> dict[str, Any]:
        decision = self._router.route(task_type, override=override)
        return _decision_to_envelope(decision)

    # ─────────────────────────────────────────────────────────────────
    # Inference
    # ─────────────────────────────────────────────────────────────────

    async def generate(
        self,
        *,
        prompt: str,
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        metadata: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        purpose: str = "generate",
    ) -> dict[str, Any]:
        resolved = self._resolve_model("generic", model)
        request_payload = {
            "prompt_chars": len(prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "metadata": metadata or {},
        }
        await self._adapter.dispatch_pre_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=_preview(prompt),
                purpose=purpose,
                request=request_payload,
            )
        )

        start = time.monotonic()
        try:
            response = await self._client.generate(
                model=resolved,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            await self._dispatch_error_post(
                resolved, _preview(prompt), purpose, request_payload, exc, tenant_id
            )
            raise

        elapsed_ms = (time.monotonic() - start) * 1000

        prompt_tokens = int(response.get("prompt_eval_count") or 0)
        completion_tokens = int(response.get("eval_count") or 0)
        text = str(response.get("response") or "")

        await self._adapter.dispatch_post_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=_preview(prompt),
                purpose=purpose,
                request=request_payload,
                response=_preview(text),
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                duration_ms=elapsed_ms,
            )
        )
        self._log_call("generate", resolved, prompt_tokens, completion_tokens, elapsed_ms)

        return {
            "model": resolved,
            "response": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "elapsed_ms": int(elapsed_ms),
            "done": bool(response.get("done", True)),
        }

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        metadata: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        purpose: str = "chat",
    ) -> dict[str, Any]:
        resolved = self._resolve_model("generic", model)
        request_payload = {
            "message_count": len(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "metadata": metadata or {},
        }
        preview = _chat_preview(messages)

        await self._adapter.dispatch_pre_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=preview,
                purpose=purpose,
                request=request_payload,
            )
        )

        start = time.monotonic()
        try:
            response = await self._client.chat(
                model=resolved,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            await self._dispatch_error_post(
                resolved, preview, purpose, request_payload, exc, tenant_id
            )
            raise

        elapsed_ms = (time.monotonic() - start) * 1000

        msg = response.get("message") or {}
        prompt_tokens = int(response.get("prompt_eval_count") or 0)
        completion_tokens = int(response.get("eval_count") or 0)
        text = str(msg.get("content") or "")

        await self._adapter.dispatch_post_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=preview,
                purpose=purpose,
                request=request_payload,
                response=_preview(text),
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                duration_ms=elapsed_ms,
            )
        )
        self._log_call("chat", resolved, prompt_tokens, completion_tokens, elapsed_ms)

        return {
            "model": resolved,
            "message": {
                "role": str(msg.get("role") or "assistant"),
                "content": text,
            },
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "elapsed_ms": int(elapsed_ms),
            "done": bool(response.get("done", True)),
        }

    async def embed(
        self,
        *,
        inputs: list[str],
        model: Optional[str],
        metadata: Optional[dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        purpose: str = "embed",
    ) -> dict[str, Any]:
        resolved = self._resolve_embedding_model(model)
        preview = _preview(inputs[0] if inputs else "")
        request_payload = {
            "input_count": len(inputs),
            "metadata": metadata or {},
        }
        await self._adapter.dispatch_pre_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=preview,
                purpose=purpose,
                request=request_payload,
            )
        )

        start = time.monotonic()
        try:
            vectors = await self._client.embed(model=resolved, inputs=inputs)
        except Exception as exc:
            await self._dispatch_error_post(
                resolved, preview, purpose, request_payload, exc, tenant_id
            )
            raise

        elapsed_ms = (time.monotonic() - start) * 1000
        dim = len(vectors[0]) if vectors else 0

        await self._adapter.dispatch_post_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=preview,
                purpose=purpose,
                request=request_payload,
                response=None,
                usage={"vectors": len(vectors), "dim": dim},
                duration_ms=elapsed_ms,
            )
        )
        self._log_call(
            "embed",
            resolved,
            prompt_tokens=0,
            completion_tokens=0,
            elapsed_ms=elapsed_ms,
            extra={"vector_count": len(vectors), "dim": dim},
        )

        return {
            "model": resolved,
            "embeddings": vectors,
            "count": len(vectors),
            "dim": dim,
            "elapsed_ms": int(elapsed_ms),
        }

    # ─────────────────────────────────────────────────────────────────
    # Streaming
    # ─────────────────────────────────────────────────────────────────

    async def generate_stream(
        self,
        *,
        prompt: str,
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        tenant_id: Optional[str] = None,
        purpose: str = "generate_stream",
    ) -> AsyncIterator[dict[str, Any]]:
        resolved = self._resolve_model("generic", model)
        request_payload = {
            "prompt_chars": len(prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        await self._adapter.dispatch_pre_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=_preview(prompt),
                purpose=purpose,
                request=request_payload,
            )
        )

        start = time.monotonic()
        prompt_tokens = 0
        completion_tokens = 0
        accumulated: list[str] = []
        try:
            async for chunk in self._client.generate_stream(
                model=resolved,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                prompt_tokens = int(chunk.get("prompt_eval_count") or prompt_tokens)
                completion_tokens = int(chunk.get("eval_count") or completion_tokens)
                delta = chunk.get("response", "")
                if delta:
                    accumulated.append(delta)
                yield {
                    "model": resolved,
                    "delta": delta,
                    "done": bool(chunk.get("done", False)),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
        except Exception as exc:
            await self._dispatch_error_post(
                resolved, _preview(prompt), purpose, request_payload, exc, tenant_id
            )
            raise

        elapsed_ms = (time.monotonic() - start) * 1000
        await self._adapter.dispatch_post_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=_preview(prompt),
                purpose=purpose,
                request=request_payload,
                response=_preview("".join(accumulated)),
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                duration_ms=elapsed_ms,
            )
        )
        self._log_call(
            "generate_stream", resolved, prompt_tokens, completion_tokens, elapsed_ms
        )

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        tenant_id: Optional[str] = None,
        purpose: str = "chat_stream",
    ) -> AsyncIterator[dict[str, Any]]:
        resolved = self._resolve_model("generic", model)
        request_payload = {
            "message_count": len(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        preview = _chat_preview(messages)
        await self._adapter.dispatch_pre_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=preview,
                purpose=purpose,
                request=request_payload,
            )
        )

        start = time.monotonic()
        prompt_tokens = 0
        completion_tokens = 0
        accumulated: list[str] = []
        try:
            async for chunk in self._client.chat_stream(
                model=resolved,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                prompt_tokens = int(chunk.get("prompt_eval_count") or prompt_tokens)
                completion_tokens = int(chunk.get("eval_count") or completion_tokens)
                msg = chunk.get("message") or {}
                delta = msg.get("content", "")
                if delta:
                    accumulated.append(delta)
                yield {
                    "model": resolved,
                    "delta": delta,
                    "role": msg.get("role", "assistant"),
                    "done": bool(chunk.get("done", False)),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }
        except Exception as exc:
            await self._dispatch_error_post(
                resolved, preview, purpose, request_payload, exc, tenant_id
            )
            raise

        elapsed_ms = (time.monotonic() - start) * 1000
        await self._adapter.dispatch_post_llm_call(
            LlmCallPayload(
                tenant_id=tenant_id,
                provider=PROVIDER_LABEL,
                model=resolved,
                prompt_preview=preview,
                purpose=purpose,
                request=request_payload,
                response=_preview("".join(accumulated)),
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                duration_ms=elapsed_ms,
            )
        )
        self._log_call(
            "chat_stream", resolved, prompt_tokens, completion_tokens, elapsed_ms
        )

    # ─────────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────────

    def _resolve_model(self, task_type: str, override: Optional[str]) -> str:
        if override:
            return override
        return self._router.route(task_type, override=None).primary

    def _resolve_embedding_model(self, override: Optional[str]) -> str:
        if override:
            return override
        decision = self._router.route("embedding", override=None)
        return decision.primary or self._config.embedding_model

    async def _dispatch_error_post(
        self,
        model: str,
        preview: str,
        purpose: str,
        request_payload: dict[str, Any],
        exc: BaseException,
        tenant_id: Optional[str],
    ) -> None:
        try:
            await self._adapter.dispatch_post_llm_call(
                LlmCallPayload(
                    tenant_id=tenant_id,
                    provider=PROVIDER_LABEL,
                    model=model,
                    prompt_preview=preview,
                    purpose=purpose,
                    request=request_payload,
                    error=str(exc),
                )
            )
        except Exception:  # pragma: no cover - defensive
            pass

    def _log_call(
        self,
        op: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        elapsed_ms: float,
        *,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        fields: dict[str, Any] = {
            "op": op,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "elapsed_ms": int(elapsed_ms),
        }
        if extra:
            fields.update(extra)
        _logger.info("aep.llm.call", **fields)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _decision_to_envelope(decision: RouteDecision) -> dict[str, Any]:
    return {
        "task_type": decision.task_type,
        "model": decision.primary,
        "fallback": decision.fallback,
        "source": decision.source,
    }


_service: Optional[LlmGatewayService] = None


def get_llm_gateway_service() -> LlmGatewayService:
    global _service
    if _service is None:
        _service = LlmGatewayService()
    return _service


def reset_llm_gateway_service() -> None:
    global _service
    _service = None


def validate_route_request(task_type: str) -> None:
    if not task_type or not isinstance(task_type, str):
        raise InvalidRequest("`task_type` must be a non-empty string")


__all__ = [
    "LlmGatewayService",
    "get_llm_gateway_service",
    "reset_llm_gateway_service",
    "validate_route_request",
]
