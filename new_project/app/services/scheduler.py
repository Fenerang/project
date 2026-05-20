import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import WebApplication
from app.services.backup_engine import BackupEngine

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _run_scheduled_backup(app_id: int) -> None:
  db: Session = SessionLocal()
  try:
    app = db.query(WebApplication).filter(WebApplication.id == app_id, WebApplication.is_active).first()
    if not app:
      return
    BackupEngine(db).run_backup(app, is_manual=False)
    logger.info("Scheduled backup completed for app_id=%s", app_id)
  except Exception:
    logger.exception("Scheduled backup failed for app_id=%s", app_id)
  finally:
    db.close()


def sync_schedules() -> None:
  """Пересоздать задания планировщика из БД."""
  scheduler.remove_all_jobs()
  db = SessionLocal()
  try:
    apps = db.query(WebApplication).filter(WebApplication.is_active.is_(True)).all()
    for app in apps:
      if not app.schedule_cron:
        continue
      parts = app.schedule_cron.strip().split()
      if len(parts) != 5:
        logger.warning("Invalid cron for app %s: %s", app.name, app.schedule_cron)
        continue
      minute, hour, day, month, day_of_week = parts
      scheduler.add_job(
        _run_scheduled_backup,
        CronTrigger(
          minute=minute,
          hour=hour,
          day=day,
          month=month,
          day_of_week=day_of_week,
        ),
        args=[app.id],
        id=f"backup_app_{app.id}",
        replace_existing=True,
      )
      logger.info("Scheduled backup for %s: %s", app.name, app.schedule_cron)
  finally:
    db.close()


def start_scheduler() -> None:
  if not scheduler.running:
    scheduler.start()
  sync_schedules()


def stop_scheduler() -> None:
  if scheduler.running:
    scheduler.shutdown(wait=False)
