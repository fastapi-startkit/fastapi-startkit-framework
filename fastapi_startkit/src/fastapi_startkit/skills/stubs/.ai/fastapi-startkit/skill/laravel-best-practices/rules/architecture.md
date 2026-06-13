# Architecture Rules — fastapi-startkit (Laravel-inspired)

This framework follows Laravel conventions adapted to Python and FastAPI. The rules below govern how to structure providers, containers, controllers, models, routes, and config in a fastapi-startkit application.

---

## Rule 1 — Provider pattern: `register()` for bindings, `boot()` for logic

`register()` must only bind things into the container. Never resolve other bindings inside `register()` — other providers may not have run yet. All logic that depends on resolved services belongs in `boot()`.

```python
# ✅ DO
class OrdersProvider(Provider):
    def register(self) -> None:
        self.app.bind("orders", OrderService())   # pure binding

    def boot(self) -> None:
        service = self.app.make("orders")         # safe to resolve here
        service.configure(self.app.make("config").get("orders"))

# ❌ DON'T
class OrdersProvider(Provider):
    def register(self) -> None:
        config = self.app.make("config")           # resolving in register() — unsafe
        self.app.bind("orders", OrderService(config))
```

---

## Rule 2 — Service container: prefer constructor injection via `resolve()`

Use `app.resolve(callable)` to auto-wire dependencies by type hint instead of calling `app.make()` manually (service locator anti-pattern). Reserve `make()` for entry points and bootstrap code.

```python
# ✅ DO — container resolves OrderRepository automatically
class OrderService:
    def __init__(self, repo: OrderRepository) -> None:
        self.repo = repo

instance = app().resolve(OrderService)

# ❌ DON'T — service locator hides dependencies
class OrderService:
    def __init__(self) -> None:
        self.repo = app().make("orders.repo")   # hidden dependency
```

---

## Rule 3 — Single responsibility per provider

Each `Provider` subclass owns exactly one concern. Mixing unrelated bindings into one provider makes the app harder to understand and test.

```python
# ✅ DO — separate providers
class AuthProvider(Provider):
    def register(self) -> None:
        self.app.bind("auth", AuthManager())

class MailProvider(Provider):
    def register(self) -> None:
        self.app.bind("mail", MailManager())

# ❌ DON'T — one provider for everything
class AppProvider(Provider):
    def register(self) -> None:
        self.app.bind("auth", AuthManager())
        self.app.bind("mail", MailManager())
        self.app.bind("cache", CacheManager())
        self.app.bind("queue", QueueManager())
```

---

## Rule 4 — Resourceful controllers: one per resource, all `async def`

One controller class per resource. Use the standard `index / show / store / update / destroy` method names. Every method must be `async def`. Collection endpoints return `ResourceCollection`; single-resource endpoints return a `Resource`.

```python
# ✅ DO
from fastapi_startkit.jsonapi import JsonResource, ResourceCollection

class TaskResource(JsonResource["Task"]):
    hidden = ["deleted_at"]

class TasksController:
    async def index(self, project_id: int) -> ResourceCollection:
        tasks = await Task.where("project_id", project_id).paginate()
        return TaskResource.collection(tasks)

    async def show(self, task: int) -> TaskResource:
        return TaskResource(await Task.find_or_fail(task))

    async def store(self, data: TaskCreateSchema) -> TaskResource:
        return TaskResource(await Task.create(data.model_dump()))

    async def destroy(self, task: int) -> dict:
        await (await Task.find_or_fail(task)).delete()
        return {"deleted": True}

# ❌ DON'T — sync methods, raw dicts, no resource wrapping
class TasksController:
    def index(self):                          # missing async
        return Task.all()                     # missing await, returns raw collection
    def get_task(self, id):                   # non-standard method name
        return {"id": id, "title": "..."}     # raw dict, no Resource
```

---

## Rule 5 — ORM conventions: always `await`, relationships as descriptors

Every ORM query is async — always `await` it. Declare relationships as class-level descriptors, not inside methods. Avoid raw SQL unless no ORM equivalent exists; prefer `where_raw` / `or_where_raw` over embedding SQL strings elsewhere.

```python
# ✅ DO
from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm.relationships import HasMany, BelongsTo

class Post(Model):
    title: str
    user_id: int
    author = BelongsTo("User", foreign_key="user_id")  # descriptor

async def get_posts(user_id: int):
    return await Post.where("user_id", user_id).get()  # awaited

# ❌ DON'T
class Post(Model):
    async def get_author(self):              # relationship inside a method — not a descriptor
        return await User.find(self.user_id)

def get_posts(user_id: int):                # not async
    return Post.where("user_id", user_id).get()   # unawaited coroutine — silent bug
```

---

## Rule 6 — Route organisation: separate guest/auth routers, middleware at Router level

Create distinct `Router` instances for guest and authenticated routes. Apply middleware (e.g. `Depends(require_auth)`) at the `Router` constructor level, not per-route. Use `router.resource()` for CRUD resources.

```python
# ✅ DO
from fastapi import Depends
from fastapi_startkit.fastapi import Router

guest = Router()
guest.get("/login",  auth_controller.create)
guest.post("/login", auth_controller.store)

auth = Router(dependencies=[Depends(require_auth)])  # middleware at Router level
auth.resource("tasks",    tasks_controller)
auth.resource("projects", projects_controller)

# ❌ DON'T — scatters middleware across individual routes
router = Router()
router.get("/tasks",      tasks_controller.index,   dependencies=[Depends(require_auth)])
router.post("/tasks",     tasks_controller.store,   dependencies=[Depends(require_auth)])
router.get("/tasks/{id}", tasks_controller.show,    dependencies=[Depends(require_auth)])
```

---

## Rule 7 — Configuration: dataclass + `env()`, never hardcoded values

Define all config as a `@dataclass` with fields sourced via `env()`. Register the config object in a provider. Never hardcode hostnames, keys, or connection strings in application code.

```python
# ✅ DO
from dataclasses import dataclass, field
from fastapi_startkit.environment import env

@dataclass
class RedisConfig:
    host: str     = field(default_factory=lambda: env("REDIS_HOST", "127.0.0.1"))
    port: int     = field(default_factory=lambda: env("REDIS_PORT", 6379))
    password: str = field(default_factory=lambda: env("REDIS_PASSWORD", ""))

class RedisProvider(Provider):
    def register(self) -> None:
        self.app.bind("redis.config", RedisConfig())

# ❌ DON'T — hardcoded values
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379

class RedisClient:
    def __init__(self):
        self.host = "127.0.0.1"   # hardcoded — breaks across environments
```

---

## Rule 8 — No business logic in routes or controllers

Routes delegate to controllers; controllers delegate to service classes or models. Business logic (validation beyond Pydantic, workflow orchestration, external API calls) belongs in a dedicated service layer.

```python
# ✅ DO — controller is thin, delegates to service
class OrdersController:
    async def store(self, data: OrderCreateSchema) -> OrderResource:
        order = await OrderService().place(data)
        return OrderResource(order)

class OrderService:
    async def place(self, data: OrderCreateSchema) -> Order:
        await self._validate_inventory(data.items)
        order = await Order.create(data.model_dump())
        await self._charge_payment(order)
        OrderShipped(order.id).emit()
        return order

# ❌ DON'T — business logic inline in a controller method
class OrdersController:
    async def store(self, data: OrderCreateSchema) -> dict:
        for item in data.items:
            stock = await Inventory.find(item.id)
            if stock.quantity < item.qty:
                raise HTTPException(400, "Out of stock")
        order = await Order.create(data.model_dump())
        await stripe.charge(order.total)       # payment logic in controller
        OrderShipped(order.id).emit()
        return {"id": order.id}
```

---

## Rule 9 — Broadcasting: `BroadcastEvent` subclasses, auth in `routes/channels.py`, no facades

Define events as `BroadcastEvent` subclasses. Dispatch with `await .emit()` or `await broadcast(event)`. Authorize private/presence channels exclusively in `routes/channels.py` using the `@channel` decorator. Do not use the `Broadcast` facade.

```python
# ✅ DO
from fastapi_startkit.broadcasting import BroadcastEvent, PrivateChannel, channel, broadcast

class OrderShipped(BroadcastEvent):
    def __init__(self, order_id: int) -> None:
        self.payload = {"order_id": order_id}
    def broadcast_on(self) -> list:
        return [PrivateChannel(f"orders.{self.payload['order_id']}")]

# Dispatch
await OrderShipped(order_id=123).emit()

# routes/channels.py — auth callbacks
@channel("orders.{order_id}")
async def authorize_orders(user, order_id: int) -> bool:
    return user is not None and user.id == order_id

# ❌ DON'T
from fastapi_startkit.facades.Broadcast import Broadcast

await Broadcast.event(event)            # facade — avoid
await Broadcast.dispatch(event)         # facade — avoid

# auth callback inline in a route handler — not in routes/channels.py
@router.post("/some-route")
async def handler():
    if not await check_channel_auth(...):  # auth logic leaking into route
        ...
```

---

## Rule 10 — Async discipline: all I/O is `async/await`, no blocking calls in async context

Every function that performs I/O (database, HTTP, file system, sleep) must be `async def` and `await`-ed at every call site. Never call synchronous blocking I/O (e.g. `requests.get`, `time.sleep`, sync file reads) from inside an async function — it blocks the entire event loop.

```python
# ✅ DO
import asyncio
import httpx

async def fetch_and_save(url: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)           # async HTTP
    record = await ExternalData.create({"body": response.text})  # async ORM
    await asyncio.sleep(1)                         # async sleep

# ❌ DON'T
import requests
import time

async def fetch_and_save(url: str) -> None:
    response = requests.get(url)          # BLOCKS the event loop
    time.sleep(1)                         # BLOCKS the event loop
    ExternalData.create({"body": response.text})  # unawaited coroutine — silent bug
```
