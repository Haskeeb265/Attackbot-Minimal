"""
Smoke test for the scraping DB persistence layer.

Exercises the full lifecycle against a REAL Postgres instance:
add -> upsert -> replace weaknesses (x2, catches stale-row bugs) ->
replace exclusions (x2) -> scope add/get -> deactivate (soft, with
is_active cascade) -> delete + FK cascade.

Everything runs inside ONE outer atomic() block that is rolled back at
the end, so the DB is left clean regardless of pass/fail. Set
ROLLBACK = False at the bottom if you want to inspect the data manually
after the run instead.

Run with the repo root on the path:
    PYTHONPATH=. python tests/scraper/smoke_test_db.py
"""

import sys
import traceback

import shared.db as db
from db.repos import bounty_master as master_q
from db.repos import bounty_detail as detail_q
from db.repos import bounty_weaknesses as weakness_q
from db.repos import bounty_exclusions as exclusion_q

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
    master_id = master_q.add_program(conn, handle="smoketest_prog", scope_count=1)
    row = master_q.get_program_by_id(conn, master_id)
    check("program inserted", row is not None)
    check("is_active True on insert", row and row["is_active"] is True)
    check("scope_count == 1", row and row["scope_count"] == 1, detail=str(row))
    created_at_original = row["created_at"]

    print("\n--- 2. upsert_program (same handle, new scope_count) ---")
    upserted_id = master_q.upsert_program(conn, handle="smoketest_prog", scope_count=5)
    check("upsert returns same PK", upserted_id == master_id, detail=f"{upserted_id} vs {master_id}")
    row2 = master_q.get_program_by_id(conn, master_id)
    check("scope_count updated to 5", row2["scope_count"] == 5, detail=str(row2))
    check("created_at unchanged", row2["created_at"] == created_at_original)
    check("updated_at changed", row2["updated_at"] != row["updated_at"])

    print("\n--- 3. replace_weaknesses first pass (w1, w2) ---")
    weakness_q.replace_weaknesses(conn, master_id, [
        {"weakness_id": "42", "hackerone_weakness_id": "CWE-79",
         "weakness_name": "XSS", "weakness_description": "cross site scripting"},
        {"weakness_id": "57", "hackerone_weakness_id": "CWE-89",
         "weakness_name": "SQLi", "weakness_description": "sql injection"},
    ])
    weaknesses = weakness_q.get_weaknesses_by_master_id(conn, master_id)
    ids = {w["weakness_id"] for w in weaknesses}
    check("exactly 2 weaknesses present", len(weaknesses) == 2, detail=str(ids))
    check("API ids 42 and 57 present", ids == {"42", "57"}, detail=str(ids))
    # The CWE identifier round-trips into hackerone_weakness_id
    by_id = {w["weakness_id"]: w for w in weaknesses}
    check("hackerone_weakness_id = CWE-79 round-trips",
          by_id.get("42", {}).get("hackerone_weakness_id") == "CWE-79", detail=str(by_id))

    print("\n--- 4. replace_weaknesses second pass (w2, w3) -- stale row check ---")
    weakness_q.replace_weaknesses(conn, master_id, [
        {"weakness_id": "57", "hackerone_weakness_id": "CWE-89",
         "weakness_name": "SQLi", "weakness_description": "sql injection"},
        {"weakness_id": "73", "hackerone_weakness_id": "CWE-22",
         "weakness_name": "Path Traversal", "weakness_description": "path traversal"},
    ])
    weaknesses2 = weakness_q.get_weaknesses_by_master_id(conn, master_id)
    ids2 = {w["weakness_id"] for w in weaknesses2}
    check("weakness 42 removed (stale row cleared)", "42" not in ids2, detail=str(ids2))
    check("weakness 57 retained", "57" in ids2, detail=str(ids2))
    check("weakness 73 newly added", "73" in ids2, detail=str(ids2))
    check("exactly 2 weaknesses after replace", len(weaknesses2) == 2, detail=str(ids2))

    print("\n--- 5. replace_exclusions first pass ---")
    exclusion_q.replace_exclusions(conn, master_id, [
        {"exclusion_category": "physical", "exclusion_details": "social engineering out of scope"},
        {"exclusion_category": "dos", "exclusion_details": "denial of service out of scope"},
    ])
    exclusions = exclusion_q.get_exclusions_by_master_id(conn, master_id)
    cats = {e["exclusion_category"] for e in exclusions}
    check("exactly 2 exclusions present", len(exclusions) == 2, detail=str(cats))
    check("physical and dos present", cats == {"physical", "dos"}, detail=str(cats))

    print("\n--- 6. replace_exclusions second pass -- stale row check ---")
    exclusion_q.replace_exclusions(conn, master_id, [
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

    print("\n--- 8. deactivate_program -- soft delete + is_active cascade ---")
    master_q.deactivate_program(conn, master_id)
    deactivated = master_q.get_program_by_id(conn, master_id)
    check("get_program_by_id returns None after deactivate (is_active filter)", deactivated is None,
          detail=str(deactivated))
    raw = db.fetch_one(conn, "SELECT is_active FROM bounty_master WHERE id = %s", (master_id,))
    check("master row still physically present with is_active=False", raw is not None and raw["is_active"] is False,
          detail=str(raw))

    # Child rows must be soft-deactivated too (Bug #5 fix)
    raw_scope = db.fetch_one(conn, "SELECT is_active FROM bounty_detail WHERE id = %s", (scope_id,))
    check("child bounty_detail is_active cascaded to False", raw_scope is not None and raw_scope["is_active"] is False,
          detail=str(raw_scope))
    raw_weak = db.fetch_one(conn, "SELECT is_active FROM bounty_weaknesses WHERE master_id = %s", (master_id,))
    check("child bounty_weaknesses is_active cascaded to False", raw_weak is not None and raw_weak["is_active"] is False,
          detail=str(raw_weak))
    raw_excl = db.fetch_one(conn, "SELECT is_active FROM bounty_exclusion WHERE master_id = %s", (master_id,))
    check("child bounty_exclusion is_active cascaded to False", raw_excl is not None and raw_excl["is_active"] is False,
          detail=str(raw_excl))

    # Active-filtered reads now return nothing for the deactivated program
    active_scopes = detail_q.get_scopes_by_master_id(conn, master_id)
    check("get_scopes_by_master_id returns [] after deactivate (is_active filter)",
          active_scopes == [], detail=str(active_scopes))

    print("\n--- 9. delete_program -- FK cascade check ---")
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
