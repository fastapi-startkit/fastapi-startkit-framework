from sqlalchemy import column
from sqlalchemy import table as sa_table
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# Each supported driver maps to its dialect-specific INSERT builder so the
# generated statement can express the right "on conflict" upsert clause.
_INSERTERS = {
    "postgres": postgres_insert,
    "sqlite": sqlite_insert,
    "mysql": mysql_insert,
}


def build_upsert_statement(driver, table_name, rows, unique_by, update_columns):
    """Build a single bulk INSERT ... ON CONFLICT/DUPLICATE KEY statement.

    `rows` must already be normalised to share an identical column set so the
    multi-row VALUES clause is well formed.
    """
    inserter = _INSERTERS.get(driver)
    if inserter is None:
        raise ValueError(f"upsert() is not supported for the '{driver}' driver")

    columns = list(rows[0].keys())
    target = sa_table(table_name, *[column(name) for name in columns])
    statement = inserter(target).values(rows)

    if driver == "mysql":
        if update_columns:
            return statement.on_duplicate_key_update(
                {name: statement.inserted[name] for name in update_columns}
            )
        # No columns to update: keep a unique key untouched to make it a no-op.
        return statement.on_duplicate_key_update(
            {unique_by[0]: statement.inserted[unique_by[0]]}
        )

    if update_columns:
        return statement.on_conflict_do_update(
            index_elements=unique_by,
            set_={name: statement.excluded[name] for name in update_columns},
        )

    return statement.on_conflict_do_nothing(index_elements=unique_by)
