from fastapi_startkit.masoniteorm.schema import Schema


_SQLITE_SYSTEM_TABLES = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat2", "sqlite_stat3", "sqlite_stat4"}


async def wipe(schema: Schema) -> None:
    for connection in ("default", "dev"):
        tables = await schema.on(connection).get_all_tables()
        for table in tables:
            if table in _SQLITE_SYSTEM_TABLES:
                continue
            await schema.on(connection).drop_table_if_exists(table)


async def migrate(schema: Schema) -> None:
    async with await schema.on("default").create_table_if_not_exists("users") as table:
        table.id()
        table.string("name")
        table.string("email").unique()
        table.boolean("is_admin").default(False)
        table.timestamp("email_verified_at").nullable()
        table.date("date_of_birth").nullable()
        table.decimal("session_duration").nullable()
        table.string("punch_in_time").nullable()
        table.json("preferences").nullable()
        table.text("address").nullable()
        table.timestamps()

    async with await schema.create_table_if_not_exists("profiles") as table:
        table.integer("id").primary()
        table.string("name")
        table.integer("user_id")

    async with await schema.create_table_if_not_exists("articles") as table:
        table.id()
        table.string("title")
        table.integer("user_id")
        table.datetime("published_date")

    async with await schema.create_table_if_not_exists("logos") as table:
        table.id()
        table.integer("article_id")
        table.datetime("published_date")

    async with await schema.create_table_if_not_exists("users") as table:
        table.id()
        table.string("name")
        table.boolean("is_admin").default(False)
        table.datetime("created_at")
        table.datetime("updated_at")

    async with await schema.create_table_if_not_exists("stores") as table:
        table.integer("id").primary()
        table.string("name")

    async with await schema.create_table_if_not_exists("products") as table:
        table.id()
        table.string("name")
        table.timestamps()

    async with await schema.create_table_if_not_exists("product_table") as table:
        table.id()
        table.integer("store_id")
        table.integer("product_id")

    async with await schema.create_table_if_not_exists("product_store") as table:
        table.id()
        table.integer("store_id")
        table.integer("product_id")
        table.timestamps()

    async with await schema.create_table_if_not_exists("likes") as table:
        table.id()
        table.string("likeable_type")
        table.integer("likeable_id")
        table.timestamps()

    async with await schema.on("dev").create_table_if_not_exists("countries") as table:
        table.integer("country_id").primary()
        table.string("name")

    async with await schema.on("dev").create_table_if_not_exists("ports") as table:
        table.integer("port_id").primary()
        table.string("name")
        table.integer("port_country_id")

    async with await schema.on("dev").create_table_if_not_exists("incoming_shipments") as table:
        table.integer("shipment_id").primary()
        table.string("name")
        table.integer("from_port_id")
