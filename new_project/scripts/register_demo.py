#!/usr/bin/env python3
"""Регистрация demo_app в системе бэкапов через API."""

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = str(ROOT / "demo_app")
DB_CONN = f"sqlite:///{ROOT / 'demo_app' / 'data' / 'app.db'}"


def main():
  base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
  payload = {
    "name": "Demo Notes App",
    "description": "Демонстрационное веб-приложение с SQLite",
    "source_path": DEMO_PATH,
    "db_type": "sqlite",
    "db_connection": DB_CONN,
    "schedule_cron": "0 3 * * *",
    "retention_days": 14,
  }
  r = httpx.post(f"{base}/api/applications", json=payload, timeout=10)
  if r.status_code == 201:
    print("Зарегистрировано:", r.json())
  elif r.status_code == 400 and "уже существует" in r.text:
    print("Demo app уже зарегистрирован")
  else:
    print("Ошибка:", r.status_code, r.text)
    sys.exit(1)


if __name__ == "__main__":
  main()
