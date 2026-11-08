from fastapi import APIRouter

from fastapi_startkit.logging import Log

public = APIRouter()


@public.get("/")
async def index():
    Log.info("Welcome to FastAPI StartKit!")
    Log.info("Version: 1.0.0")
    Log.info("Docs: /docs")
    Log.log("debug", "Debugging the application!")
    return {
        "message": "Welcome to FastAPI StartKit!",
        "version": "1.0.0",
        "docs": "/docs",
    }


@public.get("/health")
async def health():
    Log.info("Health check passed")
    return {"status": "healthy"}
