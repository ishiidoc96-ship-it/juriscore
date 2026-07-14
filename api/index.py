import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from models.database import engine, Base
from routers import cases, statutes, constitution, notebook, flashcards, study, export
from services import ai_service

app = FastAPI(
    title="Juriscore API",
    description="Legal research companion for Kenyan law students.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    ai_service.init_backend()

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
