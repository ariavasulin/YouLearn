---
date: 2026-02-05T21:45:00-08:00
researcher: Ariav Asulin
git_commit: ed1b506
branch: main
repository: YouLearn
topic: "Hackathon Sponsor Integration Analysis for Self-Improving Learning Agent"
tags: [research, hackathon, sponsors, render, you-com, composio, plivo, akash, agi-api]
status: complete
last_updated: 2026-02-05
last_updated_by: Ariav Asulin
---

# Research: Hackathon Sponsor Integration Analysis

**Date**: 2026-02-05T21:45:00-08:00
**Researcher**: Ariav Asulin
**Git Commit**: ed1b506
**Branch**: main
**Repository**: YouLearn

## Research Question

Which 3 hackathon sponsors should we integrate for a 5-hour hackathon building a self-improving learning agent with OpenWebUI frontend and Agno backend?

## Project Context

**Core Product Concept**: Self-improving learning agent that:
- Takes lecture notes in real-time and codes them into LaTeX
- Maintains a growing "textbook" per class with predefined schema
- Has background agents continuously improving the corpus
- Supports study sessions where users upload assignments
- May include appendix, glossary, and study session logs

**Tech Stack**:
- Frontend: OpenWebUI
- Backend: Agno (Python)
- Output: LaTeX textbook corpus

## Summary

**Recommended Stack (3 sponsors)**:
1. **Render** - Deployment infrastructure (easiest, most natural fit)
2. **You.com** - Web research API for enriching lecture content with citations
3. **TBD** - Third sponsor requires trade-off between Composio, AGI API, or Plivo

The third sponsor is the hardest choice. None of the remaining options (Composio, AGI API, Plivo) feel like core value-adds—they're checkbox integrations to satisfy the "3 sponsors" requirement.

---

## Detailed Findings

### 1. Render (RECOMMENDED)

**What It Is**: Cloud platform for deploying web apps, APIs, and background workers.

**Prize**:
- 1st: $1,000 credits
- 2nd: $400 credits
- 3rd: $200 credits

**Why It Fits**:
- You need to deploy somewhere anyway
- Supports FastAPI/Agno backend natively
- Background workers for LaTeX compilation
- Cron jobs for scheduled "textbook evolution"
- Redis (Key Value) for task queues
- Infrastructure-as-Code via `render.yaml` blueprint

**Integration Effort**: Low (~30 mins)

**Key Features to Use**:
| Feature | Use Case |
|---------|----------|
| Web Service | FastAPI/Agno backend |
| Static Site | OpenWebUI frontend |
| Background Worker | LaTeX compilation jobs |
| Cron Job | Scheduled textbook improvements |
| Redis | Task queue for background agents |

**render.yaml Example**:
```yaml
services:
  - type: web
    name: youlearn-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: OPENROUTER_API_KEY
        sync: false

  - type: worker
    name: latex-compiler
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python worker.py

  - type: redis
    name: youlearn-cache
    plan: free
```

**Documentation**:
- [Render Docs](https://docs.render.com/)
- [render.yaml Reference](https://docs.render.com/blueprint-spec)
- [Python on Render](https://docs.render.com/deploy-python)

---

### 2. You.com Search API (RECOMMENDED)

**What It Is**: Web search API optimized for AI agents with $100 free credits (~16,000 searches).

**Prize**: $50 Amazon Gift Card per team member + $200 API credits

**Why It Fits**:
- Enriches lecture notes with real-world research
- Adds citations and authoritative sources to textbook
- Background agents can research topics to improve content
- Natural fit for "self-improving" aspect

**Integration Effort**: Medium (~1 hour)

**Key Endpoints**:
| Endpoint | Purpose |
|----------|---------|
| `/search` | General web search |
| `/news` | Recent news on topics |
| `/rag` | RAG-optimized search for AI agents |

**Python Example**:
```python
import requests

def research_topic(topic: str) -> dict:
    """Research a topic using You.com API."""
    response = requests.get(
        "https://api.ydc-index.io/search",
        params={"query": topic},
        headers={"X-API-Key": YOU_API_KEY}
    )
    return response.json()

# Use in lecture note generation
def enrich_lecture_notes(raw_notes: str, topics: list[str]) -> str:
    """Add citations and context to lecture notes."""
    enrichments = []
    for topic in topics:
        research = research_topic(topic)
        enrichments.append({
            "topic": topic,
            "sources": research.get("hits", [])[:3]
        })
    # Pass to LLM to integrate citations
    return generate_enriched_notes(raw_notes, enrichments)
```

**Documentation**:
- [You.com API Docs](https://documentation.you.com/)
- [Search API Reference](https://documentation.you.com/api-reference/)
- [Python SDK](https://github.com/You-com/you-python)

---

### 3. Composio (CONDITIONAL)

**What It Is**: Integration platform with 500+ pre-built tool integrations for AI agents.

**Prize**: $1,000 cash + $2,000 credits

**Honest Assessment**: Feels bolted-on rather than core to the product. Google Docs export or Calendar scheduling doesn't add fundamental value to a learning agent.

**Potential Use Cases**:
| Use Case | Integration | Value-Add |
|----------|-------------|-----------|
| Export notes | Google Docs | Low - PDF/LaTeX already exists |
| Schedule review | Google Calendar | Medium - spaced repetition |
| Sync to Notion | Notion | Low - not core |
| Send reminders | Slack/Discord | Medium - study nudges |

**If You Use It - Best Option**: Google Calendar for spaced repetition
```python
from composio import Composio

composio = Composio(api_key=COMPOSIO_API_KEY)

# After study session, schedule next review
result = composio.tools.execute(
    slug="GOOGLECALENDAR_CREATE_EVENT",
    arguments={
        "summary": f"Review: {topic}",
        "start": next_review_date.isoformat(),
        "end": (next_review_date + timedelta(hours=1)).isoformat(),
        "description": "Spaced repetition review session"
    },
    user_id="default"
)
```

**Integration Effort**: Medium (~1-2 hours)

**Documentation**:
- [Composio Docs](https://docs.composio.dev/docs)
- [Python SDK](https://docs.composio.dev/python/python-sdk-reference)
- [Google Calendar Tools](https://docs.composio.dev/toolkits/googlecalendar)

---

### 4. AGI API (CONDITIONAL)

**What It Is**: Browser automation API for AI agents from AGI, Inc.

**Prize**: $1,000 cash

**What It Does**:
- Web navigation, form filling, data extraction
- Natural language task execution
- Real-time monitoring via VNC

**Potential Use Cases**:
| Use Case | How | Risk Level |
|----------|-----|------------|
| Scrape course syllabus | Auto-navigate Canvas/LMS | High |
| Gather lecture slides | Download from course site | High |
| Research citations | Multi-site data collection | Medium |

**Honest Assessment**: Higher risk, higher reward. Browser automation in a 5-hour hackathon is ambitious. Failure modes include:
- Auth issues with university sites
- Anti-scraping measures
- Debugging headless browser issues

**Python Example**:
```python
from pyagi import AGIClient

client = AGIClient(api_key=AGI_API_KEY)

with client.session("agi-0") as session:
    result = session.run_task(
        "Go to the MIT OpenCourseWare page for 6.006 and "
        "extract the lecture topics and reading list"
    )
    return result.extracted_data
```

**Integration Effort**: High (~2+ hours with debugging)

**Documentation**:
- [AGI API Docs](https://docs.agi.tech)
- [AGI SDK GitHub](https://github.com/agi-inc/agisdk)
- [AGI, Inc.](https://ai.theagi.company/)

---

### 5. Plivo (NOT RECOMMENDED)

**What It Is**: Voice and SMS API platform.

**Prize**: $250 gift cards + $250 Plivo credits

**Potential Use Cases**:
- Voice lecture transcription input
- Call-based study sessions
- SMS study reminders

**Why Not Recommended**:
- Building a voice agent is its own hackathon project
- Adds significant complexity
- Not core to the product vision
- 5 hours is not enough time

**If You Must**: Use for simple SMS reminders only
```python
import plivo

client = plivo.RestClient(auth_id=PLIVO_AUTH_ID, auth_token=PLIVO_AUTH_TOKEN)

# Send study reminder
client.messages.create(
    src=PLIVO_PHONE,
    dst=user_phone,
    text=f"Time to review: {topic}. Open YouLearn to start your session."
)
```

**Documentation**:
- [Plivo Docs](https://www.plivo.com/docs/)
- [Python SDK](https://www.plivo.com/docs/sms/quickstart/python/)

---

### 6. Akash (NOT RECOMMENDED)

**What It Is**: Decentralized compute marketplace.

**Prize**: Compute credits for hackers

**Why Not Recommended**:
- Decentralized deployment adds complexity
- Debugging provider issues could eat entire hackathon
- Render is far simpler and also a sponsor
- No clear advantage for this use case

---

## Architecture Recommendation

```
┌──────────────────────────────────────────────────────────┐
│                      Render                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ OpenWebUI   │  │ FastAPI/    │  │ Background      │  │
│  │ (Frontend)  │──│ Agno Agent  │──│ Worker (LaTeX)  │  │
│  └─────────────┘  └──────┬──────┘  └─────────────────┘  │
│                          │                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │               Redis (Task Queue)                 │    │
│  └─────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
    ┌──────────────┐               ┌──────────────┐
    │   You.com    │               │   Third      │
    │  Search API  │               │   Sponsor    │
    │  (research)  │               │   (TBD)      │
    └──────────────┘               └──────────────┘
```

---

## 5-Hour Time Budget

| Hour | Activity |
|------|----------|
| 0-1 | Set up Render (`render.yaml`), deploy skeleton FastAPI + OpenWebUI |
| 1-2 | Implement core prompts (lecture, study) with basic memory |
| 2-3 | Integrate You.com for research during lecture notes |
| 3-4 | Add third sponsor integration (Composio or minimal AGI API) |
| 4-5 | Polish, add LaTeX background worker, test full flow |

---

## Decision Matrix

| Sponsor | Fit | Effort | Risk | Prize | Recommendation |
|---------|-----|--------|------|-------|----------------|
| Render | 10/10 | Low | Low | $1,000 credits | **USE** |
| You.com | 9/10 | Medium | Low | $50 + credits | **USE** |
| Composio | 5/10 | Medium | Low | $1,000 cash | Maybe |
| AGI API | 6/10 | High | High | $1,000 cash | Maybe |
| Plivo | 3/10 | High | Medium | $500 total | Skip |
| Akash | 2/10 | High | High | Credits | Skip |

---

## Open Questions

1. **Third sponsor decision**: Should we pick Composio (simpler, lower value-add) or AGI API (riskier, potentially more impressive)?

2. **Google Calendar OAuth**: If using Composio for spaced repetition, can we get OAuth working in 5 hours?

3. **You.com rate limits**: Are $100 credits enough for a demo with multiple users?

4. **LaTeX compilation**: Do we need Tectonic on Render, or compile client-side?

---

## Code References

- YouLab LaTeX tools: `src/ralph/tools/latex_tools.py`
- Background task infrastructure: `src/ralph/background/`
- Agno agent setup: `src/ralph/server.py`
