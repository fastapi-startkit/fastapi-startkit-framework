from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from fastapi_startkit.vite import template

web = APIRouter()


@web.get("/", response_class=HTMLResponse)
async def index():
    return template("index.html")


@web.get("/api/health")
async def health():
    return {"status": "healthy"}
