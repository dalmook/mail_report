from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


@dataclass(frozen=True)
class Settings:
    app_title: str = os.getenv('APP_TITLE', 'Mail Archive Dashboard')
    app_host: str = os.getenv('APP_HOST', '127.0.0.1')
    app_port: int = int(os.getenv('APP_PORT', '8010'))
    app_base_url: str = os.getenv('APP_BASE_URL', 'http://127.0.0.1:8010')

    db_path: Path = BASE_DIR / os.getenv('DB_PATH', 'data/archive.db')
    storage_root: Path = BASE_DIR / os.getenv('STORAGE_ROOT', 'storage')
    ingest_interval_minutes: int = int(os.getenv('INGEST_INTERVAL_MINUTES', '0'))

    pop3_host: str = os.getenv('POP3_HOST', '')
    pop3_user: str = os.getenv('POP3_USER', '')
    pop3_pass: str = os.getenv('POP3_PASS', '')
    pop3_use_ssl: bool = _as_bool(os.getenv('POP3_USE_SSL', 'true'), True)
    pop3_port: int = int(os.getenv('POP3_PORT', '995'))
    pop3_delete_after_fetch: bool = _as_bool(os.getenv('POP3_DELETE_AFTER_FETCH', 'false'), False)
    pop3_max_messages_per_run: int = int(os.getenv('POP3_MAX_MESSAGES_PER_RUN', '30'))

    llm_enabled: bool = _as_bool(os.getenv('LLM_ENABLED', 'true'), True)
    llm_api_base: str = os.getenv('LLM_API_BASE', '')
    llm_model: str = os.getenv('LLM_MODEL', 'openai/gpt-oss-120b')
    llm_credential_key: str = os.getenv('LLM_CREDENTIAL_KEY', '')
    llm_user_id: str = os.getenv('LLM_USER_ID', '')
    llm_user_type: str = os.getenv('LLM_USER_TYPE', 'AD_ID')
    llm_send_system_name: str = os.getenv('LLM_SEND_SYSTEM_NAME', 'GOC_MAIL_RAG_PIPELINE')
    llm_timeout_seconds: int = int(os.getenv('LLM_TIMEOUT_SECONDS', '60'))
    llm_temperature: float = float(os.getenv('LLM_TEMPERATURE', '0.2'))
    llm_max_tokens: int = int(os.getenv('LLM_MAX_TOKENS', '1200'))


settings = Settings()
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
settings.storage_root.mkdir(parents=True, exist_ok=True)
(settings.storage_root / 'eml').mkdir(parents=True, exist_ok=True)
(settings.storage_root / 'attachments').mkdir(parents=True, exist_ok=True)
