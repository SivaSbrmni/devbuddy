# 06 — Agent Executor (ReAct Loop)

**Parent**: [AGENT_GUIDE.md](../AGENT_GUIDE.md)
**Prev**: [05_PROJECT_STRUCTURE.md](./05_PROJECT_STRUCTURE.md)

---

## What is the Agent Executor?

The core intelligence of DevBuddy. Takes a user request and executes it via the **ReAct** (Reasoning + Acting) pattern:

1. **Decompose**: Break into subtasks
2. **Plan**: Order by dependencies
3. **Execute**: Run skills
4. **Validate**: Check outputs
5. **Fix**: Retry if needed
6. **Deliver**: Present to user

---

## ReAct Loop Detail

```
User Request
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. DECOMPOSE (LLM call)                                          │
│    Prompt: "Break this into subtasks. Return JSON array."        │
│    Output: [                                                      │
│      {"id": 1, "description": "Read existing form code",           │
│       "dependencies": [], "estimated_complexity": "low"},         │
│      {"id": 2, "description": "Design validation schema",          │
│       "dependencies": [1], "estimated_complexity": "medium"},    │
│      {"id": 3, "description": "Generate React component",        │
│       "dependencies": [1, 2], "estimated_complexity": "medium"}, │
│      {"id": 4, "description": "Write tests",                      │
│       "dependencies": [3], "estimated_complexity": "low"}       │
│    ]                                                              │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. PLAN (topological sort)                                       │
│    Batch 1: [1]           ← No dependencies                      │
│    Batch 2: [2]           ← Depends on 1                         │
│    Batch 3: [3]           ← Depends on 1, 2                      │
│    Batch 4: [4]           ← Depends on 3                         │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. EXECUTE (parallel within batch, sequential across batches)   │
│                                                                  │
│    For each batch:                                               │
│      For each subtask in parallel (asyncio.gather):            │
│        • Select skill based on description                      │
│        • Call skill function                                     │
│        • Log to audit                                            │
│        • Store result                                            │
│                                                                  │
│    Skills available:                                             │
│      • read_file(path)                                          │
│      • write_file(path, content)                                │
│      • run_python(code) ← Sandboxed                             │
│      • web_search(query)                                        │
│      • recall_memory(query)                                     │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. VALIDATE                                                      │
│    For each generated file:                                      │
│      • Syntax check (tree-sitter or language server)              │
│      • Test run (if tests found)                                 │
│      • Security scan (pattern match for secrets, SQL injection)  │
│                                                                  │
│    Result: VALID | INVALID                                       │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼ (if INVALID)
┌─────────────────────────────────────────────────────────────────┐
│ 5. FIX (1 retry only)                                            │
│    Prompt: "Previous attempt failed with: <error>. Fix it."      │
│    Re-execute failed subtasks                                    │
│    If still fails → Mark FAILED → Human review                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. HUMAN CHECKPOINTS                                             │
│                                                                  │
│    SECURITY_REVIEW (if touches auth/payment code):              │
│      → Show security scan results                                │
│      → Require explicit approval                                 │
│                                                                  │
│    HUMAN_REVIEW (always):                                        │
│      → Show diff of all changes                                  │
│      → User: Approve | Request Changes | Cancel                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. DELIVERY                                                      │
│    On approval:                                                  │
│      • Create branch (if GitHub connected)                        │
│      • Commit with message describing changes                   │
│      • Push (if user confirms)                                  │
│                                                                  │
│    Or:                                                           │
│      • Bundle files for download                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Code Locations

### Main Entry Point

**File**: `backend/app/services/agent_executor.py`
**Function**: `execute_task(task_id: UUID)`

```python
async def execute_task(task_id: UUID):
    """
    Main ReAct loop. Runs in background task.
    Updates task status and subtasks in database.
    Sends WebSocket updates to frontend.
    """
    task = await get_task(task_id)
    
    # 1. DECOMPOSE
    subtasks = await _decompose(task.description)
    await save_subtasks(task_id, subtasks)
    
    # 2. PLAN
    batches = _plan_batches(subtasks)  # topological sort
    
    # 3. EXECUTE
    for batch in batches:
        results = await asyncio.gather(
            *[execute_subtask(st) for st in batch]
        )
    
    # 4. VALIDATE
    validation = await _validate_results(results)
    
    # 5. FIX (if needed)
    if not validation.valid:
        await _fix_and_retry(validation.errors)
    
    # 6. CHECKPOINT
    await _await_human_approval(task_id)
    
    # 7. DELIVER
    await _deliver_results(task_id)
```

### Task Decomposition

**Function**: `_decompose(description: str) -> List[Subtask]`

Uses LLM to break request into subtasks. Prompt includes:
- Current tech stack (from context)
- Available skills
- Dependency rules

```python
async def _decompose(description: str) -> List[Subtask]:
    prompt = f"""
    Break this request into subtasks:
    
    Request: {description}
    
    Available skills: read_file, write_file, run_python, web_search
    
    Return JSON array:
    [
      {{
        "id": 1,
        "description": "what to do",
        "dependencies": [],
        "estimated_complexity": "low|medium|high"
      }}
    ]
    """
    
    response = await llm_generate(prompt)
    return parse_json(response)
```

### Skill Registry

**File**: `backend/app/services/skills.py`

```python
from typing import Callable, Dict, Any

# Registry of all skills
SKILL_REGISTRY: Dict[str, Callable] = {}

def skill(description: str, params: Dict[str, Any]):
    """Decorator to register a skill."""
    def decorator(func: Callable):
        SKILL_REGISTRY[func.__name__] = {
            "func": func,
            "description": description,
            "params": params
        }
        return func
    return decorator

@skill(
    description="Read file contents",
    params={"path": {"type": "string", "description": "File path"}}
)
async def read_file(path: str) -> str:
    # Implementation
    pass

@skill(
    description="Write file (creates dirs if needed)",
    params={
        "path": {"type": "string"},
        "content": {"type": "string"}
    }
)
async def write_file(path: str, content: str) -> str:
    # Implementation
    pass

@skill(
    description="Execute Python code in sandbox",
    params={"code": {"type": "string"}}
)
async def run_python(code: str) -> str:
    # Sandboxed execution via e2b or subprocess
    pass
```

### Subtask Execution

```python
async def execute_subtask(subtask: Subtask) -> SubtaskResult:
    """
    Execute a single subtask by selecting and calling appropriate skill.
    """
    # Parse description to select skill
    # (In practice, the LLM outputs skill calls directly)
    
    skill_name = select_skill(subtask.description)
    skill_def = SKILL_REGISTRY[skill_name]
    
    # Extract parameters from description
    params = extract_params(subtask.description, skill_def["params"])
    
    # Execute
    result = await skill_def["func"](**params)
    
    # Log
    await log_audit(
        task_id=subtask.task_id,
        event="subtask_completed",
        details={"subtask_id": subtask.id, "skill": skill_name}
    )
    
    return SubtaskResult(
        subtask_id=subtask.id,
        status="completed",
        output=result
    )
```

---

## State Transitions in Code

```python
# backend/app/services/agent_executor.py

class TaskState:
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    FIXING = "FIXING"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    READY_TO_PUSH = "READY_TO_PUSH"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# Transitions
transitions = {
    TaskState.PENDING: [TaskState.PLANNING],
    TaskState.PLANNING: [TaskState.APPROVAL_REQUIRED],
    TaskState.APPROVAL_REQUIRED: [TaskState.EXECUTING, TaskState.FAILED],
    TaskState.EXECUTING: [TaskState.VALIDATING],
    TaskState.VALIDATING: [TaskState.SECURITY_REVIEW, TaskState.FIXING, TaskState.HUMAN_REVIEW],
    TaskState.FIXING: [TaskState.VALIDATING, TaskState.FAILED],
    TaskState.SECURITY_REVIEW: [TaskState.HUMAN_REVIEW, TaskState.FAILED],
    TaskState.HUMAN_REVIEW: [TaskState.READY_TO_PUSH, TaskState.FAILED, TaskState.EXECUTING],
    TaskState.READY_TO_PUSH: [TaskState.COMPLETED, TaskState.FAILED],
}
```

---

## Human Checkpoints

### Security Review Trigger

Triggered when generated code matches patterns:
- Auth-related (login, password, token)
- Payment-related (billing, credit card)
- Database writes to sensitive tables
- Network calls to external APIs

```python
def requires_security_review(generated_files: List[File]) -> bool:
    security_patterns = [
        r'password|auth|login|token|jwt',
        r'payment|billing|credit|charge',
        r'DELETE FROM|DROP TABLE',
        r'eval\(|exec\(',
    ]
    
    for file in generated_files:
        content = file.content.lower()
        for pattern in security_patterns:
            if re.search(pattern, content):
                return True
    return False
```

### Human Review UI

Frontend shows:
1. Summary of changes
2. Diff view (old vs new)
3. Test results
4. Security scan results
5. Actions: [Approve] [Request Changes] [Cancel]

---

## Parallel Execution

**Current**: Asyncio gather within dependency-free batches
**Future**: True parallel with Temporal/Cadence for scale

```python
async def execute_batch(subtasks: List[Subtask]):
    """Execute subtasks in parallel where dependencies allow."""
    
    # All these can run simultaneously
    coroutines = [execute_subtask(st) for st in subtasks]
    
    # Gather results
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    
    # Handle failures
    for subtask, result in zip(subtasks, results):
        if isinstance(result, Exception):
            await handle_subtask_failure(subtask, result)
        else:
            await mark_subtask_complete(subtask, result)
```

---

## Retry & Fix Logic

```python
MAX_RETRIES = 1

async def _fix_and_retry(subtask: Subtask, error: str):
    if subtask.retry_count >= MAX_RETRIES:
        await mark_failed(subtask, "Max retries exceeded")
        return
    
    # Generate fix prompt
    fix_prompt = f"""
    The previous attempt failed with:
    {error}
    
    Original task: {subtask.description}
    
    Please fix the issue and try again.
    """
    
    # LLM generates corrected approach
    correction = await llm_generate(fix_prompt)
    
    # Update subtask and retry
    subtask.description = correction
    subtask.retry_count += 1
    
    return await execute_subtask(subtask)
```

---

## Streaming Updates

WebSocket sends real-time progress:

```python
async def send_progress_update(task_id: UUID, message: str):
    await websocket_manager.broadcast(
        task_id,
        {
            "type": "progress",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# Usage in executor
await send_progress_update(task_id, "Planning task...")
await send_progress_update(task_id, "Executing subtask 1/4...")
await send_progress_update(task_id, "Validating outputs...")
```

---

## Modifying the ReAct Loop

### Adding a New Skill

```python
# backend/app/services/skills.py

@skill(
    description="Run npm install in a directory",
    params={
        "directory": {"type": "string", "description": "Project root"},
        "package": {"type": "string", "description": "Package name (optional)"}
    }
)
async def npm_install(directory: str, package: str = None) -> str:
    """Install npm dependencies."""
    import subprocess
    
    cmd = ["npm", "install"]
    if package:
        cmd.append(package)
    
    result = subprocess.run(
        cmd,
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    return result.stdout if result.returncode == 0 else result.stderr
```

### Changing Validation Logic

Edit `backend/app/services/agent_executor.py` → `_validate_results()`:

```python
async def _validate_results(files: List[File]) -> ValidationResult:
    errors = []
    
    # Syntax check
    for file in files:
        if not syntax_valid(file.content, file.language):
            errors.append(f"{file.path}: Syntax error")
    
    # Security scan
    security_issues = security_scan(files)
    if security_issues:
        errors.extend(security_issues)
    
    # YOUR NEW VALIDATION HERE
    # e.g., lint check, type check, etc.
    
    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors
    )
```

---

**Next**: Read [07_SECURITY_HARDENING.md](./07_SECURITY_HARDENING.md) for security details.
