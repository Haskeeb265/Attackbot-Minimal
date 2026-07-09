"""
baseline schema

Revision ID: 0001
Revises:
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "bounty_master",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("handle", sa.Text, nullable=False, unique=True),
        sa.Column("scope_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_severity", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "bounty_detail",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bounty_master.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_type", sa.Text, nullable=False),
        sa.Column("scope_identifier", sa.Text, nullable=False),
        sa.Column("scope_instructions", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("master_id", "scope_type", "scope_identifier"),
    )

    op.create_table(
        "program_weaknesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bounty_master.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weakness_id", sa.Text, nullable=False),
        sa.Column("weakness_name", sa.Text),
        sa.Column("weakness_description", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("master_id", "weakness_id"),
    )

    op.create_table(
        "bounty_exclusion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("master_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bounty_master.id", ondelete="CASCADE"), nullable=False),
        sa.Column("exclusion_category", sa.Text, nullable=False),
        sa.Column("exclusion_details", sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_index("idx_bounty_exclusion_master_id", "bounty_exclusion", ["master_id"])


def downgrade():
    op.drop_table("bounty_exclusion")
    op.drop_table("program_weaknesses")
    op.drop_table("bounty_detail")
    op.drop_table("bounty_master")