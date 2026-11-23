from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    llm_provider: str = "gemini"
    llm_model: str = ""
    gemini_api_key: SecretStr | None = None  # SecretStr: never shows up in repr/logs
    anthropic_api_key: SecretStr | None = None
    database_url: str = "postgresql://loan:loan_dev_pw@localhost:5433/loan_intake"  # local dev default
    # Comma-separated browser origins allowed to call the API (the deployed UI's URL, no trailing slash).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Where uploaded PDFs are stored; point at a mounted persistent disk in production. Blank = data/uploads.
    uploads_dir: str = ""
