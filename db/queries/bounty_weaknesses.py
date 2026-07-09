import shared.db as db


def add_weakness(conn, master_id, weakness_id: str, weakness_name: str | None = None, weakness_description: str | None = None):
    row = db.fetch_one(
        conn,

        """
        INSERT INTO bounty_weaknesses (master_id, weakness_id, weakness_name, weakness_description)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,

        (master_id, weakness_id, weakness_name, weakness_description),
    )

    return row["id"]


def get_weakness_by_id(conn, weakness_row_id):
    return db.fetch_one(
        conn,
        "SELECT * FROM bounty_weaknesses WHERE id = %s AND is_active = TRUE",
        (weakness_row_id,),
    )


def get_weaknesses_by_master_id(conn, master_id):
    return db.fetch_all(
        conn,
        "SELECT * FROM bounty_weaknesses WHERE master_id = %s AND is_active = TRUE",
        (master_id,),
    )


def list_active_weaknesses(conn):
    return db.fetch_all(
        conn,
        "SELECT * FROM bounty_weaknesses WHERE is_active = TRUE ORDER BY master_id",
    )


def delete_weaknesses_for_program(conn, master_id):
    """Hard delete all weakness rows for a program. Used internally by replace_weaknesses()."""
    return db.execute(
        conn,
        "DELETE FROM bounty_weaknesses WHERE master_id = %s",
        (master_id,),
    )


def update_weaknesses(conn, master_id, incoming_weaknesses: list[dict]):
    """
    Full replace: deletes all existing weakness rows for this program and
    inserts the current set fresh. No history is preserved — only the
    content as of this scrape matters, per project requirements. Wrapped
    in its own atomic() block so the delete+inserts commit or roll back
    together even if called standalone; if a caller already has an
    outer atomic() open on the same conn, this nests safely as a
    savepoint rather than starting a conflicting transaction.

    incoming_weaknesses: list of dicts with keys weakness_id,
    weakness_name, weakness_description.
    """
    with db.atomic(conn):
        delete_weaknesses_for_program(conn, master_id)
        for w in incoming_weaknesses:
            add_weakness(
                conn,
                master_id,
                w["weakness_id"],
                w.get("weakness_name"),
                w.get("weakness_description"),
            )