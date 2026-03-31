from pathlib import Path

from app import db
from app.config import settings
from app.services.repository import list_issue_candidates, upsert_issue_candidate


def test_issue_candidate_upsert(tmp_path: Path) -> None:
    test_db = tmp_path / 'candidate.db'
    old_db = settings.db_path
    object.__setattr__(settings, 'db_path', test_db)
    try:
        db.init_db()
        with db.get_conn() as conn:
            mid = int(
                conn.execute(
                    "INSERT INTO messages(subject, body_preview, received_at, eml_path, has_attachment) VALUES ('긴급 장애 요청', '마감 일정 지연', datetime('now'), '/tmp/a.eml', 1)"
                ).lastrowid
            )
            conn.execute(
                "INSERT INTO summaries(message_id, summary_short, importance_score) VALUES (?, '리스크 발생 가능', 80)",
                (mid,),
            )
        assert upsert_issue_candidate(mid) is True
        rows = list_issue_candidates('PENDING')
        assert rows
        assert rows[0]['message_id'] == mid
    finally:
        object.__setattr__(settings, 'db_path', old_db)
