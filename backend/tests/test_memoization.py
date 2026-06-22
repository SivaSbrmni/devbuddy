"""Tests for Priority 0 — Response Memoization (Cache-First Routing).

Spec DoD:
  - cache hit, cache miss
  - cross-tenant isolation
  - TTL expiry (unit-level)
  - automatic invalidation on file-content change
  - no-cache-on-failed-validation
  - coder/planner excluded unless explicit override
"""

from __future__ import annotations

import pytest

from app.llm.memoization import (
    _compute_signature_hash,
    _normalize_error_type,
    _hash_stack_trace_top_frames,
    _sha256_text,
    _ttl_for,
    DebuggerCanonicalizer,
    TestCanonicalizer,
    DevOpsCanonicalizer,
    ResponseMemoizer,
)
from app.core.feature_flags import FeatureFlagService


class TestCanonicalizers:
    """Exact-signature canonicalization must be deterministic and content-bound."""

    def test_debugger_canonicalizer_includes_file_content_hash(self):
        ctx = {
            "error_message": "SyntaxError at line 42",
            "stack_trace": "File /app/src/main.py:42\n  foo()",
            "target_file_content": "def foo(): pass",
            "language": "python",
            "lockfile_hash": "lock123",
        }
        sig = DebuggerCanonicalizer("debugger").canonicalize(ctx)
        assert sig["language"] == "python"
        assert sig["file_content_hash"] == _sha256_text("def foo(): pass")
        assert sig["dependency_lock_hash"] == "lock123"
        assert sig["error_type"] == "SyntaxError at"

    def test_file_content_change_changes_signature(self):
        ctx1 = {"error_message": "x", "target_file_content": "a", "language": "py"}
        ctx2 = {"error_message": "x", "target_file_content": "b", "language": "py"}
        c1 = DebuggerCanonicalizer("debugger").canonicalize(ctx1)
        c2 = DebuggerCanonicalizer("debugger").canonicalize(ctx2)
        assert _compute_signature_hash(c1) != _compute_signature_hash(c2)

    def test_stack_trace_top_frames_normalized(self):
        trace = "File /home/user/proj/src/main.py:42\nFile /home/user/proj/src/lib.py:10"
        fp = _hash_stack_trace_top_frames(trace, top_n=2)
        assert fp
        # Same logical trace with different absolute path should still match
        trace2 = "File /opt/app/src/main.py:42\nFile /opt/app/src/lib.py:10"
        fp2 = _hash_stack_trace_top_frames(trace2, top_n=2)
        assert fp == fp2

    def test_error_normalization_strips_line_numbers(self):
        assert _normalize_error_type("SyntaxError at line 42") == "SyntaxError at"

    def test_signature_hash_deterministic(self):
        ctx = {"error_message": "x", "target_file_content": "a", "language": "py"}
        c = DebuggerCanonicalizer("debugger").canonicalize(ctx)
        assert _compute_signature_hash(c) == _compute_signature_hash(c)

    def test_tenant_id_not_part_of_signature(self):
        """Cross-tenant isolation is enforced by the lookup key, not the hash."""
        ctx = {"error_message": "x", "target_file_content": "a", "language": "py"}
        c = DebuggerCanonicalizer("debugger").canonicalize(ctx)
        # Adding a synthetic tenant field would be wrong; the schema has no such field
        assert "tenant_id" not in c


class TestScopeAndTTL:
    """Default scope excludes coder/planner; TTLs are type-specific."""

    def test_default_scope_excludes_coder_and_planner(self, monkeypatch):
        flags = FeatureFlagService()
        flags._env_cache = {"response_memoization_enabled": True}
        monkeypatch.delenv("AEP_FLAG_RESPONSE_MEMOIZATION_SCOPE", raising=False)
        memoizer = ResponseMemoizer()
        memoizer.feature_flags = flags  # type: ignore
        assert memoizer._is_memoization_scoped("debugger", {})
        assert memoizer._is_memoization_scoped("test", {})
        assert memoizer._is_memoization_scoped("devops", {})
        assert not memoizer._is_memoization_scoped("coder", {})
        assert not memoizer._is_memoization_scoped("planner", {})

    def test_explicit_override_can_include_coder(self, monkeypatch):
        flags = FeatureFlagService()
        flags._env_cache = {"response_memoization_enabled": True}
        monkeypatch.setenv("AEP_FLAG_RESPONSE_MEMOIZATION_SCOPE", '["coder"]')
        memoizer = ResponseMemoizer()
        memoizer.feature_flags = flags  # type: ignore
        assert memoizer._is_memoization_scoped("coder", {})
        assert not memoizer._is_memoization_scoped("planner", {})

    def test_skip_cache_bypasses_scope(self, monkeypatch):
        flags = FeatureFlagService()
        flags._env_cache = {"response_memoization_enabled": True}
        monkeypatch.delenv("AEP_FLAG_RESPONSE_MEMOIZATION_SCOPE", raising=False)
        memoizer = ResponseMemoizer()
        memoizer.feature_flags = flags  # type: ignore
        assert not memoizer._is_memoization_scoped("debugger", {"skip_cache": True})

    def test_ttl_devops_indefinite(self):
        assert _ttl_for("devops") is None

    def test_ttl_debugger_longer_than_test(self):
        d = _ttl_for("debugger")
        t = _ttl_for("test")
        assert d and t
        assert d > t


class TestResponseValidation:
    """Only validated, non-error responses are stored."""

    @pytest.mark.asyncio
    async def test_store_ignores_error_response(self):
        memoizer = ResponseMemoizer()
        # no DB is fine for this unit test because it returns early on error
        assert await memoizer.store(
            "debugger",
            {"target_file_content": "a"},
            {"text": "", "finish_reason": "error", "usage": {}, "provider": "p", "model": "m"},
        ) is None

    @pytest.mark.asyncio
    async def test_store_ignores_empty_response(self):
        memoizer = ResponseMemoizer()
        assert await memoizer.store(
            "debugger",
            {"target_file_content": "a"},
            {"text": "", "finish_reason": "stop", "usage": {}, "provider": "p", "model": "m"},
        ) is None

    @pytest.mark.asyncio
    async def test_store_ignores_unvalidated_response(self):
        memoizer = ResponseMemoizer()
        assert await memoizer.store(
            "debugger",
            {"target_file_content": "a"},
            {"text": "fix", "finish_reason": "stop", "usage": {}, "provider": "p", "model": "m"},
            validated=False,
        ) is None
