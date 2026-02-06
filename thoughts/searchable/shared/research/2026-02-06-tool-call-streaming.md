# Tool Call Streaming: Agno + OpenWebUI Implementation Research

**Date**: 2026-02-06
**Context**: YouLab uses Agno agents streamed through a Ralph server to OpenWebUI via a pipe. Tool calls currently execute silently. This document researches how to make tool calls visible in the UI.

---

## Table of Contents

1. [Current Implementation (What Works, What Doesn't)](#1-current-implementation)
2. [Agno's Tool Call Streaming Capabilities](#2-agno-tool-call-streaming)
3. [OpenWebUI's Expected Format for Tool Calls](#3-openwebui-tool-call-format)
4. [OpenAI-Compatible Tool Call Streaming Format](#4-openai-streaming-format)
5. [Implementation Approach](#5-implementation-approach)
6. [Code Examples](#6-code-examples)

---

## 1. Current Implementation

### What Works

- **Text streaming**: The Ralph server streams text tokens from the Agno agent to the OpenWebUI pipe via SSE. Each content chunk arrives in real-time.
- **Status events**: A "Thinking..." status is shown while the agent processes.
- **Error handling**: Errors during streaming are caught and displayed to the user.
- **Honcho persistence**: User and assistant messages are saved asynchronously.

### What Doesn't Work

- **Tool calls are invisible**: When the agent invokes tools (MemoryBlockTools, FileTools, ShellTools, HonchoTools, LaTeXTools), the user sees nothing. The stream effectively pauses while tools execute.
- **No progress indication**: Long-running tools like LaTeX compilation give zero feedback.
- **No tool call metadata**: The user can't see what tools were called, with what arguments, or what they returned.

### Current Data Flow

```
OpenWebUI → Pipe (pipe.py) → Ralph Server (server.py) → Agno Agent
                                                            │
                                                      agent.arun(stream=True)
                                                            │
                                                      yields RunContentEvent only
                                                      (tool calls happen silently)
                                                            │
                                                      SSE: {"type":"message","content":"..."}
```

### Key Code: server.py (lines 343-359)

```python
async for chunk in agent.arun(
    prompt,
    stream=True,
    user_id=request.user_id,
    session_id=request.chat_id,
    dependencies={"user_id": request.user_id, "chat_id": request.chat_id},
):
    content = chunk.content
    if content:
        response_chunks.append(content)
        yield {
            "event": "message",
            "data": json.dumps({"type": "message", "content": content}),
        }
```

**Problem**: Only `chunk.content` is checked. Tool call events are not yielded because `stream_events=True` is not passed to `agent.arun()`.

### Key Code: pipe.py (lines 132-167)

The pipe only handles 4 event types: `status`, `message`, `done`, `error`. There is no handler for tool call events.

---

## 2. Agno Tool Call Streaming Capabilities

### The Key Parameter: `stream_events=True`

Agno's `agent.arun()` accepts two streaming parameters:
- `stream=True` — enables token-by-token streaming (yields `RunContentEvent` objects)
- `stream_events=True` — enables full lifecycle events including tool calls

With `stream_events=True`, the async iterator yields typed dataclass events:

### Tool Call Event Types

| Event | When Emitted | Key Fields |
|---|---|---|
| `ToolCallStartedEvent` | Before tool executes | `tool.tool_name`, `tool.tool_args`, `tool.tool_call_id` |
| `ToolCallCompletedEvent` | After tool succeeds | `tool.tool_name`, `tool.result`, `content`, `images` |
| `ToolCallErrorEvent` | If tool fails | `tool.tool_name`, `error` |
| `ToolCallArgsDeltaEvent` | During argument streaming (newer) | `tool_call_name`, `arguments_delta` |

### ToolExecution Object

```python
@dataclass
class ToolExecution:
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_call_error: Optional[bool] = None
    result: Optional[str] = None
    metrics: Optional[Metrics] = None
    requires_confirmation: Optional[bool] = None  # HITL
    confirmed: Optional[bool] = None
```

### Full Event Type List (RunOutputEvent union)

All events inherit from `BaseAgentRunEvent`:
- **Lifecycle**: `RunStartedEvent`, `RunCompletedEvent`, `RunErrorEvent`, `RunCancelledEvent`, `RunPausedEvent`, `RunContinuedEvent`
- **Content**: `RunContentEvent`, `IntermediateRunContentEvent`, `RunContentCompletedEvent`
- **Tool Calls**: `ToolCallStartedEvent`, `ToolCallCompletedEvent`, `ToolCallErrorEvent`
- **Reasoning**: `ReasoningStartedEvent`, `ReasoningStepEvent`, `ReasoningContentDeltaEvent`, `ReasoningCompletedEvent`
- **Model**: `ModelRequestStartedEvent`, `ModelRequestCompletedEvent`
- **Hooks**: `PreHookStartedEvent/CompletedEvent`, `PostHookStartedEvent/CompletedEvent`
- **Memory/Session**: `MemoryUpdateStartedEvent/CompletedEvent`, `SessionSummaryStartedEvent/CompletedEvent`

### Agno Internal Flow with Tool Calls

When `agent.arun(stream=True, stream_events=True)`:
1. Agno streams model output tokens as `RunContentEvent`
2. When model returns `finish_reason: "tool_calls"`, Agno accumulates tool call data
3. Yields `ToolCallStartedEvent` with tool name and arguments
4. Executes the tool synchronously
5. Yields `ToolCallCompletedEvent` with result
6. Sends tool result back to model as a `tool` message
7. Streams model's next response as more `RunContentEvent` chunks
8. Repeats until model returns `finish_reason: "stop"`

---

## 3. OpenWebUI Tool Call Format

### HTML `<details>` Protocol

OpenWebUI displays tool calls using HTML `<details>` elements embedded in message content. The key Svelte component is `Collapsible.svelte` which detects `type="tool_calls"` on details elements.

### Format: Tool Call In Progress

```html
<details type="tool_calls" done="false" id="{tool_call_id}" name="{tool_name}" arguments="{html_escaped_json_arguments}">
<summary>Executing...</summary>
</details>
```

### Format: Tool Call Completed

```html
<details type="tool_calls" done="true" id="{tool_call_id}" name="{tool_name}" arguments="{html_escaped_json_arguments}" result="{html_escaped_json_result}">
<summary>Tool Executed</summary>
</details>
```

### Optional Attributes

- `files="{html_escaped_json_array}"` — Array of file objects (images, PDFs) produced by the tool
- `embeds="{html_escaped_json_array}"` — Array of HTML embed objects for interactive content

### Frontend Rendering Behavior

The `Collapsible.svelte` component (lines 92-219):
- When `done !== "true"`: Shows a **spinner** animation with "Executing **{NAME}**..." text, plus a shimmer CSS effect
- When `done === "true"`: Shows "View Result from **{NAME}**" with an expand arrow
- When expanded: Renders arguments and result as JSON code blocks in markdown
- If `files` contains images: Renders them inline below the result

### How Events Reach the Frontend

OpenWebUI's backend middleware (`utils/middleware.py`) serializes content blocks to HTML via `serialize_content_blocks()`. The pipe communicates via `__event_emitter__` callback:

```python
# Status events
await __event_emitter__({"type": "status", "data": {"description": "...", "done": False}})

# Message content (can include HTML)
await __event_emitter__({"type": "message", "data": {"content": "<details ...>...</details>"}})

# Completion
await __event_emitter__({"type": "status", "data": {"description": "Complete", "done": True}})
```

**The content field can contain HTML**, including `<details>` tags. OpenWebUI's markdown renderer passes through HTML elements, and `Collapsible.svelte` picks up `<details>` with `type="tool_calls"`.

### Content Block Internal Structure (Middleware)

The middleware maintains typed content blocks:

```python
content_blocks = [
    {"type": "text", "content": "Let me search for that..."},
    {"type": "tool_calls", "content": [tool_calls_array], "results": [results_array]},
    {"type": "text", "content": "Based on the results..."},
]
```

`serialize_content_blocks()` converts these to a single HTML string.

---

## 4. OpenAI-Compatible Tool Call Streaming Format

### SSE Event Sequence

OpenAI streams tool calls as `chat.completion.chunk` objects with `delta.tool_calls`:

**Chunk 1 — Role assignment:**
```json
{"choices":[{"index":0,"delta":{"role":"assistant","content":null},"finish_reason":null}]}
```

**Chunk 2 — Tool call initiated (id + name + empty args):**
```json
{"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_abc","type":"function","function":{"name":"get_weather","arguments":""}}]},"finish_reason":null}]}
```

**Chunks 3-N — Argument fragments:**
```json
{"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"location\":"}}]},"finish_reason":null}]}
```

**Final chunk — finish_reason:**
```json
{"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}
```

### Key Rules

1. First chunk for a tool call has `id`, `type`, and `function.name`
2. Subsequent chunks only have `index` and `function.arguments` (a JSON fragment)
3. Arguments must be concatenated client-side
4. `finish_reason: "tool_calls"` signals tool execution needed
5. For parallel tool calls, chunks interleave with different `index` values

### Relevance

This format is what OpenWebUI's middleware natively handles when talking to OpenAI-compatible backends. However, since our Ralph pipe uses a **custom SSE protocol** (not OpenAI chat completions format), we need to translate Agno events into OpenWebUI's `<details>` HTML format ourselves.

---

## 5. Implementation Approach

### Architecture Decision: Where to Handle Tool Call Events

**Option A: Ralph Server emits tool call SSE events → Pipe converts to OpenWebUI format**
- Server adds new event types: `tool_call_start`, `tool_call_complete`, `tool_call_error`
- Pipe converts these to `<details>` HTML and emits via `__event_emitter__`
- Pros: Clean separation, server stays format-agnostic
- Cons: Two files to modify, more SSE event types to maintain

**Option B: Ralph Server emits pre-formatted `<details>` HTML as message content**
- Server generates the HTML directly in the SSE stream
- Pipe passes through unchanged (already handles `type: "message"`)
- Pros: No pipe changes needed, simpler
- Cons: Server becomes coupled to OpenWebUI's display format

**Option C: Ralph Server mimics OpenAI streaming format**
- Server emits `chat.completion.chunk` objects with `delta.tool_calls`
- Pipe parses OpenAI format and converts
- Pros: Standard format
- Cons: Over-engineering, adds complexity without clear benefit

### Recommended: Option A (Clean SSE Protocol)

This preserves the clean separation between server and pipe, and allows other clients to consume tool call events in their own way.

### Step-by-Step Implementation

#### Step 1: Enable `stream_events=True` in server.py

Change the `agent.arun()` call:

```python
async for chunk in agent.arun(
    prompt,
    stream=True,
    stream_events=True,  # <-- ADD THIS
    user_id=request.user_id,
    session_id=request.chat_id,
    dependencies={...},
):
```

#### Step 2: Handle Tool Call Events in server.py

Add event type detection in the streaming loop:

```python
from agno.run.agent import (
    RunContentEvent,
    ToolCallStartedEvent,
    ToolCallCompletedEvent,
    ToolCallErrorEvent,
    RunCompletedEvent,
)

async for chunk in agent.arun(prompt, stream=True, stream_events=True, ...):
    if isinstance(chunk, ToolCallStartedEvent) and chunk.tool:
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "tool_call_start",
                "tool_call_id": chunk.tool.tool_call_id or "",
                "tool_name": chunk.tool.tool_name or "",
                "tool_args": chunk.tool.tool_args or {},
            }),
        }
    elif isinstance(chunk, ToolCallCompletedEvent) and chunk.tool:
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "tool_call_complete",
                "tool_call_id": chunk.tool.tool_call_id or "",
                "tool_name": chunk.tool.tool_name or "",
                "result": chunk.tool.result or "",
            }),
        }
    elif isinstance(chunk, ToolCallErrorEvent) and chunk.tool:
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "tool_call_error",
                "tool_call_id": chunk.tool.tool_call_id or "",
                "tool_name": chunk.tool.tool_name or "",
                "error": chunk.error or "Unknown error",
            }),
        }
    elif hasattr(chunk, "content") and chunk.content:
        response_chunks.append(chunk.content)
        yield {
            "event": "message",
            "data": json.dumps({"type": "message", "content": chunk.content}),
        }
```

#### Step 3: Handle Tool Call Events in pipe.py

Add tool call handling to `_handle_sse_event()`:

```python
import html

def _format_tool_call_html(
    tool_call_id: str,
    tool_name: str,
    arguments: dict,
    done: bool,
    result: str | None = None,
) -> str:
    """Format tool call as OpenWebUI <details> HTML."""
    args_json = html.escape(json.dumps(arguments, indent=2))
    attrs = (
        f'type="tool_calls" done="{str(done).lower()}" '
        f'id="{html.escape(tool_call_id)}" '
        f'name="{html.escape(tool_name)}" '
        f'arguments="{args_json}"'
    )
    if done and result is not None:
        result_escaped = html.escape(json.dumps(result) if not isinstance(result, str) else result)
        attrs += f' result="{result_escaped}"'

    summary = "Tool Executed" if done else "Executing..."
    return f"<details {attrs}>\n<summary>{summary}</summary>\n</details>"
```

In `_handle_sse_event()`, add handlers:

```python
elif event_type == "tool_call_start":
    tool_html = _format_tool_call_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments=event.get("tool_args", {}),
        done=False,
    )
    await emitter({"type": "message", "data": {"content": tool_html}})

elif event_type == "tool_call_complete":
    tool_html = _format_tool_call_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments={},  # Args already shown in start event
        done=True,
        result=event.get("result", ""),
    )
    await emitter({"type": "message", "data": {"content": tool_html}})

elif event_type == "tool_call_error":
    tool_html = _format_tool_call_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments={},
        done=True,
        result=f"Error: {event.get('error', 'Unknown')}",
    )
    await emitter({"type": "message", "data": {"content": tool_html}})
```

#### Step 4: Handle Content Block Ordering

OpenWebUI expects tool calls to be embedded in the content stream. The pipe needs to track state to properly interleave text and tool call HTML:

```python
# In pipe.__init__ or as instance variable
self._pending_tool_calls: dict[str, dict] = {}

# In _handle_sse_event for tool_call_start:
self._pending_tool_calls[event["tool_call_id"]] = {
    "name": event["tool_name"],
    "args": event["tool_args"],
}
# Emit pending HTML

# In _handle_sse_event for tool_call_complete:
pending = self._pending_tool_calls.pop(event["tool_call_id"], {})
# Emit completed HTML with full args from pending + result
```

### Edge Cases to Handle

1. **Multiple sequential tool calls**: Agent may call several tools before responding. Each needs its own `<details>` block.
2. **Parallel tool calls**: If the model requests multiple tools at once, Agno may execute them sequentially but the events will be interleaved.
3. **Tool calls with large results**: Results from FileTools or ShellTools can be large. Consider truncating in the display.
4. **RunOutput final event**: The last event in the stream is a `RunOutput` object (not a dataclass event). Check for it to avoid errors.
5. **Intermediate content**: Between tool calls, the model may emit `IntermediateRunContentEvent`. These should be treated as regular content.

### Verification Strategy

1. Start Ralph server with the changes
2. Open OpenWebUI chat
3. Ask the agent to do something that triggers a tool (e.g., "List my memory blocks")
4. Verify: Tool call appears with spinner during execution
5. Verify: Tool call shows "View Result" when complete
6. Verify: Text content before/after tool calls displays correctly
7. Test error case: Ask for something that will fail (e.g., read nonexistent file)

---

## 6. Code Examples

### Complete SSE Event Flow (After Implementation)

A user asks: "What's in my student profile?"

```
SSE: {"type": "status", "content": "Thinking..."}
SSE: {"type": "message", "content": "Let me check your "}
SSE: {"type": "message", "content": "student profile."}
SSE: {"type": "tool_call_start", "tool_call_id": "call_abc", "tool_name": "list_memory_blocks", "tool_args": {}}
SSE: {"type": "tool_call_complete", "tool_call_id": "call_abc", "tool_name": "list_memory_blocks", "result": "[{\"label\": \"student\", \"title\": \"Student Profile\"}]"}
SSE: {"type": "tool_call_start", "tool_call_id": "call_def", "tool_name": "read_memory_block", "tool_args": {"label": "student"}}
SSE: {"type": "tool_call_complete", "tool_call_id": "call_def", "tool_name": "read_memory_block", "result": "## About Me\n\nI'm studying CS..."}
SSE: {"type": "message", "content": "Your student profile "}
SSE: {"type": "message", "content": "shows that you're studying CS..."}
SSE: {"type": "done"}
```

### What the User Sees in OpenWebUI

```
Let me check your student profile.

[Spinner] Executing list_memory_blocks...     ← collapses when done
[Spinner] Executing read_memory_block...      ← collapses when done

Your student profile shows that you're studying CS...
```

After completion:

```
Let me check your student profile.

[▶] View Result from list_memory_blocks       ← expandable
[▶] View Result from read_memory_block        ← expandable

Your student profile shows that you're studying CS...
```

### Minimal Working Example (server.py changes only)

```python
from agno.run.agent import (
    ToolCallStartedEvent,
    ToolCallCompletedEvent,
    ToolCallErrorEvent,
)

# In generate():
async for chunk in agent.arun(
    prompt,
    stream=True,
    stream_events=True,
    user_id=request.user_id,
    session_id=request.chat_id,
    dependencies={"user_id": request.user_id, "chat_id": request.chat_id},
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
        # Truncate very long results for display
        display_result = result[:2000] + "..." if len(str(result)) > 2000 else result
        yield {
            "event": "message",
            "data": json.dumps({
                "type": "tool_call_complete",
                "tool_call_id": chunk.tool.tool_call_id or "",
                "tool_name": chunk.tool.tool_name or "unknown",
                "result": str(display_result),
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
    else:
        # Regular content or other events
        content = getattr(chunk, "content", None)
        if content and isinstance(content, str):
            response_chunks.append(content)
            yield {
                "event": "message",
                "data": json.dumps({"type": "message", "content": content}),
            }
```

### Minimal Working Example (pipe.py changes only)

```python
import html as html_lib

def _format_tool_html(
    tool_call_id: str,
    tool_name: str,
    arguments: dict | str,
    done: bool,
    result: str | None = None,
) -> str:
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
    return f"<details {attrs}>\n<summary>{summary}</summary>\n</details>"


# In _handle_sse_event(), add before the json.JSONDecodeError except:
elif event_type == "tool_call_start":
    tool_html = _format_tool_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments=event.get("tool_args", {}),
        done=False,
    )
    await emitter({"type": "message", "data": {"content": tool_html}})

elif event_type == "tool_call_complete":
    tool_html = _format_tool_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments=event.get("tool_args", {}),
        done=True,
        result=event.get("result", ""),
    )
    await emitter({"type": "message", "data": {"content": tool_html}})

elif event_type == "tool_call_error":
    tool_html = _format_tool_html(
        tool_call_id=event.get("tool_call_id", ""),
        tool_name=event.get("tool_name", ""),
        arguments={},
        done=True,
        result=f"Error: {event.get('error', 'Unknown')}",
    )
    await emitter({"type": "message", "data": {"content": tool_html}})
```

---

## Open Questions

1. **Does OpenWebUI properly update `<details>` blocks?** The pending state (`done="false"`) is emitted first, then the completed state (`done="true"`). Does OpenWebUI replace the pending block or append a new one? Need to test whether the `id` attribute is used for matching/replacing.

2. **Content accumulation in pipe**: The pipe currently emits each chunk independently. For tool calls, we need the completed HTML to replace the pending HTML. This may require the pipe to track tool call state and emit a "replace" rather than "append" for the completed version.

3. **`ToolCallArgsDeltaEvent` availability**: This newer event enables streaming arguments as they arrive. Worth testing with OpenRouter to see if it works.

4. **RunOutput as final event**: The last item yielded by `agent.arun()` is a `RunOutput` (not a dataclass event). Need to handle this gracefully — it has `.content` for any final text.

5. **`strip_agno_fields()` compatibility**: Does adding `stream_events=True` change how Agno formats tool definitions for the model? Need to verify the existing Mistral workaround still works.

6. **Intermediate content events**: Between tool calls, the model may emit `IntermediateRunContentEvent`. These should display as regular text but need testing.

7. **How does OpenWebUI handle the `<details>` update cycle?** The middleware internally uses `serialize_content_blocks()` which rebuilds the entire message content each time. In our pipe, we're streaming incrementally. We may need to emit the full accumulated content (all text + all tool blocks) on each update rather than just the delta.
