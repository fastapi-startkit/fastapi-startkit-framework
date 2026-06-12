---
name: orm-models
description: Define and query database models with the fastapi-startkit async ORM. Use when creating model classes, reading/writing records, filtering with the QueryBuilder, or working with relationships.
---

# ORM Models

`Model` is the base class for all database models. It auto-pluralises the table name, tracks `created_at`/`updated_at` timestamps, and exposes a fluent async `QueryBuilder`.

## Defining a model

```python
from fastapi_startkit.masoniteorm import Model

class User(Model):
    name: str
    email: str
    role: str = "user"
```

- Class name is automatically pluralised to the table name (`User` → `users`). Override with `__table__ = "my_users"`.
- Annotated class-level attributes become `__fillable__` fields automatically.
- `created_at` and `updated_at` are managed as `Carbon` (pendulum) objects.

## Creating records

```python
user = await User.create({"name": "Alice", "email": "alice@example.com"})
```

## Basic querying

```python
# All records
users = await User.all()

# By primary key
user = await User.find(1)
user = await User.find_or_fail(1)   # raises ModelNotFoundException if missing

# First match
user = await User.where("role", "admin").first()
user = await User.where("role", "admin").first_or_fail()

# Filtered collection
admins = await User.where("role", "admin").get()

# Chained conditions
result = await (
    User
    .where("active", True)
    .where_not_null("email")
    .order_by("name")
    .limit(10)
    .get()
)
```

## Updating and deleting

```python
user = await User.find_or_fail(1)
await user.update({"name": "Bob"})
await user.delete()
```

## Upserts

```python
user = await User.first_or_create({"email": "bob@example.com"}, {"name": "Bob"})
user = await User.update_or_create({"email": "bob@example.com"}, {"name": "Bob", "role": "editor"})
```

## Aggregates

```python
count  = await User.count()
exists = await User.where("email", "x@example.com").exists()
total  = await Order.sum("amount")
```

## Advanced query patterns

### Lambda-grouped WHERE clauses

Pass a lambda to `where()` to group conditions in parentheses. The lambda receives a fresh `QueryBuilder` and must return it after chaining:

```python
import datetime

cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()

# SQL:
# WHERE project_id = ?
# AND (
#   status NOT IN (?,?)
#   OR completed_at >= ?
#   OR completed_at IS NULL
# )
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

### Excluding values

```python
active = await Task.where_not_in("status", ["archived", "deleted"]).get()
```

### OR conditions

```python
results = await Task.where("priority", "high").or_where("due_today", True).get()
results = await Task.where_null("deleted_at").or_where_null("archived_at").get()
```

### Raw fragments

Use `where_raw` / `or_where_raw` only when the ORM cannot express the condition:

```python
tasks = await Task.where_raw("LOWER(title) LIKE ?", ("%search%",)).get()
tasks = await Task.where("active", True).or_where_raw("priority > 5").get()
```

### Pagination

`paginate()` returns a `LengthAwarePaginator`. Pass it to `JsonResource.collection()` and pagination meta is included automatically in the JSON:API envelope.

```python
# 15 records per page (default)
paginator = await Task.where("project_id", project_id).paginate()

# Custom page size and page (inject from request query params)
paginator = await Task.where("project_id", project_id).paginate(per_page=25, page=page)

# paginator attributes: total, per_page, current_page, last_page
print(paginator.total, paginator.current_page)

# Wrap for JSON:API response
from fastapi_startkit.jsonapi import JsonResource
return TaskResource.collection(paginator)
# → {"data": [...], "meta": {"total": 120, "per_page": 25, "current_page": 2, ...}}
```

For a lighter paginator that only detects whether a next page exists (no COUNT query):

```python
paginator = await Task.paginate_simple(per_page=25, page=page)
```

### Joins

```python
tasks = await (
    Task
    .join("projects", "tasks.project_id", "=", "projects.id")
    .where("projects.owner_id", user_id)
    .select("tasks.*", "projects.name")
    .get()
)
```

## Relationships

```python
from fastapi_startkit.masoniteorm.relationships import HasMany, BelongsTo

class Post(Model):
    title: str
    user_id: int
    author = BelongsTo("User", foreign_key="user_id")

class User(Model):
    name: str
    posts = HasMany("Post", foreign_key="user_id")
```

Eager-load to avoid N+1 queries:

```python
users = await User.with_("posts").get()
for user in users:
    print(user.posts)
```

## Connections

```python
users = await User.on("read_replica").where("active", True).get()
```
