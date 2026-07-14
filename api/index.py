import sys
import os
import logging
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


@app.get("/api/diag")
async def diag():
    results = {"python": sys.version, "cwd": os.getcwd(), "backend_path": _backend_path, "sys_path": sys.path[:5], "imports": {}}

    for mod_name in ["models.database", "models.schemas", "services.scraper", "services.ai_service", "routers.cases", "routers.statutes", "routers.constitution", "routers.notebook", "routers.flashcards", "routers.study", "routers.export"]:
        try:
            __import__(mod_name)
            results["imports"][mod_name] = "OK"
        except Exception as e:
            results["imports"][mod_name] = f"FAIL: {e}"

    return results


# Register routers with detailed error tracking
_load_errors = {}

try:
    from routers import cases
    app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
    _load_errors["cases"] = "OK"
except Exception as e:
    _load_errors["cases"] = f"{type(e).__name__}: {e}"
    logger.error(f"Failed to load cases router: {traceback.format_exc()}")

try:
    from routers import statutes
    app.include_router(statutes.router, prefix="/api/statutes", tags=["Statutes"])
    _load_errors["statutes"] = "OK"
except Exception as e:
    _load_errors["statutes"] = f"{type(e).__name__}: {e}"
    logger.error(f"Failed to load statutes router: {traceback.format_exc()}")

try:
    from routers import constitution
    app.include_router(constitution.router, prefix="/api/constitution", tags=["Constitution"])
    _load_errors["constitution"] = "OK"
except Exception as e:
    _load_errors["constitution"] = f"{type(e).__name__}: {e}"
    logger.error(f"Failed to load constitution router: {traceback.format_exc()}")

try:
    from routers import notebook
    app.include_router(notebook.router, prefix="/api/notebook", tags=["Notebook"])
    _load_errors["notebook"] = "OK"
except Exception as e:
    _load_errors["notebook"] = f"{type(e).__name__}: {e}"
    logger.error(f"Failed to load notebook router: {traceback.format_exc()}")

try:
    from routers import flashcards
    app.include_router(flashcards.router, prefix="/api/flashcards", tags=["Flashcards"])
    _load_errors["flashcards"] = "OK"
except Exception as e:
    _load_errors["flashcards"] = f"{type(e).__name__}: {e}"
    logger.error(f"Failed to load flashcards router: {traceback.format_exc()}")

try:
    from routers import study
    app.include_router(study.router, prefix="/api/study", tags=["Study"])
    _load_errors["study"] = "OK"
except Exception as e:
    _load_errors["study"] = f"{type(e).__name__}: {e}"
    logger.error(f"Failed to load study router: {traceback.format_exc()}")

try:
    from routers import export
    app.include_router(export.router, prefix="/api/export", tags=["Export"])
    _load_errors["export"] = "OK"
except Exception as e:
    _load_errors["export"] = f"{type(e).__name__}: {e}"
    logger.error(f"Failed to load export router: {traceback.format_exc()}")


@app.get("/api/router-status")
async def router_status():
    return _load_errors


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan startup...")
    try:
        from models.database import engine, Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    try:
        from services import ai_service
        ai_service.init_backend()
        logger.info("AI service initialized")
    except Exception as e:
        logger.error(f"AI init failed: {e}")

    logger.info("Juriscore API ready")
    yield
    logger.info("Juriscore API shutting down")
