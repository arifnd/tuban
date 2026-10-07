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
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy the project and install it (editable) into the virtualenv.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked


# Final image without uv. Must match the builder's Python image so the
# interpreter path baked into the virtualenv stays valid.
FROM python:3.12-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Drop privileges for the running application.
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

WORKDIR /app

# Virtualenv from the builder, then the application code. Everything that is
# not needed at runtime is kept out via .dockerignore.
COPY --from=builder --chown=nonroot:nonroot /opt/venv /opt/venv
COPY --chown=nonroot:nonroot . /app

RUN mkdir -p /app/instance /app/media \
 && chown -R nonroot:nonroot /app/instance /app/media

USER nonroot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/opt/venv/bin/python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"]

CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
