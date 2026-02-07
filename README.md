# YouLearn

**AI study companion that maintains a living LaTeX notebook per class.** Student talks, notebook evolves.

Built in 5 hours for the [Continual Learning Hackathon](https://lu.ma/continuallearning). YouLearn replaces scattered notes, static PDFs, and generic chatbots with a single AI agent that reads, writes, compiles, and fact-checks a real LaTeX notebook — then remembers your learning journey across sessions.

**Demo notebook:** A full Math 104 (Intro to Real Analysis) course with 5 lectures, 2 homework sets, a glossary, and auto-generated index. Check it out here: https://drive.google.com/file/d/11edgzTcymJqX6K1sXf_Gs1CqYOxdJsKQ/view?usp=sharing

---

## How It Works

```
Student chats in OpenWebUI
        │
        ▼
   Mode Detection ──→ /Lec  /Rev  /Work  /Done  (or general chat)
        │
        ▼
   Context Loading ──→ Loads relevant .tex files into agent memory
        │
        ▼
   Agno AI Agent ──→ Reads, writes, creates, compiles LaTeX
        │
        ▼
   Background Agents ──→ Fact-check (You.com) + Progress narrative
        │
        ▼
   Compiled PDF ──→ Viewable in browser via /pdf endpoint
```

The student types natural language (or messy shorthand during lectures). The agent converts it to properly formatted LaTeX, manages the notebook structure, and compiles to PDF on demand. After each session, background agents verify factual claims and update a narrative portrait of the student's learning.

---

## Modes

YouLearn adapts its behavior per-message based on a simple prefix:

### `/Lec` — Live Lecture Dictation
The student is in a live lecture. The agent **only transcribes** — it never invents content. Converts shorthand (`->` to `\to`, `A int B` to `A \cap B`, `x in A` to `x \in A`) and organizes content into proper LaTeX sections with theorem environments.

### `/Rev` — Review & Quizzing
Active studying. The agent quizzes the student, makes connections between lectures ("This relates to the Heine-Borel theorem from Lecture 5"), generates practice problems, and creates study materials using the notebook's summary system.

### `/Work` — Homework Help
**Guide, don't solve.** The agent reads the assignment, checks current progress, and helps with hints — never completing work for the student. When stuck, it creates visual "explainer" documents with TikZ diagrams and intuition guides.

### `/Done` — Session Wrap-Up
Summarizes what was accomplished, creates a timestamped session log, and triggers two background agents:
1. **Fact-checker** — Verifies claims in lecture notes via You.com Search API
2. **Progress writer** — Updates a living narrative of the student's learning journey

---

## The Living Notebook

YouLearn manages a real, compilable LaTeX notebook using the [`subfiles`](https://ctan.org/pkg/subfiles) pattern. Each lecture compiles standalone or as part of the full notebook.

### Compiled PDF Structure
| Section | Content |
|---------|---------|
| **Syllabus** | Course overview, requirements, objectives, weekly calendar |
| **Lectures** | Individual lecture sections with summaries and theorem environments |
| **Assignments** | Homework summaries with embedded PDF submissions |
| **Student Progress** | AI-maintained narrative of the student's learning journey |
| **Sessions** | Chronological study session logs |
| **Resources** | Textbook references and supplementary materials |
| **Glossary** | Curated definitions organized by topic |
| **Index** | Auto-generated page index from `\defn{}` commands |

### Custom LaTeX Environments
- **`lecturesummary`** — Orange box for high-level lecture overview
- **`summarybox`** — Baby blue box for section-level summary
- **`notebox`** — Light red box for proof technique notes
- **`\defn{term}`** — Red bold text + automatic index entry

Plus standard theorem environments: `theorem`, `lemma`, `proposition`, `corollary`, `definition`, `example`, `remark`.

---

## Agent Tools

The AI agent has 6 tools for direct notebook manipulation:

| Tool | What It Does |
|------|-------------|
| `read_file(path)` | Read any file in the notebook |
| `write_file(path, content)` | Write/update files, auto-creates directories |
| `list_files(subdir)` | Browse notebook directory structure |
| `create_lecture(num, date, topic)` | Create new lecture from template, register in master.tex |
| `create_session(date, mode, summary, ...)` | Create timestamped session log as LaTeX subfile |
| `compile_notes(target)` | Compile to PDF via pdflatex + makeindex |

All file operations include path traversal protection.

---

## Background Agents

### Fact-Check Agent (You.com Search API)
After each session, a background agent scans recently-edited lectures for verifiable claims — historical attributions, named theorems, dates — and checks them against web sources. Results are written to a JSON report that's loaded into the chat agent's context.

```json
{
  "claim": "Hermite proved e is transcendental in 1873",
  "status": "correct",
  "source_url": "https://en.wikipedia.org/wiki/Transcendental_number",
  "explanation": "Confirmed: Charles Hermite published the proof in 1873."
}
```

### Student Progress Narrative
A separate agent maintains `progress.tex` — a living document that reads like a thoughtful tutor's journal. It tracks the student's evolving understanding, conceptual breakthroughs, productive struggles, and areas that need attention. This gives the chat agent cross-session memory.

---

## Smart Context Loading

Each mode pre-loads different notebook content so the agent doesn't start from zero:

| Mode | What's Loaded |
|------|--------------|
| `/Lec` | LaTeX preamble + template + last 2 full lectures + syllabus |
| `/Rev` | All lecture summaries + section summaryboxes + glossary |
| `/Work` | Assignment text + current submission + explainers + lecture summaries |
| `/Done` | Lecture index + session list + sessions.tex container |

The fact-check report and student progress narrative are injected into **every** mode.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    OpenWebUI (Frontend)                        │
│                 SvelteKit Chat UI + Auth                       │
└────────────────────────┬─────────────────────────────────────┘
                         │ SSE via pipe.py
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Backend Service                      │
│                                                                │
│   Mode Detector → Context Loader → System Prompt → Agno Agent │
│                                                                │
│   ┌────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│   │ NotebookTools  │  │ ComposioDrive  │  │  Background   │  │
│   │ (6 tools)      │  │ (Google Drive)  │  │   Agents      │  │
│   │ read/write/    │  │ find/list/     │  │  fact-check   │  │
│   │ create/compile │  │ download       │  │  + progress   │  │
│   └────────────────┘  └────────────────┘  └───────────────┘  │
│                                                                │
│   ┌────────────────────────────────────────────────────────┐  │
│   │              LaTeX Workspace (classes/Math-104/)        │  │
│   │   master.tex ← subfile includes ← pdflatex+makeindex  │  │
│   └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴────┐         ┌────┴────┐         ┌────┴────┐
    │OpenRouter│         │ You.com │         │Composio │
    │  (LLM)  │         │(Search) │         │(GDrive) │
    └─────────┘         └─────────┘         └─────────┘
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | OpenWebUI (SvelteKit) |
| Backend | FastAPI + Uvicorn |
| AI Agent | Agno + OpenRouter (GPT-4o-mini default) |
| Streaming | Server-Sent Events (sse-starlette + httpx-sse) |
| LaTeX | pdflatex + makeindex (TeX Live) |
| Fact-Checking | You.com Search API |
| File Import | Composio (Google Drive) |
| Config | pydantic-settings |
| Packaging | uv + hatchling |
| Deployment | Render (Docker) |

---

## Sponsor Integrations

| Sponsor | What We Use | How |
|---------|------------|-----|
| **Render** | Deployment platform | Hosts frontend (OpenWebUI) and backend (FastAPI + TeX Live) as Docker services |
| **You.com** | Search API | Background agent verifies factual claims in lecture notes against web sources |
| **Composio** | Google Drive SDK | Students search, browse, and download files from Drive into the notebook |

---

## Running Locally

```bash
# Backend
cd backend
make setup
cp .env.example .env  # fill in YOULEARN_OPENROUTER_API_KEY
make server            # starts on :8200

# Frontend
cd openwebui
npm run dev            # starts on :5173
# Register pipe.py content in OpenWebUI Admin > Functions
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOULEARN_OPENROUTER_API_KEY` | Yes | OpenRouter API key for LLM access |
| `YOULEARN_OPENROUTER_MODEL` | No | Model ID (default: `openai/gpt-4o-mini`) |
| `YOULEARN_YOU_API_KEY` | No | You.com Search API key (enables fact-checking) |
| `COMPOSIO_API_KEY` | No | Composio key (enables Google Drive import) |
| `YOULEARN_BACKEND_URL` | No | Public URL for PDF links (set in production) |

---

## Production Deployment

Both services deploy on Render via `render.yaml`:

```bash
git push  # Render auto-rebuilds backend from Dockerfile
```

**Backend Dockerfile:** Python 3.11 slim + TeX Live + uv (~755MB image). The `classes/Math-104/` notebook is baked into the image.

---

## Project Structure

```
YouLearn/
├── render.yaml                    # Render deployment blueprint
├── backend/
│   ├── Dockerfile                 # Python 3.11 + TeX Live + uv
│   ├── pipe.py                    # OpenWebUI ↔ Backend SSE bridge
│   ├── pyproject.toml             # Dependencies (agno, fastapi, composio)
│   ├── Makefile                   # make setup, make server
│   └── src/youlearn/
│       ├── server.py              # FastAPI app, SSE streaming, PDF serving
│       ├── modes.py               # Mode detection + 5 system prompts
│       ├── context.py             # Context loading from .tex files
│       ├── config.py              # pydantic-settings configuration
│       ├── factcheck.py           # Background fact-check agent
│       ├── progress.py            # Background progress narrative agent
│       └── tools/
│           ├── notebook_tools.py  # NotebookTools (6 tools)
│           ├── youcom_tools.py    # You.com Search API wrapper
│           └── composio_drive_tools.py  # Google Drive via Composio
├── classes/
│   └── Math-104/                  # Demo notebook (Real Analysis)
│       ├── Makefile               # make, make lec01, make clean
│       ├── notes/latex/
│       │   ├── master/master.tex  # Master document (8 sections)
│       │   ├── lec01-05/          # 5 lectures on real analysis
│       │   ├── temp/temp.tex      # Template for new lectures
│       │   ├── syllabus/          # Course syllabus
│       │   ├── assignments/       # Assignment summaries
│       │   ├── sessions/          # Session logs (auto-generated)
│       │   ├── progress/          # Student progress narrative
│       │   ├── resources/         # Course resources
│       │   └── glossary/          # Curated glossary + auto-index
│       └── hw/
│           ├── hw1/               # HW1: Rudin Ch.1 problems
│           └── hw2/               # HW2: Rudin Ch.2 problems
└── openwebui/                     # Forked OpenWebUI frontend
```

---

## Demo Content

The Math-104 notebook contains real university-level Real Analysis content:

| Lecture | Topic |
|---------|-------|
| 1 | Ordered Sets, Least Upper Bound Property, Fields |
| 2 | Construction of the Real Numbers (Dedekind Cuts) |
| 3 | Set Theory and Countability (Cantor's Diagonal Argument) |
| 4 | Topological Spaces and Metric Topology |
| 5 | Compactness and Perfect Sets (Heine-Borel) |

Two homework sets from Rudin's *Principles of Mathematical Analysis*, each with problem statements, LaTeX submissions, and visual explainer documents.
