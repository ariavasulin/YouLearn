# YouLearn

# Problem Description

Students are unique. Teachers continually struggle to **1)** Meet students where they are and **2)** Present lessons in a way that students can understand

Likewise students struggle to **1)** digest course material efficiently (lecture) **2)** synthesize new ideas (HW) **3)** Gain understanding (exams / long term utility).


# Agent Description

Continually updates to the student along 3 vectors

How the student learns (Visual, explainers, mini problems, intuition)
What the student knows (Meet them where they are + course materials)
How the student works 


## Agent Modes

* **/lec** (Lecture note taking, live Q/A)

* **/rev** (Material Review, get the student up and running with course concepts)

* **/work** (Work alongside student to finish assignments effectively)



# The Ubook (Where everything is stored)

**Table Of Contents:**

* Syllabus - high-level overview of the course

* Assignments

* Course Requirements

* Learning Objectives

* Calendar

* Lecture notes (1 per lecture)

    * Lecture Overview

    * Each Section has a section overview

* Assignments (/work) (1 per assignment)

* Sessions (A description of what was worked on)

* Resources (Websites, textbooks, etc.)

* Glossary (Where to find specific topics)

# Sponsors

* [Composio](https://docs.composio.dev/docs) — AI-first integration platform (850+ toolkits, 11k+ actions)
* [Render](https://render.com/docs) — Cloud hosting with managed PostgreSQL + pgvector
* [you.com](https://documentation.you.com/get-started/welcome) — LLM-native search API (93% accuracy, 445ms)

---

# How We Use Each Sponsor

## Composio — The Integration Layer

Composio is middleware between our AI agent and external apps. One unified interface for all integrations, with managed OAuth (no auth headaches).

**Key integrations for ULearn:**
- **Canvas LMS** (89+ actions) — pull syllabus, assignments, deadlines, submit work
- **Notion** — Ubook storage (structured pages, databases, glossary)
- **Google Calendar** — schedule deadlines, study sessions, spaced repetition
- **Google Drive** — file storage for lecture materials, PDFs
- **GitHub** — assignment repos, code management
- **Slack/Discord** — study group collaboration
- **Exa / Tavily** — neural/web search for finding resources
- **CodeInterpreter** — run and test student code in sandbox
- **FileManager** — local file operations
- **RAG tools** — semantic search over course materials

**Per mode:**
- **/lec**: Auto-organize notes into Notion, pull today's context from Canvas, detect "due Monday" → create Calendar event
- **/rev**: Generate quizzes → track results in Notion DB, schedule spaced repetition via Calendar, curate resources by learning style using Exa search
- **/work**: Open assignment from Canvas, create GitHub repo with starter code, run tests with CodeInterpreter, submit to Canvas on completion
- **Ubook**: One command → pull Canvas syllabus → auto-create entire Notion structure (lectures, assignments, glossary, resources)

**Setup:**
```python
from composio import Composio
composio = Composio(api_key=COMPOSIO_API_KEY)
session = composio.create_session(user_id="student_123")
tools = session.get_tools(["NOTION", "CANVAS", "GOOGLECALENDAR", "GITHUB", "EXA"])
```

**Pricing:** Free tier = 20k tool calls/month, 1k/hour (plenty for hackathon)

---

## Render — The Deployment Platform

Render hosts our entire stack. Key advantage: PostgreSQL with **pgvector** extension gives us structured data AND vector embeddings in one database.

**Services we deploy:**

| Service | Type | Cost | Purpose |
|---------|------|------|---------|
| ulearn-web | Web Service (FastAPI) | FREE | API + WebSocket for live /lec Q&A |
| ulearn-frontend | Static Site | FREE | React/Next.js UI |
| ulearn-db | PostgreSQL + pgvector | FREE (256MB) | Ubook storage + semantic search |
| ulearn-redis | Key Value (Redis) | FREE (25MB) | Session cache + task queue |
| ulearn-worker | Background Worker | FREE | Process lectures, generate embeddings |
| ulearn-sync | Cron Job | $1/mo | Daily LMS course sync |

**Total hackathon cost: $0-1/month**

**pgvector for Ubook:**
```sql
CREATE EXTENSION vector;

-- Store lecture chunks with embeddings
CREATE TABLE lecture_embeddings (
  id UUID PRIMARY KEY,
  lecture_id UUID REFERENCES lectures(id),
  chunk_text TEXT,
  embedding vector(1536),
  metadata JSONB
);

-- Fast similarity search
CREATE INDEX ON lecture_embeddings USING hnsw (embedding vector_cosine_ops);

-- Hybrid query: find relevant chunks for a course
SELECT chunk_text, 1 - (embedding <=> $1::vector) as similarity
FROM lecture_embeddings
WHERE course_id = $2 AND similarity > 0.7
ORDER BY similarity DESC LIMIT 5;
```

**Deploy entire stack with one file (`render.yaml`):**
```yaml
services:
  - type: web
    name: ulearn-web
    runtime: python
    startCommand: "uvicorn main:app --host 0.0.0.0 --port 8000"
    envVars:
      - key: DATABASE_URL
        fromDatabase: { name: ulearn-db, property: connectionString }
      - key: REDIS_URL
        fromService: { name: ulearn-redis, type: redis, property: connectionString }

  - type: worker
    name: ulearn-worker
    runtime: python
    startCommand: "celery -A tasks worker"

databases:
  - name: ulearn-db
    plan: starter
  - name: ulearn-redis
    plan: starter
```

---

## You.com — The Search & Intelligence Layer

You.com provides real-time web search optimized for LLMs. Snippets come pre-processed — ready to inject into prompts, no scraping needed.

**APIs we use:**

| API | Latency | Best For |
|-----|---------|----------|
| Express API | 2-3s | /lec — fast answers during lectures |
| Search API | 445ms | /rev — find resources, practice problems |
| Deep Search API | Slower | /work — precise debugging, verified code examples |
| Contents API | Varies | Ubook — fetch full page content as markdown |

**Per mode:**
- **/lec**: Student asks "what is gradient descent?" → Express API returns explanation with citations in 2-3s, stored in lecture notes
- **/rev**: Search for practice problems matching difficulty + learning style. "Find visual explanations of quicksort" → ranked results with snippets
- **/work**: Search exact error messages for debugging. `"IndexError: list index out of range" recursive function` → Deep Search returns verified solutions with context
- **Ubook**: Auto-enrich glossary — for each new term, fetch definition + examples from authoritative sources via Contents API

**Setup:**
```python
# Fast answer during lecture
response = you.express.chat(
    query="explain backpropagation with visual examples",
    include_citations=True
)

# Find practice problems for review
results = you.search.unified(
    query="binary tree practice problems with solutions",
    count=10, freshness="year"
)

# Debug an error during /work
results = you.search.deep(
    query='"TypeError: NoneType" pandas dataframe',
    count=5
)
```

**Pricing:** Free tier = 1,000 API calls for trial

---

# Architecture

```
Student → React Frontend (Render Static Site, FREE)
               ↓ WebSocket + REST
          FastAPI Backend (Render Web Service)
               ↓
     ┌─────────┼─────────────┐
     ↓         ↓             ↓
 Composio    You.com    PostgreSQL + pgvector
 (actions)   (search)   (Ubook knowledge base)
     ↓                       ↑
 Canvas, Notion,        Background Worker
 Calendar, GitHub       (embeddings, summaries)
```

---

# Demo Script (10 min)

**1. Setup (2 min):** "I'm taking CS 161 - Data Structures"
- Agent pulls syllabus from Canvas via Composio
- Auto-creates entire Ubook in Notion (lectures, assignments, glossary)
- Populates Calendar with all deadlines
- You.com enriches each topic with resources

**2. /lec Mode (3 min):** Live lecture on binary trees
- Type messy notes → agent auto-structures in Notion
- Ask "what's a balanced tree?" → You.com Express API answers in 2s with citations
- Agent links answer to glossary, adds to lecture notes
- Detects "Assignment 3 due Friday" → creates Calendar event

**3. /rev Mode (2 min):** "Quiz me on trees"
- Agent generates adaptive quiz from Ubook content
- Wrong answer on traversal → You.com finds visual animation matching learning style
- Updates knowledge vector: "arrays 95%, traversal 60%"
- Schedules spaced repetition review in Calendar

**4. /work Mode (3 min):** "Help with Assignment 3: Implement AVL tree"
- Composio opens assignment from Canvas, creates GitHub repo
- Student codes, hits bug → You.com Deep Search finds similar issues
- Agent guides fix without giving answer, runs tests via CodeInterpreter
- "Submit" → tests pass → Composio submits to Canvas, commits to GitHub

---

# Build Plan

**Priority 1 (MVP):** FastAPI + PostgreSQL/pgvector on Render, basic chat with You.com search
**Priority 2 (Core):** Composio integration (Notion for Ubook, Canvas for course data)
**Priority 3 (Polish):** WebSocket /lec mode, adaptive quizzing in /rev, CodeInterpreter in /work
**Priority 4 (Wow):** Progress dashboard, knowledge graph visualization, spaced repetition scheduling
