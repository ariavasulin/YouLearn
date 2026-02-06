# YouLearn Backend Boilerplate Implementation Plan

## Overview

Set up a minimal Agno + FastAPI backend for YouLearn that reuses proven patterns from YouLab's Ralph server. The backend serves an OpenWebUI pipe, giving an AI agent access to the `classes/` workspace (read/write files, run shell commands). No database, no persistence layer, no PDF viewer — just a working agent loop.

## Current State

- `openwebui/` — Full OpenWebUI fork (SvelteKit), runs with `npm run dev`
- `classes/Math-104/` — LaTeX lecture notes, homework, explainers with Makefile
- No backend exists yet
- No Python project config

## Desired End State

A working agent accessible from OpenWebUI that can:
1. Read/write files in `classes/`
2. Run shell commands (e.g., `make` to compile LaTeX)
3. Stream responses via SSE

Verify by:
1. `make server` starts the backend on port 8200
2. `curl localhost:8200/health` returns `{"status": "ok"}`
3. OpenWebUI pipe connects and chat works end-to-end

## What We're NOT Doing

- No Dolt database / memory blocks
- No Honcho message persistence
- No background task system
- No PDF-in-artifact viewer (LaTeXTools)
- No Docker / sandbox
- No workspace sync
- No tests (hackathon)
- No linting/typecheck config (hackathon)

## Implementation Approach

Copy the minimal set of files from YouLab, strip out everything we don't need. Three files from YouLab become three files in YouLearn, plus config and packaging.

---

## Phase 1: Python Project Scaffolding

### Overview
Create the Python package structure and dependency config.

### Changes Required:

#### 1. `backend/pyproject.toml`
**File**: `backend/pyproject.toml` (new)

```toml
[project]
name = "youlearn"
version = "0.1.0"
description = "YouLearn AI backend"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
    "structlog>=24.1.0",
    "httpx>=0.27.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "agno>=1.4.5",
    "sse-starlette>=2.0.0",
]

[project.scripts]
youlearn-server = "youlearn.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/youlearn"]
```

#### 2. Directory structure
```
backend/
├── pyproject.toml
├── .env.example
├── .env              # (gitignored, copied from .env.example)
├── Makefile
└── src/
    └── youlearn/
        ├── __init__.py
        ├── config.py
        └── server.py
```

#### 3. `backend/src/youlearn/__init__.py`
**File**: `backend/src/youlearn/__init__.py` (new, empty)

---

## Phase 2: Config

### Overview
Minimal config — just OpenRouter credentials and workspace path.

### Changes Required:

#### 1. `backend/src/youlearn/config.py`
**File**: `backend/src/youlearn/config.py` (new)

Copied from `YouLab/src/ralph/config.py`, stripped to essentials:

```python
"""Configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """YouLearn configuration."""

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    # Workspace — where the agent reads/writes files
    workspace: str = str(Path(__file__).parent.parent.parent.parent / "classes")

    # Server
    host: str = "0.0.0.0"
    port: int = 8200

    model_config = {"env_prefix": "YOULEARN_", "env_file": _ENV_FILE}


@lru_cache
def get_settings() -> Settings:
    """Get settings singleton."""
    return Settings()
```

#### 2. `backend/.env.example`
**File**: `backend/.env.example` (new)

```bash
# YouLearn Backend Configuration
# Copy to .env and fill in your values

# OpenRouter API key (get from https://openrouter.ai/keys)
YOULEARN_OPENROUTER_API_KEY=

# Model (default: claude-sonnet-4)
# YOULEARN_OPENROUTER_MODEL=openai/gpt-4o-mini

# Workspace path (default: ../classes relative to backend/)
# YOULEARN_WORKSPACE=/Users/you/Git/YouLearn/classes
```

---

## Phase 3: Server

### Overview
FastAPI server with SSE streaming. Copied from `YouLab/src/ralph/server.py`, stripped to ~80 lines.

### Changes Required:

#### 1. `backend/src/youlearn/server.py`
**File**: `backend/src/youlearn/server.py` (new)

Key differences from Ralph's `server.py`:
- No lifespan (no Dolt, no scheduler, no Honcho)
- No memory blocks, no memory context building
- No `strip_agno_fields()` (not targeting Mistral)
- No Honcho persistence
- No CLAUDE.md reading (could add later)
- Tools: just `FileTools` + `ShellTools` from Agno built-ins

```python
"""YouLearn HTTP Backend Service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import uvicorn
from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from agno.tools.file import FileTools
from agno.tools.shell import ShellTools
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from youlearn.config import get_settings

log = structlog.get_logger()

app = FastAPI(title="YouLearn Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    user_id: str = ""
    chat_id: str = ""
    messages: list[ChatMessage]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "youlearn"}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    async def generate() -> AsyncGenerator[dict[str, Any], None]:
        settings = get_settings()
        workspace = Path(settings.workspace)

        agent = Agent(
            model=OpenRouter(
                id=settings.openrouter_model,
                api_key=settings.openrouter_api_key,
            ),
            tools=[
                ShellTools(base_dir=workspace),
                FileTools(base_dir=workspace),
            ],
            instructions=f"""You are a helpful AI study companion.
Your workspace is: {workspace}
You can read and write files, and execute shell commands within this workspace.
Be helpful, encouraging, and focused on the student's learning goals.""",
            markdown=True,
        )

        messages = request.messages
        if len(messages) <= 1:
            prompt = messages[-1].content if messages else ""
        else:
            history_parts = []
            for msg in messages[:-1]:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_parts.append(f"{role_label}: {msg.content}")
            history = "\n\n".join(history_parts)
            current_message = messages[-1].content
            prompt = f"Conversation so far:\n\n{history}\n\n---\n\nUser: {current_message}"

        try:
            yield {
                "event": "message",
                "data": json.dumps({"type": "status", "content": "Thinking..."}),
            }

            async for chunk in agent.arun(prompt, stream=True):
                if chunk.content:
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "message", "content": chunk.content}),
                    }

            yield {"event": "message", "data": json.dumps({"type": "done"})}

        except Exception as e:
            log.exception("chat_stream_error", error=str(e))
            yield {"event": "message", "data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(generate())


def main() -> None:
    settings = get_settings()
    log.info("starting_youlearn_server", port=settings.port)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
```

---

## Phase 4: Pipe

### Overview
Copy the OpenWebUI pipe from YouLab. Only change: name and default URL.

### Changes Required:

#### 1. `backend/pipe.py`
**File**: `backend/pipe.py` (new)

Copied from `YouLab/src/ralph/pipe.py` with changes:
- `name = "YouLearn"` (was "Ralph Wiggum")
- `YOULEARN_SERVICE_URL` valve name (was `RALPH_SERVICE_URL`)
- Docstring metadata updated
- Otherwise identical — the pipe protocol is the same

This file gets registered in OpenWebUI admin as a function/pipe.

---

## Phase 5: Makefile & Gitignore

### Overview
Convenience commands and ignore patterns.

### Changes Required:

#### 1. `backend/Makefile`
**File**: `backend/Makefile` (new)

```makefile
.PHONY: setup server

# Install dependencies
setup:
	uv sync

# Run the backend server
server:
	uv run youlearn-server
```

#### 2. Update `.gitignore`
**File**: `/Users/ariasulin/Git/YouLearn/.gitignore` (append)

Add at the top:
```
# Backend
backend/.env
backend/.venv/
```

---

## Phase 6: Copy API Key

### Overview
Copy the OpenRouter API key from YouLab's `.env` into `backend/.env`.

### Changes Required:

1. `cp backend/.env.example backend/.env`
2. Copy `RALPH_OPENROUTER_API_KEY` value from YouLab `.env` → `YOULEARN_OPENROUTER_API_KEY` in YouLearn `.env`

---

## File Summary

| Source (YouLab) | Target (YouLearn) | Changes |
|---|---|---|
| `src/ralph/config.py` | `backend/src/youlearn/config.py` | Strip to 3 env vars, rename prefix |
| `src/ralph/server.py` | `backend/src/youlearn/server.py` | Strip Dolt/Honcho/memory/LaTeX, ~80 lines |
| `src/ralph/pipe.py` | `backend/pipe.py` | Rename, change URL valve name |
| (new) | `backend/pyproject.toml` | Minimal deps |
| (new) | `backend/Makefile` | setup + server |
| (new) | `backend/.env.example` | 2 env vars |

## Verification

```bash
cd backend
make setup                          # Install deps
cp .env.example .env                # Create env file
# Fill in YOULEARN_OPENROUTER_API_KEY
make server                         # Start on :8200
curl localhost:8200/health          # Should return {"status":"ok","service":"youlearn"}
```

Then in OpenWebUI:
1. Admin → Functions → Add `pipe.py` content
2. Start a chat, select YouLearn pipe
3. Send a message, verify streaming response
