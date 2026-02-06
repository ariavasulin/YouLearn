# Tool Call Streaming Implementation Plan

## Overview

Make tool calls visible in the OpenWebUI chat UI. Currently, when the Agno agent invokes tools (read_file, write_file, compile_notes, etc.), the user sees nothing — the stream pauses silently. After this change, users see a spinner with the tool name during execution, and an expandable "View Result" block when it completes.

## Current State Analysis

**server.py** (line 158): calls `agent.arun(prompt, stream=True)` — only yields `RunContentEvent` text chunks. Tool calls execute silently.

**pipe.py** (line 132-166): `_handle_sse_event()` handles 4 event types: `status`, `message`, `done`, `error`. No tool call handling.

**OpenWebUI**: Renders `<details type="tool_calls" ...>` HTML as collapsible tool call blocks via `Collapsible.svelte`. When `done="false"` shows a spinner; when `done="true"` shows expandable result.

### Key Discoveries:
- Agno's `stream_events=True` parameter unlocks `ToolCallStartedEvent`, `ToolCallCompletedEvent`, `ToolCallErrorEvent`
- Import paths: `ToolCallStartedEvent`/`ToolCallCompletedEvent` from `agno.agent`; `ToolCallErrorEvent` from `agno.run.agent` (not re-exported)
- `IntermediateRunContentEvent` from `agno.run.agent` — emitted between tool calls, has `.content`
- `ToolExecution` fields: `tool_call_id`, `tool_name`, `tool_args`, `result`
- OpenWebUI **re-renders the entire message** on every content update (`marked.lexer()` re-runs). The `id` attribute is for DOM IDs, not match/replace.
- The pipe streams incrementally via `__event_emitter__` with `type: "message"`. Each emit **appends** to the displayed content — OpenWebUI does NOT replace previous content on each emit.

## Desired End State

When the agent calls a tool:
1. User sees spinner: "Executing **compile_notes**..." (collapsible, shimmer effect)
2. After tool completes: "View Result from **compile_notes**" (expandable, shows args + result)
3. Text content before/after tool calls renders normally
4. Multiple sequential tool calls each get their own block
5. Errors show as completed blocks with error text in the result

### Verification:
- Start backend, open OpenWebUI, send a message that triggers tool use (e.g., `/Lec` to trigger lecture creation)
- Verify spinner appears during tool execution
- Verify result block is expandable after completion
- Verify text before/after tool calls displays correctly
- Verify error case (e.g., read a nonexistent file)

## What We're NOT Doing

- **Streaming tool arguments** (`ToolCallArgsDeltaEvent` — not available in our Agno version)
- **File/image attachments** in tool results (no tools produce these currently)
- **Parallel tool call handling** (Agno executes tools sequentially)
- **Changing the OpenWebUI frontend** (we use the existing `<details>` protocol)
- **OpenAI-compatible streaming format** (over-engineering for our use case)

## Implementation Approach

**Option A (selected): Clean SSE Protocol** — Server emits structured tool call events, pipe converts to OpenWebUI `<details>` HTML.

The server stays format-agnostic (emits `tool_call_start`, `tool_call_complete`, `tool_call_error` events). The pipe is responsible for converting these to OpenWebUI's `<details>` HTML format.

**Content accumulation in the pipe**: Since each `__event_emitter__` call **appends** content, the pipe emits:
- On `tool_call_start`: the `<details done="false" ...>` HTML block
- On `tool_call_complete`: a `<details done="true" ...>` HTML block (with full args + result)

**Important**: OpenWebUI's Collapsible.svelte matches `<details>` by `id` attribute for DOM rendering. We emit the completed block as a **new** `<details>` element. The pending block (done="false") and completed block (done="true") will both be in the content, but OpenWebUI's markdown tokenizer will parse them separately. Testing needed to confirm whether two blocks with the same `id` cause issues — if so, we use different IDs for pending vs completed.

**Fallback approach**: If two `<details>` blocks with the same `id` cause rendering issues, we switch to emitting only the completed `<details done="true">` block (no pending spinner). This still provides value — users see what tools were called and their results — just without the in-progress spinner.

---

## Phase 1: Server-Side Tool Call Events

### Overview
Enable `stream_events=True` in `agent.arun()` and emit structured SSE events for tool call lifecycle.

### Changes Required:

#### 1. server.py — Streaming Loop
**File**: `backend/src/youlearn/server.py`
**Changes**: Add `stream_events=True`, import event types, handle tool call events in the streaming loop.

Add imports at top of file:
```python
from agno.agent import (
    RunContentEvent,
    ToolCallStartedEvent,
    ToolCallCompletedEvent,
)
from agno.run.agent import (
    IntermediateRunContentEvent,
    ToolCallErrorEvent,
)
```

Replace the streaming loop (current lines 158-163) with:
```python
response_chunks: list[str] = []

async for chunk in agent.arun(
    prompt,
    stream=True,
    stream_events=True,
):
    if isinstance(chunk, ToolCallStartedEvent) and chunk.tool:
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "tool_call_start",
                "tool_call_id": chunk.tool.tool_call_id or f"call_{id(chunk)}",
                "tool_name": chunk.tool.tool_name or "unknown",
                "tool_args": chunk.tool.tool_args or {},
            }),
        }
    elif isinstance(chunk, ToolCallCompletedEvent) and chunk.tool:
        result = chunk.tool.result or chunk.content or ""
        display_result = str(result)[:2000] + "..." if len(str(result)) > 2000 else str(result)
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "tool_call_complete",
                "tool_call_id": chunk.tool.tool_call_id or "",
                "tool_name": chunk.tool.tool_name or "unknown",
                "tool_args": chunk.tool.tool_args or {},
                "result": display_result,
            }),
        }
    elif isinstance(chunk, ToolCallErrorEvent):
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "tool_call_error",
                "tool_call_id": chunk.tool.tool_call_id if chunk.tool else "",
                "tool_name": chunk.tool.tool_name if chunk.tool else "unknown",
                "error": chunk.error or "Unknown error",
            }),
        }
    elif isinstance(chunk, (RunContentEvent, IntermediateRunContentEvent)):
        content = chunk.content
        if content and isinstance(content, str):
            response_chunks.append(content)
            yield {
                "event": "message",
                "data": json.dumps({"type": "message", "content": content}),
            }
    # All other event types (RunStarted, RunCompleted, ModelRequest, etc.) are silently ignored
```

Note: The `response_chunks` list is kept for potential future use (e.g., saving full response). The previous code referenced `chunk.content` directly; now we explicitly check event types.

### Success Criteria:

#### Automated Verification:
- [x] Server starts without import errors: `cd backend && make server`
- [ ] Health check responds: `curl http://localhost:8200/health`

#### Manual Verification:
- [ ] Send a chat message that triggers tools — verify SSE events appear in browser DevTools Network tab
- [ ] Verify text content still streams normally
- [ ] Verify no duplicate or missing content

**Implementation Note**: After completing this phase and verifying server starts cleanly, pause for manual confirmation before proceeding to Phase 2.

---

## Phase 2: Pipe-Side Tool Call Rendering

### Overview
Add `<details type="tool_calls">` HTML generation to the pipe so OpenWebUI renders tool call blocks.

### Changes Required:

#### 1. pipe.py — Tool Call HTML Formatter
**File**: `backend/pipe.py`
**Changes**: Add `_format_tool_html()` helper and handle new event types in `_handle_sse_event()`.

Add import at top:
```python
import html as html_lib
```

Add helper method to the `Pipe` class (before `_handle_sse_event`):
```python
@staticmethod
def _format_tool_html(
    tool_call_id: str,
    tool_name: str,
    arguments: dict | str,
    done: bool,
    result: str | None = None,
) -> str:
    """Format a tool call as OpenWebUI <details> HTML."""
    if isinstance(arguments, dict):
        args_str = json.dumps(arguments, indent=2)
    else:
        args_str = str(arguments)

    attrs = (
        f'type="tool_calls" '
        f'done="{str(done).lower()}" '
        f'id="{html_lib.escape(tool_call_id)}" '
        f'name="{html_lib.escape(tool_name)}" '
        f'arguments="{html_lib.escape(args_str)}"'
    )
    if done and result is not None:
        attrs += f' result="{html_lib.escape(str(result))}"'

    summary = "Tool Executed" if done else "Executing..."
    return f"<details {attrs}>\n<summary>{summary}</summary>\n</details>\n\n"
```

Add handling in `_handle_sse_event()` — add these branches after the `elif event_type == "error"` block (before the `except json.JSONDecodeError`):

```python
elif event_type == "tool_call_start":
    tool_html = self._format_tool_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments=event.get("tool_args", {}),
        done=False,
    )
    await emitter({"type": "message", "data": {"content": tool_html}})

elif event_type == "tool_call_complete":
    tool_html = self._format_tool_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments=event.get("tool_args", {}),
        done=True,
        result=event.get("result", ""),
    )
    await emitter({"type": "message", "data": {"content": tool_html}})

elif event_type == "tool_call_error":
    tool_html = self._format_tool_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments={},
        done=True,
        result=f"Error: {event.get('error', 'Unknown')}",
    )
    await emitter({"type": "message", "data": {"content": tool_html}})
```

### Design Decision: Pending + Completed Blocks

Since `__event_emitter__` appends content, both the `done="false"` and `done="true"` blocks will exist in the final message. This means:

1. **During execution**: User sees the spinner block (`done="false"`)
2. **After completion**: User sees both blocks — the spinner AND the result

This may look odd (two blocks per tool call). If testing reveals this is problematic:

**Fix option**: Skip emitting `tool_call_start` entirely. Only emit `tool_call_complete` (with `done="true"`). Users won't see a spinner during execution, but they'll see the result block when done. The "Thinking..." status event already provides feedback that something is happening.

This is noted as a decision to make during testing, not a blocker for implementation.

### Success Criteria:

#### Automated Verification:
- [x] Backend starts: `cd backend && make server`
- [x] Pipe has no syntax errors: `cd backend && .venv/bin/python -c "import pipe"`

#### Manual Verification:
- [ ] Tool calls render as collapsible blocks in OpenWebUI
- [ ] Expanding a completed block shows arguments and result
- [ ] Text content before/after tool calls displays correctly
- [ ] Multiple tool calls in one response each get their own block

**Implementation Note**: After completing this phase, pause for manual testing. If two `<details>` blocks per tool call looks bad, switch to emitting only the completed block (remove the `tool_call_start` handler in the pipe).

---

## Phase 3: Edge Cases and Polish

### Overview
Handle edge cases discovered during testing. This phase is conditional — only needed if Phase 2 testing reveals issues.

### Potential Changes:

#### 1. Pending Block Cleanup (if needed)
If the dual-block issue (pending + completed) looks bad, remove the `tool_call_start` handler from pipe.py. Only emit completed blocks.

#### 2. Large Results Truncation
The server already truncates results >2000 chars. If tool results still render poorly, add client-side truncation in `_format_tool_html()`:

```python
# Truncate result for display
if result and len(result) > 1000:
    result = result[:1000] + "\n... (truncated)"
```

#### 3. Compile Notes Special Handling
`compile_notes` can take several seconds. If the lack of in-progress feedback is noticeable, emit a status event before the tool call:

```python
elif event_type == "tool_call_start":
    tool_name = event.get("tool_name", "")
    # Emit a status for long-running tools
    if tool_name == "compile_notes":
        await emitter({
            "type": "status",
            "data": {"description": "Compiling LaTeX notes...", "done": False},
        })
    # ... existing tool_html emit
```

### Success Criteria:

#### Manual Verification:
- [ ] No visual glitches with tool call blocks
- [ ] Long-running tools (compile_notes) give adequate feedback
- [ ] Error cases display correctly
- [ ] Chat history with tool calls renders properly on page reload

---

## Testing Strategy

### Unit Tests:
Not applicable — the changes are in the streaming plumbing, best tested with integration/manual tests.

### Integration Tests:
- Start backend server
- Send POST to `/chat/stream` with a message that triggers tools
- Verify SSE events include `tool_call_start` and `tool_call_complete` types
- Verify content events still flow correctly between tool calls

### Manual Testing Steps:
1. Open OpenWebUI, select YouLearn pipe
2. Send: `/Lec Today we'll cover integration by parts...` (triggers `create_lecture` + `write_file` + `compile_notes`)
3. Verify tool call blocks appear for each tool invocation
4. Expand each block — verify args and results are readable
5. Send: `/Rev Quiz me on chapter 1` (triggers `read_file`)
6. Verify tool call block appears for file reads
7. Test error: Send a message that causes a tool error (e.g., compile with bad LaTeX)
8. Verify error block renders with error message

## Performance Considerations

- `stream_events=True` yields more events per response (~3 extra per tool call). Negligible overhead.
- Result truncation at 2000 chars prevents large tool outputs from bloating the SSE stream.
- No additional API calls or storage — purely a display improvement.

## References

- Research doc: `thoughts/shared/research/2026-02-06-tool-call-streaming.md`
- OpenWebUI Collapsible component: `openwebui/src/lib/components/common/Collapsible.svelte`
- Agno event types: `agno.agent` (ToolCallStartedEvent, ToolCallCompletedEvent), `agno.run.agent` (ToolCallErrorEvent, IntermediateRunContentEvent)
- OpenWebUI middleware: `openwebui/backend/open_webui/utils/middleware.py:2349` (serialize_content_blocks)
