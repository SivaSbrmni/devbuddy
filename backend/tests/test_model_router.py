"""Model router unit tests (no API keys needed)."""

from app.core.model_router import ModelTier, TaskCategory, TASK_TIER_MAP, ModelRouter


def test_tier_mapping_completeness():
    """Every TaskCategory must have a tier mapping."""
    for category in TaskCategory:
        assert category in TASK_TIER_MAP, f"Missing tier mapping for {category}"


def test_draft_categories_use_llama():
    draft_categories = [
        TaskCategory.REQUIREMENT_ANALYSIS,
        TaskCategory.PLANNING_DRAFT,
        TaskCategory.TASK_DECOMPOSITION,
        TaskCategory.SUMMARIZATION,
        TaskCategory.LOG_ANALYSIS,
    ]
    for cat in draft_categories:
        assert TASK_TIER_MAP[cat] == ModelTier.DRAFT


def test_engineer_categories_use_claude():
    engineer_categories = [
        TaskCategory.CODING,
        TaskCategory.CODE_REVIEW,
        TaskCategory.SECURITY_REVIEW,
        TaskCategory.ROOT_CAUSE_ANALYSIS,
        TaskCategory.DEBUGGING,
    ]
    for cat in engineer_categories:
        assert TASK_TIER_MAP[cat] == ModelTier.ENGINEER


def test_router_tier_selection():
    router = ModelRouter()
    assert router._select_tier(TaskCategory.CODING) == ModelTier.ENGINEER
    assert router._select_tier(TaskCategory.SUMMARIZATION) == ModelTier.DRAFT
