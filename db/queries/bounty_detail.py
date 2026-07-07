from shared.db import db


def add_scope(conn, master_id, scope_type: str, scope_identifier: str, scope_instructions: str | None = None):
    row = db.fetch_one(
        conn,

        """
        INSERT INTO bounty_detail (master_id, scope_type, scope_identifier, scope_instructions)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,

        (master_id, scope_type, scope_identifier, scope_instructions),
    )

    return row["id"]


def upsert_scope(conn, master_id, scope_type: str, scope_identifier: str, scope_instructions: str | None = None):
    row = db.fetch_one(
        conn,

        """
        INSERT INTO bounty_detail (master_id, scope_type, scope_identifier, scope_instructions)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (master_id, scope_type, scope_identifier) DO UPDATE
            SET scope_instructions = EXCLUDED.scope_instructions,
                updated_at = %s
        RETURNING id
        """,

        (master_id, scope_type, scope_identifier, scope_instructions, db.now()),
    )

    return row["id"]


def get_scope_by_id(conn, scope_id):
    return db.fetch_one(
        conn,
        "SELECT * FROM bounty_detail WHERE id = %s AND is_active = TRUE",
        (scope_id,),
    )


def get_scopes_by_master_id(conn, master_id):
    return db.fetch_all(
        conn,
        "SELECT * FROM bounty_detail WHERE master_id = %s AND is_active = TRUE",
        (master_id,),
    )


def list_active_scopes(conn):
    return db.fetch_all(
        conn,
        "SELECT * FROM bounty_detail WHERE is_active = TRUE ORDER BY master_id",
    )


def update_scope(conn, scope_id, scope_instructions: str | None = None):
    fields = []
    params = []

    if scope_instructions is not None:
        fields.append("scope_instructions = %s")
        params.append(scope_instructions)

    if not fields:
        return 0  # nothing to update

    fields.append("updated_at = %s")
    params.append(db.now())
    params.append(scope_id)

    query = f"UPDATE bounty_detail SET {', '.join(fields)} WHERE id = %s"
    return db.execute(conn, query, tuple(params))


def deactivate_scope(conn, scope_id):
    return db.execute(
        conn,
        "UPDATE bounty_detail SET is_active = FALSE, updated_at = %s WHERE id = %s",
        (db.now(), scope_id),
    )


def delete_scope(conn, scope_id):
    return db.execute(
        conn,
        "DELETE FROM bounty_detail WHERE id = %s",
        (scope_id,),
    )