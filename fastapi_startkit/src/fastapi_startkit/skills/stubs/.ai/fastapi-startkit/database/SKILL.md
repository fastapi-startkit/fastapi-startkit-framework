---
name: database
description: Async ORM for fastapi-startkit — models, relationships, migrations, seeders, and the query builder.
---

# Database & ORM

fastapi-startkit ships an async-first Masonite ORM built on SQLAlchemy. Every
database operation is `async`/`await`. Table names are auto-pluralized from the
model class via `inflection`, and `created_at`/`updated_at` are managed as
`pendulum` Carbon objects.

## Models

```python
# app/models/user.py
from fastapi_startkit.masoniteorm import Model
from fastapi_startkit.masoniteorm import HasOne, HasMany, BelongsTo, BelongsToMany


class User(Model):
    __table__ = "users"          # optional — inferred as "users" otherwise

    name: str
    email: str
    role: str

    profile = HasOne("Profile")
    courses = BelongsToMany(
        "Course",
        local_foreign_key="user_id",
        other_foreign_key="course_id",
        table="course_user",
        with_timestamps=True,
        with_fields=["progress", "completed_at"],
    )
```

Relationships available: `HasOne`, `HasMany`, `BelongsTo`, `BelongsToMany`,
`HasManyThrough`, and `MorphMany`. Reference the related model by class name as a
string to avoid circular imports.

## Query builder

All queries are awaited:

```python
from app.models.user import User

user = await User.find(1)
user = await User.where("email", "a@b.com").first()
users = await User.where("role", "admin").get()
user = await User.create({"name": "Ada", "email": "ada@example.com"})
await user.update({"role": "admin"})
await user.delete()
```

Eager-load relationships to avoid N+1 queries:

```python
courses = await Course.with_("category", "lessons").get()
```

## Migrations

```python
# databases/migrations/2024_01_01_000000_create_lessons_table.py
from fastapi_startkit.masoniteorm import Migration


class CreateLessonsTable(Migration):
    async def up(self):
        async with await self.schema.create("lessons") as table:
            table.increments("id")
            table.integer("course_id").unsigned()
            table.foreign("course_id").references("id").on("courses").on_delete("cascade")
            table.string("title")
            table.timestamps()

    async def down(self):
        await self.schema.drop("lessons")
```

## Seeders

```python
# databases/seeders/course_seeder.py
from fastapi_startkit.masoniteorm.seeds import Seeder
from app.models.course import Course


class CourseSeeder(Seeder):
    async def run(self):
        await Course.create({"title": "Python for Beginners", "price": 0})
```

## Console commands

```bash
uv run artisan db:make:model User          # scaffold a model
uv run artisan db:make:migration create_users_table
uv run artisan db:migrate                  # run pending migrations
uv run artisan db:migrate:rollback         # roll back the last batch
uv run artisan db:migrate:fresh            # drop all + re-migrate
uv run artisan db:migrate:status           # show migration state
uv run artisan db:seed                     # run seeders
```
