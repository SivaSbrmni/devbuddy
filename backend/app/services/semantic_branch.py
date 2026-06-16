"""Semantic Branch Naming Service

Generates professional, human-readable branch names from AI intent analysis.

Rules:
- Maximum 4 words
- 35 characters maximum
- lowercase kebab-case
- Semantic meaning (no random hashes)
- Categories: feature/, bugfix/, refactor/, chore/, docs/, test/

Examples:
- devbuddy/feature/image-copy
- devbuddy/bugfix/login-timeout
- devbuddy/refactor/auth-module
- devbuddy/chore/update-angular

If collision: devbuddy/feature/image-copy-2 (never random hashes)
"""

from __future__ import annotations

import re
from typing import Optional
from dataclasses import dataclass

import structlog

log = structlog.get_logger()


@dataclass
class BranchIntent:
    """Parsed intent from user request."""
    category: str  # feature, bugfix, refactor, chore, docs, test, hotfix
    action: str     # add, fix, update, implement, create, etc.
    target: str     # what is being changed (image-copy, auth-module, etc.)
    descriptor: Optional[str] = None  # additional context


class SemanticBranchNamingService:
    """Generate professional branch names from user requests."""
    
    # Category detection patterns
    CATEGORY_PATTERNS = {
        'feature': [
            r'(?i)(add|implement|create|introduce|build|develop|support|enable)\s+(?:a\s+)?(?:new\s+)?',
            r'(?i)(feature|enhancement|capability|functionality)',
        ],
        'bugfix': [
            r'(?i)(fix|repair|correct|resolve|patch|address|bug)',
            r'(?i)(broken|not working|error|issue|problem|fail)',
            r'(?i)(crash|exception|timeout|null|undefined)',
        ],
        'refactor': [
            r'(?i)(refactor|restructure|reorganize|cleanup|clean up|simplify)',
            r'(?i)(improve|optimize|enhance|streamline|consolidate)',
            r'(?i)(extract|split|separate|modularize|componentize)',
            r'(?i)(remove|delete|eliminate|unused|dead code)',
        ],
        'chore': [
            r'(?i)(update|upgrade|bump|migrate|sync)',
            r'(?i)(dependency|dependencies|package|lib|library|version)',
            r'(?i)(config|configuration|setup|tooling|ci|cd|pipeline)',
            r'(?i)(format|lint|style|prettier|eslint)',
        ],
        'docs': [
            r'(?i)(document|documentation|readme|doc|guide|comment)',
            r'(?i)(explain|describe|clarify|example|tutorial)',
        ],
        'test': [
            r'(?i)(test|spec|testing|coverage|e2e|integration|unit test)',
            r'(?i)(mock|stub|fixture|scenario|assertion)',
        ],
        'hotfix': [
            r'(?i)(hotfix|critical|urgent|emergency|production|prod)',
            r'(?i)(severe|security|vulnerability|cve|exploit)',
        ],
    }
    
    # Common words to remove (articles, prepositions, etc.)
    NOISE_WORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
        'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
        'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'into',
        'onto', 'upon', 'within', 'without', 'through', 'during', 'before',
        'after', 'above', 'below', 'between', 'among', 'against', 'across',
        'using', 'based', 'according', 'following', 'regarding', 'concerning',
    }
    
    # Technical terms that should be kept as-is (even if short)
    TECHNICAL_TERMS = {
        'api', 'ui', 'ux', 'db', 'sql', 'jwt', 'auth', 'css', 'html', 'js',
        'ts', 'json', 'xml', 'yaml', 'csv', 'pdf', 'png', 'jpg', 'gif', 'svg',
        'http', 'https', 'url', 'uri', 'rest', 'graphql', 'grpc', 'rpc',
        'aws', 'gcp', 'azure', 'docker', 'k8s', 'kube', 'ci', 'cd', 'git',
        'github', 'gitlab', 'oauth', 'ssl', 'tls', 'cors', 'csrf', 'xss',
        'pdf', 'csv', 'md', 'html', 'css', 'scss', 'sass', 'less', 'ts',
        'tsx', 'jsx', 'vue', 'svelte', 'angular', 'react', 'next', 'nuxt',
        'express', 'fastapi', 'flask', 'django', 'spring', 'laravel',
    }
    
    @classmethod
    def generate(cls, request: str, max_length: int = 35) -> str:
        """Generate semantic branch name from user request.
        
        Args:
            request: User's natural language request
            max_length: Maximum length of branch name (default 35)
            
        Returns:
            Semantic branch name like "feature/image-copy"
        """
        # Parse intent
        intent = cls._parse_intent(request)
        
        # Build semantic name
        semantic_name = cls._build_name(intent, max_length - len(intent.category) - 1)
        
        branch_name = f"{intent.category}/{semantic_name}"
        
        log.info(
            "branch.generated",
            request=request[:50],
            category=intent.category,
            branch=branch_name,
        )
        
        return branch_name
    
    @classmethod
    def _parse_intent(cls, request: str) -> BranchIntent:
        """Parse user intent to determine category and semantic meaning."""
        request_lower = request.lower()
        
        # Detect category
        category_scores = {}
        for cat, patterns in cls.CATEGORY_PATTERNS.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, request_lower):
                    score += 1
            if score > 0:
                category_scores[cat] = score
        
        # Default to feature if unclear
        category = max(category_scores, key=category_scores.get) if category_scores else 'feature'
        
        # Extract action and target
        action, target, descriptor = cls._extract_semantic_parts(request, category)
        
        return BranchIntent(
            category=category,
            action=action,
            target=target,
            descriptor=descriptor,
        )
    
    @classmethod
    def _extract_semantic_parts(cls, request: str, category: str) -> tuple:
        """Extract action and target from request."""
        # Remove code blocks, URLs, and special characters
        cleaned = re.sub(r'```[\s\S]*?```', '', request)  # Code blocks
        cleaned = re.sub(r'https?://\S+', '', cleaned)  # URLs
        cleaned = re.sub(r'[^\w\s-]', ' ', cleaned)      # Special chars
        
        # Split into words
        words = cleaned.split()
        
        # Remove noise words (but keep technical terms)
        meaningful = [
            w for w in words 
            if w.lower() not in cls.NOISE_WORDS or w.lower() in cls.TECHNICAL_TERMS
        ]
        
        # Extract action verb (usually first meaningful word)
        action_words = {
            'add': ['add', 'implement', 'create', 'introduce', 'build', 'develop', 'support'],
            'fix': ['fix', 'repair', 'correct', 'resolve', 'patch', 'address'],
            'update': ['update', 'upgrade', 'bump', 'migrate', 'sync', 'refresh'],
            'refactor': ['refactor', 'restructure', 'reorganize', 'simplify', 'optimize'],
            'remove': ['remove', 'delete', 'eliminate', 'drop', 'clean', 'cleanup'],
            'test': ['test', 'spec', 'mock', 'stub'],
            'document': ['document', 'doc', 'explain', 'describe'],
        }
        
        action = 'update'  # Default
        for act, synonyms in action_words.items():
            if any(s in request_lower for s in synonyms):
                action = act
                break
        
        # Extract target (nouns and compound terms)
        target_words = []
        for i, word in enumerate(meaningful):
            word_lower = word.lower()
            # Skip if it's an action word
            is_action = any(
                word_lower in synonyms 
                for synonyms in action_words.values()
            )
            if not is_action and len(word) > 2:
                target_words.append(cls._slugify_single(word))
        
        # Limit to most important words (first 3 meaningful)
        target = '-'.join(target_words[:3])
        
        # If target is empty, use a fallback
        if not target:
            target = 'changes'
        
        return action, target, None
    
    @classmethod
    def _build_name(cls, intent: BranchIntent, max_length: int) -> str:
        """Build the semantic branch name."""
        # Start with target (most important)
        name_parts = [intent.target]
        
        # Add descriptor if present and space allows
        if intent.descriptor and len(intent.target) < 20:
            descriptor_slug = cls._slugify_single(intent.descriptor)
            combined = f"{intent.target}-{descriptor_slug}"
            if len(combined) <= max_length:
                name_parts.append(descriptor_slug)
        
        # Join and truncate if necessary
        name = '-'.join(name_parts)
        
        # Ensure it doesn't exceed max length
        if len(name) > max_length:
            # Try to truncate at word boundary
            truncated = name[:max_length]
            last_hyphen = truncated.rfind('-')
            if last_hyphen > 10:  # Only truncate if we keep at least 10 chars
                name = truncated[:last_hyphen]
            else:
                name = truncated
        
        # Clean up any double hyphens or trailing hyphens
        name = re.sub(r'-+', '-', name)
        name = name.strip('-')
        
        return name
    
    @classmethod
    def _slugify_single(cls, word: str) -> str:
        """Convert single word to slug format."""
        return word.lower().strip('-_')
    
    @classmethod
    def handle_collision(cls, base_name: str, existing_branches: list[str]) -> str:
        """Handle branch name collision by adding incremental number.
        
        Never use random hashes. Always use -2, -3, etc.
        """
        if base_name not in existing_branches:
            return base_name
        
        # Extract category and name
        parts = base_name.split('/', 1)
        if len(parts) != 2:
            return base_name
        
        category, name = parts
        
        # Find highest existing number
        max_num = 1
        pattern = re.compile(re.escape(name) + r'-(\d+)$')
        
        for branch in existing_branches:
            match = pattern.search(branch)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        
        # Generate next number
        return f"{category}/{name}-{max_num + 1}"


# Singleton instance and convenience function
branch_namer = SemanticBranchNamingService()


def generate_branch_name(request: str, existing_branches: Optional[list] = None) -> str:
    """Generate semantic branch name from request.
    
    Args:
        request: User's natural language request
        existing_branches: List of existing branch names to check for collisions
        
    Returns:
        Semantic branch name like "devbuddy/feature/image-copy"
    """
    # Generate base name
    base = branch_namer.generate(request)
    
    # Add devbuddy/ prefix
    full_name = f"devbuddy/{base}"
    
    # Handle collision if existing branches provided
    if existing_branches:
        full_name = branch_namer.handle_collision(full_name, existing_branches)
    
    return full_name


# Legacy support - semantic version of old generate
_semantic_counter = {}


def generate_semantic_branch_name(
    request: str,
    existing_branches: Optional[list] = None,
) -> str:
    """Primary entry point for semantic branch naming.
    
    This is the function that should be used by the agent system.
    """
    return generate_branch_name(request, existing_branches)
