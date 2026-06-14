---
title: DevBuddy
emoji: 🚀
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# DevBuddy Lite — Autonomous Software Engineer Platform

A production-quality autonomous software engineering system that understands requirements, plans work, writes code, debugs software, repairs failures, deploys applications, and continuously improves software with minimal human intervention.

## Architecture

```
User → FastAPI API → Task Orchestrator → Requirement Analyzer → Planner → Architect
  → Engineering Review Gateway (Claude) → Coder → Engineering Workspace
  → Reviewer → Tester → Fix Agent → Git Repository → GitHub Actions
  → Execution Controller → Failure Analyzer → Patch Generator → Retry Engine
  → Deployment Manager → Production → Observability → Continuous Improvement
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python / FastAPI |
| Frontend | React |
| Database | PostgreSQL + pgvector |
| Containers | Docker |
| VCS | GitHub |
| Execution | GitHub Actions |
| Deploy | HuggingFace Spaces / Railway / Vercel / Docker VPS |
| LLM | Ollama Cloud + Anthropic Claude + Llama Cloud |

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Project Structure

```
backend/
  app/
    main.py              # FastAPI entrypoint
    core/                # Config, security, dependencies
    db/                  # Database engine, session, base
    models/              # SQLAlchemy ORM models
    schemas/             # Pydantic request/response schemas
    api/routes/          # API route handlers
    agents/              # All autonomous agents
    workspace/           # Engineering workspace (file/shell/runtime/log ops)
    browser/             # Browser automation agent
    memory/              # Project memory system
    knowledge/           # Knowledge store (pgvector)
    skills/              # Reusable engineering skills
    execution/           # GitHub Actions integration
    repair/              # Autonomous repair loop
    deployment/          # Deployment manager (Railway/Vercel/Docker)
    security/            # Workflow validator, secret management
    observability/       # Metrics, dashboards, reports
    improvement/         # Continuous improvement engine
  alembic/               # Database migrations
  tests/                 # Test suite
frontend/
  src/
    components/          # React UI components
    pages/               # Route pages
    hooks/               # Custom hooks
    api/                 # API client
    store/               # State management
    utils/               # Utilities
```
