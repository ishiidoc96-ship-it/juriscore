import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from .models.database import engine, Base
from .routers import (
    cases,
    statutes,
    constitution,
    notebook,
    flashcards,
    study,
    export,
    search,
)
from .services import ai_service

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Juriscore API...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    ai_service.init_backend()
    logger.info("Juriscore API ready")
    yield
    logger.info("Shutting down Juriscore API")


app = FastAPI(
    title="Juriscore API",
    description="Legal research companion for Kenyan law students.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "juriscore-api", "version": "1.0.0"}


@app.get("/")
async def root():
    return JSONResponse({"message": "Welcome to Juriscore API", "docs": "/docs"})


app.include_router(cases.router, prefix="/cases", tags=["Cases"])
app.include_router(statutes.router, prefix="/statutes", tags=["Statutes"])
app.include_router(constitution.router, prefix="/constitution", tags=["Constitution"])
app.include_router(notebook.router, prefix="/notebook", tags=["Notebook"])
app.include_router(flashcards.router, prefix="/flashcards", tags=["Flashcards"])
app.include_router(study.router, prefix="/study", tags=["Study"])
app.include_router(export.router, prefix="/export", tags=["Export"])
app.include_router(search.router, prefix="/search", tags=["Search"])
