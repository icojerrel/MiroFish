# =============================================================================
# Stage 1: Build frontend
# =============================================================================
# syntax=docker/dockerfile:1
# Supports: docker buildx build --platform linux/amd64,linux/arm64

# =============================================================================
# Stage 1: Build frontend
# =============================================================================
FROM node:18-alpine AS frontend-builder

WORKDIR /app

# Install frontend dependencies
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm ci && npm ci --prefix frontend

# Build production assets
COPY frontend/ ./frontend/
RUN npm run build
# Output: frontend/dist/


# =============================================================================
# Stage 2: Production backend
# =============================================================================
FROM python:3.11-slim

# System deps: only what's needed at runtime
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       curl \
       ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies (uv sync without --frozen so new deps are resolved)
COPY backend/pyproject.toml backend/uv.lock ./backend/
RUN cd backend && uv sync --no-dev

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend into location Flask will serve
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create uploads directory
RUN mkdir -p backend/uploads backend/uploads/simulations

# Optional: install Playwright for Scrapling dynamic mode
# Uncomment the next two lines if you need to scrape JS-heavy sites:
# RUN backend/.venv/bin/playwright install chromium --with-deps 2>/dev/null || true
# ENV SCRAPLING_BROWSER_PATH=/root/.cache/ms-playwright

EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:5001/health || exit 1

# Production: gunicorn with 4 worker threads
CMD ["backend/.venv/bin/gunicorn", \
     "--bind", "0.0.0.0:5001", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "300", \
     "--worker-class", "gthread", \
     "--chdir", "backend", \
     "run:create_wsgi_app()"]
