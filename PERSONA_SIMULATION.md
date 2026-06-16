# Persona Simulation Report — 7 Core Developers

## Methodology
Each persona was walked through the complete DevBuddy flow from landing to task completion. Every hesitation, confusion, and blocker was documented.

---

## Persona 1: JUNIOR DEVELOPER (0-2 years exp)
**Mental model**: "AI tools are magic. I want to build something cool but I'm overwhelmed by choices."

### Journey
1. Lands on devbuddy.org, sees "Invite Only — Private Beta"
2. **HESITATION**: "I'm not invited. Can I still use this?"
3. Fills email form. Gets "We'll reach out" message.
4. **BLOCKER**: "So I can't try it at all? No demo?"
5. (Assuming access): Goes to `/app`, signs in with Google
6. Sees empty state: "Welcome back, Alex" — but this is their first time
7. **CONFUSION**: "Welcome BACK? I've never been here."
8. Clicks "Build a REST API" quick action
9. **HESITATION**: "Which model do I pick? Claude? Llama? Ollama? I don't know what these mean."
10. Clicks send with default model
11. Sees phase timeline: Planning → Understanding → Implementing → Delivering
12. **HESITATION**: "Where's the code? It's just showing me phases."
13. Task completes, sees "Pull Request #42"
14. **CONFUSION**: "What's a Pull Request? I just wanted to see the code."

**Critical issues**: No model guidance, empty state assumes returning user, no code preview

---

## Persona 2: SENIOR DEVELOPER (5-8 years exp)
**Mental model**: "I know what I need. Don't make me think. Show me the code."

### Journey
1. Goes directly to `/app` (has bookmark)
2. Empty state with quick actions
3. Types: "Create a FastAPI service with JWT auth and PostgreSQL"
4. **HESITATION**: "Which model is best for code generation? The dropdown doesn't tell me."
5. Sends with default (Claude)
6. Sees phase timeline
7. **HESITATION**: "I want to see the actual code being generated, not just 'Implementing — 5 steps completed'"
8. Task completes, gets PR link
9. **HESITATION**: "Can I see the code BEFORE it opens a PR? I want to review first."
10. Clicks PR, reviews on GitHub
11. **HESITATION**: "How do I iterate? Same chat? New chat?"

**Critical issues**: Phases not expandable, no preview before PR, no iteration guidance

---

## Persona 3: ARCHITECT (10+ years exp)
**Mental model**: "I need to understand the reasoning. Show me your work."

### Journey
1. Lands on devbuddy.org, sees "Invite Only"
2. **HESITATION**: "I'm not waiting for an invite. This looks like a toy."
3. (If access): Opens `/app`
4. **HESITATION**: "No keyboard shortcut reference? No power-user features?"
5. Opens Settings
6. **CONFUSION**: "Settings is just API keys? Where are export options, retention, themes?"
7. Types: "Design event-driven architecture for payments with idempotency"
8. **HESITATION**: "No model recommendation for architecture tasks?"
9. Sees phase timeline
10. **HESITATION**: "I can't expand these phases to see the detailed reasoning. This is a black box."
11. Clicks "Planning" phase — nothing happens
12. **BLOCKER**: "Without seeing the reasoning, I can't validate the approach."

**Critical issues**: Phases not expandable, no model guidance, settings too shallow

---

## Persona 4: DEVOPS ENGINEER
**Mental model**: "I need infrastructure code. Give me files I can review and apply."

### Journey
1. Opens `/app`, logged in
2. Types: "Set up GitHub Actions for Docker build and ECS deploy"
3. **HESITATION**: "Do I need to connect GitHub first? There's no obvious repo connection."
4. Discovers GitHub panel via ⌘K command palette
5. **HESITATION**: "Why is repo connection hidden in a command palette?"
6. Connects repo, sends message
7. Sees "Delivering — PR opened"
8. **CONFUSION**: "I wanted the workflow file locally, not a PR. Can I download it?"
9. Opens workspace panel
10. **HESITATION**: "I see files but no obvious download button. Do I copy-paste?"

**Critical issues**: GitHub connection hidden, no download/preview option

---

## Persona 5: QA ENGINEER
**Mental model**: "I need test cases I can run locally before sharing."

### Journey
1. Opens `/app`
2. Types: "Write tests for user auth API"
3. **HESITATION**: "No file upload for OpenAPI spec? I have to paste it?"
4. Pastes spec, sends
5. Sees "Implementing — 5 steps completed"
6. **HESITATION**: "The tests are in a PR? I need to preview and run them first."
7. Clicks PR link
8. **BLOCKER**: "I can't run these without checking out the branch. I wanted to see them in the UI."

**Critical issues**: No preview before PR, no file upload

---

## Persona 6: OPEN SOURCE MAINTAINER
**Mental model**: "Is this open source? Can I self-host? Where's the code?"

### Journey
1. Lands on devbuddy.org
2. **HESITATION**: "No GitHub link? No documentation? Is this even open source?"
3. Scrolls to footer: "© 2026 DevBuddy · Invite-only private beta"
4. **BLOCKER**: "No trust signals. I'm not giving this my email."
5. (If gets in): Opens `/app`
6. Types: "Generate release notes from last 10 commits"
7. **HESITATION**: "How do I connect my repo? There's no 'Connect GitHub' button."
8. Discovers GitHub panel via command palette after 30 seconds
9. **HESITATION**: "Why is this hidden?"

**Critical issues**: No trust signals on landing, GitHub connection not discoverable

---

## Persona 7: CONSULTANT
**Mental model**: "I work with multiple clients. I need isolation and export."

### Journey
1. Opens `/app` at client site
2. **HESITATION**: "Google auth — is client data going through Google?"
3. Signs in
4. **HESITATION**: "No client folders or projects? Just a flat list of conversations?"
5. Creates conversation for Client A
6. **HESITATION**: "How do I export this for the client? No export button."
7. Checks settings
8. **HESITATION**: "Settings is only API keys. No export, no privacy, no sharing."

**Critical issues**: No project/client organization, no export, no privacy settings

---

## Cross-Persona Critical Issues (Ranked by Impact)

| # | Issue | Personas Affected | Severity |
|---|-------|-------------------|----------|
| 1 | **TaskCard phases not expandable** | Senior, Architect, DevOps, QA | Critical |
| 2 | **No code preview before PR** | Senior, DevOps, QA | Critical |
| 3 | **No model guidance** | Junior, Senior, Architect | High |
| 4 | **Empty state says "Welcome back" to new users** | Junior | High |
| 5 | **GitHub connection hidden in command palette** | DevOps, QA, OSS | High |
| 6 | **Landing page no sign-in link** | All returning | Medium |
| 7 | **Settings is only API keys** | Architect, Consultant | Medium |
| 8 | **No trust signals on landing** | OSS, Consultant | Medium |
