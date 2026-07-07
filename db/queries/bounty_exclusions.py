from shared.db import db


def add_exclusion(
    conn,
    master_id,
    exclusion_category: str,
    exclusion_details: str | None = None,
):
    row = db.fetch_one(
        conn,
        """
        INSERT INTO bounty_exclusion
            (master_id, exclusion_category, exclusion_details)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (master_id, exclusion_category, exclusion_details),
    )

    return row["id"]


def get_exclusion_by_id(conn, exclusion_row_id):
    return db.fetch_one(
        conn,
        "SELECT * FROM bounty_exclusion WHERE id = %s AND is_active = TRUE",
        (exclusion_row_id,),
    )


def get_exclusions_by_master_id(conn, master_id):
    return db.fetch_all(
        conn,
        "SELECT * FROM bounty_exclusion WHERE master_id = %s AND is_active = TRUE",
        (master_id,),
    )


def list_active_exclusions(conn):
    return db.fetch_all(
        conn,
        "SELECT * FROM bounty_exclusion WHERE is_active = TRUE ORDER BY master_id",
    )


def delete_exclusions_for_program(conn, master_id):
    """Hard delete all exclusion rows for a program."""
    return db.execute(
        conn,
        "DELETE FROM bounty_exclusion WHERE master_id = %s",
        (master_id,),
    )


def update_exclusions(conn, master_id, incoming_exclusions: list[dict]):
    """
    Full replace: deletes all existing exclusion rows for this program and
    inserts the current set fresh. No history is preserved—only the
    latest scrape matters.

    incoming_exclusions: list of dicts with keys:
    exclusion_category, exclusion_details.
    """
    with db.atomic(conn):
        delete_exclusions_for_program(conn, master_id)

        for e in incoming_exclusions:
            add_exclusion(
                conn,
                master_id,
                e["exclusion_category"],
                e.get("exclusion_details"),
            )