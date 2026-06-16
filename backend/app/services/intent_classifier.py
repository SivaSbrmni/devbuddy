"""Intent Classification Service

Distinguishes between different user intents to route requests appropriately:

1. ANALYZE - User wants to understand/explain something (no code changes)
   Examples: "What does this project do?", "Explain the architecture"

2. IMPLEMENT - User wants code changes (create branch, PR, workflow)
   Examples: "Add JWT auth", "Fix the bug", "Implement feature X"

3. QUESTION - User has a specific technical question
   Examples: "How do I configure X?", "Why does Y happen?"

4. CHAT - General conversation
   Examples: "Hello", "Thanks", "Goodbye"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import structlog

log = structlog.get_logger()


class IntentType(Enum):
    """Types of user intents."""
    ANALYZE = "analyze"           # Understand/explain, no code changes
    IMPLEMENT = "implement"       # Code changes required
    QUESTION = "question"         # Technical question
    CHAT = "chat"                 # General conversation


@dataclass
class IntentClassification:
    """Result of intent classification."""
    intent: IntentType
    confidence: float  # 0-1
    should_create_branch: bool
    should_create_pr: bool
    explanation: str  # Why this intent was chosen


class IntentClassifier:
    """Classify user messages into intents."""

    # Patterns that indicate ANALYZE intent (understanding, no code changes)
    ANALYZE_PATTERNS = [
        # Direct explanation requests
        r'(?i)^(can you |could you |please )?(explain|describe|tell me about|what is|what does)',
        r'(?i)^(help me )?(understand|comprehend|grasp)',
        r'(?i)^(give me |provide )?(an? )?(overview|summary|breakdown|analysis)',
        r'(?i)how (does|is|are|do) .+ (work|function|operate)',
        r'(?i)what\s+(is|are|does) .+ (mean|do|mean by)',
        r'(?i)walk me through',
        r'(?i)break down',
        # Context-seeking questions
        r'(?i)purpose of .+\?',
        r'(?i)architecture of',
        r'(?i)design of',
        r'(?i)structure of',
    ]

    # Patterns that indicate QUESTION intent (technical question, no code changes)
    QUESTION_PATTERNS = [
        r'(?i)^(how|why|when|where|what|which|who) .+\?',
        r'(?i)^(is|are|can|could|would|should|will|did|do|does) .+\?',
        r'(?i)^(what|which) (is|are) (the )?(best|recommended|proper)',
        r'(?i)how (to|can|do) (I|we|you)',
        r'(?i)what (happens|would happen|is the)',
    ]

    # Patterns that indicate CHAT intent (no work needed)
    CHAT_PATTERNS = [
        r'(?i)^(hi|hello|hey|greetings|howdy)(\s|$|!)',
        r'(?i)^(thanks|thank you|ty|thx)(\s|$|!)',
        r'(?i)^(goodbye|bye|see you|talk later)',
        r'(?i)^(nice|great|awesome|cool|wow)(\s|$|!)',
        r'(?i)^(ok|okay|sure|yes|no)(\s|$|!)',
        r'(?i)^(got it|understood|makes sense|I see)',
    ]

    # Patterns that indicate IMPLEMENT intent (code changes)
    IMPLEMENT_PATTERNS = [
        # Action verbs indicating code work
        r'(?i)\b(add|implement|create|build|develop|make|generate)\b',
        r'(?i)\b(fix|repair|correct|resolve|patch|address|solve)\b',
        r'(?i)\b(update|upgrade|modify|change|refactor|improve|enhance)\b',
        r'(?i)\b(remove|delete|eliminate|drop|clean up)\b',
        r'(?i)\b(enable|disable|support|integrate|connect)\b',
        r'(?i)\b(setup|configure|install|deploy|publish)\b',
        r'(?i)\b(test|validate|verify|check|ensure)\b',
        r'(?i)\b(export|import|migrate|convert|transform)\b',
        # File/code operations
        r'(?i)\b(in|to|from)\s+(the\s+)?(file|code|script|module|class|function|method|component|page|route|api)\b',
        # Explicit requests
        r'(?i)^(please\s+)?(add|implement|create|fix|update|change|modify|remove)\b',
    ]

    # Negative patterns - these OVERRIDE other patterns
    NEGATIVE_IMPLEMENT_PATTERNS = [
        # "Add explanation", "Add documentation" - docs, not code
        r'(?i)\b(add|include)\s+(an?\s+)?(explanation|description|documentation|docs|comment)',
        # "Explain how to add" - question, not implement
        r'(?i)explain\s+how\s+(to|do|can)',
        r'(?i)show\s+me\s+how\s+(to|do)',
        # "What does X add" - question
        r'(?i)(what|which|how)\s+.*\b(add|implement|create|fix)',
    ]

    @classmethod
    def classify(cls, message: str) -> IntentClassification:
        """Classify user message into intent type.

        Args:
            message: User's natural language message

        Returns:
            IntentClassification with intent type and metadata
        """
        message_lower = message.lower().strip()

        # Check CHAT first (simplest, no work)
        chat_score = cls._score_patterns(message_lower, cls.CHAT_PATTERNS)
        if chat_score > 0.7:
            return IntentClassification(
                intent=IntentType.CHAT,
                confidence=chat_score,
                should_create_branch=False,
                should_create_pr=False,
                explanation="Detected casual conversation pattern",
            )

        # Check ANALYZE - user wants to understand, not change
        analyze_score = cls._score_patterns(message_lower, cls.ANALYZE_PATTERNS)

        # Boost analyze score for clear explanation requests
        if any(w in message_lower for w in ['explain', 'understand', 'what does', 'how does', 'architecture', 'overview']):
            analyze_score += 0.2

        if analyze_score > 0.6:
            return IntentClassification(
                intent=IntentType.ANALYZE,
                confidence=analyze_score,
                should_create_branch=False,
                should_create_pr=False,
                explanation="Detected analysis/explanation request (no code changes needed)",
            )

        # Check QUESTION - technical question
        question_score = cls._score_patterns(message_lower, cls.QUESTION_PATTERNS)

        # Check if it looks like a question but contains implement words
        # "How do I add X?" is a question, not implement
        has_question_words = question_score > 0.3
        has_implement_words = cls._score_patterns(message_lower, cls.IMPLEMENT_PATTERNS) > 0.3

        # If it's a "how do I..." question, treat as QUESTION not IMPLEMENT
        if has_question_words and has_implement_words:
            if re.search(r'(?i)how (do|can|should) (i|we)', message_lower):
                return IntentClassification(
                    intent=IntentType.QUESTION,
                    confidence=0.8,
                    should_create_branch=False,
                    should_create_pr=False,
                    explanation="Detected 'how-to' question (user asking for guidance, not requesting implementation)",
                )

        if question_score > 0.6:
            return IntentClassification(
                intent=IntentType.QUESTION,
                confidence=question_score,
                should_create_branch=False,
                should_create_pr=False,
                explanation="Detected technical question",
            )

        # Check for NEGATIVE patterns that override IMPLEMENT
        negative_score = cls._score_patterns(message_lower, cls.NEGATIVE_IMPLEMENT_PATTERNS)

        # Check IMPLEMENT - code changes needed
        implement_score = cls._score_patterns(message_lower, cls.IMPLEMENT_PATTERNS)

        # Apply negative patterns
        if negative_score > 0.5:
            implement_score -= 0.4

        # Require stronger signals for short messages
        if len(message_lower.split()) < 5:
            implement_score -= 0.2

        if implement_score > 0.5:
            return IntentClassification(
                intent=IntentType.IMPLEMENT,
                confidence=implement_score,
                should_create_branch=True,
                should_create_pr=True,
                explanation="Detected implementation request (code changes required)",
            )

        # Default to QUESTION for unclear cases (safest)
        return IntentClassification(
            intent=IntentType.QUESTION,
            confidence=0.5,
            should_create_branch=False,
            should_create_pr=False,
            explanation="Unclear intent, treating as question for safety",
        )

    @classmethod
    def _score_patterns(cls, text: str, patterns: list[str]) -> float:
        """Score text against list of regex patterns.

        Returns score 0-1 based on number of matches.
        """
        if not patterns:
            return 0.0

        matches = sum(1 for p in patterns if re.search(p, text))
        # Normalize with diminishing returns
        return min(matches / 2, 1.0) if matches > 0 else 0.0


# Singleton and convenience function
intent_classifier = IntentClassifier()


def classify_intent(message: str) -> IntentClassification:
    """Classify user message intent.

    Args:
        message: User's natural language message

    Returns:
        IntentClassification with routing information
    """
    result = intent_classifier.classify(message)

    log.info(
        "intent.classified",
        message_preview=message[:50],
        intent=result.intent.value,
        confidence=result.confidence,
        create_branch=result.should_create_branch,
    )

    return result


def should_trigger_code_workflow(message: str) -> bool:
    """Quick check if message should trigger code workflow.

    Returns True only for IMPLEMENT intent with high confidence.
    """
    classification = classify_intent(message)
    return (
        classification.intent == IntentType.IMPLEMENT
        and classification.confidence > 0.6
    )


# Example usage / test cases
if __name__ == "__main__":
    test_cases = [
        # Should be ANALYZE (no code changes)
        ("Can you understand and explain me what this project does?", IntentType.ANALYZE),
        ("What is the architecture of this codebase?", IntentType.ANALYZE),
        ("Explain how the authentication works", IntentType.ANALYZE),
        ("Give me an overview of the project structure", IntentType.ANALYZE),
        ("Walk me through the main components", IntentType.ANALYZE),

        # Should be QUESTION (no code changes)
        ("How do I configure the database?", IntentType.QUESTION),
        ("Why does this error happen?", IntentType.QUESTION),
        ("What is the best practice for X?", IntentType.QUESTION),

        # Should be IMPLEMENT (code changes)
        ("Add JWT authentication to the API", IntentType.IMPLEMENT),
        ("Fix the timeout bug in login", IntentType.IMPLEMENT),
        ("Implement image copy feature", IntentType.IMPLEMENT),
        ("Update the README with new instructions", IntentType.IMPLEMENT),

        # Should be CHAT
        ("Thanks for the help!", IntentType.CHAT),
        ("Hello", IntentType.CHAT),
    ]

    print("\n=== Intent Classification Tests ===\n")
    for message, expected in test_cases:
        result = classify_intent(message)
        status = "✅" if result.intent == expected else "❌"
        print(f"{status} [{result.intent.value:12}] {message[:50]}...")
        if result.intent != expected:
            print(f"   Expected: {expected.value}, Got: {result.intent.value}")
            print(f"   Explanation: {result.explanation}")
