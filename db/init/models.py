import uuid
from sqlalchemy import Column, String, Integer, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)


class BountyMaster(Base, TimestampMixin):
    __tablename__ = "bounty_master"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    handle = Column(String, nullable=False, unique=True)
    scope_count = Column(Integer, nullable=False, default=0)
    max_severity = Column(String)


class BountyDetail(Base, TimestampMixin):
    __tablename__ = "bounty_detail"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bounty_master_id = Column(UUID(as_uuid=True), ForeignKey("bounty_master.id", ondelete="CASCADE"), nullable=False)
    asset_type = Column(String, nullable=False)
    asset_identifier = Column(String, nullable=False)
    instructions = Column(String)
    is_exclusion = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("bounty_master_id", "asset_type", "asset_identifier", "is_exclusion"),
    )