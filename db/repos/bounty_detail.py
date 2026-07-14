import shared.db as db


def add_scope(
    conn,
    master_id,
    scope_type: str,
    scope_identifier: str,
    max_severity: str | None = None,
    scope_instructions: str | None = None,
):
    row = db.fetch_one(
        conn,
        """
        INSERT INTO bounty_detail
            (
                master_id,
                scope_type,
                scope_identifier,
                max_severity,
                scope_instructions
            )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            master_id,
            scope_type,
            scope_identifier,
            max_severity,
            scope_instructions,
        ),
    )

    return row["id"]


def get_scope_by_id(conn, scope_id):
    return db.fetch_one(
        conn,
        """
        SELECT *
        FROM bounty_detail
        WHERE id = %s
          AND is_active = TRUE
        """,
        (scope_id,),
    )


def get_scopes_by_master_id(conn, master_id):
    return db.fetch_all(
        conn,
        """
        SELECT *
        FROM bounty_detail
        WHERE master_id = %s
          AND is_active = TRUE
        ORDER BY scope_identifier
        """,
        (master_id,),
    )


def list_active_scopes(conn):
    return db.fetch_all(
        conn,
        """
        SELECT *
        FROM bounty_detail
        WHERE is_active = TRUE
        ORDER BY master_id, scope_identifier
        """
    )


def update_scope(
    conn,
    scope_id,
    max_severity: str | None = None,
    scope_instructions: str | None = None,
):
    fields = []
    params = []

    if max_severity is not None:
        fields.append("max_severity = %s")
        params.append(max_severity)

    if scope_instructions is not None:
        fields.append("scope_instructions = %s")
        params.append(scope_instructions)

    if not fields:
        return 0

    fields.append("updated_at = %s")
    params.append(db.now())

    params.append(scope_id)

    query = f"""
        UPDATE bounty_detail
        SET {', '.join(fields)}
        WHERE id = %s
    """

    return db.execute(conn, query, tuple(params))


def deactivate_scope(conn, scope_id):
    return db.execute(
        conn,
        """
        UPDATE bounty_detail
        SET
            is_active = FALSE,
            updated_at = %s
        WHERE id = %s
        """,
        (db.now(), scope_id),
    )


def delete_scope(conn, scope_id):
    return db.execute(
        conn,
        """
        DELETE FROM bounty_detail
        WHERE id = %s
        """,
        (scope_id,),
    )


def delete_scopes_for_program(conn, master_id):
    """
    Hard delete all scope rows for a program.
    """
    return db.execute(
        conn,
        """
        DELETE FROM bounty_detail
        WHERE master_id = %s
        """,
        (master_id,),
    )


def update_scopes(conn, master_id, incoming_scopes: list[dict]):
    
    with db.atomic(conn):
        delete_scopes_for_program(conn, master_id)

        for scope in incoming_scopes:
            add_scope(
                conn,
                master_id,
                scope["scope_type"],
                scope["scope_identifier"],
                scope.get("max_severity"),
                scope.get("scope_instructions"),
            )