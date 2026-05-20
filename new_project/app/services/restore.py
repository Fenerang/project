from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Optional
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from app.models import BackupRecord, DbType, WebApplication

logger = logging.getLogger(__name__)


class RestoreService:
  """Восстановление веб-приложения из архива бэкапа."""

  def restore(self, app: WebApplication, backup: BackupRecord, *, target_path: Optional[str] = None) -> dict:
    if not backup.archive_path:
      raise ValueError("У записи бэкапа нет пути к архиву")
    archive = Path(backup.archive_path)
    if not archive.exists():
      raise FileNotFoundError(f"Архив не найден: {archive}")

    restore_to = Path(target_path or app.source_path).resolve()
    restore_to.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
      tmp_path = Path(tmp)
      with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(tmp_path)

      manifest_path = tmp_path / "manifest.json"
      manifest = {}
      if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

      files_src = tmp_path / "files"
      if files_src.exists():
        if restore_to.exists():
          shutil.rmtree(restore_to)
        shutil.copytree(files_src, restore_to)

      db_restored = False
      db_dir = tmp_path / "database"
      if db_dir.exists() and app.db_type != DbType.NONE and app.db_connection:
        self._restore_database(app, db_dir)
        db_restored = True

    return {
      "restored_to": str(restore_to),
      "database_restored": db_restored,
      "manifest": manifest,
    }

  def _restore_database(self, app: WebApplication, db_dir: Path) -> None:
    if app.db_type == DbType.SQLITE:
      src = db_dir / "database.sqlite"
      if not src.exists():
        raise FileNotFoundError("SQLite дамп не найден в архиве")
      dest = Path(app.db_connection.replace("sqlite:///", "")).resolve()
      dest.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(src, dest)
    elif app.db_type == DbType.POSTGRESQL:
      sql_file = db_dir / "database.sql"
      if not sql_file.exists():
        raise FileNotFoundError("PostgreSQL дамп не найден в архиве")
      parsed = urlparse(app.db_connection)
      env = {"PGPASSWORD": parsed.password or ""}
      cmd = [
        "psql",
        "-h",
        parsed.hostname or "localhost",
        "-p",
        str(parsed.port or 5432),
        "-U",
        parsed.username or "postgres",
        "-d",
        parsed.path.lstrip("/"),
        "-f",
        str(sql_file),
      ]
      subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
    elif app.db_type == DbType.MYSQL:
      sql_file = db_dir / "database.sql"
      if not sql_file.exists():
        raise FileNotFoundError("MySQL дамп не найден в архиве")
      parsed = urlparse(app.db_connection)
      cmd = [
        "mysql",
        "-h",
        parsed.hostname or "localhost",
        "-P",
        str(parsed.port or 3306),
        "-u",
        parsed.username or "root",
        f"-p{parsed.password or ''}",
        parsed.path.lstrip("/"),
      ]
      with open(sql_file, encoding="utf-8") as f:
        subprocess.run(cmd, stdin=f, check=True, stderr=subprocess.PIPE, text=True)
