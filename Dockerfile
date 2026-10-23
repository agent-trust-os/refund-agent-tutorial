# One image with everything the tutorial needs: Python, uv and the Refund Bot.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY python ./python

# Install from the lock file at build time, so the container needs no network to run.
RUN cd python && uv sync --frozen

WORKDIR /app/python
EXPOSE 8000
ENTRYPOINT ["uv", "run", "--no-sync", "refund-bot"]
CMD ["--serve", "--host", "0.0.0.0", "--port", "8000"]
