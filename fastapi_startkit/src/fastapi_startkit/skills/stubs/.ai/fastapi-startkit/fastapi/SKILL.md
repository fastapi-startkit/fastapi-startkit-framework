---
name: fastapi-startkit
description: Routing, controllers, ORM, requests, resources, and action pattern for fastapi-startkit applications.
---

# Fastapi's Routing

### Fastapi Startkit's Router
```python
# routes/web.py
from fastapi_startkit.fastapi import Router

router = Router()
```

and register routes explicitly, for example
```python
router.get("/users", users_controller.index)
router.post("/users", users_controller.store)
router.get("/users/{user_id}", users_controller.show)
router.put("/users/{user_id}", users_controller.update)
router.patch("/users/{user_id}", users_controller.update)
router.delete("/users/{user_id}", users_controller.destroy)
```

### Resourceful controllers

Prefer `router.resource()` to register the seven standard CRUD routes in one
call. It maps to a **resourceful controller** with these methods:

| Method    | Verb & URI                  | Purpose                          |
|-----------|-----------------------------|----------------------------------|
| `index`   | GET `/users`                | List the collection              |
| `create`  | GET `/users/create`         | Show the "new" form              |
| `store`   | POST `/users`               | Persist a new record             |
| `show`    | GET `/users/{user}`         | Show a single record             |
| `edit`    | GET `/users/{user}/edit`    | Show the "edit" form             |
| `update`  | PUT/PATCH `/users/{user}`   | Persist changes to a record      |
| `destroy` | DELETE `/users/{user}`      | Delete a record                  |

```python
# routes/web.py
router.resource("users", users_controller)

# subset / exclusions
router.resource("users", users_controller, only=['index', 'show'])
router.resource("users", users_controller, excepts=['create', 'edit'])
```

A full resourceful controller mirrors those seven methods exactly:
```python
# app/http/controllers/users_controller.py
from fastapi_startkit.jsonapi import JsonResource

from app.models import User
from app.http.requests.user_store_request import UserStoreRequest

async def index():
    users = await User.all()
    return JsonResource.collection(users)

async def create():
    # render/return the "create" form payload
    ...

async def store(request: UserStoreRequest):
    user = await User.create(request.model_dump())
    return JsonResource(user)

async def show(user: int):
    return JsonResource(await User.find_or_fail(user))

async def edit(user: int):
    # render/return the "edit" form payload for the record
    return JsonResource(await User.find_or_fail(user))

async def update(user: int, request: UserStoreRequest):
    record = await User.find_or_fail(user)
    await record.update(request.model_dump())
    return JsonResource(record)

async def destroy(user: int):
    record = await User.find_or_fail(user)
    await record.delete()
    return JsonResource(record)
```

## ORM
```python
# app/models/user.py
from fastapi_startkit.masoniteorm import Model

class User(Model):
    id: int
    name: str
    email: str
    metadata: dict
```

and use the orm as:
```python
# app/http/controllers/users_controller.py
from app.models import User

async def store(request: UserStoreRequest):
    user = User.create(request.model_dump())
    ...
```

the `UserStoreRequest` will look like:
```python
# app/http/requests/user_store_request.py
from pydantic import BaseModel

class UserStoreRequest(BaseModel):
    name: str
```

and use JsonApiResource to return JSON response from the controller:
```python
from fastapi_startkit.jsonapi import JsonResource

# app/http/controllers/users_controller.py
from app.models import User

async def store(request: UserStoreRequest):
    user = User.create(request.model_dump())
    return JsonResource(user)
```

## Architecture

use the action pattern to write complex logic.
```python
# app/actions/user_actions.py
from app.models import User

class UserStoreAction:
    def __init__(self, request: UserStoreRequest):
        self.request = request

    @staticmethod
    def prepare(request: UserStoreRequest) -> 'UserStoreAction':
        return UserStoreAction(request)

    def handle(self) -> JsonResource[User]:
        user = User.create(self.request.model_dump())
        return JsonResource(user)
```
