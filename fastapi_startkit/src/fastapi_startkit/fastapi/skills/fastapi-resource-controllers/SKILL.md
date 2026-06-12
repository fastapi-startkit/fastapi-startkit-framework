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
router.resource("users", UsersController)
```

This registers:

| Method | Path | Controller method | Route name |
|--------|------|-------------------|------------|
| GET | `/users` | `index` | `users` |
| GET | `/users/create` | `create` | `users.create` |
| POST | `/users` | `store` | `users.store` |
| GET | `/users/{user}` | `show` | `users.show` |
| GET | `/users/{user}/edit` | `edit` | `users.edit` |
| PUT | `/users/{user}` | `update` | `users.update` |
| DELETE | `/users/{user}` | `destroy` | `users.destroy` |

Only methods that **exist** on the controller are registered — missing methods are silently skipped.

## Controller pattern

A resource controller is a plain class with async handler methods:

```python
class UsersController:
    async def index(self):
        return await User.all()

    async def show(self, user: int):
        return await User.find_or_fail(user)

    async def store(self, data: UserCreateSchema):
        return await User.create(data.model_dump())

    async def update(self, user: int, data: UserUpdateSchema):
        instance = await User.find_or_fail(user)
        await instance.update(data.model_dump(exclude_unset=True))
        return instance

    async def destroy(self, user: int):
        instance = await User.find_or_fail(user)
        await instance.delete()
        return {"deleted": True}
```

## Filtering routes with `only` and `excepts`

```python
# Only register read routes
router.resource("posts", PostsController, only={"index", "show"})

# Register everything except the create/edit form routes
router.resource("posts", PostsController, excepts={"create", "edit"})
```

## Custom route names

```python
router.resource("posts", PostsController, names={"index": "post.list", "show": "post.detail"})
```

## Custom URL parameter name

By default the parameter is derived from the resource name (e.g. `users` → `user`). Override it:

```python
router.resource("categories", CategoriesController, parameters={"categories": "category_id"})
# Routes become /categories/{category_id}
```
