"""Create a single OpenRouter user_llm_provider via the DevBuddy API."""

import json
import os
import urllib.request
import urllib.error

TOKEN = os.environ.get("DEVBUDDY_TOKEN", "")
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

payload = {
    "name": "OpenRouter",
    "provider_type": "openai-compatible",
    "base_url": "https://openrouter.ai/api/v1",
    "api_key": API_KEY,
    "default_model": "qwen/qwen3-coder-480b",
    "available_models": [
        "qwen/qwen3-coder-480b",
        "deepseek/deepseek-r1",
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.5-flash-preview",
        "mistralai/mistral-small-latest"
    ],
    "supports_streaming": True,
    "supports_tools": True,
    "supports_vision": False,
    "context_size": 128000,
    "max_tokens": 8192,
    "priority": 100,
    "is_default": True
}

req = urllib.request.Request(
    "https://sivasbrmni-devbuddy.hf.space/api/v1/llm-providers",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.status)
        print(json.dumps(json.loads(resp.read().decode()), indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.reason}")
    print(e.read().decode())
