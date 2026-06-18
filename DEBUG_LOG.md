# DevBuddy Debug Investigation - June 18, 2026

## Executive Summary
Two critical bugs causing broken UX:
1. **Duplicate user messages** - Race condition between SSE and API response
2. **Empty assistant responses** - Errors swallowed by internal catch block

## Issues Found

### Issue 1: Duplicate User Messages
**Root Cause:** Race condition in `useServerConversations.ts` `createMessage()`

**Flow:**
1. `createMessage()` adds optimistic message with temp ID
2. Server creates message, broadcasts SSE `message_created`
3. SSE handler adds real message to state
4. API response returns, tries to replace optimistic by temp ID
5. Result: `[..., real_msg, real_msg]` - DUPLICATE

**Evidence:**
- Network: Single POST to `/messages` (request #22)
- UI: Shows same user message twice in chat bubble
- Sidebar shows "3" messages for a conversation that should have 2

**Fix Required:** `useServerConversations.ts` line ~335 - check if real message already exists before replacement

### Issue 2: Empty Assistant Bubble
**Root Cause:** `runCloudAgent()` in `Workspace.tsx` catches 401 error internally, patches task card, but does NOT re-throw

**Flow:**
1. User sends message, `runCloudAgent()` creates empty assistant message with taskCard
2. Calls `/cloud-agent/run` → returns 401 "GitHub not connected"
3. `runCloudAgent()` catch block (line 897) patches task card with error status
4. Returns `true` - no error thrown
5. `send()` catch block never executes
6. User sees empty assistant bubble (task card with empty content)

**Evidence:**
- Network: POST `/cloud-agent/run` returns 401 (request #27)
- Console: "Failed to load resource: 401" error
- UI: Empty assistant bubble with just timestamp

**Fix Required:** `Workspace.tsx` line ~897 - re-throw non-network errors

### Issue 3: updateActive Creates Duplicate Server Messages
**Root Cause:** `updateActive()` iterates over ALL messages and calls `createServerMessage()` for each one, every time it's called. No deduplication.

**Flow:**
1. `updateActive([userMsg], title)` → creates user message
2. `updateActive([userMsg, agentMsg], title)` → tries to create BOTH user AND assistant messages again
3. The backend might silently ignore duplicates or create new ones

**Fix Required:** `Workspace.tsx` `updateActive()` - only create messages that don't already exist on server

## Network Trace (single message send)
```
#22 POST /conversations/{id}/messages        -> 200 (user message created)
#23 PATCH /conversations/{id}                 -> 200 (title update)
#24 POST /conversations/{id}/messages        -> 200 (assistant message with empty content)
#25 POST /conversations/{id}/messages        -> 200 (??? possibly duplicate)
#26 PATCH /conversations/{id}                 -> 200
#27 POST /cloud-agent/run                     -> 401 (GitHub not connected)
#28 PATCH /conversations/{id}                 -> 200
```

## Fix Plan
1. Fix `useServerConversations.ts` - dedup in createMessage success handler
2. Fix `Workspace.tsx` - re-throw non-network errors in runCloudAgent
3. Fix `Workspace.tsx` - updateActive should not recreate existing messages
4. Rebuild, deploy, verify
