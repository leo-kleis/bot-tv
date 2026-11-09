# syntax=docker/dockerfile:1

# ── Etapa 1: Compilación del Frontend con Vite (Rolldown) ──
FROM node:24-slim AS frontend-builder
WORKDIR /build
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml vite.config.js ./
COPY src/bot_tv/web/static ./src/bot_tv/web/static
RUN pnpm install --frozen-lockfile && pnpm run build

# ── Etapa 2: Runtime ligero de Python + Uvicorn + TwitchIO ──
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    APP_ENV=production \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8080

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
# Copiar el bundle optimizado generado por Vite en la etapa 1
COPY --from=frontend-builder /build/src/bot_tv/web/dist ./src/bot_tv/web/dist

RUN uv sync --frozen --no-dev && \
    useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["uv", "run", "--no-sync", "bot-tv"]
