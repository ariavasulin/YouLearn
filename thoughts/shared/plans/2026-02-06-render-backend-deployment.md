# Render Backend Deployment Implementation Plan

## Overview

Deploy the YouLearn Python backend (FastAPI + Agno agent) to Render as a public web service, and wire up the OpenWebUI pipe to connect to it. The OpenWebUI instance is already deployed on Render (same account, `runtime: image` from ghcr.io, standard plan, Oregon region).

## Current State Analysis

- **OpenWebUI**: Deployed at `/tmp/openwebui-render` fork, `runtime: image` pulling `ghcr.io/open-webui/open-webui:v0.6.41`, standard plan, Oregon, Postgres DB
- **Backend**: No Dockerfile, no `render.yaml`. Runs locally via `uv run youlearn-server` on port 8200
- **Pipe**: `pipe.py` connects to backend via `YOULEARN_SERVICE_URL` valve (default `http://host.docker.internal:8200`). Registered manually in OpenWebUI Admin > Functions
- **Dependencies**: Python 3.11, uv/hatchling, TeX Live (pdflatex + makeindex), various Python packages
- **File I/O**: Agent reads/writes `.tex` files in `classes/Math-104/`. No persistent disk — content baked into Docker image from git, changes are ephemeral

### Key Discoveries:
- `config.py:25` — `workspace` default computed from `__file__` (won't work in container, must override via `YOULEARN_WORKSPACE`)
- `config.py:32` — Port defaults to 8200, Render expects 10000
- `server.py:44` — `load_dotenv` reads `.env` relative to `__file__` (fine in container, just won't find the file — env vars come from Render)
- `server.py:153-155` — `backend_url` used for PDF download links in compile_notes output. In production this needs to be the public Render URL
- `notebook_tools.py:297-306` — `compile_notes` shells out to `pdflatex` and `makeindex` — must be in the Docker image
- `pyproject.toml:16` — `composio>=0.11.0` dependency (large, pulls in many sub-deps)
- OpenWebUI render.yaml uses `runtime: image`, but for the backend we'll use `runtime: docker` (builds from Dockerfile in repo)

## Desired End State

- Backend running on Render as a public `web` service (standard plan, Oregon)
- Health check passing at `GET /health`
- Pipe in OpenWebUI connecting to the backend's public URL via SSE
- LaTeX compilation working (pdflatex + makeindex available in container)
- PDF serving working at `GET /pdf/Math-104/{filename}`
- `classes/Math-104/` baked into the Docker image (no persistent disk)
- All env vars (OpenRouter key, You.com key, Composio key) configured in Render dashboard

### Verification:
- `curl https://<backend-url>/health` returns `{"status": "ok", "service": "youlearn"}`
- Sending a chat message via OpenWebUI pipe gets a streamed response
- `/Lec` mode creates/writes `.tex` files and compiles to PDF
- PDF viewable at `https://<backend-url>/pdf/Math-104/Math-104-Notes.pdf`

## What We're NOT Doing

- No persistent disk (changes are ephemeral, reset on redeploy)
- No CI/CD pipeline (manual deploy via Render dashboard or git push)
- No authentication on the backend API (hackathon demo)
- No custom domain
- Not modifying the OpenWebUI fork/deployment
- Not using `pserv` (using public `web` for easier debugging)

## Implementation Approach

Three files to create, one file to modify:
1. `backend/Dockerfile` — Multi-stage build: Python 3.11 slim + TeX Live + uv dependencies
2. `render.yaml` — Render blueprint at repo root for the backend service
3. `backend/src/youlearn/config.py` — Add `backend_url` setting so PDF links work in production
4. After deploy: configure pipe valve URL in OpenWebUI admin UI

## Phase 1: Create Backend Dockerfile

### Overview
Create a Dockerfile that builds the backend with all dependencies including TeX Live for LaTeX compilation.

### Changes Required:

#### 1. `backend/Dockerfile` (new file)
**File**: `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim-bookworm

# Install TeX Live for pdflatex + makeindex
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ src/

# Copy classes directory (baked into image)
COPY ../classes /data/classes

# Set environment
ENV YOULEARN_WORKSPACE=/data/classes
ENV YOULEARN_HOST=0.0.0.0
ENV YOULEARN_PORT=10000

EXPOSE 10000

CMD ["uv", "run", "youlearn-server"]
```

**Note**: The `COPY ../classes` won't work because Docker can't copy from outside the build context. We have two options:
- **Option A**: Set `dockerContext` to the repo root in `render.yaml` and adjust paths
- **Option B**: Set the Dockerfile's build context to repo root, reference `backend/` paths

We'll use **Option A** — set `dockerContext: .` (repo root) and `dockerfilePath: ./backend/Dockerfile`, then all COPY paths are relative to repo root.

Revised Dockerfile with repo-root context:

```dockerfile
FROM python:3.11-slim-bookworm

# Install TeX Live for pdflatex + makeindex
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy backend dependency files (cache layer)
COPY backend/pyproject.toml backend/uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy backend source
COPY backend/src/ src/

# Copy classes directory (baked into image, no persistent disk)
COPY classes/ /data/classes/

# Environment
ENV YOULEARN_WORKSPACE=/data/classes
ENV YOULEARN_HOST=0.0.0.0
ENV YOULEARN_PORT=10000

EXPOSE 10000

CMD ["uv", "run", "youlearn-server"]
```

### Success Criteria:

#### Automated Verification:
- [x] `docker build -f backend/Dockerfile -t youlearn-backend .` completes successfully (run from repo root)
- [x] `docker run --rm youlearn-backend pdflatex --version` shows TeX Live version (2022/Debian)
- [x] `docker run --rm youlearn-backend makeindex --version` shows makeindex available
- [x] `docker run --rm -p 10000:10000 -e YOULEARN_OPENROUTER_API_KEY=test youlearn-backend` starts and `/health` returns ok

#### Manual Verification:
- [x] Image size is reasonable (< 2GB) — 755MB

**Implementation Note**: After completing this phase, test locally with `docker build` and `docker run` before proceeding.

---

## Phase 2: Create render.yaml

### Overview
Create a Render blueprint that deploys the backend as a public web service.

### Changes Required:

#### 1. `render.yaml` (new file at repo root)
**File**: `render.yaml`

```yaml
services:
  - type: web
    name: youlearn-backend
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    dockerContext: .
    plan: standard
    region: oregon
    healthCheckPath: /health
    envVars:
      - key: YOULEARN_OPENROUTER_API_KEY
        sync: false
      - key: YOULEARN_OPENROUTER_MODEL
        value: "openai/gpt-4o-mini"
      - key: YOULEARN_YOU_API_KEY
        sync: false
      - key: COMPOSIO_API_KEY
        sync: false
      - key: YOULEARN_BACKEND_URL
        sync: false
```

Notes:
- `sync: false` means "set manually in dashboard, not stored in yaml" — for API keys
- `YOULEARN_BACKEND_URL` will be set to the service's own public URL (e.g., `https://youlearn-backend.onrender.com`) after deploy, so PDF download links work
- Port, host, and workspace are baked into the Dockerfile ENV defaults (10000, 0.0.0.0, /data/classes)
- `dockerContext: .` means the build context is the repo root, allowing `COPY classes/` to work

### Success Criteria:

#### Automated Verification:
- [x] `render.yaml` is valid YAML (no syntax errors)

#### Manual Verification:
- [ ] Render dashboard shows the blueprint and creates the service
- [ ] Build completes on Render (may take 5-10 min first time due to TeX Live)
- [ ] Health check passes (green status in Render dashboard)
- [ ] `curl https://<backend-url>/health` returns `{"status": "ok", "service": "youlearn"}`

**Implementation Note**: Deploy via `https://dashboard.render.com/blueprint/new?repo=https://github.com/<org>/YouLearn`. After the service is created, set the `sync: false` env vars in the Render dashboard. Then set `YOULEARN_BACKEND_URL` to the service's public URL.

---

## Phase 3: Config — Add `backend_url` Setting

### Overview
The `compile_notes` tool generates PDF download links like `http://localhost:8200/pdf/Math-104/...`. In production, these need to use the public Render URL. Add a `backend_url` config setting.

### Changes Required:

#### 1. `backend/src/youlearn/config.py`
**File**: `backend/src/youlearn/config.py`
**Changes**: Add `backend_url` field to Settings

```python
class Settings(BaseSettings):
    """YouLearn configuration."""

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    # You.com Search API
    you_api_key: str = ""

    # Workspace — where the agent reads/writes files
    workspace: str = str(Path(__file__).parent.parent.parent.parent / "classes")

    # Active class (hardcoded for hackathon demo)
    active_class: str = "Math-104"

    # Server
    host: str = "0.0.0.0"
    port: int = 8200

    # Public URL for PDF download links (set in production)
    backend_url: str = ""

    model_config = {"env_prefix": "YOULEARN_", "env_file": _ENV_FILE, "extra": "ignore"}
```

#### 2. `backend/src/youlearn/server.py`
**File**: `backend/src/youlearn/server.py`
**Changes**: Use `settings.backend_url` when constructing NotebookTools, falling back to the local URL

Replace lines 153-156:
```python
        # Use configured backend_url for PDF links, fall back to local
        if settings.backend_url:
            backend_url = settings.backend_url
        else:
            backend_url = f"http://localhost:{settings.port}"
        tools = [NotebookTools(class_dir, backend_url=backend_url)]
```

### Success Criteria:

#### Automated Verification:
- [x] Server starts locally with no `YOULEARN_BACKEND_URL` set (falls back to localhost)
- [x] Setting `YOULEARN_BACKEND_URL=https://example.com` makes compile_notes return links with that URL

#### Manual Verification:
- [ ] After deploying, compile_notes returns `https://youlearn-backend.onrender.com/pdf/...` links

---

## Phase 4: Deploy & Wire Up Pipe

### Overview
Push code, deploy via Render, configure env vars, and update the pipe's service URL in OpenWebUI admin.

### Steps:

1. **Commit and push** the new Dockerfile, render.yaml, and config changes
2. **Deploy via Render Blueprint**: Go to `https://dashboard.render.com/blueprint/new?repo=https://github.com/<org>/YouLearn`
3. **Set env vars in Render dashboard**:
   - `YOULEARN_OPENROUTER_API_KEY` — your OpenRouter key
   - `YOULEARN_YOU_API_KEY` — your You.com API key
   - `COMPOSIO_API_KEY` — your Composio key (optional)
   - `YOULEARN_BACKEND_URL` — the service's own public URL (e.g., `https://youlearn-backend.onrender.com`)
4. **Wait for build + deploy** (first build may take 5-10 min)
5. **Verify health**: `curl https://youlearn-backend.onrender.com/health`
6. **Update pipe in OpenWebUI**:
   - Go to OpenWebUI Admin > Functions
   - Find the YouLearn pipe
   - Update the `YOULEARN_SERVICE_URL` valve to `https://youlearn-backend.onrender.com`
   - Save
7. **Test end-to-end**: Send a message in OpenWebUI, verify it streams through

### Success Criteria:

#### Automated Verification:
- [ ] `curl https://<backend-url>/health` returns 200

#### Manual Verification:
- [ ] Send a general chat message via OpenWebUI → get a streamed response
- [ ] Send `/Lec test lecture` → agent creates/writes `.tex` file
- [ ] Send compile request → PDF generated and viewable at `/pdf/Math-104/...`
- [ ] PDF link in chat response uses the public URL (not localhost)

---

## Troubleshooting Guide

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| Build fails on TeX Live install | Render out of memory during build | Ensure standard plan (2GB) |
| Health check fails | Port mismatch | Verify `YOULEARN_PORT=10000` in Dockerfile ENV |
| Pipe can't connect | Wrong URL in valve | Check `YOULEARN_SERVICE_URL` matches Render URL exactly |
| `pdflatex` not found at runtime | TeX Live not installed in image | Check Dockerfile `apt-get install` step |
| PDF links show `localhost` | `YOULEARN_BACKEND_URL` not set | Set it in Render dashboard to the public URL |
| `classes/` not found | Workspace path wrong | Verify `YOULEARN_WORKSPACE=/data/classes` in Dockerfile |
| OOM at runtime | Agent + TeX Live too large | Standard plan has 2GB, should be sufficient |
| Composio import fails | `COMPOSIO_API_KEY` not set or composio package too large | Optional — can skip for demo |

## References

- OpenWebUI render.yaml: `/tmp/openwebui-render/render.yaml`
- Render deployment research: `thoughts/shared/research/2026-02-06-render-deployment.md`
- Backend server: `backend/src/youlearn/server.py`
- Config: `backend/src/youlearn/config.py`
- Pipe: `backend/pipe.py`
- NotebookTools: `backend/src/youlearn/tools/notebook_tools.py`
