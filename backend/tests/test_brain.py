"""Tests for DevBuddy Brain planner."""

from app.agent.brain import DevBuddyBrain, _default_plan


def test_default_plan_with_repo():
    plan = _default_plan("Add JWT auth", has_repo=True)
    assert len(plan.steps) >= 4
    assert plan.steps[0].id == "understand"
    assert any(s.id == "deliver" for s in plan.steps)


def test_default_plan_without_repo():
    plan = _default_plan("Explain recursion", has_repo=False)
    assert len(plan.steps) >= 2
    assert plan.steps[-1].id == "respond"


def test_parse_plan_fallback():
    brain = DevBuddyBrain()
    plan = brain.__class__.__mro__[0]  # noqa - just use module function
    from app.agent.brain import _parse_plan_json
    result = _parse_plan_json("not json", "test task", True)
    assert result.summary
    assert len(result.steps) > 0
