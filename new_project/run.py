import uvicorn

from app.config import settings

if __name__ == "__main__":
  settings.ensure_dirs()
  uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
