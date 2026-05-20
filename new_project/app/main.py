import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import router
from app.database import init_db
from app.services import scheduler as sched

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
  init_db()
  sched.start_scheduler()
  logger.info("WebBackup system started")
  yield
  sched.stop_scheduler()
  logger.info("WebBackup system stopped")


app = FastAPI(
  title="WebBackup",
  description="Система резервного копирования веб-приложений",
  version="1.0.0",
  lifespan=lifespan,
)

app.include_router(router)
if STATIC_DIR.exists():
  app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
