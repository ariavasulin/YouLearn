"""YouLearn HTTP Backend Service."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
import uvicorn
from agno.agent import Agent
from agno.models.openrouter import OpenRouter
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from youlearn.config import get_settings
from youlearn.context import build_context
from youlearn.factcheck import run_fact_check
from youlearn.modes import build_system_prompt, detect_mode
from youlearn.tools.notebook_tools import NotebookTools

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


@app.get("/pdf/{class_slug}/{filename}")
async def serve_pdf(class_slug: str, filename: str) -> FileResponse:
    """Serve a compiled PDF from the classes directory."""
    settings = get_settings()
    workspace = Path(settings.workspace)
    # Only allow .pdf files, no path traversal
    if not filename.endswith(".pdf") or "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    pdf_path = (workspace / class_slug / filename).resolve()
    if not str(pdf_path).startswith(str(workspace.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    async def generate() -> AsyncGenerator[dict[str, Any], None]:
        settings = get_settings()
        workspace = Path(settings.workspace)
        class_dir = workspace / settings.active_class

        # 1. Detect mode from latest message
        latest = request.messages[-1].content if request.messages else ""
        mode = detect_mode(latest)

        # 2. Parse hw_id for /Work mode
        hw_id = None
        if mode.name == "work" and mode.user_message:
            hw_match = re.match(r"(hw\d+)", mode.user_message.lower())
            if hw_match:
                hw_id = hw_match.group(1)

        # 3. Build context
        context = build_context(class_dir, mode.name, hw_id=hw_id)

        # 4. Build system prompt
        class_name = settings.active_class.replace("-", " ")
        system_prompt = build_system_prompt(mode.name, context, class_name)

        # 5. Create agent with NotebookTools
        backend_url = f"http://{settings.host}:{settings.port}"
        if settings.host == "0.0.0.0":
            backend_url = f"http://localhost:{settings.port}"
        agent = Agent(
            model=OpenRouter(
                id=settings.openrouter_model,
                api_key=settings.openrouter_api_key,
            ),
            tools=[NotebookTools(class_dir, backend_url=backend_url)],
            instructions=system_prompt,
            markdown=True,
        )

        # 6. Build the user prompt
        messages = request.messages
        if len(messages) <= 1:
            prompt = mode.user_message or "(session started)"
        else:
            history_parts = []
            for msg in messages[:-1]:
                role_label = "User" if msg.role == "user" else "Assistant"
                history_parts.append(f"{role_label}: {msg.content}")
            history = "\n\n".join(history_parts)
            prompt = f"Conversation so far:\n\n{history}\n\n---\n\nUser: {mode.user_message}"

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
