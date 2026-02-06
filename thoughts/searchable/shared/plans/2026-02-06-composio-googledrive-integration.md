# Composio Google Drive Integration — Implementation Plan

## Overview

Add Composio Google Drive tools to the Agno agent so students can import files from Google Drive into their notebook workspace. This is a hackathon MVP — Composio is a sponsor and we need to use them. Replaces the previously planned Google Calendar integration.

## Current State

- Agent lives in `backend/src/youlearn/server.py:60-74` with `ShellTools` + `FileTools`
- No Composio packages installed (`backend/pyproject.toml` has no composio dependency)
- No Composio API keys configured
- Build plan references Composio for Calendar — we're pivoting to Drive

## Desired End State

Student can say "grab my lecture slides from Google Drive" or paste a Drive link, and the agent:
1. Searches/downloads the file from Google Drive via Composio
2. Saves it to the class workspace
3. Can then read/process it with existing FileTools

Verified by: agent successfully downloads a file from Google Drive when given a link or search query.

## What We're NOT Doing

- Google Calendar integration (cut for now, can add later)
- Multi-user OAuth flow (CLI auth for demo is fine)
- File format conversion (agent uses existing tools to read downloaded files)
- Upload back to Drive
- The new `composio` v0.11 SDK (no Agno provider yet — use legacy `composio-agno`)

## Phase 1: Install + Auth Setup

### Overview
Get `composio-agno` installed and Google Drive OAuth connected for the demo account.

### Changes Required:

#### 1. Add dependency
**File**: `backend/pyproject.toml`

Add `composio-agno` to dependencies:
```toml
dependencies = [
    ...existing deps...
    "composio-agno>=0.7.0",
]
```

#### 2. Add env var to config
**File**: `backend/src/youlearn/config.py`

Add `composio_api_key` to Settings:
```python
class Settings(BaseSettings):
    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    # Composio
    composio_api_key: str = ""

    # Workspace
    workspace: str = str(Path(__file__).parent.parent.parent.parent / "classes")

    # Server
    host: str = "0.0.0.0"
    port: int = 8200

    model_config = {"env_prefix": "YOULEARN_", "env_file": _ENV_FILE}
```

Note: Composio SDK reads `COMPOSIO_API_KEY` from env directly (not prefixed). We store it in our Settings for documentation, but also need the unprefixed env var set. Simplest approach: set both `YOULEARN_COMPOSIO_API_KEY` (for our config) and `COMPOSIO_API_KEY` (for Composio SDK) in `.env`, OR just set `COMPOSIO_API_KEY` and don't bother with the prefixed version. For hackathon, just set `COMPOSIO_API_KEY` directly — skip adding it to our Settings class to avoid confusion.

**Revised**: Don't add to config.py. Just set `COMPOSIO_API_KEY` in `.env`. The Composio SDK reads it automatically.

#### 3. CLI auth for Google Drive

Run once on dev machine:
```bash
cd backend
uv run pip install composio-agno
composio login            # enter API key from composio.dev dashboard
composio add googledrive  # opens browser for Google OAuth
```

### Success Criteria:

#### Automated Verification:
- [x] `cd backend && uv sync` succeeds (dependency resolves)
- [x] `uv run python -c "from composio_agno import ComposioToolSet, Action, App; print('OK')"` works

#### Manual Verification:
- [ ] `composio add googledrive` completes OAuth flow successfully
- [ ] `COMPOSIO_API_KEY` is set in `.env`

---

## Phase 2: Wire Composio Tools into Agent

### Overview
Add Google Drive tools to the agent's tool list in server.py. Keep it to 3-4 targeted actions.

### Changes Required:

#### 1. Add Composio tools to agent creation
**File**: `backend/src/youlearn/server.py`

Add imports at top:
```python
from composio_agno import Action, ComposioToolSet
```

In the `generate()` function, create Composio toolset and add to agent:
```python
async def generate() -> AsyncGenerator[dict[str, Any], None]:
    settings = get_settings()
    workspace = Path(settings.workspace)

    # Composio Google Drive tools
    composio_toolset = ComposioToolSet()
    gdrive_tools = composio_toolset.get_tools(
        actions=[
            Action.GOOGLEDRIVE_FIND_FILE,
            Action.GOOGLEDRIVE_DOWNLOAD_A_FILE,
            Action.GOOGLEDRIVE_LIST_FILES_AND_FOLDERS,
        ]
    )

    agent = Agent(
        model=OpenRouter(
            id=settings.openrouter_model,
            api_key=settings.openrouter_api_key,
        ),
        tools=[
            ShellTools(base_dir=workspace),
            FileTools(base_dir=workspace),
            *gdrive_tools,
        ],
        instructions=f"""You are a helpful AI study companion.
Your workspace is: {workspace}
You can read and write files, execute shell commands, and access Google Drive.
When a user asks you to get a file from Google Drive, use the Google Drive tools to find and download it, then save it to the workspace.""",
        markdown=True,
    )
    # ...rest unchanged
```

#### 2. Handle Composio not being configured gracefully

If `COMPOSIO_API_KEY` isn't set, the agent should still work — just without Drive tools. Wrap the Composio setup:

```python
# Composio Google Drive tools (optional — needs COMPOSIO_API_KEY)
gdrive_tools = []
try:
    composio_toolset = ComposioToolSet()
    gdrive_tools = composio_toolset.get_tools(
        actions=[
            Action.GOOGLEDRIVE_FIND_FILE,
            Action.GOOGLEDRIVE_DOWNLOAD_A_FILE,
            Action.GOOGLEDRIVE_LIST_FILES_AND_FOLDERS,
        ]
    )
except Exception:
    log.warning("composio_not_configured", hint="Set COMPOSIO_API_KEY to enable Google Drive")

agent = Agent(
    ...
    tools=[
        ShellTools(base_dir=workspace),
        FileTools(base_dir=workspace),
        *gdrive_tools,
    ],
    ...
)
```

### Success Criteria:

#### Automated Verification:
- [x] `cd backend && uv run youlearn-server` starts without errors (with COMPOSIO_API_KEY set)
- [x] `cd backend && uv run youlearn-server` starts without errors (without COMPOSIO_API_KEY — graceful fallback)

#### Manual Verification:
- [ ] Send a chat message like "List my Google Drive files" → agent uses Composio tools and returns results
- [ ] Send a chat message like "Download the file called 'Lecture 3 Slides' from my Drive" → agent finds and downloads it

**Implementation Note**: After completing this phase and verifying the agent can list/download Drive files, pause for manual confirmation before proceeding.

---

## Phase 3: Update Build Plan + Demo Polish

### Overview
Update the build plan to reflect Drive instead of Calendar, and make sure the demo story works.

### Changes Required:

#### 1. Update build-plan.md
**File**: `thoughts/build-plan.md`

Replace all Google Calendar references with Google Drive:
- Architecture diagram: "Google Drive / File Import" instead of "Google Cal / Scheduling"
- Sponsor #3 section: describe Drive file import use case
- /End mode: remove calendar scheduling, replace with "import materials from Drive"
- Demo script: show importing a file from Drive instead of calendar event

#### 2. Agent instructions for demo
The agent instructions should mention the Drive capability clearly so the LLM knows to use it. The instructions in Phase 2 already cover this.

### Success Criteria:

#### Manual Verification:
- [ ] Demo flow works: student says "grab my CS 301 slides from Google Drive" → agent searches → downloads → confirms
- [x] Build plan accurately reflects the Drive integration

---

## Testing Strategy

### Manual Testing (hackathon — no automated tests):
1. Start server with `COMPOSIO_API_KEY` set
2. Send message: "What files do I have in Google Drive?" → verify list comes back
3. Upload a test PDF to Google Drive
4. Send message: "Download the file called 'test.pdf' from my Drive" → verify it downloads
5. Send message: "What's in the file you just downloaded?" → verify agent can read it with FileTools
6. Start server WITHOUT `COMPOSIO_API_KEY` → verify it still starts and works (just no Drive tools)

## Action Name Note

The exact `Action.GOOGLEDRIVE_*` enum names may differ from what's documented. If imports fail, inspect available actions at runtime:

```python
from composio_agno import Action
gdrive_actions = [a for a in dir(Action) if a.startswith("GOOGLEDRIVE")]
print(gdrive_actions)
```

Pick the closest matches to: find file, download file, list files.

## References

- Research: `thoughts/shared/research/2026-02-06-composio-agno-googledrive-integration.md`
- Composio Agno docs: https://docs.composio.dev/frameworks/agno
- Composio Google Drive toolkit: https://docs.composio.dev/toolkits/googledrive
- Current server: `backend/src/youlearn/server.py`
- Build plan: `thoughts/build-plan.md`
