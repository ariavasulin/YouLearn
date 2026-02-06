---
date: 2026-02-06T12:00:00-08:00
researcher: ARI
git_commit: 835f5d4326dbea5b39fbe350eaa6152b572f68b2
branch: main
repository: YouLearn
topic: "Comprehensive feature list, workflow, and architecture for presentation"
tags: [research, codebase, presentation, architecture, features, workflow]
status: complete
last_updated: 2026-02-06
last_updated_by: ARI
---

# Research: YouLearn — Comprehensive Overview for Presentation

**Date**: 2026-02-06
**Researcher**: ARI
**Git Commit**: 835f5d4
**Branch**: main
**Repository**: YouLearn

## Research Question
Comprehensive feature list, workflow documentation, and architecture overview for hackathon presentation and README.

## Summary

YouLearn is an AI study companion that maintains a living LaTeX notebook per class. Built in 5 hours for the Continual Learning hackathon, it uses a forked OpenWebUI frontend piped to a FastAPI + Agno backend that reads, writes, and compiles a real university-level Real Analysis (Math 104) notebook with 5 lectures, 2 homework sets, a glossary, and auto-generated index. Three sponsor integrations: Render (deployment), You.com (fact-checking), Composio (Google Drive import).

## Feature List

### 1. Multi-Mode AI Study Companion
The agent adapts its behavior per-message based on mode prefixes:

| Mode | Prefix | Purpose | Agent Behavior |
|------|--------|---------|----------------|
| **Lecture** | `/Lec` | Live lecture dictation | Transcription-only — never invents content. Converts shorthand (→, ∩, ∈) to LaTeX. Brief confirmations. |
| **Review** | `/Rev` | Active studying & quizzing | Quizzes student, makes cross-lecture connections, generates practice problems, creates study guides |
| **Homework** | `/Work` | Assignment help | Guide-don't-solve pedagogy. Hints over answers. Creates visual "explainer" documents, never completes work for student |
| **Done** | `/Done` | Session wrap-up | Summarizes session, creates timestamped log, triggers background agents, suggests next steps |
| **Default** | _(none)_ | General chat | Answers questions, navigates notebook, suggests appropriate mode |

### 2. Living LaTeX Notebook (The "Ubook")
A real, compilable LaTeX notebook using the `subfiles` pattern:

**Document Structure (8 sections in compiled PDF):**
1. **Syllabus** — Course overview, requirements, objectives, 8-week calendar
2. **Lectures** — Individual lecture sections (lec01–lec06), each with summaries and theorem environments
3. **Assignments** — Homework summaries with embedded PDF submissions via `\includepdf`
4. **Student Progress** — AI-maintained narrative of the student's learning journey
5. **Sessions** — Chronological study session logs (auto-generated via `/Done`)
6. **Resources** — Textbook references and supplementary materials
7. **Glossary** — Curated definitions organized by topic
8. **Index of Definitions** — Auto-generated page index from `\defn{}` commands

**Custom LaTeX Environments:**
- `lecturesummary` — Orange box for high-level lecture overview
- `summarybox` — Baby blue box for section-level summary
- `notebox` — Light red box for proof technique notes
- `theorem`, `lemma`, `proposition`, `corollary`, `definition`, `example`, `remark` — Numbered theorem environments

**Key Command: `\defn{term}`** — Renders term in red bold AND auto-adds to the index. Every definition in the notebook is automatically indexed.

### 3. Notebook Tools (6 Agent Tools)
The AI agent has direct file-system access via a custom Agno toolkit:

| Tool | Purpose |
|------|---------|
| `read_file(path)` | Read any file in the notebook (with path traversal protection) |
| `write_file(path, content)` | Write/update files, auto-creates directories |
| `list_files(subdir)` | Browse notebook directory structure |
| `create_lecture(num, date, topic)` | Create new lecture from template, register in master.tex |
| `create_session(date, mode, summary, ...)` | Create timestamped session log as LaTeX subfile |
| `compile_notes(target)` | Compile to PDF via pdflatex + makeindex (3-pass for master) |

### 4. Smart Context Loading
Each mode loads different notebook content into the agent's context window:

| Mode | Context Loaded | ~Tokens |
|------|---------------|---------|
| `/Lec` | LaTeX preamble + template + last 2 full lectures + syllabus | 4-6K |
| `/Rev` | All lecture summaries + section summaryboxes + glossary | 4-5K |
| `/Work` | Assignment text + current submission + explainers + lecture summaries | 3-5K |
| `/Done` | Lecture index + session list + sessions.tex container | ~1K |
| Default | Syllabus + lecture summaries + hw/session lists | ~3K |

Context is built by regex-parsing `.tex` files — extracting `\renewcommand` metadata and `lecturesummary`/`summarybox` environment contents.

### 5. Background Fact-Check Agent (You.com)
An autonomous agent that verifies factual claims in lecture notes using web search:

- **Trigger**: Auto-fires after `/Done` mode, or manually via `POST /fact-check/trigger`
- **Incremental**: Only checks lectures modified since last run (tracks timestamp in `.fact-check-state.json`)
- **Read-only**: Has `YouComSearchTools` only — cannot edit files
- **Report-based**: Writes structured JSON report to `fact-check-report.json`
- **Context injection**: Report is loaded into chat agent's context for all modes
- **What it checks**: Historical attributions, named theorems, dates, people
- **What it skips**: Formal proofs, pure definitions, LaTeX formatting

**Report format per finding:**
```json
{
  "file": "notes/latex/lec03/lec03.tex",
  "claim": "Hermite proved e is transcendental in 1873",
  "status": "correct",
  "correction": null,
  "source_url": "https://en.wikipedia.org/wiki/Transcendental_number",
  "explanation": "Confirmed: Charles Hermite published the proof in 1873."
}
```

### 6. Student Progress Narrative Agent
An AI agent that maintains a living "tutor's journal" about the student's learning:

- **Trigger**: Auto-fires after `/Done` mode, or manually via `POST /progress/trigger`
- **Output**: Rewrites `progress.tex` as a rich, reflective narrative
- **Voice**: First-person plural ("We began exploring...") with observational assessment ("The student has developed a remarkably intuitive grasp of...")
- **Sections**:
  - "Where We Are" — Current understanding, strengths, gaps
  - "The Journey So Far" — Thematic arc across sessions
  - "Edges of Understanding" — Partially formed concepts, misconceptions
  - "Looking Forward" — Pedagogical recommendations
- **Full rewrite each time**: Avoids append-bloat, lets narrative evolve organically
- **Context injection**: Loaded into all modes so the agent remembers the student across sessions

### 7. Google Drive Integration (Composio)
Students can import files from Google Drive:

| Tool | Purpose |
|------|---------|
| `find_file(query)` | Search Drive for files by name/keyword |
| `list_files(folder_id)` | Browse Drive folder contents |
| `download_file(file_id, name)` | Download file content |

- **Optional**: Gracefully skipped if `COMPOSIO_API_KEY` not set
- **OAuth**: Managed via Composio dashboard (no per-user auth)

### 8. Real-Time Tool Call Visibility
Agent tool executions are visible in the chat UI:

- **Server** streams `tool_call_start`, `tool_call_complete`, `tool_call_error` SSE events
- **Pipe** converts to OpenWebUI's `<details type="tool_calls">` HTML
- Student sees: spinner during execution → expandable result block when done
- Tool results truncated at 2000 chars for readability

### 9. PDF Compilation & Serving
- **Compilation**: pdflatex + makeindex (3-pass for master, 1-pass for individual lectures)
- **Serving**: `GET /pdf/{class}/{filename}` with `Content-Disposition: inline` for in-browser viewing
- **Security**: Path traversal protection via `resolve() + startswith()` check
- Agent returns clickable download link after compilation

### 10. Homework Workflow
Structured homework assistance with pedagogical guardrails:

- `hw/hwN/assignment.txt` — Problem statements
- `hw/hwN/submission/*.tex` — Student's LaTeX solutions (embedded in compiled PDF)
- `hw/hwN/explainers/pM/*.tex` — Visual concept explainers (TikZ diagrams, intuition guides)
- `hw/hwN/book_probs/` — Original textbook problems
- Agent reads assignment, reads current progress, guides with hints, writes up ONLY what student provides

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenWebUI (Frontend)                     │
│                    SvelteKit Chat UI + Auth                     │
│              https://open-webui-xlww.onrender.com               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ SSE (POST /chat/stream)
                           │ via pipe.py
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend Service                      │
│              https://youlearn-backend-6q83.onrender.com         │
│                                                                  │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │  Mode    │→│ Context  │→│  System   │→│   Agno Agent    │  │
│  │ Detector │  │ Loader   │  │  Prompt   │  │  (OpenRouter)   │  │
│  │modes.py  │  │context.py│  │ Builder   │  │                 │  │
│  └──────────┘  └─────────┘  └──────────┘  │  ┌─────────────┐ │  │
│                                            │  │NotebookTools│ │  │
│                                            │  │ (6 tools)   │ │  │
│                                            │  ├─────────────┤ │  │
│                                            │  │ComposioDrive│ │  │
│                                            │  │ (3 tools)   │ │  │
│                                            │  └─────────────┘ │  │
│                                            └─────────────────┘  │
│                                                                  │
│  ┌──────────────────────┐  ┌────────────────────────────────┐   │
│  │  Fact-Check Agent    │  │   Progress Narrative Agent     │   │
│  │  (background, async) │  │   (background, async)          │   │
│  │  YouComSearchTools   │  │   Pure generation (no tools)   │   │
│  │  → report.json       │  │   → progress.tex               │   │
│  └──────────────────────┘  └────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   LaTeX Workspace                         │   │
│  │  classes/Math-104/notes/latex/  ←  pdflatex + makeindex  │   │
│  │  ├── master/master.tex (8 sections, 48+ pages)           │   │
│  │  ├── lec01-06/*.tex (individual lectures)                │   │
│  │  ├── syllabus, assignments, sessions, resources          │   │
│  │  ├── progress/progress.tex (AI-maintained)               │   │
│  │  └── glossary/glossary.tex + auto-generated index        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │OpenRouter│ │ You.com  │ │Composio  │
        │  (LLM)   │ │(Search)  │ │(GDrive)  │
        │ gpt-4o-  │ │ Fact-    │ │ File     │
        │  mini    │ │ checking │ │ import   │
        └──────────┘ └──────────┘ └──────────┘
```

### Request Flow

```
1. User types "/Lec Today we're covering sequences" in OpenWebUI
2. OpenWebUI → pipe.py (SSE POST to backend /chat/stream)
3. server.py: detect_mode("/Lec ...") → Mode("lec", "Today we're covering sequences")
4. server.py: build_context(class_dir, "lec") → loads preamble + last 2 lectures + syllabus
5. server.py: build_system_prompt("lec", context, "Math 104") → full system prompt
6. server.py: creates Agno Agent with NotebookTools + ComposioDriveTools
7. Agent streams response via SSE:
   - ToolCallStartedEvent → pipe shows spinner
   - ToolCallCompletedEvent → pipe shows expandable result
   - RunContentEvent → pipe shows text content
8. After /Done mode:
   - asyncio.create_task(run_fact_check(settings))  → background fact-check
   - asyncio.create_task(run_progress_update(settings))  → background progress update
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | OpenWebUI v0.6.41 (forked) — SvelteKit |
| **Backend** | FastAPI + Uvicorn |
| **AI Agent** | Agno framework + OpenRouter (model flexibility) |
| **Default LLM** | GPT-4o-mini via OpenRouter |
| **Streaming** | Server-Sent Events (SSE) via sse-starlette + httpx-sse |
| **LaTeX** | pdflatex + makeindex (TeX Live) |
| **Config** | pydantic-settings + `.env` files |
| **Package Mgmt** | uv (Python), hatchling (build) |
| **Deployment** | Render (Docker, standard plan, Oregon) |
| **Fact-Checking** | You.com Search API |
| **File Import** | Composio (Google Drive SDK) |
| **Logging** | structlog |

### Deployment Architecture

**Two services on Render:**

| Service | URL | Runtime | Image Size |
|---------|-----|---------|-----------|
| OpenWebUI (Frontend) | `open-webui-xlww.onrender.com` | Prebuilt Docker image | ~1.5GB |
| YouLearn Backend | `youlearn-backend-6q83.onrender.com` | Custom Dockerfile | ~755MB |

**Backend Dockerfile layers:**
1. Python 3.11 slim base
2. TeX Live (pdflatex + makeindex + fonts)
3. uv package manager
4. Python dependencies (`uv sync --frozen --no-dev`)
5. Backend source code
6. LaTeX notebook (baked in at `/data/classes`)

**Env vars (set in Render dashboard):**
- `YOULEARN_OPENROUTER_API_KEY` — LLM access
- `YOULEARN_OPENROUTER_MODEL` — Model selection
- `YOULEARN_YOU_API_KEY` — Fact-checking
- `COMPOSIO_API_KEY` — Google Drive
- `YOULEARN_BACKEND_URL` — PDF link generation

### The Math-104 Notebook (Demo Content)

Real university-level Real Analysis content:

| Lecture | Topic | Key Content |
|---------|-------|-------------|
| 1 | Ordered Sets, LUB Property, Fields | √2 irrationality, partial/total orders, supremum/infimum, LUBP |
| 2 | Construction of ℝ | Dedekind cuts, Archimedean property, density of ℚ, Cantor set, ℂ, Schwarz inequality |
| 3 | Set Theory & Countability | Cardinality, countable sets, Cantor's diagonal argument, algebraic vs transcendental |
| 4 | Topological Spaces, Metric Topology | Open/closed sets, basis, product topology, epsilon-delta, closure, limit points |
| 5 | Compactness, Perfect Sets | Open covers, Heine-Borel, Weierstrass, finite intersection property, Cantor set is perfect |
| 6 | (Created by agent) | Template-generated, demonstrating live lecture creation |

**Homework:**
- **HW1**: Rudin Ch.1 — Problems 1,5,9,18 + bonus 7,8,20
- **HW2**: Rudin Ch.2 — Problems 2,4,5,6,9,22,23,24,26 + bonus 16,25

Each with `assignment.txt`, `submission/*.tex`, `explainers/`, `book_probs/`.

## Code References

### Backend Core
- `backend/src/youlearn/server.py` — FastAPI app, SSE streaming, PDF serving, background agent triggers
- `backend/src/youlearn/modes.py` — Mode detection + 5 system prompts (260 lines)
- `backend/src/youlearn/context.py` — Context loading via regex parsing of .tex files (305 lines)
- `backend/src/youlearn/config.py` — pydantic-settings configuration (44 lines)

### Agent Tools
- `backend/src/youlearn/tools/notebook_tools.py` — NotebookTools Agno toolkit (354 lines, 6 tools)
- `backend/src/youlearn/tools/youcom_tools.py` — You.com Search API wrapper (76 lines)
- `backend/src/youlearn/tools/composio_drive_tools.py` — Google Drive via Composio (117 lines)

### Background Agents
- `backend/src/youlearn/factcheck.py` — Fact-check agent (236 lines)
- `backend/src/youlearn/progress.py` — Progress narrative agent (272 lines)

### Frontend Integration
- `backend/pipe.py` — OpenWebUI pipe (224 lines)

### Infrastructure
- `backend/Dockerfile` — Python 3.11 + TeX Live + uv (36 lines)
- `render.yaml` — Render deployment blueprint (21 lines)
- `backend/pyproject.toml` — Dependencies + entry point (29 lines)

### LaTeX Notebook
- `classes/Math-104/notes/latex/master/master.tex` — Master document (185 lines)
- `classes/Math-104/notes/latex/temp/temp.tex` — Lecture template (30 lines)
- `classes/Math-104/Makefile` — Build system (29 lines)

## Sponsor Integration Summary

| Sponsor | Integration | How It's Used |
|---------|------------|---------------|
| **Render** ($1K credits) | Deployment platform | Hosts both frontend (OpenWebUI) and backend (FastAPI + TeX Live) as Docker services in Oregon |
| **You.com** ($50 + credits) | Search API for fact-checking | Background agent verifies historical claims, theorem attributions, dates in lecture notes |
| **Composio** ($1K cash + $2K credits) | Google Drive SDK | Students can search, browse, and download files from Google Drive into the notebook |

## Key Design Decisions

1. **LaTeX over Markdown**: Real academic quality — theorem environments, auto-indexing, compilable PDFs
2. **Mode-per-message**: Non-sticky modes allow fluid switching mid-conversation
3. **Context injection**: Pre-loads relevant notebook content so agent doesn't need tool calls for basic knowledge
4. **Report-based fact-checking**: Background agent writes report, chat agent decides what to act on
5. **Narrative progress**: AI-maintained "tutor's journal" gives cross-session memory
6. **OpenRouter**: Single API key, any model — easy to switch from gpt-4o-mini to Claude/Llama
7. **Subfiles pattern**: Each lecture compiles standalone OR as part of master
8. **Baked-in content**: Classes directory in Docker image (no persistent disk needed for hackathon)
