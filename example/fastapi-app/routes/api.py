from fastapi import APIRouter

from fastapi_startkit.logging import Logger

public = APIRouter()


@public.get("/")
async def index():
    Logger.info("Welcome to FastAPI StartKit!")
    Logger.info("Version: 1.0.0")
    Logger.info("Docs: /docs")
    Logger.log("debug", "Debugging the application!")
    return {
        "message": "Welcome to FastAPI StartKit!",
        "version": "1.0.0",
        "docs": "/docs",
    }


@public.get("/health")
async def health():
    Logger.info("Health check passed")
    return {"status": "healthy"}
