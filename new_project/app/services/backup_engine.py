from __future__ import annotations

import json
import logging
from typing import Optional
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import settings
from app.models import BackupRecord, BackupStatus, DbType, WebApplication

logger = logging.getLogger(__name__)


class BackupEngine:
  """Создание архивов файлов и дампов БД веб-приложений."""

  def __init__(self, db: Session) -> None:
    self.db = db

  def run_backup(self, app: WebApplication, *, is_manual: bool = True) -> BackupRecord:
    record = BackupRecord(
      application_id=app.id,
      status=BackupStatus.RUNNING,
      backup_type="full",
      is_manual=is_manual,
    )
    self.db.add(record)
    self.db.commit()
    self.db.refresh(record)

    try:
      archive_path = self._create_backup_archive(app)
      record.archive_path = str(archive_path)
      record.size_bytes = archive_path.stat().st_size
      record.status = BackupStatus.SUCCESS
      record.finished_at = datetime.utcnow()
      self._cleanup_old_backups(app)
    except Exception as exc:
      logger.exception("Backup failed for app %s", app.name)
      record.status = BackupStatus.FAILED
      record.error_message = str(exc)
      record.finished_at = datetime.utcnow()

    self.db.commit()
    self.db.refresh(record)
    return record

  def _create_backup_archive(self, app: WebApplication) -> Path:
    source = Path(app.source_path).resolve()
    if not source.exists():
      raise FileNotFoundError(f"Путь приложения не найден: {source}")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    app_dir = settings.backup_storage_path / f"app_{app.id}"
    app_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"{app.name}_{timestamp}.tar.gz"
    archive_path = app_dir / archive_name

    with tempfile.TemporaryDirectory() as tmp:
      tmp_path = Path(tmp)
      manifest = {
        "application": app.name,
        "source_path": str(source),
        "db_type": app.db_type.value,
        "created_at": datetime.utcnow().isoformat(),
      }

      files_dest = tmp_path / "files"
      shutil.copytree(source, files_dest, dirs_exist_ok=True)
      manifest["files_included"] = True

      if app.db_type != DbType.NONE and app.db_connection:
        db_dest = tmp_path / "database"
        db_dest.mkdir()
        dump_file = self._dump_database(app, db_dest)
        manifest["database_dump"] = dump_file.name if dump_file else None

      (tmp_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
      )

      with tarfile.open(archive_path, "w:gz") as tar:
        for item in tmp_path.iterdir():
          tar.add(item, arcname=item.name)

    return archive_path

  def _dump_database(self, app: WebApplication, dest: Path) -> Optional[Path]:
    if app.db_type == DbType.SQLITE:
      return self._dump_sqlite(app.db_connection, dest)
    if app.db_type == DbType.POSTGRESQL:
      return self._dump_postgresql(app.db_connection, dest)
    if app.db_type == DbType.MYSQL:
      return self._dump_mysql(app.db_connection, dest)
    return None

  def _dump_sqlite(self, connection: Optional[str], dest: Path) -> Path:
    if not connection:
      raise ValueError("Не указана строка подключения SQLite")
    db_path = Path(connection.replace("sqlite:///", "")).resolve()
    if not db_path.exists():
      raise FileNotFoundError(f"SQLite БД не найдена: {db_path}")
    out = dest / "database.sqlite"
    shutil.copy2(db_path, out)
    return out

  def _dump_postgresql(self, connection: Optional[str], dest: Path) -> Path:
    if not connection:
      raise ValueError("Не указана строка подключения PostgreSQL")
    out = dest / "database.sql"
    parsed = urlparse(connection)
    env = {"PGPASSWORD": parsed.password or ""}
    cmd = [
      "pg_dump",
      "-h",
      parsed.hostname or "localhost",
      "-p",
      str(parsed.port or 5432),
      "-U",
      parsed.username or "postgres",
      "-d",
      parsed.path.lstrip("/"),
      "-f",
      str(out),
    ]
    subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
    return out

  def _dump_mysql(self, connection: Optional[str], dest: Path) -> Path:
    if not connection:
      raise ValueError("Не указана строка подключения MySQL")
    out = dest / "database.sql"
    parsed = urlparse(connection)
    cmd = [
      "mysqldump",
      "-h",
      parsed.hostname or "localhost",
      "-P",
      str(parsed.port or 3306),
      "-u",
      parsed.username or "root",
      f"-p{parsed.password or ''}",
      parsed.path.lstrip("/"),
    ]
    with open(out, "w", encoding="utf-8") as f:
      subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.PIPE, text=True)
    return out

  def _cleanup_old_backups(self, app: WebApplication) -> None:
    cutoff = datetime.utcnow() - timedelta(days=app.retention_days)
    old_records = (
      self.db.query(BackupRecord)
      .filter(
        BackupRecord.application_id == app.id,
        BackupRecord.status == BackupStatus.SUCCESS,
        BackupRecord.started_at < cutoff,
      )
      .all()
    )
    for record in old_records:
      if record.archive_path:
        path = Path(record.archive_path)
        if path.exists():
          path.unlink()
      self.db.delete(record)
    self.db.commit()
