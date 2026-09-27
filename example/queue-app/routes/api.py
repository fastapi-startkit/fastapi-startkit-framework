from fastapi import APIRouter
from fastapi_startkit.logging import Logger
from tasks.example_task import send_welcome_email, process_data

public = APIRouter()


@public.get("/")
async def index():
    Logger.info("Welcome to FastAPI StartKit Queue Example!")
    return {
        "message": "Welcome to FastAPI StartKit Queue Example!",
        "version": "1.0.0",
        "docs": "/docs",
    }


@public.get("/health")
async def health():
    Logger.info("Health check passed")
    return {"status": "healthy"}


@public.post("/jobs/email")
async def dispatch_email(email: str, name: str):
    """Dispatch a welcome email job to the queue."""
    task = await send_welcome_email.kiq(email=email, name=name)
    Logger.info(f"Dispatched send_welcome_email task: {task.task_id}")
    return {"task_id": task.task_id, "status": "queued"}


@public.post("/jobs/process")
async def dispatch_process(payload: dict):
    """Dispatch a data processing job to the queue."""
    task = await process_data.kiq(payload=payload)
    Logger.info(f"Dispatched process_data task: {task.task_id}")
    return {"task_id": task.task_id, "status": "queued"}


@public.get("/jobs/{task_id}/result")
async def get_result(task_id: str):
    """Poll a task result by its task ID."""
    from bootstrap.application import app as startkit_app

    broker = startkit_app.make("broker")
    result = await broker.result_backend.get_result(task_id)

    if result is None:
        return {"task_id": task_id, "status": "pending"}

    return {
        "task_id": task_id,
        "status": "completed" if not result.is_err else "failed",
        "result": result.return_value,
    }
