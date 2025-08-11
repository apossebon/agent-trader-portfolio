# Use an appropriate base image
FROM python:3.13-slim as base


WORKDIR /app
 
# Update and install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*
 
# install UV
RUN pip install uv

COPY * .

ENV PYTHONPATH="src:src"
ENV PATH="/app/.venv/bin:$PATH"
