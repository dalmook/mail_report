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


def _as_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f'Invalid integer for {name}: {value}') from exc


def _as_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f'Invalid float for {name}: {value}') from exc


@dataclass(frozen=True)
class Settings:
    app_title: str
    app_host: str
    app_port: int
    app_base_url: str

    db_path: Path
    storage_root: Path
    ingest_interval_minutes: int

    pop3_host: str
    pop3_user: str
    pop3_pass: str
    pop3_use_ssl: bool
    pop3_port: int
    pop3_delete_after_fetch: bool
    pop3_max_messages_per_run: int

    llm_enabled: bool
    llm_api_base: str
    llm_model: str
    llm_credential_key: str
    llm_user_id: str
    llm_user_type: str
    llm_send_system_name: str
    llm_timeout_seconds: int
    llm_temperature: float
    llm_max_tokens: int



def load_settings() -> Settings:
    return Settings(
        app_title=os.getenv('APP_TITLE', 'Mail Archive Operator Console'),
        app_host=os.getenv('APP_HOST', '127.0.0.1'),
        app_port=_as_int('APP_PORT', 8010),
        app_base_url=os.getenv('APP_BASE_URL', 'http://127.0.0.1:8010'),
        db_path=BASE_DIR / os.getenv('DB_PATH', 'data/archive.db'),
        storage_root=BASE_DIR / os.getenv('STORAGE_ROOT', 'storage'),
        ingest_interval_minutes=_as_int('INGEST_INTERVAL_MINUTES', 0),
        pop3_host=os.getenv('POP3_HOST', ''),
        pop3_user=os.getenv('POP3_USER', ''),
        pop3_pass=os.getenv('POP3_PASS', ''),
        pop3_use_ssl=_as_bool(os.getenv('POP3_USE_SSL', 'true'), True),
        pop3_port=_as_int('POP3_PORT', 995),
        pop3_delete_after_fetch=_as_bool(os.getenv('POP3_DELETE_AFTER_FETCH', 'false'), False),
        pop3_max_messages_per_run=_as_int('POP3_MAX_MESSAGES_PER_RUN', 30),
        llm_enabled=_as_bool(os.getenv('LLM_ENABLED', 'true'), True),
        llm_api_base=os.getenv('LLM_API_BASE', ''),
        llm_model=os.getenv('LLM_MODEL', 'openai/gpt-oss-120b'),
        llm_credential_key=os.getenv('LLM_CREDENTIAL_KEY', ''),
        llm_user_id=os.getenv('LLM_USER_ID', ''),
        llm_user_type=os.getenv('LLM_USER_TYPE', 'AD_ID'),
        llm_send_system_name=os.getenv('LLM_SEND_SYSTEM_NAME', 'GOC_MAIL_RAG_PIPELINE'),
        llm_timeout_seconds=_as_int('LLM_TIMEOUT_SECONDS', 60),
        llm_temperature=_as_float('LLM_TEMPERATURE', 0.2),
        llm_max_tokens=_as_int('LLM_MAX_TOKENS', 1200),
    )


settings = load_settings()
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
settings.storage_root.mkdir(parents=True, exist_ok=True)
(settings.storage_root / 'eml').mkdir(parents=True, exist_ok=True)
(settings.storage_root / 'attachments').mkdir(parents=True, exist_ok=True)
