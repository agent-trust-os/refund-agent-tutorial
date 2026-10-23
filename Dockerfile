# One image with everything the tutorial needs: Python, uv, the shared core and the plain-Python agent.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY core ./core
COPY python ./python

# Install both environments at build time from the lock files, so the container needs no network to run.
RUN cd core && uv sync --frozen \
 && cd ../python && uv sync --frozen

WORKDIR /app/python
ENTRYPOINT ["uv", "run", "--no-sync", "python", "-m", "refund_bot"]
CMD ["--list"]
