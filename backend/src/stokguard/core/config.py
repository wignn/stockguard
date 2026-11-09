from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STOKGUARD_", env_file=".env", extra="ignore")

    data_dir: Path = Path(__file__).resolve().parents[4] / "data"
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    secure_cookies: bool = False
    tesseract_command: str = "tesseract"
    ocr_languages: str = "eng"

    @field_validator("data_dir", mode="before")
    @classmethod
    def local_disk_only(cls, value):
        if str(value).startswith(("\\\\", "//")):
            raise ValueError("Database harus berada di disk lokal, bukan network share.")
        return Path(value).expanduser().resolve()

    @property
    def database_path(self) -> Path:
        return self.data_dir / "stokguard.db"
