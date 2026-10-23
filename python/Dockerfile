# The Refund Bot image: Python, uv and the app, with every dependency installed at build time.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .
RUN uv sync --frozen

EXPOSE 8000
ENTRYPOINT ["uv", "run", "--no-sync", "refund-bot"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
