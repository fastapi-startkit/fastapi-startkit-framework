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

## Querying records

```python
# All records
users = await User.all()

# Single record by primary key
user = await User.find(1)

# Raise ModelNotFoundException if not found
user = await User.find_or_fail(1)

# First matching record
user = await User.where("role", "admin").first()
user = await User.where("role", "admin").first_or_fail()

# Filtered collection
admins = await User.where("role", "admin").get()

# Chained conditions
result = await User.where("active", True).where_not_null("email").order_by("name").limit(10).get()
```

## Updating and deleting

```python
user = await User.find_or_fail(1)
await user.update({"name": "Bob"})
await user.delete()
```

## Upserts

```python
# Find or create
user = await User.first_or_create({"email": "bob@example.com"}, {"name": "Bob"})

# Update or create
user = await User.update_or_create({"email": "bob@example.com"}, {"name": "Bob", "role": "editor"})
```

## Aggregates

```python
count = await User.count()
exists = await User.where("email", "x@example.com").exists()
```

## Relationships

Declare relationships as class-level descriptors:

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

Eager-load relationships to avoid N+1 queries:

```python
users = await User.with_("posts").get()
for user in users:
    print(user.posts)
```

## Connections

Switch the database connection at query time:

```python
users = await User.on("read_replica").where("active", True).get()
```

## Raw where clauses

```python
users = await User.where_raw("lower(email) = ?", ("alice@example.com",)).get()
```
