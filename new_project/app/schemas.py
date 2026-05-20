from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models import BackupStatus, DbType


class WebApplicationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_path: str
    db_type: DbType = DbType.NONE
    db_connection: Optional[str] = None
    schedule_cron: Optional[str] = Field(None, description="Cron: мин час день месяц день_недели")
    retention_days: int = Field(30, ge=1, le=365)


class WebApplicationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_path: Optional[str] = None
    db_type: Optional[DbType] = None
    db_connection: Optional[str] = None
    schedule_cron: Optional[str] = None
    retention_days: Optional[int] = None
    is_active: Optional[bool] = None


class WebApplicationResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    source_path: str
    db_type: DbType
    db_connection: Optional[str]
    schedule_cron: Optional[str]
    retention_days: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupRecordResponse(BaseModel):
    id: int
    application_id: int
    status: BackupStatus
    backup_type: str
    archive_path: Optional[str]
    size_bytes: Optional[int]
    error_message: Optional[str]
    is_manual: bool
    started_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_applications: int
    active_applications: int
    total_backups: int
    successful_backups: int
    failed_backups: int
    total_storage_bytes: int
