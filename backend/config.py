import os
import tempfile
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "AUDITRA"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"
    # Vercel's filesystem is read-only except /tmp, so the demo SQLite file lives in the temp dir.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(tempfile.gettempdir(), 'auditra.db')}" if os.getenv("VERCEL") else "sqlite:///./auditra.db",
    )
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()

# Providers hand out postgres:// URLs; SQLAlchemy needs the psycopg (v3) dialect name.
for _prefix in ("postgres://", "postgresql://"):
    if settings.DATABASE_URL.startswith(_prefix):
        settings.DATABASE_URL = "postgresql+psycopg://" + settings.DATABASE_URL[len(_prefix):]
        break
