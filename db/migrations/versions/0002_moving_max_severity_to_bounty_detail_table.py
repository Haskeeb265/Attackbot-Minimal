"""
Move max_severity from bounty_master to bounty_detail.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12

"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Remove program-level severity
    op.drop_column("bounty_master", "max_severity")

    # Add scope-level severity
    op.add_column(
        "bounty_detail",
        sa.Column("max_severity", sa.Text, nullable=True),
    )


def downgrade():
    # Remove scope-level severity
    op.drop_column("bounty_detail", "max_severity")

    # Restore program-level severity
    op.add_column(
        "bounty_master",
        sa.Column("max_severity", sa.Text, nullable=True),
    )