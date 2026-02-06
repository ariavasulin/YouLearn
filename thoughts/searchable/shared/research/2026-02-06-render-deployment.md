# Render.com Deployment Research for YouLearn

**Date**: 2026-02-06
**Status**: Research complete

## Architecture Overview

YouLearn has three components to deploy:

| Component | Tech | Port | Description |
|-----------|------|------|-------------|
| **OpenWebUI** (frontend + backend) | SvelteKit + Python FastAPI | 8080 | Forked open-webui. Dockerfile builds frontend into static files, bundles with Python backend into single container |
| **YouLearn Backend** | Python FastAPI + Agno | 8200 | Custom AI agent server (modeled after YouLab's Ralph server) |
| **Database** | SQLite (OpenWebUI) / TBD | - | OpenWebUI uses SQLite by default, stored in `/app/backend/data` |

---

## Recommended Architecture: 2-Service Deployment

### Option A: Combined OpenWebUI Container + Separate YouLearn Backend (Recommended)

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  Render Web Service         │     │  Render Private Service     │
│  "youlearn-webui"           │     │  "youlearn-backend"         │
│                             │     │                             │
│  OpenWebUI Dockerfile       │────▶│  YouLearn Agent Server      │
│  (frontend + backend        │     │  (Agno + OpenRouter)        │
│   bundled, port 8080)       │     │  Port 8200                  │
│                             │     │                             │
│  Persistent Disk:           │     │  No disk needed             │
│  /app/backend/data (1GB)    │     │  (stateless - uses APIs)    │
└─────────────────────────────┘     └─────────────────────────────┘
```

**Why this is best:**
1. OpenWebUI's Dockerfile already bundles frontend + backend into one container — just use it as-is
2. In production, the frontend uses relative URLs (`''` base) so everything goes through the same origin on port 8080
3. The YouLearn backend is stateless (uses OpenRouter API, no local DB) so it doesn't need persistent storage
4. Private service for the backend means no public exposure, lower cost potential
5. OpenWebUI connects to YouLearn backend via a Pipe (like YouLab's Ralph pipe)

### Why NOT separate the frontend as a static site

The OpenWebUI frontend *could* be deployed as a static site (it uses `adapter-static`), but:
- The frontend uses relative API URLs in production (empty string base URL in `constants.ts:6-7`)
- Separating would require configuring CORS and absolute API URLs
- The official Dockerfile is designed for the combined pattern
- You'd have to modify the frontend code to point at an external API
- No cost savings: static sites are free on Render, but you still need the backend service

### Why NOT a 3-service split

- Adds complexity with no benefit
- OpenWebUI's architecture is designed as a monolith (frontend served by FastAPI)
- Extra service = extra cost and inter-service communication overhead

---

## Detailed Service Configuration

### Service 1: OpenWebUI (Web Service, Docker)

Uses the existing `openwebui/Dockerfile` which:
1. **Stage 1**: Builds SvelteKit frontend with `npm run build` → outputs to `/app/build`
2. **Stage 2**: Sets up Python 3.11, installs dependencies, copies frontend build, runs uvicorn on port 8080
3. FastAPI serves both the SPA (via `SPAStaticFiles` at `/`) and API endpoints (at `/api/v1/...`)

**Key details from Dockerfile analysis:**
- Exposes port 8080
- Entry: `bash start.sh` which runs `uvicorn open_webui.main:app --host 0.0.0.0 --port 8080`
- Frontend build is copied to `/app/build`, served by `SPAStaticFiles` class
- Health check: needs `/health` or similar endpoint
- Data directory: `/app/backend/data` (SQLite DB, uploads, etc.)

**Render config:**
- Type: `web`
- Runtime: `docker`
- Plan: `starter` ($7/mo) minimum — needed for persistent disk
- Disk: mount at `/app/backend/data` for SQLite + uploads
- Build args: `USE_OLLAMA=false`, `USE_SLIM=true` (skip ML model downloads to reduce image size)
- Health check: `/health` (OpenWebUI has this)

### Service 2: YouLearn Backend (Private Service, Docker)

Modeled after YouLab's Ralph server pattern:
- FastAPI + Agno agent + OpenRouter for LLM inference
- SSE streaming responses at `/chat/stream`
- Health check at `/health`
- Connected to OpenWebUI via a Pipe

**Render config:**
- Type: `pserv` (private service — not publicly accessible)
- Runtime: `docker`
- Plan: `starter` ($7/mo)
- No disk needed (stateless)
- Communicates with OpenWebUI over Render's private network

### Communication Pattern

Following YouLab's proven pattern:
1. User sends message in OpenWebUI chat
2. OpenWebUI invokes the YouLearn Pipe (installed as a function/pipe in OpenWebUI)
3. Pipe makes HTTP POST to `http://youlearn-backend:8200/chat/stream` (internal hostname)
4. YouLearn backend streams SSE events back through the Pipe to the frontend

The Pipe code (based on `YouLab/src/ralph/pipe.py`) connects to the backend using the `RALPH_SERVICE_URL` valve, which on Render would be the internal hostname.

---

## render.yaml Blueprint

```yaml
services:
  # OpenWebUI: Frontend + Backend combined (official Dockerfile pattern)
  - type: web
    name: youlearn-webui
    runtime: docker
    repo: https://github.com/YOUR_ORG/YouLearn.git
    dockerfilePath: ./openwebui/Dockerfile
    dockerContext: ./openwebui
    plan: starter
    region: oregon
    healthCheckPath: /health
    buildFilter:
      paths:
        - openwebui/**
    envVars:
      - key: WEBUI_SECRET_KEY
        generateValue: true
      - key: ENABLE_SIGNUP
        value: "false"
      # Point to YouLearn backend via private network
      - key: YOULEARN_BACKEND_URL
        fromService:
          name: youlearn-backend
          type: pserv
          property: hostport
      # OpenAI-compatible API (OpenRouter)
      - key: OPENAI_API_BASE_URL
        value: "https://openrouter.ai/api/v1"
      - key: OPENAI_API_KEY
        sync: false  # Set manually, not stored in repo
      - fromGroup: youlearn-shared
    disk:
      name: webui-data
      mountPath: /app/backend/data
      sizeGB: 1

  # YouLearn Backend: Custom Agno agent server
  - type: pserv
    name: youlearn-backend
    runtime: docker
    repo: https://github.com/YOUR_ORG/YouLearn.git
    dockerfilePath: ./backend/Dockerfile   # You'll create this
    dockerContext: ./backend
    plan: starter
    region: oregon
    envVars:
      - key: OPENROUTER_API_KEY
        sync: false
      - key: OPENROUTER_MODEL
        value: "openai/gpt-4o-mini"
      - fromGroup: youlearn-shared

envVarGroups:
  - name: youlearn-shared
    envVars:
      - key: ENVIRONMENT
        value: production
```

---

## Environment Variables

### OpenWebUI Service

| Variable | Required | Description | How to set |
|----------|----------|-------------|------------|
| `WEBUI_SECRET_KEY` | Yes | Session encryption | `generateValue: true` |
| `ENABLE_SIGNUP` | No | Allow public signups | `"false"` for private |
| `OPENAI_API_KEY` | Yes* | OpenRouter API key for direct model access | `sync: false` |
| `OPENAI_API_BASE_URL` | Yes* | OpenRouter endpoint | `https://openrouter.ai/api/v1` |
| `WEBUI_URL` | No | Public URL of the instance | Set to Render URL |
| `USE_OLLAMA` | No | Disable Ollama | `"false"` |
| `DATA_DIR` | No | Data directory path | Default `/app/backend/data` |

*If using OpenRouter directly from OpenWebUI for some models.

### YouLearn Backend Service

| Variable | Required | Description | How to set |
|----------|----------|-------------|------------|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key | `sync: false` |
| `OPENROUTER_MODEL` | No | Default model | `openai/gpt-4o-mini` |
| `PORT` | No | Server port | `8200` |

---

## Cost Analysis

### Free Tier (Not recommended for production)

| What | Limit | Problem |
|------|-------|---------|
| 750 instance hours/month | Shared across all services | 2 services = ~375 hrs each = ~15.6 days. **Not enough for always-on.** |
| 512 MB RAM per service | | OpenWebUI Docker image is heavy (~1.5GB+); may OOM |
| No persistent disk | | SQLite DB and uploads lost on every redeploy/spin-down |
| Spins down after 15 min | | 50-70s cold start, terrible UX |
| No private services | | Backend would need public exposure |

**Verdict**: Free tier is only viable for demos with a single service (OpenWebUI only, no custom backend).

### Starter Tier ($14/month total)

| Service | Plan | Cost | RAM | CPU |
|---------|------|------|-----|-----|
| OpenWebUI (web) | Starter | $7/mo | 512 MB | 0.5 |
| YouLearn Backend (pserv) | Starter | $7/mo | 512 MB | 0.5 |
| Persistent Disk (1GB) | - | $0.25/mo | - | - |
| **Total** | | **$14.25/mo** | | |

**Risk**: 512 MB may be tight for OpenWebUI. The Docker image includes sentence-transformer models (~500MB). Using `USE_SLIM=true` build arg skips these downloads.

### Standard Tier ($50/month total) — Recommended

| Service | Plan | Cost | RAM | CPU |
|---------|------|------|-----|-----|
| OpenWebUI (web) | Standard | $25/mo | 2 GB | 1 |
| YouLearn Backend (pserv) | Standard | $25/mo | 2 GB | 1 |
| Persistent Disk (1GB) | - | $0.25/mo | - | - |
| **Total** | | **$50.25/mo** | | |

### Mixed Tier ($32/month) — Good Compromise

| Service | Plan | Cost | RAM | CPU |
|---------|------|------|-----|-----|
| OpenWebUI (web) | Standard | $25/mo | 2 GB | 1 |
| YouLearn Backend (pserv) | Starter | $7/mo | 512 MB | 0.5 |
| Persistent Disk (1GB) | - | $0.25/mo | - | - |
| **Total** | | **$32.25/mo** | | |

The YouLearn backend is lightweight (just proxies to OpenRouter) so Starter is likely fine for it.

---

## Build Considerations

### OpenWebUI Docker Build

The Dockerfile is heavy — it:
1. Runs `npm ci --force` + `npm run build` (frontend)
2. Installs Python deps via `uv pip install`
3. Optionally downloads ML models (sentence-transformers, whisper, tiktoken)

**Optimizations for Render:**
- Use `USE_SLIM=true` build arg to skip ML model downloads (saves ~1GB+ and build time)
- Use `USE_OLLAMA=false` to skip Ollama installation
- Render has 10GB compressed image size limit — should be fine with slim build
- First build will be slow (~10-15 min); subsequent builds use layer cache

### YouLearn Backend Dockerfile

You'll need to create a Dockerfile for the YouLearn backend. Based on the YouLab Ralph pattern:

```dockerfile
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml .
RUN uv venv /app/.venv && uv pip install --python /app/.venv/bin/python .
COPY src/ src/

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8200
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8200/health')"
CMD ["python", "-m", "youlearn.server"]
```

---

## Key Differences from YouLab's Docker Compose Setup

| Aspect | YouLab (Docker Compose) | YouLearn (Render) |
|--------|------------------------|-------------------|
| Networking | Docker bridge network (`youlab`) | Render private network (automatic) |
| Service discovery | Container names (`dolt`, `ralph`) | Render internal hostnames (`youlearn-backend-xxxx`) |
| Port exposure | `127.0.0.1:3000:8080` (localhost only) | Public web service URL + private internal |
| External access | Cloudflare Tunnel | Render's built-in HTTPS + CDN |
| Database | Dolt (git-versioned MySQL) | SQLite (OpenWebUI default) or Render Postgres |
| Persistent storage | Docker volumes | Render persistent disk ($0.25/GB/mo) |
| Secrets | `.env.production` file | Render env vars with `sync: false` |
| Health checks | Docker HEALTHCHECK | Render health check path |
| Pipe connection | `http://host.docker.internal:8200` | `http://youlearn-backend:PORT` (private network) |

---

## Deployment Steps

### Initial Setup

1. **Push code to GitHub** (or connect Render to your repo)

2. **Create render.yaml** at repo root (see blueprint above)

3. **Deploy via Render Dashboard:**
   - Go to Blueprints → New Blueprint Instance
   - Connect your GitHub repo
   - Render reads `render.yaml` and creates all services
   - Set `sync: false` env vars when prompted (API keys, etc.)

4. **Install the YouLearn Pipe in OpenWebUI:**
   - After OpenWebUI is running, go to Admin → Functions
   - Add the pipe that connects to the YouLearn backend
   - Set `RALPH_SERVICE_URL` valve to the internal hostname

### Alternative: Manual Setup (No render.yaml)

1. Create Web Service → Docker → point to `openwebui/Dockerfile`
2. Create Private Service → Docker → point to `backend/Dockerfile`
3. Add persistent disk to web service
4. Configure env vars manually
5. Install pipe after both services are running

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| OpenWebUI OOMs on Starter (512MB) | Service crashes | Use Standard plan or `USE_SLIM=true` to reduce memory |
| SQLite on persistent disk = no scaling | Can't add instances | Acceptable for single-user/small team. Migrate to Postgres if needed |
| Render persistent disk prevents zero-downtime deploys | Brief downtime on deploy | Schedule deploys during low-traffic times |
| Cold starts on free tier | 50-70s wait | Use paid tier (always-on) |
| Render build times for OpenWebUI | 10-15 min first build | Layer caching helps subsequent builds |
| Image size exceeds 10GB limit | Build fails | Use `USE_SLIM=true` and `USE_OLLAMA=false` build args |

---

## Open Questions

1. **Database choice**: Should YouLearn use OpenWebUI's default SQLite, or set up Render Postgres? SQLite is simpler but doesn't scale. For a single-instance deployment, SQLite on a persistent disk is fine.

2. **Pipe installation**: The YouLearn pipe needs to be installed in OpenWebUI after deployment. Should it be baked into the Docker image, or installed via the admin UI?

3. **Monorepo structure**: The `render.yaml` needs both services to come from the same repo. Render supports `dockerfilePath` and `dockerContext` for this, plus `buildFilter` to only rebuild when relevant files change.

4. **Custom domain**: Render provides `*.onrender.com` URLs. Custom domain setup is straightforward via Dashboard.

5. **Dolt**: YouLab uses Dolt for git-versioned memory blocks. If YouLearn needs this, it would require a separate service (Dolt isn't available as a managed service on Render) or an external Dolt instance. For MVP, skip Dolt.
