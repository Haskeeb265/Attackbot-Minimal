import shared.db as db


def add_weakness(
    conn,
    master_id,
    weakness_id: str,
    hackerone_weakness_id: str | None = None,
    weakness_name: str | None = None,
    weakness_description: str | None = None,
):
    row = db.fetch_one(
        conn,
        """
        INSERT INTO bounty_weaknesses
            (
                master_id,
                weakness_id,
                hackerone_weakness_id,
                weakness_name,
                weakness_description
            )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            master_id,
            weakness_id,
            hackerone_weakness_id,
            weakness_name,
            weakness_description,
        ),
    )

    return row["id"]


def get_weakness_by_id(conn, weakness_row_id):
    return db.fetch_one(
        conn,
        """
        SELECT *
        FROM bounty_weaknesses
        WHERE id = %s
          AND is_active = TRUE
        """,
        (weakness_row_id,),
    )


def get_weaknesses_by_master_id(conn, master_id):
    return db.fetch_all(
        conn,
        """
        SELECT *
        FROM bounty_weaknesses
        WHERE master_id = %s
          AND is_active = TRUE
        """,
        (master_id,),
    )


def list_active_weaknesses(conn):
    return db.fetch_all(
        conn,
        """
        SELECT *
        FROM bounty_weaknesses
        WHERE is_active = TRUE
        ORDER BY master_id
        """,
    )


def delete_weaknesses_for_program(conn, master_id):
    """
    Hard delete all weakness rows for a program.
    """
    return db.execute(
        conn,
        """
        DELETE FROM bounty_weaknesses
        WHERE master_id = %s
        """,
        (master_id,),
    )


def replace_weaknesses(
    conn,
    master_id,
    incoming_weaknesses: list[dict],
):
    """
    Full replace: deletes all existing weakness rows for this program
    and inserts the latest scraped weaknesses.

    incoming_weaknesses should contain dictionaries with keys:
        - weakness_id
        - hackerone_weakness_id (optional)
        - weakness_name (optional)
        - weakness_description (optional)
    """
    with db.atomic(conn):
        delete_weaknesses_for_program(conn, master_id)

        for weakness in incoming_weaknesses:
            add_weakness(
                conn,
                master_id,
                weakness["weakness_id"],
                weakness.get("hackerone_weakness_id"),
                weakness.get("weakness_name"),
                weakness.get("weakness_description"),
            )