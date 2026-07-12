import uuid
from sqlalchemy import Column, Text, Integer, Boolean, TIMESTAMP, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_active = Column(Boolean, nullable=False, default=True)


class BountyMaster(TimestampMixin, Base):
    __tablename__ = "bounty_master"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    handle = Column(Text, nullable=False, unique=True)
    scope_count = Column(Integer, nullable=False, default=0)


class BountyDetail(TimestampMixin, Base):
    __tablename__ = "bounty_detail"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    master_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bounty_master.id", ondelete="CASCADE"),
        nullable=False)
    
    scope_type = Column(Text, nullable=False)
    scope_identifier = Column(Text, nullable=False)
    max_severity = Column(Text)
    scope_instructions = Column(Text)

    __table_args__ = (
        UniqueConstraint("master_id", "scope_type", "scope_identifier"),
    )


class ProgramWeakness(TimestampMixin, Base):
    __tablename__ = "program_weaknesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    master_id = Column(UUID(as_uuid=True), ForeignKey("bounty_master.id", ondelete="CASCADE"), nullable=False)
    weakness_id = Column(Text, nullable=False)
    weakness_name = Column(Text)
    weakness_description = Column(Text)

    __table_args__ = (
        UniqueConstraint("master_id", "weakness_id"),
    )


class BountyExclusion(TimestampMixin, Base):
    __tablename__ = "bounty_exclusion"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    master_id = Column(UUID(as_uuid=True), ForeignKey("bounty_master.id", ondelete="CASCADE"), nullable=False)
    exclusion_category = Column(Text, nullable=False)
    exclusion_details = Column(Text)