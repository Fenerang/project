"""Демо веб-приложение для тестирования системы бэкапов."""

import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DB_PATH = Path(__file__).parent / "data" / "app.db"
STATIC_DIR = Path(__file__).parent / "static"


def init_db() -> None:
  DB_PATH.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(DB_PATH)
  conn.execute(
    """
    CREATE TABLE IF NOT EXISTS notes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      content TEXT,
      created_at TEXT NOT NULL
    )
    """
  )
  count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
  if count == 0:
    conn.execute(
      "INSERT INTO notes (title, content, created_at) VALUES (?, ?, ?)",
      ("Добро пожаловать", "Это демо-заметка для проекта WebBackup", datetime.utcnow().isoformat()),
    )
  conn.commit()
  conn.close()


class Handler(BaseHTTPRequestHandler):
  def do_GET(self):
    parsed = urlparse(self.path)
    if parsed.path == "/":
      self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
    elif parsed.path == "/api/notes":
      self._json_response(self._get_notes())
    elif parsed.path.startswith("/static/"):
      rel = parsed.path[len("/static/") :]
      self._serve_file(STATIC_DIR / rel, self._guess_type(rel))
    else:
      self.send_error(404)

  def do_POST(self):
    if self.path != "/api/notes":
      self.send_error(404)
      return
    length = int(self.headers.get("Content-Length", 0))
    body = self.rfile.read(length).decode()
    params = parse_qs(body)
    title = params.get("title", [""])[0]
    content = params.get("content", [""])[0]
    if not title:
      self.send_error(400)
      return
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
      "INSERT INTO notes (title, content, created_at) VALUES (?, ?, ?)",
      (title, content, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    self._json_response({"status": "ok"})

  def _get_notes(self) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, title, content, created_at FROM notes ORDER BY id DESC").fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "content": r[2], "created_at": r[3]} for r in rows]

  def _serve_file(self, path: Path, content_type: str):
    if not path.exists():
      self.send_error(404)
      return
    self.send_response(200)
    self.send_header("Content-Type", content_type)
    self.end_headers()
    self.wfile.write(path.read_bytes())

  def _json_response(self, data):
    import json

    body = json.dumps(data, ensure_ascii=False).encode()
    self.send_response(200)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _guess_type(self, name: str) -> str:
    if name.endswith(".css"):
      return "text/css"
    if name.endswith(".js"):
      return "application/javascript"
    return "application/octet-stream"

  def log_message(self, format, *args):
    pass


def main():
  init_db()
  port = 3000
  server = HTTPServer(("127.0.0.1", port), Handler)
  print(f"Demo app: http://127.0.0.1:{port}")
  server.serve_forever()


if __name__ == "__main__":
  main()
