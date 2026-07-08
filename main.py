from shared.db import db
from db.queries.bounty_master import upsert_program, get_program_by_name
from db.queries.bounty_detail import upsert_scope, get_scopes_by_master_id

with db.get_conn() as conn:          # ONE connection checked out
    with db.atomic(conn):             # ONE transaction
        master_id = upsert_program(conn, handle="acme_corp", scope_count=2, max_severity="critical")
        upsert_scope(conn, master_id, scope_type="url", scope_identifier="https://acme.com")
        upsert_scope(conn, master_id, scope_type="url", scope_identifier="https://api.acme.com")

# connection returned to pool here; transaction already committed

# Reading it back — can be a separate get_conn(), doesn't need atomic() for pure reads
with db.get_conn() as conn:
    program = get_program_by_name(conn, "acme_corp")
    print(program)
    scopes = get_scopes_by_master_id(conn, program["id"])
    print(scopes)