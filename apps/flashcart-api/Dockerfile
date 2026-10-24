# FlashCart API container image (multi-stage, non-root, no dev dependencies).
# Build from apps/flashcart-api:  docker build -t flashcart-api .
# Debian 13 (trixie): fewer unfixed OS CVEs than Debian 12 (TS-019). Pinned by digest for reproducible builds.
ARG PYTHON_IMAGE=python:3.13-slim-trixie@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962
FROM ${PYTHON_IMAGE} AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.28 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first so code changes don't invalidate this layer. --frozen: the lockfile is the source of truth.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app

FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
# pip is not needed at runtime and its vendored urllib3/msgpack/setuptools carry CVEs (TS-019): remove it.
RUN python -m pip uninstall -y pip \
 && groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"]
# --proxy-headers: the API is only reachable through the web proxy on a private network (never published),
# so X-Forwarded-For from that proxy is trusted for per-client rate limiting.
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
