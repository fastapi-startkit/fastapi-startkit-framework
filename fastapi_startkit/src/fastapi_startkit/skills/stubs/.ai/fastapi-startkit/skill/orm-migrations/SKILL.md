---
name: orm-migrations
description: Create and run database schema migrations using the fastapi-startkit ORM. Use when creating tables, adding/dropping columns, or managing migration lifecycle with artisan commands.
---

# ORM Migrations

Migrations describe schema changes as versioned Python files. The `Blueprint` builder maps to SQL DDL for SQLite, MySQL, and PostgreSQL.

## Creating a migration

```bash
uv run artisan make:migration create_users_table
```

This generates a file in `databases/migrations/` with `up()` and `down()` methods.

## Migration class structure

```python
from fastapi_startkit.masoniteorm.migrations import Migration

class CreateUsersTable(Migration):
    async def up(self):
        async with await self.schema.create("users") as table:
            table.increments("id")
            table.string("name")
            table.string("email").unique()
            table.string("password")
            table.enum("role", ["admin", "user"]).default("user")
            table.boolean("active").default(True)
            table.timestamps()

    async def down(self):
        await self.schema.drop("users")
```

## Common Blueprint column types

| Method | SQL type |
|--------|----------|
| `increments("id")` | auto-increment primary key |
| `string("col", length=255)` | VARCHAR |
| `text("col")` | TEXT |
| `integer("col")` | INT |
| `big_integer("col")` | BIGINT |
| `boolean("col")` | BOOLEAN / TINYINT(1) |
| `decimal("col", precision, scale)` | DECIMAL |
| `float_type("col")` | FLOAT |
| `date("col")` | DATE |
| `datetime("col")` | DATETIME |
| `timestamp("col")` | TIMESTAMP |
| `timestamps()` | `created_at` + `updated_at` |
| `soft_deletes()` | `deleted_at` nullable |
| `enum("col", ["a", "b"])` | ENUM |
| `json("col")` | JSON / TEXT |
| `foreign("col")` | foreign key column |
| `uuid("col")` | UUID / CHAR(36) |

## Column modifiers

Chain these after any column method:

```python
table.string("email").unique()
table.string("bio").nullable()
table.string("status").default("active")
table.string("code").unsigned()
table.integer("views").after("title")   # MySQL only
```

## Altering an existing table

```python
async def up(self):
    async with await self.schema.table("users") as table:
        table.add_column("phone", "string", nullable=True)
        table.drop_column("legacy_field")
        table.rename_column("old_name", "new_name")
```

## Running migrations

```bash
# Run all pending migrations
uv run artisan db:migrate

# Check migration status
uv run artisan migrate:status

# Roll back the last batch
uv run artisan migrate:rollback

# Drop all tables and re-run from scratch
uv run artisan migrate:fresh
```

## Migration directory

By default migrations are read from `databases/migrations/`. Configure a custom path in `config/database.py`:

```python
@dataclass
class DatabaseConfig:
    migrations: dict = field(default_factory=lambda: {
        "directory": "databases/migrations"
    })
```
