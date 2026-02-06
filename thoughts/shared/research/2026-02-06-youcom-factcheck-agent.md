---
date: 2026-02-06T11:23:41-08:00
researcher: Ariav Asulin
git_commit: 99f510f
branch: main
repository: YouLearn
topic: "You.com Fact-Check Background Agent for LaTeX Notebook"
tags: [research, you-com, agno, fact-checking, background-agent, latex]
status: complete
last_updated: 2026-02-06
last_updated_by: Ariav Asulin
---

# Research: You.com Fact-Check Background Agent for LaTeX Notebook

**Date**: 2026-02-06T11:23:41-08:00
**Researcher**: Ariav Asulin
**Git Commit**: 99f510f
**Branch**: main
**Repository**: YouLearn

## Research Question

How can we use You.com's Search API to make a simple Agno background agent that fact-checks the notebook periodically and makes updates?

## Summary

This is fully achievable with the existing tech stack. The approach:

1. **Custom `YouComSearchTools` Agno toolkit** wraps the You.com Search API (`GET https://api.ydc-index.io/search` with `X-API-Key` header)
2. **A standalone `Agent`** with `YouComSearchTools` + `NotebookTools` (from the agent-notebook-interaction plan) extracts claims from LaTeX, verifies them, and writes corrections
3. **FastAPI lifespan + `asyncio.create_task()`** runs the agent periodically in the background
4. **Also expose `POST /fact-check/trigger`** for on-demand runs during `/Done` mode

The agent targets high-value fact-checkable content: historical attributions (dates, names), named theorems, cross-references between lectures, and concrete examples. It skips formal proofs and pure mathematics.

---

## Detailed Findings

### 1. You.com Search API

#### Authentication

- Header: `X-API-Key: <your-api-key>`
- Get key from: https://api.you.com/
- $100 free credits for hackathon (~16,000 searches)

#### Endpoints

| Endpoint | Purpose | Best For |
|----------|---------|----------|
| `GET /search` | General web search | Fact-checking claims, finding sources |
| `GET /news` | Recent news search | Not needed for academic content |
| `GET /rag` | RAG-optimized search | AI agent consumption (pre-processed snippets) |

#### Search Endpoint (`/search`)

**URL**: `https://api.ydc-index.io/search`

**Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| `query` | string | Search query (required) |
| `num_web_results` | int | Number of results (default 5, max 10) |
| `country` | string | Country code (e.g., "US") |
| `safesearch` | string | "off", "moderate", "strict" |

**Response shape**:
```json
{
  "hits": [
    {
      "title": "Hermite's Proof of the Transcendence of e",
      "url": "https://en.wikipedia.org/wiki/...",
      "description": "Charles Hermite proved in 1873 that e is transcendental...",
      "snippets": [
        "In 1873, Hermite published a proof showing that e is not algebraic..."
      ]
    }
  ]
}
```

**Key fields per hit**: `title`, `url`, `description`, `snippets[]`

#### RAG Endpoint (`/rag`)

More structured for AI consumption — returns pre-extracted snippets optimized for LLM context. Better than `/search` for our use case since the agent needs to compare claims against search results.

#### Python Usage

```python
import httpx

async def search_you_com(query: str, api_key: str, num_results: int = 5) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.ydc-index.io/search",
            params={"query": query, "num_web_results": num_results},
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()
```

#### Sources
- [You.com API Docs](https://docs.you.com/)
- [Search API Reference](https://docs.you.com/api-reference/search/v1-search)
- [API Portal](https://api.you.com/)
- [Pricing](https://you.com/pricing)

---

### 2. Agno Background Agent Patterns

#### Running Agents Programmatically

Agno agents are plain Python objects. `agent.arun(prompt)` is an async function you can call from anywhere — no chat loop required.

```python
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

agent = Agent(
    model=OpenRouter(id="openai/gpt-4o-mini", api_key="..."),
    tools=[YouComSearchTools(api_key="..."), NotebookTools(class_dir=...)],
    instructions="You are a fact-checking agent for a LaTeX notebook...",
    markdown=True,
    tool_call_limit=20,  # prevent runaway loops
)

response = await agent.arun("Fact-check lecture 5 of the Math-104 notebook.")
print(response.content)  # agent's report
```

#### Custom Toolkit Pattern

Based on Agno's built-in `SerperTools`:

```python
from agno.tools import Toolkit

class YouComSearchTools(Toolkit):
    def __init__(self, api_key: str | None = None, num_results: int = 5):
        self.api_key = api_key or os.getenv("YOULEARN_YOU_API_KEY")
        self.num_results = num_results
        super().__init__(name="you_com_search", tools=[self.search_web])

    def search_web(self, query: str) -> str:
        """Search the web for information to verify a claim.

        Args:
            query: The search query to verify a factual claim.

        Returns:
            JSON string of search results with titles, URLs, and snippets.
        """
        response = httpx.get(
            "https://api.ydc-index.io/search",
            params={"query": query, "num_web_results": self.num_results},
            headers={"X-API-Key": self.api_key},
        )
        response.raise_for_status()
        return json.dumps(response.json())
```

For async support, register an async variant:

```python
class YouComSearchTools(Toolkit):
    def __init__(self, api_key: str, num_results: int = 5):
        self.api_key = api_key
        self.num_results = num_results
        super().__init__(
            name="you_com_search",
            tools=[self.search_web],
            async_tools=[(self.asearch_web, "search_web")],
        )

    def search_web(self, query: str) -> str:
        """Search the web for information to verify a claim.

        Args:
            query: The search query.

        Returns:
            JSON string with titles, URLs, and snippets.
        """
        resp = httpx.get(
            "https://api.ydc-index.io/search",
            params={"query": query, "num_web_results": self.num_results},
            headers={"X-API-Key": self.api_key},
        )
        resp.raise_for_status()
        return json.dumps(resp.json())

    async def asearch_web(self, query: str) -> str:
        """Async web search."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.ydc-index.io/search",
                params={"query": query, "num_web_results": self.num_results},
                headers={"X-API-Key": self.api_key},
            )
            resp.raise_for_status()
            return json.dumps(resp.json())
```

#### FastAPI Integration: Periodic Background Agent

**Recommended: `asyncio.create_task()` on FastAPI lifespan**

```python
import asyncio
from contextlib import asynccontextmanager

async def periodic_fact_check(settings, interval: int = 3600):
    """Run fact-check agent every `interval` seconds."""
    workspace = Path(settings.workspace)
    class_dir = workspace / settings.active_class

    agent = Agent(
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

    while True:
        try:
            response = await agent.arun(
                "Read the lecture files in the notebook. "
                "Extract factual claims (historical dates, attributions, "
                "named theorems, concrete examples). "
                "Search the web to verify each claim. "
                "If you find errors, update the .tex files with corrections. "
                "Report what you checked and what you changed."
            )
            log.info("fact_check_complete", report=response.content[:500])
        except Exception as e:
            log.exception("fact_check_error", error=str(e))
        await asyncio.sleep(interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    task = asyncio.create_task(periodic_fact_check(settings))
    yield
    task.cancel()

app = FastAPI(title="YouLearn Backend", version="0.1.0", lifespan=lifespan)
```

**Also: manual trigger endpoint**

```python
from fastapi import BackgroundTasks

@app.post("/fact-check/trigger")
async def trigger_fact_check(background_tasks: BackgroundTasks):
    """Manually trigger a fact-check run (called during /Done mode)."""
    settings = get_settings()
    background_tasks.add_task(run_single_fact_check, settings)
    return {"status": "fact-check started"}
```

#### Sources
- [Running Agents - Agno](https://docs.agno.com/basics/agents/running-agents)
- [Custom Toolkits - Agno](https://docs.agno.com/basics/tools/creating-tools/toolkits)
- [Async Tools - Agno](https://docs.agno.com/tools/async-tools)
- [Agent Reference - Agno](https://docs.agno.com/reference/agents/agent)
- [SerperTools source](https://github.com/agno-agi/agno/blob/main/libs/agno/agno/tools/serper.py)

---

### 3. What to Fact-Check in the Notebook

Analysis of the Math-104 lectures reveals these categories of fact-checkable content:

#### High Priority: Historical Claims

Found in `notebox` environments and inline prose. These are verifiable factual claims about the real world.

| Claim | Location | Searchable? |
|-------|----------|-------------|
| "Lindemann proved π is transcendental in 1882" | `lec03:463` | Yes — date and attribution |
| "Hermite proved e is transcendental in 1873" | `lec03:463` | Yes — date and attribution |
| "√2 irrational — ancient Greek problem" | `lec01:25` | Yes — historical claim |

#### High Priority: Named Theorems & Attributions

These appear in theorem titles, `\defn{}` usage, and section headers.

| Attribution | Location | Verifiable Aspect |
|-------------|----------|-------------------|
| "Dedekind cuts" | `lec02:25` | Correct attribution to Richard Dedekind |
| "Schwarz Inequality" | `lec02:362` | Should be Cauchy-Schwarz? |
| "Heine-Borel theorem" | `lec05:224` | Correct name for this result |
| "Cantor's diagonal argument" | `lec03:441` | Correct attribution to Georg Cantor |
| "Archimedean property" | `lec02:86` | Correct naming |
| "Weierstrass theorem" | `lec05:259` | Which Weierstrass theorem? |

#### Medium Priority: Cross-References

Claims about what was proved in earlier lectures. Verifiable against the notebook itself.

| Cross-Reference | Location | References |
|-----------------|----------|------------|
| "Recall from Lecture 1 that an equivalence relation..." | `lec03:57` | lec01 content |
| "Previously we showed √2 ∉ Q" | `lec02:143` | lec01:27-43 |
| "Recall the Cantor set from Lecture 2" | `lec03:466` | lec02 content |

#### Medium Priority: Concrete Examples

Properties of specific mathematical objects that can be verified.

| Example Claim | Location |
|---------------|----------|
| "Cantor set consists of ternary expansions with only 0 and 2" | `lec02:253` |
| "R(x) is a non-Archimedean field" | `lec02:95` |
| "Cantor set is closed with C' = C" | `lec04:405` |

#### Low Priority (Skip)

- **Formal proofs**: Provable, not fact-checkable
- **Pure definitions**: Define the framework, not factual claims
- **Calculations**: Mathematical derivations

---

### 4. LaTeX Extraction Strategy

The agent needs to extract claims from `.tex` files. Key patterns to parse:

```python
import re

# Historical claims live in noteboxes
NOTEBOX_RE = re.compile(
    r"\\begin\{notebox\}(.*?)\\end\{notebox\}",
    re.DOTALL,
)

# Attributions in theorem environments
THEOREM_RE = re.compile(
    r"\\begin\{(theorem|lemma|proposition|corollary)\}(\[.*?\])?(.*?)\\end\{\1\}",
    re.DOTALL,
)

# Named definitions
DEFN_RE = re.compile(r"\\defn\{(.*?)\}")

# Lecture summaries
SUMMARY_RE = re.compile(
    r"\\begin\{lecturesummary\}(.*?)\\end\{lecturesummary\}",
    re.DOTALL,
)

# Lecture metadata
METADATA_RE = re.compile(r"\\renewcommand\{\\(\w+)\}\{(.+?)\}")
```

The agent doesn't need to use regex directly — it can read the `.tex` files with `read_file` and use the LLM to identify claims. But having the regex patterns available as a tool for structured extraction would be more reliable.

---

### 5. Recommended Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  FastAPI Server (server.py)               │
│                                                           │
│  ┌──────────────────┐    ┌───────────────────────────┐  │
│  │  Chat Agent       │    │  Fact-Check Agent          │  │
│  │  (user-facing)    │    │  (background)              │  │
│  │                    │    │                             │  │
│  │  Tools:            │    │  Tools:                     │  │
│  │  - NotebookTools   │    │  - YouComSearchTools        │  │
│  │  - YouComSearch    │    │  - NotebookTools            │  │
│  │  - ComposioTools   │    │                             │  │
│  └────────┬──────────┘    └──────────┬───────────────┘  │
│           │                           │                    │
│           ▼                           ▼                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              classes/Math-104/ (shared disk)          │ │
│  │  notes/latex/lec01/ ... lec05/                        │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   You.com API     │
                    │   /search         │
                    │   /rag            │
                    └──────────────────┘
```

Both agents share the same `classes/` workspace on disk. The fact-check agent reads lecture files, searches You.com, and writes corrections. The chat agent reads the corrected files on next interaction.

---

### 6. Implementation Plan (for hackathon)

#### Files to Create

| File | Purpose |
|------|---------|
| `backend/src/youlearn/tools/youcom_tools.py` | `YouComSearchTools` Agno toolkit |
| `backend/src/youlearn/factcheck.py` | Fact-check agent definition + periodic runner |

#### Files to Modify

| File | Change |
|------|--------|
| `backend/src/youlearn/config.py` | Add `you_api_key: str` setting |
| `backend/src/youlearn/server.py` | Add lifespan with periodic fact-check + `/fact-check/trigger` endpoint |
| `backend/pyproject.toml` | No new deps needed (httpx already present) |

#### Implementation Steps

**Step 1: YouComSearchTools (~15 min)**

Create `backend/src/youlearn/tools/youcom_tools.py`:

```python
"""You.com Search API tools for Agno agents."""

from __future__ import annotations

import json
import os

import httpx
from agno.tools import Toolkit


class YouComSearchTools(Toolkit):
    """Search the web using You.com API for fact-checking."""

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

    def search_web(self, query: str) -> str:
        """Search the web to verify a factual claim.

        Use this to fact-check historical dates, theorem attributions,
        named mathematical concepts, and other verifiable claims.

        Args:
            query: A specific search query to verify a claim.
                   Good: "When did Hermite prove e is transcendental"
                   Bad: "math stuff"

        Returns:
            JSON string with search results including titles, URLs,
            and text snippets from web sources.
        """
        resp = httpx.get(
            "https://api.ydc-index.io/search",
            params={"query": query, "num_web_results": self.num_results},
            headers={"X-API-Key": self.api_key},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # Slim down to essential fields
        results = []
        for hit in data.get("hits", []):
            results.append({
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "snippets": hit.get("snippets", [])[:2],
            })
        return json.dumps(results, indent=2)

    async def asearch_web(self, query: str) -> str:
        """Async version of search_web."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://api.ydc-index.io/search",
                params={"query": query, "num_web_results": self.num_results},
                headers={"X-API-Key": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for hit in data.get("hits", []):
                results.append({
                    "title": hit.get("title", ""),
                    "url": hit.get("url", ""),
                    "snippets": hit.get("snippets", [])[:2],
                })
            return json.dumps(results, indent=2)
```

**Step 2: Fact-Check Agent (~20 min)**

Create `backend/src/youlearn/factcheck.py`:

```python
"""Background fact-check agent for the LaTeX notebook."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

from youlearn.config import get_settings
from youlearn.tools.youcom_tools import YouComSearchTools

log = structlog.get_logger()

FACT_CHECK_INSTRUCTIONS = """\
You are a fact-checking agent for a university-level LaTeX notebook on Real Analysis.

## Your Job
1. Read each lecture file using read_file()
2. Identify factual claims that can be verified:
   - Historical attributions (e.g., "Hermite proved e is transcendental in 1873")
   - Named theorems (e.g., "Heine-Borel theorem")
   - Concrete examples (e.g., "the Cantor set consists of ternary expansions with only 0 and 2")
   - Cross-references to other lectures
3. Search the web to verify each claim
4. If a claim is wrong, fix it in the .tex file using write_file()
5. Report what you checked and any corrections made

## What NOT to Fact-Check
- Formal proofs (these are mathematical, not factual)
- Pure definitions (these define the framework)
- Theorem statements (these are proved, not claimed)

## How to Search
- Use specific, targeted queries: "When did Lindemann prove pi transcendental"
- Not vague queries: "math history"
- Search for the specific claim, not the general topic

## How to Correct
- Only change factual errors (wrong dates, wrong names, wrong attributions)
- Do NOT change mathematical content, formatting, or structure
- Do NOT add new content — only fix errors in existing content
- When correcting, preserve the exact LaTeX formatting

## Output
After checking, provide a brief report:
- Claims checked (with lecture and line references)
- Claims verified as correct
- Claims corrected (with before/after)
- Claims that couldn't be verified
"""


def create_fact_check_agent(settings=None):
    """Create a fact-check agent instance."""
    if settings is None:
        settings = get_settings()

    workspace = Path(settings.workspace)
    class_dir = workspace / settings.active_class

    # Import here to avoid circular imports
    from youlearn.tools.notebook_tools import NotebookTools

    return Agent(
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


async def run_single_fact_check(settings=None):
    """Run a single fact-check pass on the notebook."""
    agent = create_fact_check_agent(settings)

    try:
        response = await agent.arun(
            "List the lecture files, then read each one. "
            "Extract and verify factual claims (historical dates, "
            "attributions, named theorems, concrete examples). "
            "Fix any errors you find. Report your findings."
        )
        log.info("fact_check_complete", report=response.content[:500])
        return response.content
    except Exception as e:
        log.exception("fact_check_error", error=str(e))
        return f"Error: {e}"


async def periodic_fact_check(settings=None, interval: int = 3600):
    """Run fact-check agent every `interval` seconds."""
    if settings is None:
        settings = get_settings()

    while True:
        await run_single_fact_check(settings)
        await asyncio.sleep(interval)
```

**Step 3: Wire into Server (~10 min)**

Add to `config.py`:
```python
you_api_key: str = ""
```

Add to `server.py`:
```python
import asyncio
from contextlib import asynccontextmanager
from youlearn.factcheck import periodic_fact_check, run_single_fact_check

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Start periodic fact-checker (every hour)
    task = asyncio.create_task(periodic_fact_check(settings, interval=3600))
    yield
    task.cancel()

app = FastAPI(
    title="YouLearn Backend",
    version="0.1.0",
    lifespan=lifespan,
)

@app.post("/fact-check/trigger")
async def trigger_fact_check(background_tasks: BackgroundTasks):
    """Manually trigger a fact-check run."""
    background_tasks.add_task(run_single_fact_check)
    return {"status": "fact-check started"}
```

**Step 4: /Done Mode Integration (~5 min)**

In the `/Done` mode handler (when implemented), call the trigger endpoint or directly call `run_single_fact_check()`:

```python
# In the /Done mode system prompt, add:
# "After wrapping up, trigger a fact-check by calling the fact_check tool"

# Or in server.py, after /Done response is sent:
if mode.name == "done":
    asyncio.create_task(run_single_fact_check())
```

---

## Code References

- `backend/src/youlearn/server.py:60-74` — Current agent creation (to be extended with fact-check agent)
- `backend/src/youlearn/config.py:14-28` — Settings class (add `you_api_key`)
- `backend/pyproject.toml:6-17` — Dependencies (httpx already present, no additions needed)
- `thoughts/shared/plans/agent-notebook-interaction.md` — NotebookTools plan (fact-check agent reuses these tools)
- `thoughts/build-plan.md:291-311` — YouComSearchTools plan (the fact-check agent builds on this)
- `classes/Math-104/notes/latex/lec03/lec03.tex:462-464` — Example of fact-checkable content (Lindemann/Hermite dates)
- `classes/Math-104/notes/latex/lec02/lec02.tex:362` — Attribution example (Schwarz Inequality)
- `classes/Math-104/notes/latex/lec05/lec05.tex:224` — Named theorem example (Heine-Borel)

## Architecture Documentation

The fact-check agent follows the established Agno patterns in the codebase:
- Uses `OpenRouter` for model access (same as the chat agent in `server.py`)
- Custom `Toolkit` subclass for You.com API (matches pattern in the build plan's `YouComSearchTools`)
- Reuses `NotebookTools` from the agent-notebook-interaction plan for file access
- FastAPI lifespan for background scheduling (standard FastAPI pattern)
- `BackgroundTasks` for on-demand triggering (standard FastAPI pattern)

The existing build plan (`thoughts/build-plan.md`) already includes You.com as Sponsor #2 with the same API structure (`X-API-Key` header, `https://api.ydc-index.io/v1/search`). The fact-check agent extends this plan with a background execution model.

## Historical Context (from thoughts/)

- `thoughts/shared/research/2026-02-05-hackathon-sponsor-analysis.md` — Original sponsor analysis identified You.com as sponsor #2, confirmed $100 free credits (~16,000 searches), documented API endpoints and Python examples
- `thoughts/build-plan.md` — Build plan includes YouComSearchTools as a planned custom toolkit, and mentions /Done mode triggering "background You.com fact-check agent"
- `thoughts/shared/plans/agent-notebook-interaction.md` — NotebookTools plan defines the file read/write tools the fact-check agent reuses

## Related Research

- `thoughts/shared/research/2026-02-05-hackathon-sponsor-analysis.md` — Sponsor analysis with You.com API details
- `thoughts/shared/research/2026-02-06-math104-notebook-structure.md` — Notebook structure analysis

## Open Questions

1. **Rate limiting**: Each fact-check run could use 10-30 searches (one per claim). At ~16,000 searches available, that's ~500-1,600 fact-check runs. Is hourly too frequent? Consider running only on `/Done` trigger or daily.

2. **Claim extraction reliability**: Should the agent extract claims via LLM (flexible but unreliable) or regex (rigid but reliable)? Hybrid approach: regex extracts noteboxes and summaries, LLM identifies claims within those.

3. **Correction safety**: The agent writes directly to .tex files. Should there be a review step? Options:
   - Write corrections to a separate `fact-check-report.md` for human review
   - Write corrections directly but with `% FACT-CHECK: corrected from "X" to "Y"` comments
   - Use git to make corrections reviewable via diff

4. **Scope per run**: Should the agent check all lectures every run, or just the most recent? Checking all 5 lectures uses more API credits but catches errors in older content.

5. **Conflict with chat agent**: If the fact-check agent writes to a .tex file while the chat agent is also writing, there could be conflicts. For the hackathon, this is unlikely (single user, one active session), but worth noting.
