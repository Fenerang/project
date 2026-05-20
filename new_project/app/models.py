from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DbType(str, enum.Enum):
    NONE = "none"
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class BackupStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class WebApplication(Base):
    __tablename__ = "web_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    db_type: Mapped[DbType] = mapped_column(Enum(DbType), default=DbType.NONE)
    db_connection: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    backups: Mapped[List["BackupRecord"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class BackupRecord(Base):
    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("web_applications.id"), nullable=False)
    status: Mapped[BackupStatus] = mapped_column(Enum(BackupStatus), default=BackupStatus.PENDING)
    backup_type: Mapped[str] = mapped_column(String(32), default="full")
    archive_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    application: Mapped["WebApplication"] = relationship(back_populates="backups")
