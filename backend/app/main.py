"""Application entrypoint:  uvicorn app.main:app --port 8000"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent.runtime import build_runtime
from .api.routes import router
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rt = build_runtime(
        inproc=False,
        checkpoint_path=settings.checkpoint_db,
        memory_path=settings.memory_db,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Invoice Agent API", version="1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware,
                       allow_origins=["http://localhost:5173", "http://localhost:8080"],
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    return app


app = create_app()