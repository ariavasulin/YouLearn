# What's Reusable from YouLab for YouLearn Hackathon

**Date**: 2026-02-05
**Source Repo**: `/Users/ariasulin/Git/YouLab`
**Target Repo**: `/Users/ariasulin/Git/YouLearn`

## Executive Summary

YouLab is an introspective AI tutoring platform with a Ralph (Agno-based) backend serving OpenWebUI. For a 5-hour hackathon building a self-improving learning agent with LaTeX textbook generation, the following components are directly reusable:

| Component | Effort | Value | Verdict |
|-----------|--------|-------|---------|
| OpenWebUI Pipe | ~30 min | High | **Copy** |
| Agno + OpenRouter pattern | ~15 min | High | **Copy** |
| LaTeX Tools | ~20 min | Critical | **Copy** |
| File/Shell Tools | 0 min | High | **Use Agno built-in** |
| Dolt Database | Hours | Low for demo | **Skip** |
| Honcho Persistence | Hours | Low for demo | **Skip** |
| Background Tasks | Hours | Low for demo | **Skip** |

---

## Components to Reuse

### 1. OpenWebUI Pipe (`src/ralph/pipe.py`)

**What it does**: Bridges OpenWebUI frontend to your custom backend via SSE streaming.

**File**: `YouLab/src/ralph/pipe.py` (167 lines)

**Key functionality**:
- Extracts `user_id` and `chat_id` from OpenWebUI's `__user__` context
- Forwards requests to backend via HTTP POST
- Streams SSE responses back to OpenWebUI
- Handles errors and timeouts gracefully

**How to adapt**:
1. Copy the file to YouLearn
2. Change `RALPH_SERVICE_URL` valve to your backend URL (e.g., `http://localhost:8200`)
3. Register as a pipe/function in OpenWebUI admin

**Critical code sections**:
```python
# pipe.py:40-50 - Valve configuration
class Valves(BaseModel):
    RALPH_SERVICE_URL: str = Field(default="http://host.docker.internal:8200")
    REQUEST_TIMEOUT: int = Field(default=300)

# pipe.py:85-110 - Request forwarding
async with httpx.AsyncClient() as client:
    async with client.stream(
        "POST",
        f"{self.valves.RALPH_SERVICE_URL}/chat/stream",
        json=payload,
        timeout=self.valves.REQUEST_TIMEOUT,
    ) as response:
        async for line in response.aiter_lines():
            # Parse SSE and yield content
```

---

### 2. Agno Agent + OpenRouter Pattern (`src/ralph/server.py`)

**What it does**: Creates an Agno agent with OpenRouter for model flexibility.

**Key code** (`server.py:283-297`):
```python
from agno.agent import Agent
from agno.models.openrouter import OpenRouter

agent = Agent(
    model=OpenRouter(
        api_key=settings.openrouter_api_key,
        id=settings.openrouter_model,  # e.g., "anthropic/claude-sonnet-4"
    ),
    tools=tools,
    instructions=system_prompt,
    markdown=True,
)
```

**Why OpenRouter**: Single API key gives access to Claude, GPT-4, Gemini, Llama, etc. Good for hackathon flexibility.

**Minimal server pattern** (`server.py:167-200`):
```python
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    agent = Agent(...)

    async def generate():
        response = agent.run(request.messages[-1]["content"], stream=True)
        for chunk in response:
            if chunk.content:
                yield f"data: {json.dumps({'choices': [{'delta': {'content': chunk.content}}]})}\n\n"
        yield "data: [DONE]\n\n"

    return EventSourceResponse(generate())
```

---

### 3. LaTeX Tools (`src/ralph/tools/latex_tools.py`)

**What it does**: Compiles LaTeX to PDF and displays in OpenWebUI's artifact pane.

**File**: `YouLab/src/ralph/tools/latex_tools.py` (275 lines)

**This is critical for your textbook concept.**

**Key features**:
- `compile_latex_to_pdf()`: Takes LaTeX string, returns base64-encoded PDF
- `render_latex_document()`: Full document with preamble
- `render_latex_snippet()`: Quick math/formula rendering
- Embedded PDF viewer in OpenWebUI artifacts
- Uses `tectonic` for compilation (no TeX Live needed)

**Dependency**: `brew install tectonic`

**Key code sections**:
```python
# latex_tools.py:45-80 - PDF compilation
def compile_latex_to_pdf(latex_content: str, workspace: Path) -> tuple[bool, str, str]:
    """Compile LaTeX to PDF using tectonic."""
    tex_file = workspace / "document.tex"
    tex_file.write_text(latex_content)

    result = subprocess.run(
        ["tectonic", str(tex_file)],
        capture_output=True,
        text=True,
        cwd=workspace,
    )

    if result.returncode == 0:
        pdf_path = workspace / "document.pdf"
        pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode()
        return True, pdf_base64, ""
    return False, "", result.stderr

# latex_tools:150-180 - Artifact response for OpenWebUI
def create_pdf_artifact(pdf_base64: str, title: str) -> str:
    """Create HTML artifact with embedded PDF viewer."""
    return f'''
    <artifact type="application/pdf" title="{title}">
        <iframe src="data:application/pdf;base64,{pdf_base64}"
                width="100%" height="600px"></iframe>
    </artifact>
    '''
```

**How to use with Agno**:
```python
from ralph.tools.latex_tools import LaTeXTools

agent = Agent(
    model=OpenRouter(...),
    tools=[LaTeXTools(workspace=Path("./textbook"))],
    instructions="You build LaTeX textbooks...",
)
```

---

### 4. File Tools (Agno Built-in)

**No code to copy** - just use Agno's built-in tools.

```python
from agno.tools.file import FileTools

agent = Agent(
    tools=[FileTools(base_dir=Path("./textbook"))],
)
```

This gives your agent:
- `read_file(path)`: Read file contents
- `write_file(path, content)`: Write/create files
- `list_directory(path)`: List files in directory

**For your textbook**: Store chapters as `.tex` files, let agent read/write them.

---

## Components to Skip

### Dolt Database (`src/ralph/dolt.py`)

**What it is**: MySQL-compatible database with git-like versioning for memory blocks.

**Why skip for hackathon**:
- Requires Docker container
- Schema initialization
- Connection pool management
- Branch-based proposal system for edits

**Alternative**: Store textbook files on disk. Use `FileTools` to read/write. 5 hours isn't enough for versioned memory blocks.

---

### Honcho Message Persistence (`src/ralph/honcho.py`)

**What it is**: External service for storing conversation history and dialectic queries.

**Why skip for hackathon**:
- Requires another service
- API key for production
- Complex setup for demo value

**Alternative**: Use OpenWebUI's built-in chat history. Your textbook corpus persists in files anyway.

---

### Background Task System (`src/ralph/background/`)

**What it is**: Scheduler, executor, cron triggers for background agents.

**Why skip for hackathon**:
- Overkill for a demo
- Complex infrastructure
- Not visible to judges

**Alternative**: Make agents respond to prompts directly. Background improvement can be simulated.

---

## Recommended Hackathon Architecture

```
OpenWebUI (npm run dev on YouLearn)
    |
    | POST /chat/stream
    v
Pipe (copied from YouLab, registered as function)
    |
    | SSE
    v
FastAPI Backend (~100 lines)
    |
    v
Agno Agent + OpenRouter
    |-- FileTools (read/write textbook/*.tex)
    |-- LaTeXTools (compile to PDF)
    v
Textbook Files (./textbook/)
    |-- main.tex
    |-- chapters/
    |   |-- lecture-01.tex
    |   |-- lecture-02.tex
    |-- glossary.tex
    |-- appendix.tex
```

**Services needed**: Just OpenWebUI + your backend. No Docker for Dolt/Honcho.

---

## Files to Copy

### From YouLab to YouLearn

1. **`src/ralph/pipe.py`** → `backend/open_webui/functions/youlearn_pipe.py`
   - Change `RALPH_SERVICE_URL` default
   - Register in OpenWebUI admin

2. **`src/ralph/tools/latex_tools.py`** → `backend/youlearn/tools/latex_tools.py`
   - Self-contained, minimal deps
   - Needs `tectonic` installed

3. **Server pattern from `src/ralph/server.py`** → New `backend/youlearn/server.py`
   - Only need ~50-100 lines
   - Agent creation + SSE streaming

---

## Minimal Hackathon Server

```python
# backend/youlearn/server.py
import os
import json
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools.file import FileTools
from .tools.latex_tools import LaTeXTools

app = FastAPI()
WORKSPACE = Path("./textbook")
WORKSPACE.mkdir(exist_ok=True)

class ChatRequest(BaseModel):
    messages: list[dict]
    user_id: str = ""
    chat_id: str = ""

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    agent = Agent(
        model=OpenRouter(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            id="openai/gpt-4o-mini",
        ),
        tools=[
            FileTools(base_dir=WORKSPACE),
            LaTeXTools(workspace=WORKSPACE),
        ],
        instructions="""You are a study companion that builds a LaTeX textbook.

When the user shares lecture notes or asks questions:
1. Organize content into the textbook structure
2. Write/update .tex files in the textbook directory
3. Compile and show PDFs when requested

Textbook structure:
- main.tex (includes all chapters)
- chapters/lecture-XX.tex (one per lecture)
- glossary.tex (key terms)
- appendix.tex (supplementary material)
""",
        markdown=True,
    )

    async def generate():
        user_message = request.messages[-1]["content"]
        response = agent.run(user_message, stream=True)

        for chunk in response:
            if chunk.content:
                data = {"choices": [{"delta": {"content": chunk.content}}]}
                yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"

    return EventSourceResponse(generate())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8200)
```

---

## Setup Checklist

### Before Hackathon
- [ ] Copy `pipe.py` to YouLearn
- [ ] Copy `latex_tools.py` to YouLearn
- [ ] Create minimal server
- [ ] Install `tectonic` (`brew install tectonic`)
- [ ] Set `OPENROUTER_API_KEY` env var
- [ ] Test: `npm run dev` + `python server.py`

### Day of Hackathon
- [ ] Run OpenWebUI: `npm run dev`
- [ ] Run backend: `python -m youlearn.server`
- [ ] Focus on prompts and textbook schema

---

## Time Budget

| Task | Estimate |
|------|----------|
| Copy & adapt pipe | 30 min |
| Copy LaTeX tools | 10 min |
| Write minimal server | 30 min |
| Test integration | 30 min |
| **Infrastructure total** | **~1.5 hours** |
| Prompts & UX | 3.5 hours |

This leaves 3.5 hours for the actual hackathon innovation: prompts, textbook structure, and demo polish.
