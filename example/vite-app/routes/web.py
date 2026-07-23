from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from fastapi_startkit.application import app

web = APIRouter()


@web.get("/", response_class=HTMLResponse)
async def index(request: Request):
    templates = app().make("templates")
    return templates.TemplateResponse(request, "index.html")


@web.get("/api/health")
async def health():
    return {"status": "healthy"}
