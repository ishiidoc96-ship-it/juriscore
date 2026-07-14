import sys
import os

# Add api/backend to path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("juriscore")

app = FastAPI(title="Juriscore API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "juriscore-api", "version": "1.0.0"}

@app.get("/api")
async def root():
    return JSONResponse({"message": "Welcome to Juriscore API", "docs": "/docs"})

# Lazy-load heavy modules after the app is created
@app.on_event("startup")
async def startup():
    logger.info("Juriscore API starting up...")
    try:
        from models.database import engine, Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    try:
        from routers import cases, statutes, constitution, notebook, flashcards, study, export
        app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
        app.include_router(statutes.router, prefix="/api/statutes", tags=["Statutes"])
        app.include_router(constitution.router, prefix="/api/constitution", tags=["Constitution"])
        app.include_router(notebook.router, prefix="/api/notebook", tags=["Notebook"])
        app.include_router(flashcards.router, prefix="/api/flashcards", tags=["Flashcards"])
        app.include_router(study.router, prefix="/api/study", tags=["Study"])
        app.include_router(export.router, prefix="/api/export", tags=["Export"])
        logger.info("All routers loaded")
    except Exception as e:
        logger.error(f"Router loading failed: {e}")

    try:
        from services import ai_service
        ai_service.init_backend()
        logger.info("AI service initialized")
    except Exception as e:
        logger.error(f"AI init failed: {e}")

    logger.info("Juriscore API ready")
