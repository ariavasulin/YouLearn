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
