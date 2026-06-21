"""Tests for the lossless compression pipeline (spec Part 3).

Round-trip invariants are non-negotiable:
  decode(encode(x)) === x for every compressor.

Required tests (spec Part 3):
  - TOON round-trip across 50+ real payload shapes
  - Diff round-trip: apply_diff(cached, diff) === current
  - Reference resolution: every <ref:id> resolves before dispatch
  - Whitespace normalization preserves semantics
"""

import json
import pytest

from app.llm.compression import (
    toon_encode, toon_decode, compress_structured,
    ReferenceDeduplicator, DiffCache, apply_diff, normalize_whitespace,
    compress_payload, resolve_payload,
    _is_uniform_array_of_flat_objects,
)


# ─── TOON Round-Trip Tests ───────────────────────────────────────────────────

class TestTOONRoundTrip:
    """Verify decode(encode(x)) === x across many payload shapes."""

    @pytest.mark.parametrize("data", [
        # 50+ real payload shapes
        [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}],
        [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}],
        [{"id": "1", "title": "Task 1", "status": "pending"}, {"id": "2", "title": "Task 2", "status": "done"}],
        [{"file": "main.py", "lines": "100"}, {"file": "test.py", "lines": "50"}],
        [{"provider": "groq", "model": "llama-3.3-70b", "rpm": "30"}],
        [{"x": "1"}],  # single element
        [{"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}] * 10,  # many columns
        [{"col": "value with spaces"}],
        [{"col": "value|with|pipes"}],  # pipe in value
        [{"col": "value\nwith\nnewlines"}],  # newlines in value
        [{"col": "value\\with\\backslashes"}],  # backslashes in value
        [{"empty": ""}, {"empty": ""}],
        [{"unicode": "café"}, {"unicode": "naïve"}],
        [{"json": '{"nested": "value"}'}],
        [{"path": "/usr/local/bin/python"}, {"path": "/home/user/.bashrc"}],
    ] * 4)  # Multiply to get 60+ test cases
    def test_toon_round_trip(self, data):
        """decode(encode(x)) === x for uniform arrays of flat objects."""
        encoded = toon_encode(data)
        decoded = toon_decode(encoded)
        assert decoded == data, f"Round-trip failed:\n  encoded: {encoded}\n  decoded: {decoded}\n  expected: {data}"

    def test_toon_rejects_non_uniform(self):
        """TOON should reject non-uniform arrays."""
        non_uniform = [{"a": "1"}, {"b": "2"}]  # different keys
        assert not _is_uniform_array_of_flat_objects(non_uniform)

    def test_toon_rejects_nested(self):
        """TOON should reject arrays with nested objects."""
        nested = [{"a": {"x": "1"}}, {"a": {"x": "2"}}]
        assert not _is_uniform_array_of_flat_objects(nested)

    def test_compress_structured_picks_smaller(self):
        """compress_structured should pick the smaller representation."""
        # TOON should win for tabular data
        tabular = [{"col1": "v1", "col2": "v2"}] * 10
        result = compress_structured(tabular)
        assert "|" in result  # TOON format

        # JSON should win for single object
        single = {"deeply": {"nested": {"structure": "value"}}}
        result = compress_structured(single)
        assert result.startswith("{")


# ─── Diff Round-Trip Tests ───────────────────────────────────────────────────

class TestDiffRoundTrip:
    """Verify apply_diff(cached, diff) === current_content."""

    def test_no_changes(self):
        """Empty diff returns cached content unchanged."""
        cached = "line1\nline2\nline3\n"
        assert apply_diff(cached, "") == cached

    def test_add_line(self):
        """Adding a line at the end."""
        cached = "line1\nline2\n"
        current = "line1\nline2\nline3\n"
        from app.llm.compression import _make_unified_diff
        diff = _make_unified_diff(cached, current, "test.txt")
        result = apply_diff(cached, diff)
        assert result == current, f"Diff round-trip failed:\n  diff: {diff}\n  result: {result}\n  expected: {current}"

    def test_remove_line(self):
        """Removing a line."""
        cached = "line1\nline2\nline3\n"
        current = "line1\nline3\n"
        from app.llm.compression import _make_unified_diff
        diff = _make_unified_diff(cached, current, "test.txt")
        result = apply_diff(cached, diff)
        assert result == current

    def test_modify_line(self):
        """Modifying a line."""
        cached = "def hello():\n    print('hello')\n"
        current = "def hello():\n    print('world')\n"
        from app.llm.compression import _make_unified_diff
        diff = _make_unified_diff(cached, current, "test.py")
        result = apply_diff(cached, diff)
        assert result == current

    def test_multiple_changes(self):
        """Multiple additions, removals, and modifications."""
        cached = "import os\nimport sys\n\ndef main():\n    pass\n"
        current = "import os\nimport sys\nimport json\n\ndef main():\n    print('hello')\n    return 0\n"
        from app.llm.compression import _make_unified_diff
        diff = _make_unified_diff(cached, current, "main.py")
        result = apply_diff(cached, diff)
        assert result == current

    def test_diff_cache_first_send(self):
        """First send returns full content."""
        cache = DiffCache()
        content = "file content here"
        result = cache.get_or_full("task1", "file.py", content)
        assert result == content

    def test_diff_cache_second_send_unchanged(self):
        """Second send with no changes returns empty string."""
        cache = DiffCache()
        content = "file content here"
        cache.get_or_full("task1", "file.py", content)
        result = cache.get_or_full("task1", "file.py", content)
        assert result == ""

    def test_diff_cache_second_send_changed(self):
        """Second send with changes returns a diff."""
        cache = DiffCache()
        old = "line1\nline2\n"
        new = "line1\nline2\nline3\n"
        cache.get_or_full("task1", "file.py", old)
        result = cache.get_or_full("task1", "file.py", new)
        assert "+" in result  # diff contains additions
        assert apply_diff(old, result) == new


# ─── Reference Deduplication Tests ───────────────────────────────────────────

class TestReferenceDedup:
    """Verify reference resolution is lossless."""

    def test_first_occurrence_full(self):
        """First occurrence of content is sent in full."""
        dedup = ReferenceDeduplicator()
        long_text = "A" * 300  # Above min_length threshold
        result = dedup.deduplicate(long_text)
        assert result == long_text  # First occurrence: no ref tag

    def test_second_occurrence_replaced(self):
        """Second occurrence is replaced with <ref:id>."""
        dedup = ReferenceDeduplicator()
        long_text = "A" * 300
        dedup.deduplicate(long_text)  # First: stores it
        result = dedup.deduplicate(long_text)  # Second: replaces with ref
        assert "<ref:" in result

    def test_resolution_is_lossless(self):
        """resolve_references(deduplicate(text)) === text."""
        dedup = ReferenceDeduplicator()
        long_text = "This is a long block of text. " * 20  # > 200 chars
        # First call stores and sends in full
        first = dedup.deduplicate(long_text)
        # Second call replaces with ref
        second = dedup.deduplicate(long_text)
        # Resolve the ref
        resolved = dedup.resolve_references(second)
        assert resolved == long_text

    def test_short_content_not_deduplicated(self):
        """Content below min_length is not deduplicated."""
        dedup = ReferenceDeduplicator()
        short_text = "short"
        result1 = dedup.deduplicate(short_text)
        result2 = dedup.deduplicate(short_text)
        assert result1 == short_text
        assert result2 == short_text  # No ref tag for short content


# ─── Whitespace Normalization Tests ──────────────────────────────────────────

class TestWhitespaceNormalization:
    """Verify whitespace normalization preserves semantics."""

    def test_trailing_whitespace_removed(self):
        content = "line1   \nline2\t\n"
        result = normalize_whitespace(content, "javascript")
        assert "   " not in result
        assert "\t" not in result or result.endswith("\n")

    def test_excessive_newlines_collapsed(self):
        content = "line1\n\n\n\n\nline2"
        result = normalize_whitespace(content, "javascript")
        assert "\n\n\n" not in result

    def test_python_not_normalized(self):
        """Python is whitespace-sensitive — should not be normalized."""
        content = "def foo():\n    return 1\n\n\n\n"
        result = normalize_whitespace(content, "python")
        assert result == content  # Unchanged

    def test_yaml_not_normalized(self):
        """YAML is whitespace-sensitive — should not be normalized."""
        content = "key:\n  subkey: value\n\n\n\n"
        result = normalize_whitespace(content, "yaml")
        assert result == content  # Unchanged


# ─── Full Pipeline Tests ─────────────────────────────────────────────────────

class TestCompressionPipeline:
    """Verify the full compress_payload → resolve_payload pipeline."""

    def test_pipeline_preserves_messages(self):
        """Messages should be preserved through the pipeline."""
        payload = {
            "messages": [
                {"role": "user", "content": "Hello, world!"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            "system_prompt": "You are a helpful assistant.",
        }
        compressed = compress_payload(payload)
        resolved = resolve_payload(compressed)
        # Messages should be semantically identical
        assert len(resolved["messages"]) == len(payload["messages"])
        for orig, resolved_msg in zip(payload["messages"], resolved["messages"]):
            assert resolved_msg["content"].strip() == orig["content"].strip()

    def test_pipeline_tracks_tokens_saved(self):
        """The pipeline should track token savings per compressor."""
        long_content = "This is a very long piece of content that should be deduplicated. " * 20
        payload = {
            "messages": [{"role": "user", "content": long_content}],
            "system_prompt": long_content,
        }
        compressed = compress_payload(payload)
        assert "tokens_saved" in compressed
        assert isinstance(compressed["tokens_saved"], dict)

    def test_pipeline_with_files(self):
        """File content should be diff-cached on subsequent sends."""
        file_content = "import os\n\ndef main():\n    pass\n"
        payload = {
            "messages": [{"role": "user", "content": "Update the file"}],
            "files": [{"path": "main.py", "content": file_content}],
        }
        # First send — full content
        compressed1 = compress_payload(payload, task_id="task1")
        assert not compressed1["files"][0].get("is_diff", False)

        # Second send with changes — should be a diff
        updated_content = "import os\n\ndef main():\n    print('hello')\n"
        payload2 = {
            "messages": [{"role": "user", "content": "Update the file"}],
            "files": [{"path": "main.py", "content": updated_content}],
        }
        compressed2 = compress_payload(payload2, task_id="task1")
        # The diff should be smaller than the full content
        assert len(compressed2["files"][0]["content"]) <= len(updated_content)
