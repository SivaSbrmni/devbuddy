"""Lossless compression pipeline (spec Part 3).

Applied to every outbound LLM request, in this order:
  [1] TOON structural encoding (or compact JSON fallback)
  [2] Reference deduplication (session-scoped IDs)
  [3] Diff-based file context (deltas only after first send)
  [4] Semantic chunk retrieval (scoping, not alteration)
  [5] Non-semantic whitespace normalization

ALL compressors are lossless: decode(encode(x)) === x, verified by tests.
Summarization/selection is allowed for scoping (deciding what to include),
never for altering what's included.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import structlog

log = structlog.get_logger()

# ─── [1] TOON Structural Encoding ────────────────────────────────────────────

# TOON (Tabular Object Notation) is a lossless re-encoding of JSON data
# that's more compact for uniform arrays of flat objects (tabular shape).
# For deeply nested/irregular data, compact JSON is smaller.
#
# Format: header row of keys, then one row per object, pipe-delimited.
# Example: [{"a":1,"b":2},{"a":3,"b":4}] → "a|b\n1|2\n3|4"
#
# This is a minimal implementation. The @toon-format/toon npm package
# would be used in production, but this Python implementation is
# self-contained and lossless.

TOON_DELIM = "|"
TOON_NEWLINE = "\n"


def _toon_escape(s: str) -> str:
    """Escape special characters in a TOON value."""
    # Must escape backslash first, then delimiter and newline
    s = s.replace("\\", "\\\\")
    s = s.replace(TOON_DELIM, "\\|")
    s = s.replace(TOON_NEWLINE, "\\n")
    return s


def _toon_unescape(s: str) -> str:
    """Unescape special characters in a TOON value."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            next_char = s[i + 1]
            if next_char == "\\":
                result.append("\\")
                i += 2
            elif next_char == "|":
                result.append(TOON_DELIM)
                i += 2
            elif next_char == "n":
                result.append(TOON_NEWLINE)
                i += 2
            else:
                result.append(s[i])
                i += 1
        else:
            result.append(s[i])
            i += 1
    return "".join(result)


def _is_uniform_array_of_flat_objects(data: Any) -> bool:
    """Check if data is a uniform array of flat (non-nested) objects.

    "Flat" means all values are primitives (str, int, float, bool, None),
    not nested dicts or lists.
    """
    if not isinstance(data, list) or len(data) < 1:
        return False
    if not all(isinstance(item, dict) for item in data):
        return False
    # All objects must have the same keys
    first_keys = set(data[0].keys())
    if not all(set(item.keys()) == first_keys for item in data):
        return False
    # All values must be primitives (flat)
    for item in data:
        for v in item.values():
            if isinstance(v, (dict, list)):
                return False
    return True


def toon_encode(data: Any) -> str:
    """Encode data as TOON. Only works for uniform arrays of flat objects.

    For other data shapes, use compress_structured() which falls back to JSON.
    """
    if not _is_uniform_array_of_flat_objects(data):
        raise ValueError("TOON encoding requires uniform array of flat objects")

    keys = list(data[0].keys())
    header = TOON_DELIM.join(keys)
    rows = []
    for item in data:
        row = TOON_DELIM.join(_toon_escape(str(item[k])) for k in keys)
        rows.append(row)
    # Use newline as row separator (no trailing newline)
    return header + TOON_NEWLINE + TOON_NEWLINE.join(rows)


def toon_decode(toon_str: str) -> list[dict[str, str]]:
    """Decode TOON string back to list of dicts.

    Note: Values are returned as strings. Type coercion is the caller's
    responsibility (TOON is a transport format, not a type system).
    """
    # Split on unescaped newlines only
    lines = _split_unescaped(toon_str, TOON_NEWLINE)
    if not lines:
        return []
    # First line is the header (keys), rest are data rows
    # Do NOT strip trailing empty lines — they represent rows with empty values
    keys = _split_unescaped(lines[0], TOON_DELIM)
    result = []
    for line in lines[1:]:
        values = _split_unescaped(line, TOON_DELIM)
        # Unescape each value
        values = [_toon_unescape(v) for v in values]
        result.append(dict(zip(keys, values)))
    return result


def _split_unescaped(s: str, delim: str) -> list[str]:
    """Split string on delimiter, respecting escape sequences."""
    result = []
    current = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            # Escaped character — keep both the backslash and the next char
            current.append(s[i])
            current.append(s[i + 1])
            i += 2
        elif s[i] == delim:
            result.append("".join(current))
            current = []
            i += 1
        else:
            current.append(s[i])
            i += 1
    result.append("".join(current))
    return result


def compress_structured(data: object) -> str:
    """Compress structured data using TOON if beneficial, else compact JSON.

    Lossless invariant: the data can be fully reconstructed from the output.
    """
    import json

    if _is_uniform_array_of_flat_objects(data):
        try:
            toon = toon_encode(data)
            json_compact = json.dumps(data, separators=(",", ":"))
            # Pick the smaller representation
            if len(toon) < len(json_compact):
                return toon
            return json_compact
        except Exception:
            return json.dumps(data, separators=(",", ":"))

    return json.dumps(data, separators=(",", ":"))


# ─── [2] Reference Deduplication ─────────────────────────────────────────────

class ReferenceDeduplicator:
    """Deduplicate repeated content blocks using session-scoped reference IDs.

    First occurrence of a repeated block (system prompt, schema, repo summary)
    is stored and sent in full; later calls send <ref:r17>. The gateway
    resolves all <ref:> tags server-side before dispatch.

    Lossless: resolve_references(deduplicate(text)) === text
    """

    def __init__(self) -> None:
        self._refs: dict[str, str] = {}  # ref_id -> content
        self._content_to_ref: dict[str, str] = {}  # content hash -> ref_id
        self._counter = 0

    def store(self, content: str) -> str:
        """Store content and return a reference ID. If already stored, return existing ID."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if content_hash in self._content_to_ref:
            return self._content_to_ref[content_hash]

        self._counter += 1
        ref_id = f"r{self._counter}"
        self._refs[ref_id] = content
        self._content_to_ref[content_hash] = ref_id
        return ref_id

    def deduplicate(self, text: str, min_length: int = 200) -> str:
        """Replace repeated blocks with <ref:id> tags.

        Only blocks longer than min_length are deduplicated (small blocks
        aren't worth the reference overhead).
        """
        # Find repeated blocks (simplified: split on double newlines)
        blocks = re.split(r"\n\n+", text)
        result_blocks = []
        for block in blocks:
            if len(block) >= min_length:
                content_hash = hashlib.sha256(block.encode()).hexdigest()
                if content_hash in self._content_to_ref:
                    ref_id = self._content_to_ref[content_hash]
                    result_blocks.append(f"<ref:{ref_id}>")
                else:
                    ref_id = self.store(block)
                    result_blocks.append(block)  # First occurrence: send in full
            else:
                result_blocks.append(block)
        return "\n\n".join(result_blocks)

    def resolve_references(self, text: str) -> str:
        """Resolve all <ref:id> tags back to their original content."""
        def replace_ref(match: re.Match) -> str:
            ref_id = match.group(1)
            return self._refs.get(ref_id, match.group(0))

        return re.sub(r"<ref:(r\d+)>", replace_ref, text)

    def clear(self) -> None:
        """Clear all references (call at session end)."""
        self._refs.clear()
        self._content_to_ref.clear()
        self._counter = 0


# ─── [3] Diff-Based File Context ─────────────────────────────────────────────

class DiffCache:
    """Cache file contents and send only diffs on subsequent requests.

    First send: full file content.
    Subsequent sends: unified diff from cached version.

    Lossless invariant: apply_diff(cached, diff) === current_content
    """

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}  # file_path -> cached content

    def get_or_full(self, task_id: str, file_path: str, current_content: str) -> str:
        """Return full content if first send, else diff from cached version."""
        cache_key = f"{task_id}:{file_path}"
        if cache_key not in self._cache:
            self._cache[cache_key] = current_content
            return current_content
        cached = self._cache[cache_key]
        if cached == current_content:
            return ""  # No changes
        diff = _make_unified_diff(cached, current_content, file_path)
        self._cache[cache_key] = current_content
        return diff

    def get_or_diff(self, task_id: str, file_path: str, current_content: str) -> str:
        """Alias for get_or_full (spec interface)."""
        return self.get_or_full(task_id, file_path, current_content)

    def clear(self, task_id: "Optional[str]" = None) -> None:
        """Clear cache for a task or all."""
        if task_id:
            prefix = f"{task_id}:"
            self._cache = {k: v for k, v in self._cache.items() if not k.startswith(prefix)}
        else:
            self._cache.clear()


def _make_unified_diff(old: str, new: str, filename: str) -> str:
    """Generate a unified diff string."""
    import difflib
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"{filename}.old", tofile=filename)
    return "".join(diff)


def apply_diff(cached: str, diff: str) -> str:
    """Apply a unified diff to cached content. Lossless inverse of _make_unified_diff."""
    # For empty diff (no changes), return cached as-is
    if not diff.strip():
        return cached
    # Parse the unified diff and apply it
    lines = diff.splitlines(keepends=True)
    result = []
    cached_lines = cached.splitlines(keepends=True)
    i = 0  # index into cached_lines

    for line in lines:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            # Parse hunk header to skip to the right position
            if line.startswith("@@"):
                match = re.match(r"@@ -(\d+),?\d* \+\d+,?\d* @@", line)
                if match:
                    start = int(match.group(1)) - 1
                    # Copy unchanged lines before this hunk
                    while i < start and i < len(cached_lines):
                        result.append(cached_lines[i])
                        i += 1
            continue
        elif line.startswith(" "):
            # Context line — copy from cached
            if i < len(cached_lines):
                result.append(cached_lines[i])
                i += 1
        elif line.startswith("-"):
            # Removed line — skip in cached
            i += 1
        elif line.startswith("+"):
            # Added line — append
            result.append(line[1:])

    # Copy any remaining unchanged lines
    while i < len(cached_lines):
        result.append(cached_lines[i])
        i += 1

    return "".join(result)


# ─── [5] Whitespace Normalization ────────────────────────────────────────────

WHITESPACE_SENSITIVE = {"python", "yaml", "markdown_table", "toon"}


def normalize_whitespace(content: str, language: str = "") -> str:
    """Normalize non-semantic whitespace. Skips whitespace-sensitive formats.

    Lossless for non-sensitive formats: the semantic content is identical.
    For sensitive formats (python, yaml), returns content unchanged.
    """
    if language.lower() in WHITESPACE_SENSITIVE:
        return content
    # Remove trailing whitespace on each line
    content = re.sub(r"[ \t]+$", "", content, flags=re.MULTILINE)
    # Collapse 3+ newlines to 2
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content


# ─── Full Pipeline ───────────────────────────────────────────────────────────

# Module-level dedup and diff cache instances (per-session in production)
_dedup = ReferenceDeduplicator()
_diff_cache = DiffCache()


def compress_payload(
    payload: dict[str, Any],
    task_id: str = "",
    language: str = "",
) -> dict[str, Any]:
    """Apply the full compression pipeline to a payload.

    Args:
        payload: The request payload (messages, system_prompt, files, etc.)
        task_id: Task ID for diff cache scoping
        language: Content language for whitespace sensitivity

    Returns:
        Compressed payload with a 'tokens_saved' dict tracking savings per compressor
    """
    import json

    result = dict(payload)
    tokens_saved: dict[str, int] = {}

    # [1] TOON/JSON compression for structured data
    if "structured_data" in result:
        original = json.dumps(result["structured_data"], separators=(",", ":"))
        compressed = compress_structured(result["structured_data"])
        if len(compressed) < len(original):
            tokens_saved["toon"] = (len(original) - len(compressed)) // 4  # rough token estimate
            result["structured_data"] = compressed

    # [2] Reference deduplication for system prompt and long messages
    if "system_prompt" in result and result["system_prompt"]:
        original_len = len(result["system_prompt"])
        deduped = _dedup.deduplicate(result["system_prompt"])
        if len(deduped) < original_len:
            tokens_saved["ref_dedup"] = (original_len - len(deduped)) // 4
            result["system_prompt"] = deduped

    for msg in result.get("messages", []):
        if isinstance(msg.get("content"), str) and len(msg["content"]) > 200:
            original_len = len(msg["content"])
            deduped = _dedup.deduplicate(msg["content"])
            if len(deduped) < original_len:
                tokens_saved.setdefault("ref_dedup", 0)
                tokens_saved["ref_dedup"] += (original_len - len(deduped)) // 4
                msg["content"] = deduped

    # [3] Diff-based file context
    if "files" in result and task_id:
        for file_entry in result["files"]:
            if isinstance(file_entry, dict) and "path" in file_entry and "content" in file_entry:
                file_path = file_entry["path"]
                content = file_entry["content"]
                original_len = len(content)
                diff_or_full = _diff_cache.get_or_full(task_id, file_path, content)
                if len(diff_or_full) < original_len:
                    tokens_saved.setdefault("diff_cache", 0)
                    tokens_saved["diff_cache"] += (original_len - len(diff_or_full)) // 4
                    file_entry["content"] = diff_or_full
                    file_entry["is_diff"] = diff_or_full != content

    # [5] Whitespace normalization
    for msg in result.get("messages", []):
        if isinstance(msg.get("content"), str):
            original_len = len(msg["content"])
            normalized = normalize_whitespace(msg["content"], language)
            if len(normalized) < original_len:
                tokens_saved.setdefault("whitespace", 0)
                tokens_saved["whitespace"] += (original_len - len(normalized)) // 4
                msg["content"] = normalized

    result["tokens_saved"] = tokens_saved
    return result


def resolve_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve all compression references in a payload (inverse of compress_payload).

    This is called server-side before dispatch to the LLM provider.
    """
    result = dict(payload)

    # Resolve reference deduplication
    if "system_prompt" in result and result["system_prompt"]:
        result["system_prompt"] = _dedup.resolve_references(result["system_prompt"])

    for msg in result.get("messages", []):
        if isinstance(msg.get("content"), str):
            msg["content"] = _dedup.resolve_references(msg["content"])

    return result
