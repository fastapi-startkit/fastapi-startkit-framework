---
name: fastapi-routing
description: Define HTTP routes with the fastapi-startkit Router wrapper. Use when adding GET, POST, PUT, PATCH, DELETE endpoints or grouping routes by auth level with shared dependencies.
---

# FastAPI Routing

The `Router` class wraps FastAPI's `APIRouter` and adds a fluent method API. Use it instead of bare `APIRouter` so your routes stay consistent with the rest of the framework.

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

Create separate `Router` instances with shared `dependencies` to split guest and authenticated routes:

```python
from fastapi import Depends
from fastapi_startkit.fastapi import Router

guest = Router()
guest.get("/login", auth_controller.create)
guest.post("/login", auth_controller.store)

auth = Router(dependencies=[Depends(require_auth)])
auth.get("/dashboard", dashboard_controller.index)
auth.resource("users", users_controller)
```

## Including routers in routes/web.py

Register your routers with the FastAPI application:

```python
# routes/web.py
from fastapi_startkit import app

app().fastapi.include_router(guest.router)
app().fastapi.include_router(auth.router)
```

## Route options

Pass any standard FastAPI `add_api_route` keyword arguments as extra kwargs:

```python
router.get(
    "/users",
    users_controller.index,
    response_model=list[UserSchema],
    status_code=200,
    tags=["users"],
    summary="List all users",
)
```

## Accessing the underlying APIRouter

Use `router.router` to access the raw `APIRouter` instance, or rely on `__getattr__` passthrough for any attributes not defined on `Router` itself.
