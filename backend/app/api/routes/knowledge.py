"""Knowledge API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.knowledge_store import knowledge_store
from app.core.security import get_current_user
from app.models.knowledge import KnowledgeCreate, KnowledgeEntry, KnowledgeSearch
from app.models.user import User

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeExtractRequest(BaseModel):
    conversation_id: str
    messages: list[dict[str, str]] = Field(default_factory=list)


@router.post("/extract")
async def extract_knowledge(
    req: KnowledgeExtractRequest,
    user: User = Depends(get_current_user),
) -> list[KnowledgeEntry]:
    """Extract knowledge from a conversation using LLM."""
    from app.core.model_router import model_router, LLMRequest

    # Build extraction prompt
    prompt = f"""Extract key knowledge from this conversation. For each piece of knowledge, provide:
1. A clear title
2. The content/explanation
3. Relevant keywords for search
4. A category (e.g., 'code', 'concept', 'troubleshooting', 'best-practice')

Conversation:
{req.messages}

Return as JSON array with format: [{{"title": "...", "content": "...", "keywords": ["..."], "category": "..."}}]"""

    try:
        # Call LLM to extract knowledge
        llm_req = LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            task_category="planning_draft",
            model="qwen3-coder:480b",
            provider="ollama",
        )

        response = ""
        async for delta in model_router._call_provider_stream(llm_req, "ollama"):
            response += delta

        # Parse response (simplified - in production use better parsing)
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            knowledge_data = json.loads(json_match.group())
        else:
            # Fallback: create single entry
            knowledge_data = [{
                "title": "Conversation Summary",
                "content": response[:500],
                "keywords": ["summary", "conversation"],
                "category": "general"
            }]

        # Store knowledge entries
        entries = []
        for item in knowledge_data:
            entry = knowledge_store.create(KnowledgeCreate(
                conversation_id=req.conversation_id,
                title=item.get("title", "Untitled"),
                content=item.get("content", ""),
                keywords=item.get("keywords", []),
                category=item.get("category", "general")
            ))
            entries.append(entry)

        return entries

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract knowledge: {str(e)}")


@router.post("/search")
async def search_knowledge(
    search: KnowledgeSearch,
    user: User = Depends(get_current_user),
) -> list[KnowledgeEntry]:
    """Search knowledge by query."""
    try:
        results = knowledge_store.search(
            query=search.query,
            category=search.category,
            limit=search.limit
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/conversation/{conversation_id}")
async def get_conversation_knowledge(
    conversation_id: str,
    user: User = Depends(get_current_user),
) -> list[KnowledgeEntry]:
    """Get all knowledge for a conversation."""
    try:
        return knowledge_store.get_by_conversation(conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get knowledge: {str(e)}")


@router.get("/{knowledge_id}")
async def get_knowledge(
    knowledge_id: str,
    user: User = Depends(get_current_user),
) -> Optional[KnowledgeEntry]:
    """Get a specific knowledge entry."""
    try:
        entry = knowledge_store.get_by_id(knowledge_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Knowledge not found")
        return entry
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get knowledge: {str(e)}")
