import shared.db as db

from db.repos import bounty_master
from db.repos import bounty_detail
from db.repos import bounty_weaknesses
from db.repos import bounty_exclusions


def persist_program(conn, mapped_program: dict):
    with db.atomic(conn):

        master = mapped_program["master"]

        master_id = bounty_master.upsert_program(
            conn,
            handle=master["handle"],
            scope_count=master["scope_count"],
        )

        bounty_detail.update_scopes(
            conn,
            master_id,
            mapped_program["scopes"],
        )

        bounty_weaknesses.replace_weaknesses(
            conn,
            master_id,
            mapped_program["weaknesses"],
        )

        bounty_exclusions.replace_exclusions(
            conn,
            master_id,
            mapped_program["exclusions"],
        )

        return master_id