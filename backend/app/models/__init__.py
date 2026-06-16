"""SQLAlchemy models for DevBuddy."""

# Database base
from app.db.base import Base

# User & Identity
from app.models.user import Organization, User, UserSession

# Conversations & Messages (server-side persistence)
from app.models.conversation import Conversation, Message, ConversationTask, ConversationEvent, TaskEvent

# LLM Providers (universal endpoint architecture)
from app.models.llm_provider import UserLLMProvider, ProviderRoutingRule

# Memory hierarchy
from app.models.user_memory import UserMemory, RepositoryMemory, OrganizationMemory

# Legacy models (to be migrated)
from app.models.user_settings import UserSettings
from app.models.project import Project
from app.models.task import Task, Milestone, AgentStep
from app.models.execution import Run
from app.models.memory import ProjectMemory, KnowledgeEntry, Skill, DeploymentHistory

__all__ = [
    # Base
    "Base",
    # User & Identity
    "Organization",
    "User",
    "UserSession",
    # Conversations
    "Conversation",
    "Message",
    "ConversationTask",
    "ConversationEvent",
    "TaskEvent",
    # LLM Providers
    "UserLLMProvider",
    "ProviderRoutingRule",
    # Memory
    "UserMemory",
    "RepositoryMemory",
    "OrganizationMemory",
    # Legacy
    "UserSettings",
    "Project",
    "Task",
    "Milestone",
    "AgentStep",
    "Run",
    "ProjectMemory",
    "KnowledgeEntry",
    "Skill",
    "DeploymentHistory",
]
