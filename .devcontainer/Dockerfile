# Base stage with common dependencies
FROM python:3.13-slim as base

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock ./
COPY .env* ./

# Install dependencies
RUN uv venv && uv pip install -r pyproject.toml

# Full application stage
FROM base as app
COPY src/ src/
RUN uv sync
ENV PYTHONPATH="src:src"
ENV PATH="/app/.venv/bin:$PATH"

# MCP DuckDuckGo stage
FROM base as mcp_servers
COPY src/mcp_servers src/mcp_servers
COPY src/llm src/llm
RUN uv sync

ENV PYTHONPATH="src:src"
ENV PATH="/app/.venv/bin:$PATH"


