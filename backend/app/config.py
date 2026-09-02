import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CLEANED_DIR = DATA_DIR / "cleaned"
DB_DIR = DATA_DIR / "db"
REPORTS_DIR = BASE_DIR / "reports"

for directory in [DATA_DIR, UPLOADS_DIR, CLEANED_DIR, DB_DIR, REPORTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

try:
    from pydantic_settings import BaseSettings
    class Settings(BaseSettings):
        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        HOST: str = "127.0.0.1"
        PORT: int = 8000
        
        class Config:
            env_file = str(BASE_DIR / ".env")
            extra = "ignore"

    settings = Settings()
except ImportError:
    class Settings:
        def __init__(self):
            self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
            self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
            self.HOST = "127.0.0.1"
            self.PORT = 8000

    settings = Settings()
