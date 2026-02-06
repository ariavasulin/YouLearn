---
date: 2026-02-06T12:00:00-08:00
researcher: ARI
git_commit: 99f510fa15fde61ce9d9137b6468017e35fec7d8
branch: main
repository: YouLearn
topic: "Composio + Agno integration for Google Drive file retrieval"
tags: [research, composio, agno, googledrive, integration]
status: complete
last_updated: 2026-02-06
last_updated_by: ARI
---

# Research: Composio + Agno Integration for Google Drive File Retrieval

**Date**: 2026-02-06
**Researcher**: ARI
**Git Commit**: 99f510fa15fde61ce9d9137b6468017e35fec7d8
**Branch**: main
**Repository**: YouLearn

## Research Question

How can we integrate Composio with the Agno agent to have tools for grabbing files from Google Drive links?

## Summary

Composio provides a dedicated `composio-agno` Python package (v0.7.20) that bridges Composio's 250+ app integrations into Agno-compatible tools. Google Drive has **51 actions** available. Integration requires: (1) adding `composio-agno` to dependencies, (2) setting a `COMPOSIO_API_KEY` env var, (3) connecting a Google account via OAuth, and (4) passing Composio tools alongside existing FileTools/ShellTools to the Agno Agent. The YouLearn backend currently has zero Composio code — it's a greenfield addition.

## Current State of the Codebase

### Existing Agent Setup (`backend/src/youlearn/server.py`)

The agent is created on each request with two tool sets:

```python
agent = Agent(
    model=OpenRouter(id=settings.openrouter_model, api_key=settings.openrouter_api_key),
    tools=[
        ShellTools(base_dir=workspace),
        FileTools(base_dir=workspace),
    ],
    instructions=f"""You are a helpful AI study companion...""",
    markdown=True,
)
```

No Composio packages are installed (`backend/pyproject.toml` has no composio dependency).
No Composio API keys are configured (`.env.example` only has `YOULEARN_OPENROUTER_API_KEY`).

### OpenWebUI Already Has Google Drive Picker

OpenWebUI has a complete Google Drive Picker integration for file uploads:
- `openwebui/src/lib/utils/google-drive-picker.ts` — frontend picker
- `openwebui/backend/open_webui/config.py` — `ENABLE_GOOGLE_DRIVE_INTEGRATION`, `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_API_KEY`

This is a **separate mechanism** from Composio — it uses Google's Picker API in the browser for file selection/upload. Composio would give the **agent** server-side access to Google Drive.

## The `composio-agno` Package

### Installation

```bash
pip install composio-agno
# This pulls in composio-core as a dependency
```

Add to `backend/pyproject.toml`:
```toml
dependencies = [
    ...
    "composio-agno>=0.7.0",
]
```

### Key Exports

```python
from composio_agno import (
    ComposioToolSet,  # Main class — wraps Composio tools for Agno
    Action,           # Enum of all actions (e.g., Action.GOOGLEDRIVE_FIND_FILE)
    App,              # Enum of all apps (e.g., App.GOOGLEDRIVE)
    Tag,              # For filtering tools by tag
)
```

### How It Works

1. `ComposioToolSet()` initializes using `COMPOSIO_API_KEY` env var
2. `get_tools(actions=[...])` fetches action schemas from Composio's API and wraps them as Agno-compatible tool objects
3. Tools are passed to `Agent(tools=[...])` alongside existing tools
4. When the LLM invokes a tool, the Composio callback executes the action via Composio's backend using stored OAuth tokens

## Google Drive Actions (Most Relevant for YouLearn)

Out of 51 total Google Drive actions, these are the most relevant for grabbing files:

| Action Slug | Purpose |
|-------------|---------|
| `GOOGLEDRIVE_FIND_FILE` | Search for files by name/query |
| `GOOGLEDRIVE_DOWNLOAD_FILE` | Download a file by its ID |
| `GOOGLEDRIVE_PARSE_FILE` | Export Google Docs/Sheets to PDF/text |
| `GOOGLEDRIVE_LIST_FILES` | Browse/search files and folders |
| `GOOGLEDRIVE_GET_FILE_METADATA` | Check file type, size, modification date |
| `GOOGLEDRIVE_FIND_FOLDER` | Navigate to specific course folders |
| `GOOGLEDRIVE_UPLOAD_FILE` | Upload files back to Drive (max 5MB) |

## Authentication Flow

### Step 1: Get Composio API Key

Sign up at composio.dev, get API key from Settings.

```bash
export COMPOSIO_API_KEY="your_key"
```

### Step 2: Connect Google Drive (Development — CLI)

```bash
pip install composio-agno
composio login
composio add googledrive   # Opens browser for OAuth consent
```

This creates a connection for the "default" entity (single-user dev mode).

### Step 3: Connect Google Drive (Production — Programmatic)

For multi-user (each student connects their own Drive):

```python
from composio_agno import ComposioToolSet, App

toolset = ComposioToolSet(entity_id="student-123")
entity = toolset.get_entity()

request = entity.initiate_connection(
    app_name=App.GOOGLEDRIVE,
    redirect_url="https://yourapp.com/callback"
)

# Send this URL to the student
print(f"Connect your Google Drive: {request.redirectUrl}")

# Wait for completion
connected_account = request.wait_until_active(timeout=60)
```

### Token Management

- Composio stores OAuth access/refresh tokens on their platform (encrypted)
- Tokens are automatically refreshed when they expire
- Each `entity_id` has separate connections
- `entity_id="default"` is used when none specified (fine for hackathon)

## Integration Code Example

### Minimal Integration into `server.py`

```python
from composio_agno import Action, ComposioToolSet

# In the generate() function, alongside existing tools:
composio_toolset = ComposioToolSet()
gdrive_tools = composio_toolset.get_tools(
    actions=[
        Action.GOOGLEDRIVE_FIND_FILE,
        Action.GOOGLEDRIVE_DOWNLOAD_FILE,
        Action.GOOGLEDRIVE_PARSE_FILE,
        Action.GOOGLEDRIVE_LIST_FILES,
    ]
)

agent = Agent(
    model=OpenRouter(id=settings.openrouter_model, api_key=settings.openrouter_api_key),
    tools=[
        ShellTools(base_dir=workspace),
        FileTools(base_dir=workspace),
        *gdrive_tools,  # Spread Composio tools into the list
    ],
    instructions=f"""You are a helpful AI study companion.
Your workspace is: {workspace}
You can read and write files, execute shell commands, and access Google Drive.""",
    markdown=True,
)
```

### Multi-User (Per-Student Drive Access)

```python
# Use the user_id from the chat request to scope Composio
composio_toolset = ComposioToolSet(entity_id=request.user_id)
gdrive_tools = composio_toolset.get_tools(actions=[...])
```

## Handling Google Drive Links

When a student pastes a Google Drive link like `https://drive.google.com/file/d/FILE_ID/view`, the flow is:

1. Agent extracts the file ID from the URL (regex: `/d/([a-zA-Z0-9_-]+)`)
2. Uses `GOOGLEDRIVE_DOWNLOAD_FILE` with that file ID
3. File is downloaded to the workspace
4. Agent processes the file (e.g., reads it, converts to LaTeX notes)

**Limitation**: All operations require an authenticated Google account. For truly public links, you could alternatively extract the file ID and use a direct HTTP download URL (`https://drive.google.com/uc?export=download&id=FILE_ID`) without Composio.

## Environment Changes Needed

### `backend/.env.example`

```
YOULEARN_OPENROUTER_API_KEY=your_openrouter_key
COMPOSIO_API_KEY=your_composio_key
```

### `backend/pyproject.toml`

```toml
dependencies = [
    ...
    "composio-agno>=0.7.0",
]
```

## SDK Note: Legacy vs New

There are two Composio SDK generations:

| | Legacy (`composio-agno`) | New (`composio` v0.11+) |
|---|---|---|
| Status | Stable, maintained | Preview |
| Agno support | Yes, dedicated package | No Agno provider yet |
| Install | `pip install composio-agno` | `pip install composio` |
| Terminology | Action, App, entity_id | Tool, Toolkit, user_id |

**Recommendation**: Use `composio-agno` (legacy) — it's the proven path for Agno integration. The new SDK doesn't have an Agno provider yet.

## Code References

- `backend/src/youlearn/server.py:60-74` — Current agent creation (where tools would be added)
- `backend/src/youlearn/config.py:14-28` — Settings class (add COMPOSIO_API_KEY here or use separate env var)
- `backend/pyproject.toml:6-17` — Dependencies list
- `backend/.env.example` — Environment template

## Sources

- [Using Composio With Agno - Composio Docs](https://docs.composio.dev/frameworks/agno)
- [Composio Tools - Agno Docs](https://docs.agno.com/examples/concepts/tools/others/composio)
- [Google Drive Toolkit - Composio Docs](https://docs.composio.dev/toolkits/googledrive)
- [composio-agno on PyPI](https://pypi.org/project/composio-agno/)
- [Authenticating Tools - Composio Docs](https://docs.composio.dev/docs/authenticating-tools)
- [Create & Manage Connections - Composio Docs](https://docs.composio.dev/patterns/Auth/connected_account)

## Open Questions

1. **Hackathon auth flow**: For demo purposes, should we just use `composio add googledrive` CLI to connect one account, or build the full OAuth redirect flow?
2. **File size limits**: Google Drive export limit is 10MB — will that be sufficient for student materials?
3. **Rate limits**: Composio's free tier may have rate limits that matter during a demo
4. **Download directory**: Where should Composio download files to? The agent workspace (`classes/`) or a temp directory?
5. **Public links without auth**: Should we add a fallback for public Drive links that bypasses Composio entirely (direct HTTP download)?
