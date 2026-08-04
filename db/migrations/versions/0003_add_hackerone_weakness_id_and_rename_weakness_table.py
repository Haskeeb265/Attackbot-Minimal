"""
Add hackerone_weakness_id column; normalize weakness table name.

* Renames the legacy `program_weaknesses` table to `bounty_weaknesses` when a
  database was initialized before the rename (matches the `bounty_*` naming
  convention used by the other tables). Fresh databases created from the
  current `001_schema.sql` / migration 0001 already use `bounty_weaknesses`,
  so this is a no-op for them.
* Adds `hackerone_weakness_id` (the HackerOne CWE identifier, e.g. "CWE-79")
  to `bounty_weaknesses`. The existing `weakness_id` column keeps the API's
  top-level sequential id.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # Safety net: rename the legacy table if it still exists under the old name.
    # Idempotent — no-op when the table is already `bounty_weaknesses` or absent.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'program_weaknesses'
            ) THEN
                ALTER TABLE program_weaknesses RENAME TO bounty_weaknesses;
            END IF;
        END $$;
        """
    )

    # Add the CWE identifier column (idempotent via IF NOT EXISTS).
    op.execute(
        "ALTER TABLE bounty_weaknesses ADD COLUMN IF NOT EXISTS hackerone_weakness_id TEXT"
    )


def downgrade():
    op.execute(
        "ALTER TABLE bounty_weaknesses DROP COLUMN IF EXISTS hackerone_weakness_id"
    )
