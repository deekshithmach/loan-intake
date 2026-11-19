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
