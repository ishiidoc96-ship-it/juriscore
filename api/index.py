import sys
import os
import logging
import asyncio
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("juriscore")

_backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

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


# Init DB tables at module level
try:
    from models.database import engine, Base

    async def _init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_init_db())
        else:
            loop.run_until_complete(_init_db())
    except RuntimeError:
        asyncio.run(_init_db())
except Exception as e:
    logger.error(f"Database init failed at module level: {traceback.format_exc()}")


# Init AI service at module level
try:
    from services import ai_service
    ai_service.init_backend()
    logger.info("AI service initialized")
except Exception as e:
    logger.error(f"AI init failed at module level: {traceback.format_exc()}")


# Register routers
try:
    from routers import cases
    app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
    logger.info("Cases router loaded")
except Exception as e:
    logger.error(f"Failed to load cases router: {traceback.format_exc()}")

try:
    from routers import statutes
    app.include_router(statutes.router, prefix="/api/statutes", tags=["Statutes"])
    logger.info("Statutes router loaded")
except Exception as e:
    logger.error(f"Failed to load statutes router: {traceback.format_exc()}")

try:
    from routers import constitution
    app.include_router(constitution.router, prefix="/api/constitution", tags=["Constitution"])
    logger.info("Constitution router loaded")
except Exception as e:
    logger.error(f"Failed to load constitution router: {traceback.format_exc()}")

try:
    from routers import notebook
    app.include_router(notebook.router, prefix="/api/notebook", tags=["Notebook"])
    logger.info("Notebook router loaded")
except Exception as e:
    logger.error(f"Failed to load notebook router: {traceback.format_exc()}")

try:
    from routers import flashcards
    app.include_router(flashcards.router, prefix="/api/flashcards", tags=["Flashcards"])
    logger.info("Flashcards router loaded")
except Exception as e:
    logger.error(f"Failed to load flashcards router: {traceback.format_exc()}")

try:
    from routers import study
    app.include_router(study.router, prefix="/api/study", tags=["Study"])
    logger.info("Study router loaded")
except Exception as e:
    logger.error(f"Failed to load study router: {traceback.format_exc()}")

try:
    from routers import export
    app.include_router(export.router, prefix="/api/export", tags=["Export"])
    logger.info("Export router loaded")
except Exception as e:
    logger.error(f"Failed to load export router: {traceback.format_exc()}")

try:
    from routers import search
    app.include_router(search.router, prefix="/api/search", tags=["Search"])
    logger.info("Search router loaded")
except Exception as e:
    logger.error(f"Failed to load search router: {traceback.format_exc()}")

try:
    from routers import auth
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    logger.info("Auth router loaded")
except Exception as e:
    logger.error(f"Failed to load auth router: {traceback.format_exc()}")

try:
    from routers import bookmarks
    app.include_router(bookmarks.router, prefix="/api/bookmarks", tags=["Bookmarks"])
    logger.info("Bookmarks router loaded")
except Exception as e:
    logger.error(f"Failed to load bookmarks router: {traceback.format_exc()}")

try:
    from routers import gazettes
    app.include_router(gazettes.router, prefix="/api/gazettes", tags=["Gazettes"])
    logger.info("Gazettes router loaded")
except Exception as e:
    logger.error(f"Failed to load gazettes router: {traceback.format_exc()}")

try:
    from routers import tribunals
    app.include_router(tribunals.router, prefix="/api/tribunals", tags=["Tribunals"])
    logger.info("Tribunals router loaded")
except Exception as e:
    logger.error(f"Failed to load tribunals router: {traceback.format_exc()}")

try:
    from routers import workspaces
    app.include_router(workspaces.router, prefix="/api/workspaces", tags=["Workspaces"])
    logger.info("Workspaces router loaded")
except Exception as e:
    logger.error(f"Failed to load workspaces router: {traceback.format_exc()}")

try:
    from routers import history
    app.include_router(history.router, prefix="/api/history", tags=["History"])
    logger.info("History router loaded")
except Exception as e:
    logger.error(f"Failed to load history router: {traceback.format_exc()}")
