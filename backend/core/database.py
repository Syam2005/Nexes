"""
NEXUS — Database Layer
PostgreSQL async via SQLAlchemy. All persistent data lives here.
No localStorage. Everything server-side and persistent across deploys.
"""
import uuid
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Column, String, Integer, DateTime, Text,
    Boolean, Float, ForeignKey, JSON, UniqueConstraint
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email         = Column(String, unique=True, nullable=False, index=True)
    name          = Column(String, nullable=False)
    photo_url     = Column(String, nullable=True)
    phone         = Column(String, nullable=True)
    auth_provider = Column(String, default="google")   # google | github
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Settings
    email_reports    = Column(Boolean, default=True)
    risk_threshold   = Column(String, default="MEDIUM")  # LOW | MEDIUM | HIGH
    theme            = Column(String, default="dark")

    github_connections = relationship(
        "GitHubConnection", back_populates="user", cascade="all, delete-orphan"
    )
    analyses = relationship(
        "Analysis", back_populates="user", cascade="all, delete-orphan"
    )


class GitHubConnection(Base):
    __tablename__ = "github_connections"
    __table_args__ = (UniqueConstraint("user_id", "github_user_id"),)

    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id         = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    github_username = Column(String, nullable=False)
    github_user_id  = Column(String, nullable=False)
    access_token    = Column(String, nullable=False)
    avatar_url      = Column(String, nullable=True)
    connected_at    = Column(DateTime, default=datetime.utcnow)
    is_primary      = Column(Boolean, default=False)

    user = relationship("User", back_populates="github_connections")


class Analysis(Base):
    __tablename__ = "analyses"

    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Input
    input_mode           = Column(String)   # file | url | zip | cicd
    source_name          = Column(String)
    github_repo          = Column(String, nullable=True)
    github_connection_id = Column(String, ForeignKey("github_connections.id"), nullable=True)

    # Status
    status = Column(String, default="pending")   # pending|running|complete|failed
    error_message = Column(Text, nullable=True)

    # Language info
    language           = Column(String, nullable=True)
    era                = Column(String, nullable=True)
    language_breakdown = Column(JSON, nullable=True)   # {"Python": 60, "JavaScript": 40}

    # Metrics
    total_files           = Column(Integer, default=0)
    total_issues          = Column(Integer, default=0)
    security_issues       = Column(Integer, default=0)
    overall_risk          = Column(String, nullable=True)
    minimality_score      = Column(Float, nullable=True)
    complexity_before     = Column(Float, nullable=True)
    complexity_after      = Column(Float, nullable=True)
    confidence_score      = Column(Float, nullable=True)
    estimated_hours_saved = Column(Float, nullable=True)
    tests_passed          = Column(Boolean, nullable=True)
    test_count            = Column(Integer, nullable=True)

    # Full report
    full_report     = Column(JSON, nullable=True)
    report_markdown = Column(Text, nullable=True)

    user    = relationship("User", back_populates="analyses")
    changes = relationship(
        "ProposedChange", back_populates="analysis", cascade="all, delete-orphan"
    )


class ProposedChange(Base):
    __tablename__ = "proposed_changes"

    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    file_path   = Column(String, nullable=False)
    issue_type  = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    old_code    = Column(Text, nullable=False)
    new_code    = Column(Text, nullable=False)
    line_start  = Column(Integer, nullable=False)
    line_end    = Column(Integer, nullable=False)
    risk_level  = Column(String, nullable=False)   # LOW | MEDIUM | HIGH
    risk_reason = Column(Text, nullable=True)
    confidence  = Column(Float, nullable=True)
    priority    = Column(Integer, default=2)        # 1=critical 2=important 3=nice
    callers     = Column(Integer, default=0)        # how many other functions call this
    status      = Column(String, default="pending") # pending|accepted|skipped|committed

    analysis = relationship("Analysis", back_populates="changes")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables. Called on app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)