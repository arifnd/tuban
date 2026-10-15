# syntax=docker/dockerfile:1

# Build the application and its virtualenv with uv. The virtualenv lives in
# /opt/venv (not /app) so the runtime image is self-contained *and* the compose
# bind mount of the source tree over /app cannot shadow the dependencies.
FROM astral/uv:python3.12-trixie-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Install dependencies only, so this layer is cached unless pyproject/uv.lock change.
# This resolves the full `fastapi[standard]` set (uvicorn, jinja2, python-multipart,
# httpx, the OpenTelemetry SDK/exporter, and fastapi-cloud-cli).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy the project and install it (editable) into the virtualenv.
# Editable is required: PROJECT_ROOT / logging.ini are resolved relative to
# src/, so a non-editable install would look for templates under site-packages.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked


# Final image without uv. Must match the builder's Python image so the
# interpreter path baked into the virtualenv stays valid.
FROM python:3.12-slim-trixie

LABEL org.opencontainers.image.title="Tuban" \
      org.opencontainers.image.description="A knowledge base and ticketing web application." \
      org.opencontainers.image.source="https://github.com/arifnd/tuban" \
      org.opencontainers.image.url="https://arifnd.github.io/tuban/"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Drop privileges for the running application.
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

WORKDIR /app

# Virtualenv from the builder, then the application code. Everything that is
# not needed at runtime is kept out via .dockerignore.
COPY --link --from=builder --chown=nonroot:nonroot /opt/venv /opt/venv
COPY --link --chown=nonroot:nonroot . /app

RUN mkdir -p /app/instance /app/media \
 && chown -R nonroot:nonroot /app/instance /app/media

USER nonroot

EXPOSE 8000

# start-period is generous: importing the app also loads the OpenTelemetry
# instrumentation that `fastapi[standard]` brings in.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["/opt/venv/bin/python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"]

# `fastapi run` is uvicorn under the hood (reload off, 0.0.0.0), and resolves the
# app via the [tool.fastapi] entrypoint in pyproject.toml. `exec` so it becomes
# PID 1 and receives SIGTERM for a graceful shutdown.
CMD ["sh", "-c", "alembic upgrade head && exec fastapi run --host 0.0.0.0 --port 8000"]
