import shared.db as db


def add_program(conn, handle: str, scope_count: int = 0, max_severity: str | None = None ):
    row = db.fetch_one(
        conn,
        
        """
        INSERT INTO bounty_master (handle, scope_count, max_severity)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        
        (handle, scope_count, max_severity),
    )
    
    return row["id"]


def upsert_program(conn, handle: str, scope_count: int = 0, max_severity: str | None = None):
    row = db.fetch_one(
        conn,
        
        """
        INSERT INTO bounty_master (handle, scope_count, max_severity)
        VALUES (%s,%s,%s)
        ON CONFLICT (handle) DO UPDATE
            SET scope_count = EXCLUDED.scope_count,
                max_severity = EXCLUDED.max_severity,
                updated_at = %s
        RETURNING id
        """,
        
        (handle, scope_count, max_severity, db.now()),
    )
    
    return row["id"]


def get_program_by_name(conn, handle: str):
    return db.fetch_one(
        conn,
        "SELECT * FROM bounty_master WHERE handle = %s AND is_active = TRUE",
        (handle,),
    )
    


def get_program_by_id(conn, master_id):
    return db.fetch_one(
        conn,
        "SELECT * FROM bounty_master WHERE id = %s AND is_active = TRUE",
        (master_id,),
    )


def list_active_programs(conn):
    return db.fetch_all(
        conn,
        "SELECT * FROM bounty_master WHERE is_active = TRUE ORDER BY handle",
    )


def update_program(conn, master_id, scope_count: int | None = None, max_severity: str | None = None):
    fields = []
    params = []
    if scope_count is not None:
        fields.append("scope_count = %s")
        params.append(scope_count)
    if max_severity is not None:
        fields.append("max_severity = %s")
        params.append(max_severity)
        
    if not fields:
        return 0  # nothing to update

    fields.append("updated_at = %s")
    params.append(db.now())
    params.append(master_id)

    query = f"UPDATE bounty_master SET {', '.join(fields)} WHERE id = %s"
    return db.execute(conn, query, tuple(params))


def deactivate_program(conn, master_id):
    return db.execute(
        conn,
        "UPDATE bounty_master SET is_active = FALSE, updated_at = %s WHERE id = %s",
        (db.now(), master_id),
    )
    


def delete_program(conn, master_id):
    return db.execute(
        conn,
        "DELETE FROM bounty_master WHERE id = %s",
        (master_id,),
    )
