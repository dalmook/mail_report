from app.services.auto_tagger import suggest_tags


def test_auto_tagger_detects_risk_and_importance() -> None:
    tags = suggest_tags(
        subject='긴급 장애 보고',
        body_preview='서비스 장애 리스크 공유',
        from_email='ops@example.com',
        has_attachment=True,
        summary_tags=[],
        keywords=['장애'],
        category='운영',
        importance_score=85,
    )
    names = [t.tag for t in tags]
    assert '중요' in names
    assert '장애' in names
    assert '리스크' in names
