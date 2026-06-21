"""LLM Gateway package — multi-provider free-tier router.

Implements spec Part 2: LLM Gateway with provider cascade, quota ledger,
circuit breaker, and response normalization.

Architecture:
  app/llm/
    __init__.py          - Package exports
    gateway.py           - LLMGateway singleton (entry point for /LLM routes)
    providers/
      __init__.py
      base.py            - BaseProvider interface
      groq.py            - Groq provider (Llama 3.3 70B, fast)
      gemini.py          - Google AI Studio (Gemini 2.5 Flash, huge context)
      cerebras.py        - Cerebras (Llama 3.3 70B, high throughput)
      openrouter.py      - OpenRouter (28+ free models, universal fallback)
      github_models.py   - GitHub Models (free dev-tier)
      mistral.py         - Mistral (free prototyping tier)
      cloudflare.py      - Cloudflare Workers AI (small models)
    quota.py             - QuotaLedger + CircuitBreaker (in-memory, Redis-ready)
    normalize.py         - Response normalizer
"""
