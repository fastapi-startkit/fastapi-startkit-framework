---
name: fastapi
description: Define HTTP routes and RESTful resource controllers with the fastapi-startkit Router — covers verb methods, auth grouping, resource() shortcut, and the canonical async JSON-API controller pattern.
---

# FastAPI Routing & Resource Controllers

The `Router` class wraps FastAPI's `APIRouter` and adds a fluent API and `resource()` shortcut. Use it instead of bare `APIRouter` so routes stay consistent with the rest of the framework.

## Defining routes

Import `Router` from `fastapi_startkit.fastapi` and call the HTTP-verb methods:

```python
from fastapi_startkit.fastapi import Router

router = Router()

router.get("/users", users_controller.index)
router.post("/users", users_controller.store)
router.put("/users/{user_id}", users_controller.update)
router.patch("/users/{user_id}", users_controller.partial_update)
router.delete("/users/{user_id}", users_controller.destroy)
```

## Grouping routes by access level

Create separate `Router` instances with shared `dependencies` to split guest and authenticated routes. Apply middleware at the `Router` constructor level — not per-route:

```python
from fastapi import Depends
from fastapi_startkit.fastapi import Router

guest = Router()
guest.get("/login", auth_controller.create)
guest.post("/login", auth_controller.store)

auth = Router(dependencies=[Depends(require_auth)])
auth.get("/dashboard", dashboard_controller.index)
auth.resource("tasks", tasks_controller)
auth.resource("projects", projects_controller)
```

Register in `routes/web.py`:

```python
# routes/web.py
from fastapi_startkit import app

app().fastapi.include_router(guest.router)
app().fastapi.include_router(auth.router)
```

## resource() — RESTful route registration

`router.resource(name, controller)` registers the seven standard RESTful routes from a single controller. Only methods that **exist** on the controller are registered — missing methods are silently skipped.

```python
router.resource("tasks", TasksController)
```

| Method | Path | Controller method | Route name |
|--------|------|-------------------|------------|
| GET | `/tasks` | `index` | `tasks` |
| GET | `/tasks/create` | `create` | `tasks.create` |
| POST | `/tasks` | `store` | `tasks.store` |
| GET | `/tasks/{task}` | `show` | `tasks.show` |
| GET | `/tasks/{task}/edit` | `edit` | `tasks.edit` |
| PUT | `/tasks/{task}` | `update` | `tasks.update` |
| DELETE | `/tasks/{task}` | `destroy` | `tasks.destroy` |

### Filtering routes

```python
# Read-only resource
router.resource("reports", ReportsController, only={"index", "show"})

# Skip HTML form routes (API-only)
router.resource("tasks", TasksController, excepts={"create", "edit"})
```

### Custom route names

```python
router.resource("tasks", TasksController, names={"index": "task.list", "show": "task.detail"})
```

### Custom URL parameter name

```python
router.resource("categories", CategoriesController, parameters={"categories": "category_id"})
# Routes become /categories/{category_id}
```

## Canonical resource controller (JSON-API)

All controller methods must be `async def`. ORM calls must be `await`-ed. Collection endpoints return `ResourceCollection`; single-resource endpoints return a `Resource` instance. Use `find_or_fail()` — never fetch and manually raise 404. Use `Response(204)` for empty responses, not `JSONResponse({}, 204)`. Handle ORM exceptions specifically — never catch bare `Exception` alongside specific ones. Log failures with `Logger.error`, not `.debug`. Use `pendulum.now()` instead of `datetime.datetime.now()`.

```python
import pendulum
from fastapi import Response
from fastapi_startkit.jsonapi import JsonResource, ResourceCollection
from fastapi_startkit.masoniteorm.exceptions import ModelNotFound
from fastapi_startkit.logging import Logger

class TaskResource(JsonResource["Task"]):
    hidden = ["deleted_at"]

class TasksController:
    async def index(self, project_id: int) -> ResourceCollection:
        cutoff = pendulum.now().subtract(days=7).isoformat()

        tasks = await (
            Task
            .where("project_id", project_id)
            .where(lambda q: (
                q.where_not_in("tasks.status", ["completed", "cancelled"])
                 .or_where("tasks.completed_at", ">=", cutoff)
                 .or_where_raw("tasks.completed_at IS NULL")
            ))
            .paginate()
        )

        return TaskResource.collection(tasks)

    async def show(self, task: int) -> TaskResource:
        return TaskResource(await Task.find_or_fail(task))

    async def store(self, data: TaskCreateSchema) -> TaskResource:
        try:
            instance = await Task.create(data.model_dump())
            return TaskResource(instance)
        except Exception as exc:
            Logger.error(f"Failed to create task: {exc}")
            raise

    async def update(self, task: int, data: TaskUpdateSchema) -> TaskResource:
        instance = await Task.find_or_fail(task)
        payload = data.model_dump(exclude_unset=True)

        if "status" in payload and payload["status"] in ("completed", "cancelled"):
            payload.setdefault("completed_at", pendulum.now().isoformat())

        await instance.update(payload)
        return TaskResource(instance)

    async def destroy(self, task: int) -> Response:
        instance = await Task.find_or_fail(task)
        await instance.subtasks().delete()   # no orphaned child rows
        await instance.delete()
        return Response(status_code=204)
```

## Advanced ORM query patterns

### Lambda-grouped WHERE clauses

Pass a lambda to `where()` to wrap conditions in parentheses. The lambda receives a fresh `QueryBuilder` and must return it:

```python
# SQL: WHERE project_id = ? AND (status NOT IN (?,?) OR completed_at >= ? OR completed_at IS NULL)
tasks = await (
    Task
    .where("project_id", project_id)
    .where(lambda q: (
        q.where_not_in("status", ["completed", "cancelled"])
         .or_where("completed_at", ">=", cutoff)
         .or_where_raw("completed_at IS NULL")
    ))
    .get()
)
```

### Pagination

`paginate()` returns a `LengthAwarePaginator`. Pass it directly to `Resource.collection()` — pagination meta is included automatically in the JSON:API envelope.

```python
# Default: 15 per page, page 1
paginator = await Task.where("active", True).paginate()

# Custom page size and page number (inject from query params)
paginator = await Task.where("active", True).paginate(per_page=25, page=page)

return TaskResource.collection(paginator)
# → {"data": [...], "meta": {"total": 120, "per_page": 25, "current_page": 2, ...}}
```

### Excluding values

```python
active = await Task.where_not_in("status", ["archived", "deleted"]).get()
```

### Raw fragments

Use `where_raw` / `or_where_raw` only when the ORM cannot express the condition:

```python
tasks = await Task.where_raw("LOWER(title) LIKE ?", ("%search%",)).get()
```

### or_where and or_where_null

```python
results = await Task.where("user_id", user_id).or_where("shared", True).get()
overdue  = await Task.where_null("completed_at").or_where_null("due_at").get()
```
