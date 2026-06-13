---
name: inertia-controllers
description: Build server-side Inertia.js controllers with fastapi-startkit — Inertia.render(), 303 redirects, Form Request validation, database transactions, and resource serialization.
---

# Inertia Controllers

Inertia controllers render Vue/React/Svelte pages server-side using `Inertia.render()`. They follow the same resource-controller conventions as JSON-API controllers but return Inertia responses instead of JSON:API envelopes.

## Basic Inertia render

Use `Inertia.render(component, props)` to render a page component. The component path maps to your frontend file (e.g. `"Tasks/Index"` → `resources/js/Pages/Tasks/Index.vue`):

```python
from fastapi_startkit.inertia import Inertia

class TasksController:
    async def index(self) -> dict:
        tasks = await Task.paginate()
        return Inertia.render("Tasks/Index", {
            "tasks": [t.serialize() for t in tasks.result],
            "meta": {
                "current_page": tasks.current_page,
                "last_page": tasks.last_page,
                "per_page": tasks.per_page,
                "total": tasks.total,
            },
        })
```

## Resource serialization in Inertia props

Use `JsonResource` to produce consistent, hidden-field-safe serialization, then pass `.serialize()` dicts into the props dict:

```python
from fastapi_startkit.jsonapi import JsonResource

class TaskResource(JsonResource["Task"]):
    hidden = ["deleted_at", "internal_notes"]

class TasksController:
    async def show(self, task: int) -> dict:
        instance = await Task.find_or_fail(task)
        return Inertia.render("Tasks/Show", {
            "task": TaskResource(instance).serialize(),
        })
```

## Mutations with 303 redirects

After any write operation (store, update, destroy) redirect with `status_code=303` so the browser issues a GET request after the POST/PUT/DELETE. This prevents duplicate form submissions on page refresh:

```python
from fastapi.responses import RedirectResponse

class TasksController:
    async def store(self, data: TaskStoreRequest) -> RedirectResponse:
        await Task.create(data.model_dump())
        return RedirectResponse(url="/tasks", status_code=303)

    async def update(self, task: int, data: TaskUpdateRequest) -> RedirectResponse:
        instance = await Task.find_or_fail(task)
        payload = data.model_dump(exclude_unset=True)

        if "status" in payload and payload["status"] in ("completed", "cancelled"):
            payload.setdefault("completed_at", pendulum.now().isoformat())

        await instance.update(payload)
        return RedirectResponse(url=f"/tasks/{task}", status_code=303)

    async def destroy(self, task: int) -> RedirectResponse:
        instance = await Task.find_or_fail(task)
        await instance.subtasks().delete()   # delete children first — no orphaned rows
        await instance.delete()
        return RedirectResponse(url="/tasks", status_code=303)
```

## Form Requests (validation)

Declare incoming data as a Pydantic model (Form Request). FastAPI validates the payload before the controller method is called:

```python
from pydantic import BaseModel, Field
from typing import Optional

class TaskStoreRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    project_id: int
    due_at: Optional[str] = None

class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = None
    due_at: Optional[str] = None
```

Use `model_dump(exclude_unset=True)` for partial updates so only provided fields reach the ORM:

```python
await instance.update(data.model_dump(exclude_unset=True))
```

## Database transactions

Wrap multi-step writes in a transaction. Long-running jobs (email, webhooks, queued work) must be dispatched — not awaited inline — so the HTTP response is not blocked:

```python
from fastapi_startkit.masoniteorm import DB
from app.jobs import SendWelcomeEmail

class UsersController:
    async def store(self, data: UserStoreRequest) -> RedirectResponse:
        async with DB.transaction():
            user = await User.create(data.model_dump())
            await Profile.create({"user_id": user.id})

        SendWelcomeEmail(user.id).dispatch()   # queued — not awaited inline

        return RedirectResponse(url="/users", status_code=303)
```

## Error handling

Use `find_or_fail()` — never fetch and raise a manual 404. Catch only specific exceptions; never catch bare `Exception` alongside specific ones. Log failures with `Logger.error`:

```python
from fastapi_startkit.masoniteorm.exceptions import ModelNotFound
from fastapi_startkit.logging import Logger

class TasksController:
    async def edit(self, task: int) -> dict:
        try:
            instance = await Task.find_or_fail(task)
        except ModelNotFound:
            Logger.error(f"Task {task} not found")
            raise
        return Inertia.render("Tasks/Edit", {
            "task": TaskResource(instance).serialize(),
        })
```

## Complete controller example

```python
import pendulum
from fastapi.responses import RedirectResponse
from fastapi_startkit.inertia import Inertia
from fastapi_startkit.jsonapi import JsonResource
from fastapi_startkit.masoniteorm.exceptions import ModelNotFound
from fastapi_startkit.logging import Logger
from app.http.requests.task import TaskStoreRequest, TaskUpdateRequest
from app.models.Task import Task


class TaskResource(JsonResource["Task"]):
    hidden = ["deleted_at"]


class TasksController:
    async def index(self) -> dict:
        tasks = await Task.paginate()
        return Inertia.render("Tasks/Index", {
            "tasks": [TaskResource(t).serialize() for t in tasks.result],
            "meta": {
                "current_page": tasks.current_page,
                "last_page": tasks.last_page,
                "per_page": tasks.per_page,
                "total": tasks.total,
            },
        })

    async def create(self) -> dict:
        return Inertia.render("Tasks/Create", {})

    async def store(self, data: TaskStoreRequest) -> RedirectResponse:
        await Task.create(data.model_dump())
        return RedirectResponse(url="/tasks", status_code=303)

    async def show(self, task: int) -> dict:
        instance = await Task.find_or_fail(task)
        return Inertia.render("Tasks/Show", {
            "task": TaskResource(instance).serialize(),
        })

    async def edit(self, task: int) -> dict:
        instance = await Task.find_or_fail(task)
        return Inertia.render("Tasks/Edit", {
            "task": TaskResource(instance).serialize(),
        })

    async def update(self, task: int, data: TaskUpdateRequest) -> RedirectResponse:
        instance = await Task.find_or_fail(task)
        payload = data.model_dump(exclude_unset=True)

        if "status" in payload and payload["status"] in ("completed", "cancelled"):
            payload.setdefault("completed_at", pendulum.now().isoformat())

        await instance.update(payload)
        return RedirectResponse(url=f"/tasks/{task}", status_code=303)

    async def destroy(self, task: int) -> RedirectResponse:
        instance = await Task.find_or_fail(task)
        await instance.subtasks().delete()
        await instance.delete()
        return RedirectResponse(url="/tasks", status_code=303)
```
