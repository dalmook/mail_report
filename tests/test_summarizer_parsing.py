from app.services.llm_summarizer import LLMService


def test_parse_response_content_plain_json() -> None:
    content = '{"summary_short": "ok"}'
    parsed = LLMService.parse_response_content(content)
    assert parsed['summary_short'] == 'ok'


def test_parse_response_content_with_wrapper_text() -> None:
    content = '```json\n{"summary_short": "ok", "importance_score": 5}\n```'
    parsed = LLMService.parse_response_content(content)
    assert parsed['importance_score'] == 5
