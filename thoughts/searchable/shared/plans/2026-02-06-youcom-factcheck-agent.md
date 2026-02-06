# You.com Fact-Check Agent Implementation Plan

## Overview

Add a You.com-powered fact-check background agent that verifies factual claims in the LaTeX notebook and writes corrections. Triggered on-demand via a `POST /fact-check/trigger` endpoint and automatically after `/Done` mode. Architecture is ready for periodic scheduling later (a single `asyncio.create_task` call in a lifespan hook), but we don't implement periodic scheduling now.

**Depends on**: `agent-notebook-interaction.md` (Status: Implemented) — provides `NotebookTools`, `modes.py`, `context.py`, `config.py` with `active_class`.

**Research**: `thoughts/shared/research/2026-02-06-youcom-factcheck-agent.md`

## Current State Analysis

The backend already has:
- `server.py` — FastAPI app with `/chat/stream` and `/health`, mode detection, `NotebookTools` wired in
- `config.py` — `Settings` with `openrouter_api_key`, `openrouter_model`, `workspace`, `active_class`, `host`, `port`
- `tools/notebook_tools.py` — `NotebookTools(class_dir, backend_url)` with `read_file`, `write_file`, `list_files`, `create_lecture`, `create_session`, `compile_notes`
- `modes.py` — `detect_mode()`, `build_system_prompt()`, `MODE_PROMPTS` dict with `/Done` mode instructions
- `pyproject.toml` — already has `httpx>=0.27.0` (no new deps needed)

Missing:
- `you_api_key` setting in config
- `YouComSearchTools` toolkit
- Fact-check agent module
- `/fact-check/trigger` endpoint
- `/Done` mode auto-triggering the fact-checker

## Desired End State

After implementation:
1. `YOULEARN_YOU_API_KEY` env var is read by config
2. `YouComSearchTools` is a working Agno toolkit that calls `GET https://api.ydc-index.io/search`
3. `POST /fact-check/trigger` runs the fact-check agent as a `BackgroundTasks` job and returns immediately
4. When `/Done` mode is detected, the server auto-fires a fact-check after the chat response completes
5. The fact-check agent reads lecture `.tex` files, extracts factual claims, searches You.com, and writes corrections with `% FACT-CHECK:` comments

### Verification:
- `curl -X POST localhost:8200/fact-check/trigger` returns `{"status": "fact-check started"}` and logs appear
- After a `/Done` session, structlog shows `fact_check_complete` event
- Corrections appear in `.tex` files with `% FACT-CHECK:` comment markers

## What We're NOT Doing

- **Periodic scheduling** — No lifespan loop, no cron. On-demand only. (Architecture is ready: just add `asyncio.create_task(periodic_fact_check(settings))` in a lifespan later.)
- **Separate fact-check report file** — Corrections go directly into `.tex` files with comment markers. No separate `fact-check-report.md`.
- **Regex-based claim extraction** — The agent uses the LLM to identify claims from the `.tex` content. Simpler, more flexible, sufficient for hackathon.
- **Full notebook scan every run** — The agent checks all lectures (there are only 5), but uses `tool_call_limit=30` to prevent runaway API usage.
- **Chat agent also using YouComSearchTools** — That's a separate integration. This plan only covers the background fact-check agent.

---

## Phase 1: YouComSearchTools Agno Toolkit

### Overview
Create a custom Agno toolkit that wraps the You.com Search API. One tool: `search_web`. Both sync and async variants registered.

### Changes Required:

#### 1. Add `you_api_key` to config
**File**: `backend/src/youlearn/config.py`
**Changes**: Add one field to `Settings`

```python
# You.com Search API
you_api_key: str = ""
```

Add after the OpenRouter block (line 19). This reads from `YOULEARN_YOU_API_KEY` env var.

#### 2. Create YouComSearchTools
**File**: `backend/src/youlearn/tools/youcom_tools.py` (new)

```python
"""You.com Search API tools for Agno agents."""

from __future__ import annotations

import json
import os

import httpx
from agno.tools import Toolkit

_API_URL = "https://api.ydc-index.io/search"


class YouComSearchTools(Toolkit):
    """Search the web using You.com API for fact-checking and research."""

    def __init__(
        self,
        api_key: str | None = None,
        num_results: int = 5,
    ):
        self.api_key = api_key or os.getenv("YOULEARN_YOU_API_KEY", "")
        self.num_results = num_results
        super().__init__(
            name="you_com_search",
            tools=[self.search_web],
            async_tools=[(self.asearch_web, "search_web")],
        )

    def _slim_results(self, data: dict) -> str:
        """Extract essential fields from You.com response."""
        results = []
        for hit in data.get("hits", []):
            results.append({
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "snippets": hit.get("snippets", [])[:2],
            })
        return json.dumps(results, indent=2)

    def search_web(self, query: str) -> str:
        """Search the web to verify a factual claim or research a topic.

        Use this to fact-check historical dates, theorem attributions,
        named mathematical concepts, and other verifiable claims.

        Args:
            query: A specific search query to verify a claim.
                   Good: "When did Hermite prove e is transcendental"
                   Good: "Who proved the Heine-Borel theorem"
                   Bad: "math stuff"

        Returns:
            JSON string with search results including titles, URLs,
            and text snippets from web sources.
        """
        resp = httpx.get(
            _API_URL,
            params={"query": query, "num_web_results": self.num_results},
            headers={"X-API-Key": self.api_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        return self._slim_results(resp.json())

    async def asearch_web(self, query: str) -> str:
        """Async version of search_web."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                _API_URL,
                params={"query": query, "num_web_results": self.num_results},
                headers={"X-API-Key": self.api_key},
            )
            resp.raise_for_status()
            return self._slim_results(resp.json())
```

### Success Criteria:

#### Automated Verification:
- [ ] `python -c "from youlearn.tools.youcom_tools import YouComSearchTools; print('OK')"` imports cleanly
- [ ] Module has both `search_web` (sync) and `asearch_web` (async) methods
- [ ] `_slim_results` extracts only `title`, `url`, `snippets` from response

#### Manual Verification:
- [ ] With a valid `YOULEARN_YOU_API_KEY`, calling `search_web("Hermite transcendental e")` returns JSON with search results

---

## Phase 2: Fact-Check Agent Module

### Overview
Create `factcheck.py` with the agent definition, system prompt, and `run_fact_check()` async function. The agent uses `YouComSearchTools` + `NotebookTools` to read lectures, verify claims, and write corrections.

### Changes Required:

#### 1. Create factcheck module
**File**: `backend/src/youlearn/factcheck.py` (new)

```python
"""Background fact-check agent for the LaTeX notebook."""

from __future__ import annotations

from pathlib import Path

import structlog
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from youlearn.config import Settings, get_settings
from youlearn.tools.notebook_tools import NotebookTools
from youlearn.tools.youcom_tools import YouComSearchTools

log = structlog.get_logger()

FACT_CHECK_INSTRUCTIONS = """\
You are a fact-checking agent for a university-level LaTeX notebook on Real Analysis (Math 104).

## Your Job
1. Call list_files("notes/latex") to find all lecture directories
2. For each lecture (lec01, lec02, ...), call read_file("notes/latex/lecXX/lecXX.tex")
3. Identify factual claims that can be verified against web sources:
   - Historical attributions (e.g., "Hermite proved e is transcendental in 1873")
   - Named theorems (e.g., "Heine-Borel theorem", "Cauchy-Schwarz inequality")
   - Dates and people (e.g., "Cantor's diagonal argument", "Dedekind cuts")
   - Concrete examples with verifiable properties
4. For each claim, call search_web() with a specific query to verify it
5. If a claim is WRONG, fix it in the .tex file:
   - Read the full file with read_file()
   - Make the correction
   - Add a LaTeX comment on the line above: % FACT-CHECK: corrected "old" to "new" (source: URL)
   - Write the corrected file with write_file()
6. After checking all lectures, provide a summary report

## What NOT to Fact-Check
- Formal proofs (mathematical derivations, not factual claims)
- Pure definitions (these define the framework, they aren't claims about the world)
- Theorem statements themselves (these are proved, not asserted as historical fact)
- LaTeX formatting or structure

## How to Search
- Use specific, targeted queries: "When did Lindemann prove pi is transcendental"
- Not vague queries: "math history"
- One claim per search query

## How to Correct
- Only change factual errors (wrong dates, wrong names, wrong attributions)
- Do NOT change mathematical content, proofs, or formatting
- Do NOT add new content — only fix errors in existing content
- Preserve the exact LaTeX formatting around the correction
- Always add a % FACT-CHECK comment so the student can see what changed

## Output Format
After checking, provide a brief report:
- Total claims checked
- Claims verified as correct (with lecture references)
- Claims corrected (with before/after and source URL)
- Claims that couldn't be verified (ambiguous or no results)
"""


async def run_fact_check(settings: Settings | None = None) -> str:
    """Run a single fact-check pass on the notebook. Returns the agent's report."""
    if settings is None:
        settings = get_settings()

    workspace = Path(settings.workspace)
    class_dir = workspace / settings.active_class

    agent = Agent(
        name="FactChecker",
        model=OpenRouter(
            id=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
        ),
        tools=[
            YouComSearchTools(api_key=settings.you_api_key),
            NotebookTools(class_dir),
        ],
        instructions=FACT_CHECK_INSTRUCTIONS,
        markdown=True,
        tool_call_limit=30,
    )

    try:
        response = await agent.arun(
            "Fact-check the lecture notes in this notebook. "
            "List the lectures, read each one, identify verifiable factual claims, "
            "search the web to verify them, and fix any errors you find."
        )
        report = response.content or "(no report generated)"
        log.info("fact_check_complete", report=report[:500])
        return report
    except Exception as e:
        log.exception("fact_check_error", error=str(e))
        return f"Fact-check failed: {e}"
```

**Key design decisions:**
- `tool_call_limit=30` prevents runaway loops (5 lectures x ~3 claims each x 2 tool calls per claim = ~30)
- Agent gets `NotebookTools` without `backend_url` param since it doesn't need PDF serving — but `NotebookTools.__init__` has a default for it, so this works fine
- `run_fact_check()` returns the report string so the trigger endpoint can optionally expose it
- No `periodic_fact_check()` function — that's future work (just wrap `run_fact_check` in a `while True` + `asyncio.sleep`)

### Success Criteria:

#### Automated Verification:
- [ ] `python -c "from youlearn.factcheck import run_fact_check; print('OK')"` imports cleanly
- [ ] `FACT_CHECK_INSTRUCTIONS` contains "FACT-CHECK" comment instruction
- [ ] `run_fact_check` creates an Agent with both `YouComSearchTools` and `NotebookTools`

#### Manual Verification:
- [ ] With valid API keys, `asyncio.run(run_fact_check())` produces a report mentioning lecture claims

**Implementation Note**: After completing this phase and verifying imports work, pause for manual confirmation that the agent runs successfully against Math-104 before proceeding.

---

## Phase 3: Server Integration

### Overview
Add `POST /fact-check/trigger` endpoint and auto-trigger after `/Done` mode responses.

### Changes Required:

#### 1. Add trigger endpoint and /Done auto-trigger to server.py
**File**: `backend/src/youlearn/server.py`

Add import at top (after existing imports):
```python
import asyncio

from fastapi import BackgroundTasks
from youlearn.factcheck import run_fact_check
```

Add endpoint after the `/health` endpoint:
```python
@app.post("/fact-check/trigger")
async def trigger_fact_check(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Manually trigger a fact-check run on the notebook.

    The fact-check runs in the background. Check server logs for results.
    """
    settings = get_settings()
    if not settings.you_api_key:
        raise HTTPException(status_code=400, detail="YOULEARN_YOU_API_KEY not configured")
    background_tasks.add_task(run_fact_check, settings)
    return {"status": "fact-check started"}
```

Modify the `generate()` function inside `chat_stream` to auto-trigger after `/Done`:

After the existing `yield {"event": "message", "data": json.dumps({"type": "done"})}` line (line 137), add:

```python
            # Auto-trigger fact-check after /Done mode
            if mode.name == "done" and settings.you_api_key:
                asyncio.create_task(run_fact_check(settings))
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "status",
                        "content": "Fact-check agent started in background...",
                    }),
                }
```

This fires the fact-check as a background task after the `/Done` response stream completes. The status message lets the student know it's happening.

#### 2. Add YOU_API_KEY to .env.example
**File**: `backend/.env.example` (if it exists, add this line)

```
YOULEARN_YOU_API_KEY=
```

### Success Criteria:

#### Automated Verification:
- [ ] Server starts without errors: `cd backend && make server`
- [ ] Health check works: `curl localhost:8200/health`
- [ ] Trigger returns correct response: `curl -X POST localhost:8200/fact-check/trigger` returns `{"status":"fact-check started"}` (or 400 if no API key)
- [ ] No import errors on startup

#### Manual Verification:
- [ ] With valid API keys, `curl -X POST localhost:8200/fact-check/trigger` starts a background fact-check (visible in server logs)
- [ ] After sending `/Done` via OpenWebUI, server logs show `fact_check_complete` event
- [ ] Corrections appear in `.tex` files with `% FACT-CHECK:` comments
- [ ] The student sees "Fact-check agent started in background..." status in chat

---

## Testing Strategy

### Manual Testing Steps:
1. Set `YOULEARN_YOU_API_KEY` in `.env`
2. Start server: `cd backend && make server`
3. `curl -X POST localhost:8200/fact-check/trigger` — verify 200 response and log output
4. Check `.tex` files for `% FACT-CHECK:` comments after run completes
5. Send `/Done` through OpenWebUI pipe, verify fact-check auto-triggers in logs

### Edge Cases:
| Scenario | Expected Behavior |
|----------|-------------------|
| No `YOULEARN_YOU_API_KEY` set | `/fact-check/trigger` returns 400; `/Done` skips fact-check silently |
| You.com API returns error (rate limit, auth) | `fact_check_error` logged, no crash, chat continues normally |
| Agent hits `tool_call_limit=30` | Agent stops and returns partial report |
| No lecture files exist | Agent reports "no lectures found" |
| `.tex` file has no factual claims | Agent reports "no claims to verify" |

## Performance Considerations

- Each fact-check run uses ~10-30 You.com API calls (~16,000 available with $100 credits)
- Agent uses `gpt-4o-mini` via OpenRouter (cheap, fast) — ~$0.01-0.03 per run
- Background execution means zero impact on chat latency
- `tool_call_limit=30` prevents runaway API spend

## Future: Adding Periodic Scheduling

When ready to add periodic scheduling, add to `server.py`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    task = None
    if settings.you_api_key:
        async def periodic():
            while True:
                await run_fact_check(settings)
                await asyncio.sleep(3600)  # hourly
        task = asyncio.create_task(periodic())
    yield
    if task:
        task.cancel()

app = FastAPI(title="YouLearn Backend", version="0.1.0", lifespan=lifespan)
```

This is NOT part of the current plan — just documented for later.

## References

- Research: `thoughts/shared/research/2026-02-06-youcom-factcheck-agent.md`
- Dependency plan: `thoughts/shared/plans/agent-notebook-interaction.md` (Status: Implemented)
- Build plan: `thoughts/build-plan.md`
- You.com API docs: https://docs.you.com/api-reference/search/v1-search
- Agno Toolkit API: https://github.com/agno-agi/agno/blob/main/libs/agno/agno/tools/toolkit.py
- Current server: `backend/src/youlearn/server.py`
- Current config: `backend/src/youlearn/config.py`
- NotebookTools: `backend/src/youlearn/tools/notebook_tools.py`
