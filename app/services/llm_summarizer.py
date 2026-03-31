from __future__ import annotations

import json
import uuid
from typing import Any

import requests

from ..config import settings


class LLMDisabledError(RuntimeError):
    pass


class LLMService:
    def __init__(self) -> None:
        self.enabled = bool(
            settings.llm_enabled
            and settings.llm_api_base
            and settings.llm_credential_key
            and settings.llm_user_id
        )

    def _headers(self) -> dict[str, str]:
        return {
            'x-dep-ticket': settings.llm_credential_key,
            'Send-System-Name': settings.llm_send_system_name,
            'User-Id': settings.llm_user_id,
            'User-Type': settings.llm_user_type,
            'Prompt-Msg-Id': str(uuid.uuid4()),
            'Completion-Msg-Id': str(uuid.uuid4()),
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def summarize_mail(self, subject: str, body_text: str) -> dict[str, Any]:
        if not self.enabled:
            raise LLMDisabledError('LLM is disabled or required environment values are missing.')

        prompt = f'''아래 메일을 분석해서 반드시 JSON 하나만 반환하세요.

[메일 제목]
{subject}

[메일 본문]
{body_text[:12000]}

반환 스키마:
{{
  "summary_short": "3줄 이내 요약",
  "summary_long": "상세 요약",
  "keywords": ["키워드1", "키워드2"],
  "risks": ["리스크1"],
  "action_items": ["액션1"],
  "category": "운영|품질|일정|보고|기타",
  "importance_score": 0
}}
'''
        payload = {
            'model': settings.llm_model,
            'messages': [
                {
                    'role': 'system',
                    'content': '당신은 사내 메일 아카이브 분석기입니다. 항상 한국어 JSON만 반환하세요.',
                },
                {'role': 'user', 'content': prompt},
            ],
            'temperature': settings.llm_temperature,
            'max_tokens': settings.llm_max_tokens,
            'stream': False,
        }

        response = requests.post(
            settings.llm_api_base,
            headers=self._headers(),
            json=payload,
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content']

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                return json.loads(content[start : end + 1])
            raise
