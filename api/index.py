import sys
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("juriscore")

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, os.path.abspath(backend_path))

logger.info(f"API starting. Backend path: {os.path.abspath(backend_path)}")
logger.info(f"Python version: {sys.version}")
logger.info(f"NVIDIA_API_KEY set: {bool(os.getenv('NVIDIA_API_KEY'))}")

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from contextlib import asynccontextmanager
    logger.info("FastAPI imports OK")
except Exception as e:
    logger.error(f"FastAPI import failed: {e}")
    raise

try:
    from models.database import engine, Base
    logger.info("Database module imported OK")
except Exception as e:
    logger.error(f"Database import failed: {e}")
    raise

try:
    from routers import cases, statutes, constitution, notebook, flashcards, study, export
    logger.info("All routers imported OK")
except Exception as e:
    logger.error(f"Router import failed: {e}")
    raise

try:
    from services import ai_service
    logger.info("AI service imported OK")
except Exception as e:
    logger.error(f"AI service import failed: {e}")
    raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan startup...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created OK")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    try:
        ai_service.init_backend()
        logger.info("AI service initialized OK")
    except Exception as e:
        logger.error(f"AI init failed: {e}")

    logger.info("Juriscore API ready")
    yield
    logger.info("Juriscore API shutting down")


app = FastAPI(
    title="Juriscore API",
    description="Legal research companion for Kenyan law students.",
    version="1.0.0",
    lifespan=lifespan,
)

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


app.include_router(cases.router, prefix="/api/cases", tags=["Cases"])
app.include_router(statutes.router, prefix="/api/statutes", tags=["Statutes"])
app.include_router(constitution.router, prefix="/api/constitution", tags=["Constitution"])
app.include_router(notebook.router, prefix="/api/notebook", tags=["Notebook"])
app.include_router(flashcards.router, prefix="/api/flashcards", tags=["Flashcards"])
app.include_router(study.router, prefix="/api/study", tags=["Study"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
