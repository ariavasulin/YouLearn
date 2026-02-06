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

# Copy dependency files first (cache layer)
COPY backend/pyproject.toml backend/uv.lock ./

# Install dependencies into .venv
RUN uv sync --frozen --no-dev

# Copy backend source
COPY backend/src/ src/

# Copy classes directory (baked into image, no persistent disk)
COPY classes/ /data/classes/

# Environment defaults for Render
ENV YOULEARN_WORKSPACE=/data/classes
ENV YOULEARN_HOST=0.0.0.0
ENV YOULEARN_PORT=10000

EXPOSE 10000

CMD ["uv", "run", "youlearn-server"]
