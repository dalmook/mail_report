from __future__ import annotations

from datetime import datetime
from typing import Any


def render_weekly_news_html(report: dict[str, Any], issues: list[Any]) -> str:
    category_rows = ''.join(f"<li>{row['category']}: {row['cnt']}</li>" for row in report.get('category_rows', [])) or '<li>없음</li>'
    sender_rows = ''.join(f"<li>{row['from_email']}: {row['cnt']}</li>" for row in report.get('sender_top', [])) or '<li>없음</li>'
    issue_rows = ''.join(
        f"<tr><td>{item['id']}</td><td>{item['title']}</td><td>{item['status']}</td><td>{item['owner'] or '-'}</td><td>{item['due_date'] or '-'}</td></tr>"
        for item in issues[:12]
    ) or '<tr><td colspan="5">이슈 없음</td></tr>'

    return f"""
    <html><body style='font-family:Arial,sans-serif;'>
      <h2>📮 주간 운영 뉴스레터 ({report.get('period_key', '-')})</h2>
      <p>{report.get('llm_summary') or '자동 생성된 주간 요약입니다.'}</p>
      <h3>핵심 지표</h3>
      <ul>
        <li>수집 건수: {report.get('period_count', 0)}</li>
        <li>중요 메일: {report.get('important_count', 0)}</li>
        <li>리스크 메일: {report.get('risk_count', 0)}</li>
        <li>이슈 전환: {report.get('issue_converted', 0)}</li>
        <li>요약 실패: {report.get('summary_failed', 0)}</li>
      </ul>
      <h3>카테고리 분포</h3>
      <ul>{category_rows}</ul>
      <h3>발신자 TOP</h3>
      <ul>{sender_rows}</ul>
      <h3>주요 이슈 현황</h3>
      <table border='1' cellpadding='6' cellspacing='0'>
        <thead><tr><th>ID</th><th>제목</th><th>상태</th><th>담당</th><th>마감일</th></tr></thead>
        <tbody>{issue_rows}</tbody>
      </table>
      <p style='color:#666;margin-top:16px;'>생성 시각: {datetime.now().isoformat()}</p>
    </body></html>
    """
