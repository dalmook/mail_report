from app.services.news_report import render_weekly_news_html


def test_render_weekly_news_html_contains_sections() -> None:
    report = {
        'period_key': '2026-W13',
        'period_count': 10,
        'important_count': 3,
        'risk_count': 2,
        'issue_converted': 1,
        'summary_failed': 1,
        'category_rows': [{'category': '운영', 'cnt': 5}],
        'sender_top': [{'from_email': 'ops@example.com', 'cnt': 4}],
        'llm_summary': '이번 주 핵심 이슈 정리',
    }
    html = render_weekly_news_html(report, issues=[])
    assert '주간 운영 뉴스레터' in html
    assert '이번 주 핵심 이슈 정리' in html
    assert 'ops@example.com' in html
