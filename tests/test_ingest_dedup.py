from app.services.pop3_ingest import parse_uidl_lines


def test_parse_uidl_lines_sorted_and_limited() -> None:
    lines = [
        b'3 UIDL-C',
        b'1 UIDL-A',
        b'2 UIDL-B',
    ]
    parsed = parse_uidl_lines(lines, max_messages=2)
    assert parsed == [(1, 'UIDL-A'), (2, 'UIDL-B')]
