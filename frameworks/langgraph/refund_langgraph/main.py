"""The web app. Start it with ``refund-bot serve`` (or ``docker compose up``), then open http://localhost:8000/docs.

On start it prepares the database (creates the tables, adds the starting data). Every error answers with
``{"error": "..."}``: 400 bad input, 404 not found, 409 ticket not open, 503 database unavailable.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from starlette.exceptions import HTTPException

from .api.routes import data, health, scenarios, tickets
from .core.config import get_settings
from .db.session import database
from .services.tickets import TicketError


def create_app(sessions: sessionmaker[Session] | None = None) -> FastAPI:
    """Build the app. Tests pass their own ``sessions`` (an in-memory database)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.sessions = sessions or database(get_settings().database_url)
        yield

    app = FastAPI(title="Refund Bot", lifespan=lifespan,
                  description="A customer-support agent that reads tickets, refunds orders and emails customers.")
    for module in (health, tickets, data, scenarios):
        app.include_router(module.router)

    @app.exception_handler(TicketError)
    async def ticket_error(request: Request, exc: TicketError):
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def bad_input(request: Request, exc: RequestValidationError):
        return JSONResponse({"error": _describe(exc.errors()[0])}, status_code=400)

    @app.exception_handler(OperationalError)
    async def database_down(request: Request, exc: OperationalError):
        return JSONResponse({"error": f"database unavailable (check DATABASE_URL): {exc.orig}"}, status_code=503)

    @app.exception_handler(HTTPException)
    async def not_found(request: Request, exc: HTTPException):
        return JSONResponse({"error": exc.detail.lower() if isinstance(exc.detail, str) else "error"},
                            status_code=exc.status_code)

    return app


def _describe(error: dict) -> str:
    field = error["loc"][-1] if len(error["loc"]) > 1 else "body"
    if error["type"] == "missing":
        return f"{field} is required"
    if field == "body" and error["type"] in ("model_attributes_type", "dict_type"):
        return "the request body must be a JSON object (send it with Content-Type: application/json)"
    return f"{field}: {error['msg']}"


app = create_app()
