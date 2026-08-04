"""Tests for session event hub."""

import json
import uuid

from app.agent.session_hub import SessionEventHub


def test_format_event_structure():
    sid = uuid.uuid4()
    event = SessionEventHub.format_event(sid, 1, "thinking", {"content": "hello"})
    assert event["type"] == "thinking"
    assert event["session_id"] == str(sid)
    assert event["seq"] == 1
    assert event["payload"]["content"] == "hello"
    assert isinstance(event["timestamp"], int)


def test_sse_line_json():
    hub = SessionEventHub()
    line = hub.sse_line({"type": "test", "payload": {}})
    assert line.startswith("data: ")
    assert line.endswith("\n\n")
    payload = json.loads(line[6:].strip())
    assert payload["type"] == "test"
