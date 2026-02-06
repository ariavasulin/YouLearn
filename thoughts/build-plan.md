# YouLearn Build Plan — Continual Learning Hackathon

**Date**: 2026-02-06
**Hackathon**: Continual Learning (5 hours)
**Theme**: "Build agents that don't just think—they act. Create autonomous, self-improving AI agents."
**Team**: Ariav Asulin
**Sponsors (Required 3)**: Render, You.com, Composio

---

## The Pitch

**YouLearn** is a self-improving AI study companion that manages your course knowledge so you can focus on learning, not organizing. Upload a syllabus, attend lectures, work on assignments — YouLearn maintains a living, structured notebook per class that grows smarter with every interaction.

**Problem**: Students waste time managing AI context — copy-pasting notes, re-explaining course material, losing conversation history. Context engineering shouldn't be the student's job.

**Solution**: A per-class notebook (structured document corpus) that the AI agent reads, writes, and improves continuously. The student just talks; the notebook evolves.

**"Continual Learning" angle**: The agent literally learns continuously — each lecture adds to its knowledge, each study session refines its understanding, background processes enrich content with research and cross-references.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          Render (Sponsor #1)                      │
│                                                                    │
│  ┌──────────────┐    Pipe (SSE)    ┌──────────────────────────┐  │
│  │  OpenWebUI    │ ──────────────▶ │  YouLearn Backend         │  │
│  │  (Frontend +  │                 │  FastAPI + Agno Agent     │  │
│  │   Auth/Chat)  │ ◀────────────── │                          │  │
│  │  Port 8080    │                 │  Tools:                   │  │
│  └──────────────┘                 │   • NotebookTools (R/W)   │  │
│                                    │   • LaTeXTools (PDF)      │  │
│                                    │   • YouComSearch (research)│  │
│                                    │   • ComposioTools (cal)   │  │
│                                    │  Port 8200                │  │
│                                    └──────────────────────────┘  │
│                                              │                    │
│                                    ┌─────────┴─────────┐        │
│                                    │   notebooks/       │        │
│                                    │   (disk storage)   │        │
│                                    └───────────────────┘        │
└──────────────────────────────────────────────────────────────────┘
                    │                              │
         ┌──────────┘                    ┌────────┘
         ▼                               ▼
  ┌──────────────┐                ┌──────────────┐
  │  You.com API │                │   Composio   │
  │  (Sponsor #2)│                │  (Sponsor #3)│
  │  Research &  │                │  Google Cal  │
  │  Citations   │                │  Scheduling  │
  └──────────────┘                └──────────────┘
```

---

## Notebook File Structure

Each class gets a directory under `notebooks/{user_id}/{class_slug}/`:

```
notebooks/
  {user_id}/
    {class_slug}/
      notebook.json          # Metadata: class name, created date, last updated
      syllabus.md            # Course overview, objectives, calendar
      glossary.md            # Key terms and definitions (continuously updated)
      resources.md           # Links, references, supplementary material
      lectures/
        01-intro.md          # Lecture notes (numbered, one per lecture)
        02-data-structures.md
        ...
      assignments/
        hw1-sorting.md       # Assignment details + progress + solutions
        hw2-graphs.md
        ...
      sessions/
        2026-02-06-lec.md    # Session logs (date + mode)
        2026-02-06-work.md
        ...
```

### Why Markdown (Not LaTeX/JSON)

- **Agent reads/writes naturally** — LLMs are great at markdown
- **FileTools works out of the box** — no custom parsing needed
- **LaTeX only for output** — when student wants a PDF, agent reads markdown and generates LaTeX
- **Human-readable** — can be inspected, edited, version-controlled
- **Fast** — no compilation step for reading/updating

### notebook.json Schema

```json
{
  "class_name": "CS 301 - Algorithms",
  "class_slug": "cs301-algorithms",
  "created": "2026-02-06T10:00:00Z",
  "last_updated": "2026-02-06T15:30:00Z",
  "lecture_count": 5,
  "assignment_count": 2,
  "session_count": 8
}
```

### Markdown Section Templates

**Lecture note template** (`lectures/XX-topic.md`):
```markdown
# Lecture {N}: {Title}
**Date**: {date}
**Topics**: {comma-separated topics}

## Overview
{1-2 paragraph summary}

## Key Concepts

### {Concept 1}
{explanation}

### {Concept 2}
{explanation}

## Examples
{worked examples from lecture}

## Connections to Previous Material
{cross-references to other lectures/concepts}

## Sources
{citations added by You.com research}
```

**Assignment template** (`assignments/XX-name.md`):
```markdown
# Assignment: {Name}
**Due**: {date}
**Status**: not-started | in-progress | completed
**Grade**: {if available}

## Description
{assignment details}

## Approach
{student's planned approach, updated during work sessions}

## Solution Progress
{incremental work, code snippets, answers}

## Key Concepts Used
{links to relevant lecture notes and glossary terms}
```

---

## Context Loading Per Mode

The key insight: **each mode loads different slices of the notebook into the system prompt**. This is the core context engineering.

### /Lec — Live Lecture Mode

**Purpose**: Student is in a lecture. Agent listens and organizes content.

**Context loaded**:
```
System prompt (mode instructions)
+ syllabus.md (know the course structure)
+ glossary.md (know existing terminology)
+ Last 2 lecture notes (continuity)
+ notebook.json (metadata)
```

**Behavior**:
- Agent takes raw input (student typing what professor says, pasting slides, etc.)
- Organizes into structured lecture note format
- Creates new `lectures/XX-topic.md` file
- Identifies new glossary terms → queues for /End update
- Cross-references with previous lectures

**Token budget**: ~8K context for notebook, rest for conversation

### /Rev — Review Mode

**Purpose**: Student wants to study, quiz themselves, review material.

**Context loaded**:
```
System prompt (mode instructions)
+ syllabus.md
+ glossary.md
+ ALL lecture notes (or smart subset if too large)
+ Relevant assignment notes
+ resources.md
```

**Behavior**:
- Quiz-style interactions ("What is the time complexity of merge sort?")
- Concept connections ("How does this relate to what we learned in Lecture 3?")
- Generate summary PDFs via LaTeX
- Research topics via You.com for deeper understanding
- Suggest review schedule via Composio (Google Calendar)

**Token budget**: Up to 32K context for full notebook, may need to summarize older lectures

### /Work — Active Work Mode

**Purpose**: Student is working on an assignment.

**Context loaded**:
```
System prompt (mode instructions)
+ The specific assignment file
+ Relevant lecture notes (auto-detected from assignment topics)
+ glossary.md
+ notebook.json
```

**Behavior**:
- Help with specific problems without giving away answers
- Track progress in assignment file
- Suggest relevant lecture sections to review
- Upload assignment PDF → extract and store in assignments/

**Token budget**: ~4K assignment + ~8K relevant lectures

### /End — Session End

**Purpose**: Wrap up, trigger background updates.

**Context loaded**:
```
System prompt (mode instructions)
+ Current session transcript (from OpenWebUI)
+ notebook.json
+ glossary.md (for updates)
+ resources.md (for updates)
```

**Behavior** (all done inline, no actual background workers for hackathon):
1. Summarize session → write to `sessions/YYYY-MM-DD-mode.md`
2. Extract new glossary terms → append to `glossary.md`
3. Extract any URLs/resources mentioned → append to `resources.md`
4. Update `notebook.json` metadata
5. Cross-reference new content with existing notes
6. (Composio) Schedule next review session on Google Calendar based on spaced repetition

---

## Tools

### 1. NotebookTools (Custom Agno Toolkit)

Wraps FileTools with notebook-aware operations. The agent uses these to read/write notebook files.

```python
class NotebookTools(Toolkit):
    """Read and write notebook files with path resolution."""

    def __init__(self, notebooks_dir: Path):
        self.notebooks_dir = notebooks_dir
        tools = [
            self.read_notebook_file,
            self.write_notebook_file,
            self.list_notebook_files,
            self.get_notebook_context,  # Smart context loader
        ]
        super().__init__(name="notebook_tools", tools=tools)

    def read_notebook_file(self, class_slug: str, path: str) -> str:
        """Read a file from the notebook. Path is relative to the class directory.
        Examples: 'syllabus.md', 'lectures/01-intro.md', 'glossary.md'"""

    def write_notebook_file(self, class_slug: str, path: str, content: str) -> str:
        """Write/update a file in the notebook."""

    def list_notebook_files(self, class_slug: str, subdir: str = "") -> str:
        """List files in the notebook, optionally in a subdirectory."""

    def get_notebook_context(self, class_slug: str, mode: str) -> str:
        """Load the right notebook context for the current mode.
        mode: 'lec', 'rev', 'work', 'end'
        Returns concatenated notebook content appropriate for the mode."""
```

### 2. LaTeXTools (Copy from YouLab)

100% reusable from `/Users/ariasulin/Git/YouLab/src/ralph/tools/latex_tools.py`. Produces PDF artifacts in OpenWebUI.

### 3. YouComSearchTools (Custom Agno Toolkit — Sponsor #2)

```python
class YouComSearchTools(Toolkit):
    """Search the web for research and citations using You.com API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        tools = [self.search_web, self.research_topic]
        super().__init__(name="youcom_search", tools=tools)

    def search_web(self, query: str, count: int = 5) -> str:
        """Search the web for information on a topic.
        Returns results with titles, URLs, and snippets for citations."""
        # GET https://api.ydc-index.io/v1/search
        # Headers: X-API-Key

    def research_topic(self, topic: str) -> str:
        """Deep research on a topic. Searches web + news, returns
        comprehensive results with citations for enriching lecture notes."""
```

**API Details**:
- Endpoint: `https://api.ydc-index.io/v1/search`
- Auth: `X-API-Key` header
- $100 free credits (~16,000 searches)
- Response includes `results.web[].{title, url, description, snippets}`

### 4. ComposioTools (Agno Integration — Sponsor #3)

```python
from composio_agno import ComposioToolSet, Action

toolset = ComposioToolSet()
composio_tools = toolset.get_actions(actions=[
    Action.GOOGLECALENDAR_CREATE_EVENT,
    Action.GOOGLECALENDAR_LIST_EVENTS,
])
```

**Use case**: After /End session, agent schedules next review on Google Calendar using spaced repetition logic.

**Auth**: `composio add googlecalendar` CLI for dev, OAuth redirect for production.

---

## Mode Switching Implementation

### How It Works in OpenWebUI

OpenWebUI doesn't have native "slash command" mode switching. We implement it in the **backend system prompt**:

1. User types `/Lec` (or `/Rev`, `/Work`, `/End`) as their first message or mid-conversation
2. The pipe sends the full message history to the backend
3. The backend detects the mode command in the latest message
4. Backend loads appropriate notebook context for that mode
5. Backend constructs mode-specific system prompt
6. Agent responds in that mode

### Server-Side Mode Detection

```python
def detect_mode(messages: list[ChatMessage]) -> str:
    """Detect mode from latest user message."""
    last_msg = messages[-1].content.strip().lower()
    if last_msg.startswith("/lec"):
        return "lec"
    elif last_msg.startswith("/rev"):
        return "rev"
    elif last_msg.startswith("/work"):
        return "work"
    elif last_msg.startswith("/end"):
        return "end"
    return "default"  # General chat mode
```

### Mode-Specific System Prompts

Each mode gets a tailored system prompt that:
1. Describes the mode's purpose and behavior
2. Lists available tools and when to use them
3. Includes the pre-loaded notebook context
4. Sets interaction style (e.g., /Lec is passive note-taking, /Rev is active quizzing)

### Class Selection

The user's first interaction should set the class:
- "Create a new class: CS 301 Algorithms" → creates notebook directory
- Agent tracks active class in conversation context
- Can switch: "Switch to my CS 301 class"

---

## Background Tasks (/End Mode)

For the hackathon, there are no actual background workers. Instead, /End triggers the agent to do all updates inline:

```
User: /End
Agent: [Reads session transcript from conversation history]
       [Writes session summary to sessions/]
       [Reads glossary.md, identifies new terms, appends them]
       [Reads resources.md, adds any new URLs mentioned]
       [Updates notebook.json with new counts]
       [Uses You.com to research any topics that need enrichment]
       [Uses Composio to schedule next review on Google Calendar]
Agent: "Session wrapped up! Here's what I did:
        ✓ Saved session summary
        ✓ Added 3 new glossary terms: {terms}
        ✓ Added 2 new resources
        ✓ Scheduled review for Thursday at 2pm
        ✓ Enriched Lecture 3 notes with citations on {topic}"
```

This is visible to the user and judges — more impressive than invisible background work.

---

## Sponsor Integration

### Sponsor #1: Render — Deployment

**What**: Host both OpenWebUI and YouLearn backend on Render.

**Integration**:
- `render.yaml` blueprint at repo root (see render deployment research)
- OpenWebUI: Docker web service with persistent disk
- YouLearn backend: Private Docker service (stateless)
- Communication via Render's private network

**render.yaml** (simplified):
```yaml
services:
  - type: web
    name: youlearn-webui
    runtime: docker
    dockerfilePath: ./openwebui/Dockerfile
    dockerContext: ./openwebui
    plan: starter
    disk:
      name: webui-data
      mountPath: /app/backend/data
      sizeGB: 1
    envVars:
      - key: WEBUI_SECRET_KEY
        generateValue: true

  - type: pserv
    name: youlearn-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: ./backend
    plan: starter
    envVars:
      - key: OPENROUTER_API_KEY
        sync: false
      - key: YOU_API_KEY
        sync: false
      - key: COMPOSIO_API_KEY
        sync: false
```

**Demo value**: "We deployed to production on Render in 10 minutes with a single yaml file."

### Sponsor #2: You.com — Research & Citations

**What**: Agent uses You.com Search API to enrich lecture notes with real-world research and citations.

**Integration points**:
1. **During /Lec**: After organizing lecture notes, research key topics to add context and citations
2. **During /Rev**: Research topics the student is struggling with for alternative explanations
3. **During /End**: Enrich any sparse lecture sections with additional sources
4. **During /Work**: Research assignment topics for deeper understanding

**Demo value**: "Watch the agent automatically research and cite sources as it takes lecture notes — the notebook improves itself with every session."

### Sponsor #3: Composio — Google Calendar (Spaced Repetition)

**What**: Agent schedules review sessions on Google Calendar using spaced repetition intervals.

**Integration points**:
1. **During /End**: Schedule next review based on what was covered
2. **During /Rev**: Check calendar for upcoming reviews, mark completed
3. **Spaced repetition logic**: 1 day → 3 days → 7 days → 14 days → 30 days

**Demo value**: "The agent doesn't just help you study — it schedules when you should study next, directly on your Google Calendar."

**Setup**:
```bash
pip install composio-agno
composio add googlecalendar  # OAuth flow for dev account
```

---

## 5-Hour Build Order

### Hour 0-1: Skeleton & Core Loop (CRITICAL PATH)

**Goal**: Messages flow from OpenWebUI → Backend → Agent → Response

| Task | Time | Description |
|------|------|-------------|
| Create backend directory structure | 5 min | `backend/youlearn/` with `__init__.py`, `server.py` |
| Copy pipe.py from YouLab | 5 min | Adapt URL valve |
| Copy latex_tools.py from YouLab | 5 min | Direct copy |
| Write minimal server.py | 20 min | FastAPI + Agno agent, SSE streaming, mode detection |
| Write NotebookTools | 15 min | read/write/list notebook files |
| Test end-to-end | 10 min | OpenWebUI → pipe → backend → response |

**Deliverable**: Can chat with agent, agent can read/write files.

### Hour 1-2: Notebook System & Modes

**Goal**: Mode switching works, notebook context loads correctly

| Task | Time | Description |
|------|------|-------------|
| Write mode-specific system prompts | 20 min | /Lec, /Rev, /Work, /End prompts |
| Implement get_notebook_context() | 15 min | Smart context loading per mode |
| Implement class creation flow | 10 min | "Create class X" → directory + templates |
| Test /Lec mode | 15 min | Type lecture content, verify note creation |

**Deliverable**: Can create a class, switch modes, take lecture notes.

### Hour 2-3: You.com Integration (Sponsor #2)

**Goal**: Agent enriches notes with web research

| Task | Time | Description |
|------|------|-------------|
| Write YouComSearchTools | 20 min | search_web + research_topic tools |
| Integrate into agent | 10 min | Add to tool list |
| Add research to /Lec flow | 15 min | Agent researches after note-taking |
| Add research to /Rev flow | 15 min | Agent cites sources during review |

**Deliverable**: Agent adds citations to lecture notes from web research.

### Hour 3-4: Composio Integration (Sponsor #3) + /End Mode

**Goal**: Agent schedules reviews on Google Calendar, /End works

| Task | Time | Description |
|------|------|-------------|
| Set up Composio auth | 15 min | `pip install composio-agno`, connect Google Calendar |
| Add Composio tools to agent | 10 min | Calendar create/list actions |
| Implement /End session flow | 20 min | Summarize, glossary update, schedule review |
| Test full /End flow | 15 min | End session → calendar event created |

**Deliverable**: /End creates session summary, updates glossary, schedules review.

### Hour 4-5: Polish & Deploy (Sponsor #1)

**Goal**: Deployed on Render, demo-ready

| Task | Time | Description |
|------|------|-------------|
| Write backend Dockerfile | 10 min | Python 3.11 + dependencies |
| Write render.yaml | 10 min | Blueprint for both services |
| Deploy to Render | 15 min | Push, deploy, verify |
| Tool call streaming | 10 min | Show tool calls in UI (from research) |
| Demo script & polish | 15 min | Prepare walkthrough, test edge cases |

**Deliverable**: Live on Render, demo-ready.

---

## MVP vs Nice-to-Have

### MVP (Must Ship)

- [ ] Backend server with Agno agent + SSE streaming
- [ ] OpenWebUI pipe connecting to backend
- [ ] Notebook file structure (create class, read/write files)
- [ ] /Lec mode — take lecture notes into structured markdown
- [ ] /Rev mode — review and quiz from notebook
- [ ] You.com search integration — enrich notes with citations
- [ ] Composio Google Calendar — schedule review sessions
- [ ] Deployed on Render

### Nice-to-Have (If Time Permits)

- [ ] /Work mode — assignment help with progress tracking
- [ ] /End mode — full session wrap-up with all updates
- [ ] LaTeX PDF generation for beautiful study guides
- [ ] Tool call streaming (show spinners in UI)
- [ ] Spaced repetition algorithm for review scheduling
- [ ] Upload PDF syllabus → auto-parse into syllabus.md
- [ ] Cross-lecture concept mapping in glossary

### Cut (Not Doing)

- Database (Dolt, Postgres, etc.) — files on disk is enough
- Honcho message persistence — OpenWebUI handles chat history
- Background task scheduler — /End does everything inline
- Voice input (Plivo) — too complex for 5 hours
- Multi-user notebook sharing
- Frontend UI modifications to OpenWebUI

---

## File Tree (What We're Building)

```
YouLearn/
├── render.yaml                          # Render deployment blueprint
├── openwebui/                           # Forked OpenWebUI (minimal changes)
│   ├── Dockerfile                       # (existing)
│   └── ...
├── backend/
│   ├── Dockerfile                       # Python 3.11 slim + uv
│   ├── pyproject.toml                   # Dependencies
│   └── youlearn/
│       ├── __init__.py
│       ├── server.py                    # FastAPI + Agno agent + SSE
│       ├── config.py                    # Settings (env vars)
│       ├── modes.py                     # Mode detection + system prompts
│       ├── pipe.py                      # OpenWebUI pipe (copied from YouLab)
│       └── tools/
│           ├── __init__.py
│           ├── notebook_tools.py        # NotebookTools (read/write/context)
│           ├── latex_tools.py           # LaTeXTools (copied from YouLab)
│           ├── youcom_tools.py          # YouComSearchTools (You.com API)
│           └── composio_tools.py        # Composio wrapper (Google Calendar)
├── notebooks/                           # Runtime data (gitignored)
│   └── {user_id}/
│       └── {class_slug}/
│           ├── notebook.json
│           ├── syllabus.md
│           ├── glossary.md
│           ├── resources.md
│           ├── lectures/
│           ├── assignments/
│           └── sessions/
└── thoughts/                            # Planning docs (not deployed)
    ├── build-plan.md                    # This file
    └── shared/research/                 # Research docs
```

---

## Key Dependencies

```toml
[project]
name = "youlearn"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "sse-starlette>=2.0.0",
    "agno>=1.4.5",
    "httpx>=0.28.0",
    "httpx-sse>=0.4.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.1.0",
    "composio-agno>=0.7.0",
]
```

---

## Critical Decisions

1. **Markdown over LaTeX for storage** — LLMs write markdown naturally; LaTeX only for PDF output
2. **No database** — Files on disk. Simple, debuggable, sufficient for demo
3. **Mode detection in backend** — Not OpenWebUI functions/slash commands (those require frontend mods)
4. **Agno + OpenRouter** — Proven pattern from YouLab, single API key for model flexibility
5. **Inline /End over background workers** — More visible to judges, simpler to build
6. **Composio for Google Calendar** — Has native Agno integration (`composio-agno`), OAuth handled

---

## Demo Script

1. **"Create a new class: CS 301 Algorithms"** → Show notebook directory created
2. **"/Lec — Today we're covering sorting algorithms..."** → Show structured notes being written
3. **Show the You.com research** → Agent enriches notes with citations automatically
4. **"/Rev — Quiz me on what we covered"** → Agent asks questions from the notebook
5. **"/End"** → Session summary, glossary updated, Google Calendar event created
6. **Open Google Calendar** → Show the scheduled review session
7. **Show Render dashboard** → Deployed and running in production
8. **Generate PDF** → LaTeX-compiled beautiful study guide (if time)
