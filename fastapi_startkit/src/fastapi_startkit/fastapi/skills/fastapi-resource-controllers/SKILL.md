---
name: fastapi-resource-controllers
description: Scaffold RESTful CRUD routes from a controller class using router.resource(). Use when you need the standard index/create/store/show/edit/update/destroy route set with optional filtering.
---

# FastAPI Resource Controllers

`router.resource(name, controller)` registers the seven standard RESTful routes from a single controller object or class. This mirrors the resource-controller convention and keeps route registration DRY.

## Basic usage

```python
from fastapi_startkit.fastapi import Router

router = Router()
router.resource("tasks", TasksController)
```

This registers:

| Method | Path | Controller method | Route name |
|--------|------|-------------------|------------|
| GET | `/tasks` | `index` | `tasks` |
| GET | `/tasks/create` | `create` | `tasks.create` |
| POST | `/tasks` | `store` | `tasks.store` |
| GET | `/tasks/{task}` | `show` | `tasks.show` |
| GET | `/tasks/{task}/edit` | `edit` | `tasks.edit` |
| PUT | `/tasks/{task}` | `update` | `tasks.update` |
| DELETE | `/tasks/{task}` | `destroy` | `tasks.destroy` |

Only methods that **exist** on the controller are registered — missing methods are silently skipped.

## Controller pattern

All controller methods must be `async def`. ORM calls must be `await`-ed. Collection endpoints return `ResourceCollection`; single-resource endpoints return a `Resource` instance.

```python
import datetime
from fastapi_startkit.jsonapi import JsonResource, ResourceCollection

class TaskResource(JsonResource["Task"]):
    hidden = ["deleted_at"]

class TasksController:
    async def index(self, project_id: int) -> ResourceCollection:
        cutoff = (
            datetime.datetime.now() - datetime.timedelta(days=7)
        ).isoformat()

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
        instance = await Task.create(data.model_dump())
        return TaskResource(instance)

    async def update(self, task: int, data: TaskUpdateSchema) -> TaskResource:
        instance = await Task.find_or_fail(task)
        await instance.update(data.model_dump(exclude_unset=True))
        return TaskResource(instance)

    async def destroy(self, task: int) -> dict:
        instance = await Task.find_or_fail(task)
        await instance.delete()
        return {"deleted": True}
```

## Advanced ORM query patterns

### Lambda-grouped WHERE clauses

Pass a lambda to `where()` to wrap a group of conditions in parentheses. The lambda receives a fresh `QueryBuilder` and must return it after chaining:

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

`paginate()` returns a `LengthAwarePaginator` with total / per_page / current_page attributes. Pass it directly to `Resource.collection()` — pagination meta is included automatically in the JSON:API envelope.

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

Use `where_raw` / `or_where_raw` only when the ORM cannot express the condition — not as a default:

```python
tasks = await Task.where_raw("LOWER(title) LIKE ?", ("%search%",)).get()
```

## Filtering routes with `only` and `excepts`

```python
# Read-only resource
router.resource("reports", ReportsController, only={"index", "show"})

# Skip HTML form routes (API-only)
router.resource("tasks", TasksController, excepts={"create", "edit"})
```

## Custom route names

```python
router.resource("tasks", TasksController, names={"index": "task.list", "show": "task.detail"})
```

## Custom URL parameter name

By default the parameter is derived from the resource name (`tasks` → `task`). Override it:

```python
router.resource("categories", CategoriesController, parameters={"categories": "category_id"})
# Routes become /categories/{category_id}
```
