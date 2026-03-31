from pathlib import Path

from app import db
from app.config import settings
from app.services.repository import build_period_summary, create_issue_from_message


def test_issue_create_and_period_summary(tmp_path: Path) -> None:
    test_db = tmp_path / 'test.db'
    old_db = settings.db_path
    object.__setattr__(settings, 'db_path', test_db)
    try:
        db.init_db()
        with db.get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO messages(subject, received_at, eml_path, has_attachment, body_preview) VALUES ('테스트', datetime('now'), '/tmp/a.eml', 0, 'preview')"
            )
            mid = int(cur.lastrowid)
        issue_id = create_issue_from_message(mid, '테스트 이슈')
        assert issue_id > 0
        report = build_period_summary('week')
        assert report['period_count'] >= 1
        assert 'issue_converted' in report
    finally:
        object.__setattr__(settings, 'db_path', old_db)
