# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# base: Python 3.14 + uv. The virtualenv lives in /opt/venv, outside /app, so
# the development bind mount of the project never shadows it.
# ---------------------------------------------------------------------------
FROM python:3.14-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:${PATH}" \
    IN_CONTAINER=1

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

WORKDIR /app

# ---------------------------------------------------------------------------
# dev: tooling for the Dev Container, Node for the asset pipeline, dev deps.
# node_modules is NOT installed here: it lives in the bind-mounted project
# (see `make npm`).
# ---------------------------------------------------------------------------
FROM base AS dev

RUN apt-get update \
    && apt-get install -y --no-install-recommends make git postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Same Debian release as the Python image, so the binary is ABI-compatible.
COPY --from=node:24-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
