FROM astral/uv:python3.12-trixie-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache -r pyproject.toml

FROM python:3.12-slim-trixie AS runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY alembic.ini /app/alembic.ini
COPY logging.ini /app/logging.ini
COPY alembic /app/alembic
COPY src /app/src
COPY templates /app/templates
COPY static /app/static
COPY scripts /app/scripts

RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p /app/instance /app/media && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["fastapi", "run", "src/main.py", "--port", "8000", "--proxy-headers"]
