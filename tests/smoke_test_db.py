"""
Smoke test for the scraping DB persistence layer.

Exercises the full lifecycle against a REAL Postgres instance:
add -> upsert -> replace weaknesses (x2, catches stale-row bugs) ->
replace exclusions (x2) -> scope add/get -> deactivate -> delete + cascade.

Everything runs inside ONE outer atomic() block that is rolled back at
the end, so the DB is left clean regardless of pass/fail. Set
ROLLBACK = False at the bottom if you want to inspect the data manually
after the run instead.
"""

import sys
import traceback

import shared.db as db
from db.queries import bounty_master as master_q
from db.queries import bounty_detail as detail_q
from db.queries import bounty_weaknesses as weakness_q
from db.queries import bounty_exclusions as exclusion_q

PASS = []
FAIL = []


def check(label, condition, detail=""):
    if condition:
        PASS.append(label)
        print(f"  [PASS] {label}")
    else:
        FAIL.append(label)
        print(f"  [FAIL] {label}  {detail}")


def run(conn):
    print("\n--- 1. add_program ---")
    master_id = master_q.add_program(conn, handle="smoketest_prog", scope_count=1, max_severity="high")
    row = master_q.get_program_by_id(conn, master_id)
    check("program inserted", row is not None)
    check("is_active True on insert", row and row["is_active"] is True)
    check("scope_count == 1", row and row["scope_count"] == 1, detail=str(row))
    created_at_original = row["created_at"]

    print("\n--- 2. upsert_program (same handle, new scope_count) ---")
    upserted_id = master_q.upsert_program(conn, handle="smoketest_prog", scope_count=5, max_severity="critical")
    check("upsert returns same PK", upserted_id == master_id, detail=f"{upserted_id} vs {master_id}")
    row2 = master_q.get_program_by_id(conn, master_id)
    check("scope_count updated to 5", row2["scope_count"] == 5, detail=str(row2))
    check("max_severity updated to critical", row2["max_severity"] == "critical")
    check("created_at unchanged", row2["created_at"] == created_at_original)
    check("updated_at changed", row2["updated_at"] != row["updated_at"])

    print("\n--- 3. replace_weaknesses first pass (w1, w2) ---")
    weakness_q.update_weaknesses(conn, master_id, [
        {"weakness_id": "CWE-79", "weakness_name": "XSS", "weakness_description": "cross site scripting"},
        {"weakness_id": "CWE-89", "weakness_name": "SQLi", "weakness_description": "sql injection"},
    ])
    weaknesses = weakness_q.get_weaknesses_by_master_id(conn, master_id)
    ids = {w["weakness_id"] for w in weaknesses}
    check("exactly 2 weaknesses present", len(weaknesses) == 2, detail=str(ids))
    check("CWE-79 and CWE-89 present", ids == {"CWE-79", "CWE-89"}, detail=str(ids))

    print("\n--- 4. replace_weaknesses second pass (w2, w3) -- stale row check ---")
    weakness_q.update_weaknesses(conn, master_id, [
        {"weakness_id": "CWE-89", "weakness_name": "SQLi", "weakness_description": "sql injection"},
        {"weakness_id": "CWE-22", "weakness_name": "Path Traversal", "weakness_description": "path traversal"},
    ])
    weaknesses2 = weakness_q.get_weaknesses_by_master_id(conn, master_id)
    ids2 = {w["weakness_id"] for w in weaknesses2}
    check("CWE-79 removed (stale row cleared)", "CWE-79" not in ids2, detail=str(ids2))
    check("CWE-89 retained", "CWE-89" in ids2, detail=str(ids2))
    check("CWE-22 newly added", "CWE-22" in ids2, detail=str(ids2))
    check("exactly 2 weaknesses after replace", len(weaknesses2) == 2, detail=str(ids2))

    print("\n--- 5. replace_exclusions first pass ---")
    exclusion_q.update_exclusions(conn, master_id, [
        {"exclusion_category": "physical", "exclusion_details": "social engineering out of scope"},
        {"exclusion_category": "dos", "exclusion_details": "denial of service out of scope"},
    ])
    exclusions = exclusion_q.get_exclusions_by_master_id(conn, master_id)
    cats = {e["exclusion_category"] for e in exclusions}
    check("exactly 2 exclusions present", len(exclusions) == 2, detail=str(cats))
    check("physical and dos present", cats == {"physical", "dos"}, detail=str(cats))

    print("\n--- 6. replace_exclusions second pass -- stale row check ---")
    exclusion_q.update_exclusions(conn, master_id, [
        {"exclusion_category": "dos", "exclusion_details": "denial of service out of scope"},
        {"exclusion_category": "spam", "exclusion_details": "spam/social engineering out of scope"},
    ])
    exclusions2 = exclusion_q.get_exclusions_by_master_id(conn, master_id)
    cats2 = {e["exclusion_category"] for e in exclusions2}
    check("physical removed (stale row cleared)", "physical" not in cats2, detail=str(cats2))
    check("dos retained", "dos" in cats2, detail=str(cats2))
    check("spam newly added", "spam" in cats2, detail=str(cats2))
    check("exactly 2 exclusions after replace", len(exclusions2) == 2, detail=str(cats2))

    print("\n--- 7. add_scope / get_scopes_by_master_id ---")
    scope_id = detail_q.add_scope(conn, master_id, scope_type="url", scope_identifier="*.example.com",
                                   scope_instructions="in scope, standard testing rules")
    scopes = detail_q.get_scopes_by_master_id(conn, master_id)
    check("scope inserted and retrievable", any(s["id"] == scope_id for s in scopes), detail=str(scopes))
    check("scope_identifier correct", any(s["scope_identifier"] == "*.example.com" for s in scopes))

    print("\n--- 8. deactivate_program ---")
    master_q.deactivate_program(conn, master_id)
    deactivated = master_q.get_program_by_id(conn, master_id)
    check("get_program_by_id returns None after deactivate (is_active filter)", deactivated is None,
          detail=str(deactivated))
    raw = db.fetch_one(conn, "SELECT is_active FROM bounty_master WHERE id = %s", (master_id,))
    check("row still physically present with is_active=False", raw is not None and raw["is_active"] is False,
          detail=str(raw))
    raw_scope = db.fetch_one(conn, "SELECT is_active FROM bounty_detail WHERE id = %s", (scope_id,))
    print(f"  [INFO] child scope is_active after parent deactivate: {raw_scope['is_active']} "
          f"(NOTE: deactivate_program does NOT cascade is_active to children -- confirm this is intended)")

    print("\n--- 9. delete_program -- cascade check ---")
    master_q.delete_program(conn, master_id)
    gone_master = db.fetch_one(conn, "SELECT 1 FROM bounty_master WHERE id = %s", (master_id,))
    check("master row physically deleted", gone_master is None)
    gone_scope = db.fetch_one(conn, "SELECT 1 FROM bounty_detail WHERE master_id = %s", (master_id,))
    check("child bounty_detail rows cascade-deleted", gone_scope is None)
    gone_weak = db.fetch_one(conn, "SELECT 1 FROM bounty_weaknesses WHERE master_id = %s", (master_id,))
    check("child bounty_weaknesses rows cascade-deleted", gone_weak is None)
    gone_excl = db.fetch_one(conn, "SELECT 1 FROM bounty_exclusion WHERE master_id = %s", (master_id,))
    check("child bounty_exclusion rows cascade-deleted", gone_excl is None)


class _ForceRollback(Exception):
    """Internal sentinel used only to force the transaction to roll back."""
    pass


if __name__ == "__main__":
    ROLLBACK = True  # set False to keep test data for manual inspection

    run_error = None
    try:
        with db.get_conn() as conn:
            try:
                with conn.transaction():
                    try:
                        run(conn)
                    except Exception as e:
                        run_error = e
                        print("\n[ERROR] Exception raised during run() -- this is what actually happened:")
                        traceback.print_exc()
                    finally:
                        if ROLLBACK:
                            raise _ForceRollback()
            except _ForceRollback:
                print("\n[INFO] Rolled back all test data (ROLLBACK=True).")
    finally:
        db.close()

    print(f"\n=== RESULTS: {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        print("Failed checks:")
        for f in FAIL:
            print(f"  - {f}")
        sys.exit(1)
    sys.exit(0)