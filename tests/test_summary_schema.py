from app.schemas import validate_summary_payload


def test_summary_schema_fallback_importance_and_status() -> None:
    raw = {
        'summary_short': '긴급 장애 공유',
        'summary_long': '',
        'status': 'unknown-status',
        'importance_score': 0,
    }
    payload = validate_summary_payload(raw)
    assert payload.status == 'new'
    assert payload.importance_score >= 80
    assert payload.summary_long == payload.summary_short
