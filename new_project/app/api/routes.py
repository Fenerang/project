from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BackupRecord, BackupStatus, WebApplication
from app.schemas import (
  BackupRecordResponse,
  DashboardStats,
  WebApplicationCreate,
  WebApplicationResponse,
  WebApplicationUpdate,
)
from app.services.backup_engine import BackupEngine
from app.services.restore import RestoreService
from app.services import scheduler as sched

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
  apps = db.query(WebApplication).order_by(WebApplication.created_at.desc()).all()
  recent = db.query(BackupRecord).order_by(BackupRecord.started_at.desc()).limit(10).all()
  stats = _get_stats(db)
  return templates.TemplateResponse(
    "index.html",
    {"request": request, "apps": apps, "recent_backups": recent, "stats": stats},
  )


@router.get("/api/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
  return _get_stats(db)


def _get_stats(db: Session) -> DashboardStats:
  total_apps = db.query(func.count(WebApplication.id)).scalar() or 0
  active_apps = db.query(func.count(WebApplication.id)).filter(WebApplication.is_active).scalar() or 0
  total_backups = db.query(func.count(BackupRecord.id)).scalar() or 0
  successful = (
    db.query(func.count(BackupRecord.id)).filter(BackupRecord.status == BackupStatus.SUCCESS).scalar() or 0
  )
  failed = db.query(func.count(BackupRecord.id)).filter(BackupRecord.status == BackupStatus.FAILED).scalar() or 0
  storage = db.query(func.coalesce(func.sum(BackupRecord.size_bytes), 0)).scalar() or 0
  return DashboardStats(
    total_applications=total_apps,
    active_applications=active_apps,
    total_backups=total_backups,
    successful_backups=successful,
    failed_backups=failed,
    total_storage_bytes=storage,
  )


@router.get("/api/applications", response_model=List[WebApplicationResponse])
def list_applications(db: Session = Depends(get_db)):
  return db.query(WebApplication).order_by(WebApplication.name).all()


@router.post("/api/applications", response_model=WebApplicationResponse, status_code=201)
def create_application(payload: WebApplicationCreate, db: Session = Depends(get_db)):
  if db.query(WebApplication).filter(WebApplication.name == payload.name).first():
    raise HTTPException(400, "Приложение с таким именем уже существует")
  if not Path(payload.source_path).exists():
    raise HTTPException(400, f"Путь не существует: {payload.source_path}")

  app = WebApplication(**payload.model_dump())
  db.add(app)
  db.commit()
  db.refresh(app)
  sched.sync_schedules()
  return app


@router.get("/api/applications/{app_id}", response_model=WebApplicationResponse)
def get_application(app_id: int, db: Session = Depends(get_db)):
  app = db.get(WebApplication, app_id)
  if not app:
    raise HTTPException(404, "Приложение не найдено")
  return app


@router.patch("/api/applications/{app_id}", response_model=WebApplicationResponse)
def update_application(app_id: int, payload: WebApplicationUpdate, db: Session = Depends(get_db)):
  app = db.get(WebApplication, app_id)
  if not app:
    raise HTTPException(404, "Приложение не найдено")
  for key, value in payload.model_dump(exclude_unset=True).items():
    setattr(app, key, value)
  db.commit()
  db.refresh(app)
  sched.sync_schedules()
  return app


@router.delete("/api/applications/{app_id}", status_code=204)
def delete_application(app_id: int, db: Session = Depends(get_db)):
  app = db.get(WebApplication, app_id)
  if not app:
    raise HTTPException(404, "Приложение не найдено")
  for backup in app.backups:
    if backup.archive_path and Path(backup.archive_path).exists():
      Path(backup.archive_path).unlink()
  db.delete(app)
  db.commit()
  sched.sync_schedules()


@router.get("/api/applications/{app_id}/backups", response_model=List[BackupRecordResponse])
def list_backups(app_id: int, db: Session = Depends(get_db)):
  if not db.get(WebApplication, app_id):
    raise HTTPException(404, "Приложение не найдено")
  return (
    db.query(BackupRecord)
    .filter(BackupRecord.application_id == app_id)
    .order_by(BackupRecord.started_at.desc())
    .all()
  )


@router.post("/api/applications/{app_id}/backups", response_model=BackupRecordResponse, status_code=201)
def create_backup(app_id: int, db: Session = Depends(get_db)):
  app = db.get(WebApplication, app_id)
  if not app:
    raise HTTPException(404, "Приложение не найдено")
  if not app.is_active:
    raise HTTPException(400, "Приложение отключено")
  return BackupEngine(db).run_backup(app, is_manual=True)


@router.post("/api/backups/{backup_id}/restore")
def restore_backup(backup_id: int, target_path: Optional[str] = None, db: Session = Depends(get_db)):
  backup = db.get(BackupRecord, backup_id)
  if not backup:
    raise HTTPException(404, "Бэкап не найден")
  if backup.status != BackupStatus.SUCCESS:
    raise HTTPException(400, "Можно восстановить только успешный бэкап")
  app = db.get(WebApplication, backup.application_id)
  if not app:
    raise HTTPException(404, "Приложение не найдено")
  try:
    result = RestoreService().restore(app, backup, target_path=target_path)
    return {"status": "ok", **result}
  except Exception as exc:
    raise HTTPException(500, f"Ошибка восстановления: {exc}") from exc


@router.delete("/api/backups/{backup_id}", status_code=204)
def delete_backup(backup_id: int, db: Session = Depends(get_db)):
  backup = db.get(BackupRecord, backup_id)
  if not backup:
    raise HTTPException(404, "Бэкап не найден")
  if backup.archive_path and Path(backup.archive_path).exists():
    Path(backup.archive_path).unlink()
  db.delete(backup)
  db.commit()
