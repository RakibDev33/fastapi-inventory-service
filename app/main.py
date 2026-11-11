import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api import router
from app.database import Base, create_db_engine, create_session_factory
from app.services import ConflictError, NotFoundError

DEFAULT_DATABASE_URL = "sqlite:///./inventory.db"


def create_app(database_url: str | None = None) -> FastAPI:
    engine = create_db_engine(database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Keeps the sample self-contained; a production service would run Alembic migrations instead.
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Inventory Service",
        version="1.0.0",
        summary="Products, stock levels and an auditable stock movement ledger.",
        lifespan=lifespan,
    )
    app.state.session_factory = create_session_factory(engine)
    app.include_router(router)

    @app.exception_handler(NotFoundError)
    async def not_found(request: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, error: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(error)})

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
