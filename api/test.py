import sys
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("juriscore")

logger.info("=== MINIMAL TEST START ===")
logger.info(f"Python: {sys.version}")
logger.info(f"CWD: {os.getcwd()}")
logger.info(f"File: {__file__}")
logger.info(f"Dir: {os.path.dirname(__file__)}")
logger.info(f"Files in api/: {os.listdir(os.path.dirname(__file__) or '.')}")
logger.info(f"Files in api/backend/: {os.listdir(os.path.join(os.path.dirname(__file__), 'backend')) if os.path.exists(os.path.join(os.path.dirname(__file__), 'backend')) else 'NOT FOUND'}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Juriscore Test")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "healthy", "test": True}

logger.info("=== MINIMAL TEST OK ===")
