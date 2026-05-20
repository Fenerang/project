from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    backup_storage_path: Path = Path("./data/backups")
    database_url: str = "sqlite:///./data/system.db"
    secret_key: str = "dev-secret-key"
    host: str = "0.0.0.0"
    port: int = 8000

    def ensure_dirs(self) -> None:
        self.backup_storage_path.mkdir(parents=True, exist_ok=True)
        Path("./data").mkdir(parents=True, exist_ok=True)


settings = Settings()
