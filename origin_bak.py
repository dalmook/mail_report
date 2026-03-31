# -*- coding: utf-8 -*-
"""
2단계:
POP3로 최근 메일들을 읽어서
전체를 한 번에 LLM에 넣고
'신문 편집본' 형태의 HTML 생성

출력:
- news_output_step2.html

환경변수 예시 (Windows CMD)
set POP3_HOST=pop3.samsung.net
set POP3_PORT=995
set POP3_USE_SSL=1
set POP3_TIMEOUT_SEC=20
set POP3_USER=your_id
set POP3_PASSWORD=your_password

set LLM_API_BASE_URL=http://apigw.samsungds.net:8000/gpt-oss/1/gpt-oss-120b/v1/chat/completions
set LLM_CREDENTIAL_KEY=...
set LLM_USER_ID=sungmook.cho
set LLM_USER_TYPE=AD_ID
set LLM_SEND_SYSTEM_NAME=GOC_MAIL_RAG_PIPELINE
"""

import os
import re
import json
import time
import uuid
import html
import mimetypes
import poplib
import requests
from dataclasses import dataclass
from datetime import datetime, timedelta
from email import policy
from email.parser import BytesParser
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Any


# =========================================================
# 설정
# =========================================================
API_BASE_URL = os.getenv(
    "LLM_API_BASE_URL",
    "http://apigw.samsungds.net:8000/gpt-oss/1/gpt-oss-120b/v1/chat/completions"
)
CREDENTIAL_KEY = os.getenv("LLM_CREDENTIAL_KEY", "credential:TICKET-96f7bce0-efab-4516-8e62-5501b07ab43c:ST0000107488-PROD:CTXLCkSDRGWtI5HdVHkPAQgol2o-RyQiq2I1vCHHOgGw:-1:Q1RYTENrU0RSR1d0STVIZFZIa1BBUWdvbDJvLVJ5UWlxMkkxdkNISE9nR3c=:signature=eRa1UcfmWGfKTDBt-Xnz2wFhW0OvMX0WESZUpoNVgCA5uNVgpgax59LZ3osPOp8whnZwQay8s5TUvxJGtmsCD9iK-HpcsyUOcE5P58W0Weyg-YQ3KRTWFiA==").strip()
USER_ID = os.getenv("LLM_USER_ID", "sungmook.cho").strip()
USER_TYPE = os.getenv("LLM_USER_TYPE", "AD_ID").strip()
SEND_SYSTEM_NAME = os.getenv("LLM_SEND_SYSTEM_NAME", "GOC_MAIL_RAG_PIPELINE").strip()
EXCLUDE_KEYWORDS = ["[공통]", "[공급망운영 그룹]", "EDP 파트 주요 이슈"]
DEFAULT_LOOKBACK_DAYS = 7
FILTER_KEYWORDS = ["[HBM]", "[FLASH]", "[물류]", "[MOBILE]", "[EDP]", "[DO]", "[운영관리]", "[운영기획]"]
MAIL_API_CONFIG = {
    "HOST": os.getenv("MAIL_API_HOST", "https://openapi.samsung.net"),
    "TOKEN": os.getenv("MAIL_API_TOKEN", "Bearer 931e0fcb-31b8-33cf-8699-0d0ef752c85b"),
    "SYSTEM_ID": os.getenv("MAIL_API_SYSTEM_ID", "KCC10REST00621"),
}
MAIL_SENDER_ID = os.getenv("MAIL_SENDER_ID", "sungmook.cho").strip()
# 수신자는 여기에 아이디만 추가하면 됩니다.
# 예: ["sungmook.cho", "user2", "user3"]
MAIL_RECIPIENT_IDS = ["hs1979.kim","sungmook.cho","sung.w.jung","junsoo.jung","w2635.lee","jc2573.lee","sj82.han","cheon.kim","jh3.park","kyungchan.seong","suy.kim","sunok78.han","jjlive.kim","hsung.chae"]
CATEGORY_STYLES = {
    "[HBM]": {"label": "HBM", "accent": "#c85c3d", "bg": "#f7e0d6"},
    "[FLASH]": {"label": "FLASH", "accent": "#b26a00", "bg": "#f7ead2"},
    "[물류]": {"label": "물류", "accent": "#7b7f2a", "bg": "#f2f0d6"},
    "[MOBILE]": {"label": "MOBILE", "accent": "#2f7a55", "bg": "#ddf0e4"},
    "[EDP]": {"label": "EDP", "accent": "#2f608d", "bg": "#ddeaf6"},
    "[DO]": {"label": "DO", "accent": "#7c5a94", "bg": "#ebdff1"},
    "[운영관리]": {"label": "운영관리", "accent": "#516b9a", "bg": "#e2e8f6"},
    "[운영기획]": {"label": "운영기획", "accent": "#8f7d29", "bg": "#f3efcd"},
    "기타": {"label": "기타", "accent": "#666666", "bg": "#ebebeb"},
}
ISSUE_LINK_URL = "https://go/issueG"
LLM_PLAN_MAX_ATTEMPTS = 3
LLM_RETRY_DELAY_SEC = 5
STRUCTURAL_LINE_PATTERNS = [
    r"(?im)^\s*lv\s*\d+\s*:\s*.*$",
    r"(?im)^\s*level\s*\d+\s*:\s*.*$",
    r"(?im)^\s*(관리항목|관리 항목|실행조직|실행 조직|구분|분류|담당|담당자)\s*[:\-]\s*.*$",
    r"(?im)^\s*(sender|from|date|title|subject|sent|to|cc)\s*:\s*.*$",
]
IMPORTANT_SENTENCE_HINTS = [
    "이슈", "리스크", "위험", "문제", "불량", "지연", "영향", "원인", "대응", "조치",
    "요청", "필요", "완료", "예정", "계획", "진행", "확인", "공유", "부족", "증가",
    "감소", "수율", "출하", "납기", "재고", "생산", "양산", "변경", "차질",
]


# =========================================================
# 데이터 모델
# =========================================================
@dataclass
class MailQueryParams:
    user: str
    password: str
    max_count: Optional[int] = None
    lookback_days: int = DEFAULT_LOOKBACK_DAYS


@dataclass
class MailItem:
    subject: str
    sender: str
    date_str: str
    date_obj: Optional[datetime]
    body: str


# =========================================================
# LLM 호출
# =========================================================
def call_gpt_oss(prompt: str, system_prompt: Optional[str] = None,
                 temperature: float = 0.3, max_tokens: int = 1800) -> Dict[str, Any]:
    if not CREDENTIAL_KEY:
        return {"error": "LLM_CREDENTIAL_KEY 환경변수가 비어 있습니다."}

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": "openai/gpt-oss-120b",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    })

    headers = {
        "x-dep-ticket": CREDENTIAL_KEY,
        "Send-System-Name": SEND_SYSTEM_NAME,
        "User-Id": USER_ID,
        "User-Type": USER_TYPE,
        "Prompt-Msg-Id": str(uuid.uuid4()),
        "Completion-Msg-Id": str(uuid.uuid4()),
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(API_BASE_URL, headers=headers, data=payload, timeout=90)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def build_mail_recipients(recipient_ids: List[str]) -> List[Dict[str, str]]:
    recipients = []
    for recipient_id in recipient_ids:
        recipient_id = (recipient_id or "").strip()
        if not recipient_id:
            continue
        email_address = recipient_id if "@" in recipient_id else f"{recipient_id}@samsung.com"
        recipients.append({
            "emailAddress": email_address,
            "recipientType": "TO"
        })
    return recipients


def send_mail_api(
    *, sender_id: str, subject: str, contents: str,
    content_type: str = "HTML", doc_secu_type: str = "PERSONAL",
    recipients: Optional[List[Dict[str, str]]] = None,
    reserved_time: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    proxies: Optional[Dict[str, str]] = None,
    verify_ssl: bool = False, timeout: int = 30,
) -> Dict[str, Any]:
    normalized_recipients = []
    for recipient in recipients or []:
        normalized = dict(recipient)
        normalized.setdefault("recipientType", "TO")
        normalized_recipients.append(normalized)

    headers_common = {
        "Authorization": MAIL_API_CONFIG["TOKEN"],
        "System-ID": MAIL_API_CONFIG["SYSTEM_ID"],
    }
    mail_json: Dict[str, Any] = {
        "subject": subject,
        "contents": contents,
        "contentType": content_type,
        "docSecuType": doc_secu_type,
        "sender": {"emailAddress": f"{sender_id}@samsung.com"},
        "recipients": normalized_recipients,
    }
    if reserved_time:
        mail_json["reservedTime"] = reserved_time

    url = f'{MAIL_API_CONFIG["HOST"].rstrip("/")}/mail/api/v2.0/mails/send?userId={sender_id}'
    session = requests.Session()
    if proxies:
        session.proxies.update(proxies)

    attach_list = attachments or []
    if not attach_list:
        headers = dict(headers_common)
        headers["Content-Type"] = "application/json"
        response = session.post(
            url,
            json=mail_json,
            headers=headers,
            verify=verify_ssl,
            timeout=timeout
        )
    else:
        files = [("mail", (None, json.dumps(mail_json, ensure_ascii=False), "application/json"))]
        for path in attach_list:
            filename = os.path.basename(path)
            content_type_guess = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            files.append(("attachments", (filename, open(path, "rb"), content_type_guess)))
        try:
            response = session.post(
                url,
                headers=headers_common,
                files=files,
                verify=verify_ssl,
                timeout=timeout
            )
        finally:
            for _, file_tuple in files[1:]:
                try:
                    file_tuple[1].close()
                except Exception:
                    pass

    if not response.ok:
        raise requests.exceptions.HTTPError(
            f"{response.status_code} Client Error: {response.text}",
            response=response
        )
    return response.json() if (response.text or "").strip() else {"ok": True}


def extract_json_block(text: str) -> str:
    text = text.strip()
    # 코드블록 감싸진 경우 제거
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_outer_json_object(text: str) -> str:
    text = extract_json_block(text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


# =========================================================
# POP3 메일 읽기
# =========================================================
def _pop3_connect(params: MailQueryParams):
    host = os.getenv("POP3_HOST", "pop3.samsung.net")
    use_ssl = os.getenv("POP3_USE_SSL", "1").lower() not in {"0", "false", "no"}
    port_env = os.getenv("POP3_PORT", "995").strip()
    port = int(port_env) if port_env else (995 if use_ssl else 110)
    timeout = int(os.getenv("POP3_TIMEOUT_SEC", "40"))

    if use_ssl:
        client = poplib.POP3_SSL(host, port, timeout=timeout)
    else:
        client = poplib.POP3(host, port, timeout=timeout)

    client.user(params.user)
    client.pass_(params.password)
    return client


def decode_mime_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\u200b", "", text)
    return text.strip()


def remove_structural_lines(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    for pattern in STRUCTURAL_LINE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"(?im)^\s*[-=]{3,}\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*[■□▶▷]+[\s:：-]*$", "", cleaned)
    return clean_text(cleaned)


def split_sentences(text: str) -> List[str]:
    if not text:
        return []
    normalized = re.sub(r"\n+", " ", text)
    normalized = re.sub(r"([.!?。])\s+", r"\1\n", normalized)
    normalized = re.sub(r"(다\.)\s+", r"\1\n", normalized)
    parts = normalized.split("\n")
    return [clean_text(part) for part in parts if clean_text(part)]


def score_sentence(sentence: str) -> int:
    score = 0
    if re.search(r"\d", sentence):
        score += 2
    if re.search(r"\b\d{1,2}/\d{1,2}\b|\b\d{4}-\d{2}-\d{2}\b", sentence):
        score += 2
    for hint in IMPORTANT_SENTENCE_HINTS:
        if hint in sentence:
            score += 3
    if len(sentence) < 12:
        score -= 2
    if re.search(r"(?i)\b(lv|level)\s*\d+\b", sentence):
        score -= 5
    return score


def extract_important_summary_text(text: str, max_sentences: int = 3) -> str:
    cleaned = remove_structural_lines(text)
    sentences = split_sentences(cleaned)
    if not sentences:
        return ""

    scored = [(idx, sentence, score_sentence(sentence)) for idx, sentence in enumerate(sentences)]
    important = [item for item in scored if item[2] > 0]
    if not important:
        important = scored[:max_sentences]
    else:
        important = sorted(important, key=lambda item: (-item[2], item[0]))[:max_sentences]
        important = sorted(important, key=lambda item: item[0])

    return clean_text(" ".join(sentence for _, sentence, _ in important))


def extract_key_points(text: str, max_points: int = 3) -> List[str]:
    cleaned = remove_structural_lines(text)
    sentences = split_sentences(cleaned)
    if not sentences:
        return []

    scored = [(idx, sentence, score_sentence(sentence)) for idx, sentence in enumerate(sentences)]
    scored = sorted(scored, key=lambda item: (-item[2], item[0]))

    points = []
    for _, sentence, score in scored:
        if score <= 0 and points:
            continue
        sentence = summarize_text(sentence, 120) if len(sentence) > 120 else sentence
        if sentence and sentence not in points:
            points.append(sentence)
        if len(points) >= max_points:
            break
    return points


def summarize_text(text: str, max_length: int = 180) -> str:
    text = extract_important_summary_text(text) or remove_structural_lines(text) or clean_text(text)
    if len(text) <= max_length:
        return text
    clipped = text[:max_length]
    last_stop = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if last_stop >= int(max_length * 0.55):
        return clipped[:last_stop + 1]
    return clipped.rstrip() + "..."


def get_week_label(target_date: Optional[datetime] = None) -> str:
    if target_date is None:
        target_date = datetime.now()
    return f"W{target_date.isocalendar().week}"


def get_newsletter_title(target_date: Optional[datetime] = None) -> str:
    return f"GOC 주간 이슈 ({get_week_label(target_date)})"


def html_to_text_basic(html_text: str) -> str:
    if not html_text:
        return ""
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?is)<.*?>", " ", text)
    text = html.unescape(text)
    return clean_text(text)


def trim_mail_body(text: str, max_len: int = 1800) -> str:
    if not text:
        return ""
    # 회신/전달 흔적 이후 잘라내기
    split_patterns = [
        r"(?im)^[-\s]*Original Message[-\s]*$",
        r"\n[-]{2,}\s*Original Message\s*[-]{2,}",
        r"\n보낸 사람\s*:",
        r"\nFrom\s*:",
        r"\nSender\s*:",
        r"\nDate\s*:",
        r"\nTitle\s*:",
        r"\n-----Original Message-----",
        r"\n발신\s*:",
    ]
    for p in split_patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            text = text[:m.start()]
            break
    text = clean_text(text)
    text = re.sub(r"(?im)^(sender|date|title)\s*:\s*.*$", "", text)
    text = clean_text(text)
    if len(text) > max_len:
        text = text[:max_len] + " ..."
    return text


def normalize_compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def contains_any_keyword(text: str, keywords: List[str], ignore_spaces: bool = False) -> bool:
    if not text:
        return False
    target = normalize_compact(text) if ignore_spaces else text.lower()
    for keyword in keywords:
        candidate = normalize_compact(keyword) if ignore_spaces else keyword.lower()
        if candidate and candidate in target:
            return True
    return False


def should_include_mail(subject: str, body: str, date_obj: Optional[datetime], cutoff: datetime) -> bool:
    if date_obj is not None:
        if date_obj.tzinfo is not None:
            cutoff_cmp = cutoff.replace(tzinfo=date_obj.tzinfo)
        else:
            cutoff_cmp = cutoff
        if date_obj < cutoff_cmp:
            return False

    if contains_any_keyword(subject, FILTER_KEYWORDS, ignore_spaces=True) is False:
        return False

    if contains_any_keyword(subject, EXCLUDE_KEYWORDS) or contains_any_keyword(body, EXCLUDE_KEYWORDS):
        return False

    return True


def get_mail_category(subject: str) -> str:
    for keyword in FILTER_KEYWORDS:
        if contains_any_keyword(subject, [keyword], ignore_spaces=True):
            return keyword
    return "기타"


def extract_body_from_message(msg) -> str:
    plain_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            except Exception:
                try:
                    text = part.get_content()
                except Exception:
                    text = ""

            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)
    else:
        content_type = msg.get_content_type()
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            else:
                text = msg.get_content()
        except Exception:
            text = ""

        if content_type == "text/plain":
            plain_parts.append(text)
        elif content_type == "text/html":
            html_parts.append(text)

    if plain_parts:
        return trim_mail_body("\n\n".join(plain_parts))
    if html_parts:
        return trim_mail_body(html_to_text_basic("\n\n".join(html_parts)))
    return ""


def fetch_recent_mails(params: MailQueryParams) -> List[MailItem]:
    client = _pop3_connect(params)
    items: List[MailItem] = []
    cutoff = datetime.now() - timedelta(days=params.lookback_days)

    try:
        count, _ = client.stat()

        for i in range(count, 0, -1):
            _, lines, _ = client.retr(i)
            raw_email = b"\n".join(lines)
            msg = BytesParser(policy=policy.default).parsebytes(raw_email)

            subject = decode_mime_header(msg.get("Subject"))
            sender = decode_mime_header(msg.get("From"))
            raw_date = msg.get("Date", "")
            date_obj = None
            try:
                date_obj = parsedate_to_datetime(raw_date)
            except Exception:
                pass

            body = extract_body_from_message(msg)
            if not body and not subject:
                continue
            if not should_include_mail(subject, body, date_obj, cutoff):
                continue

            items.append(MailItem(
                subject=subject or "(제목 없음)",
                sender=sender or "",
                date_str=raw_date or "",
                date_obj=date_obj,
                body=body
            ))
            if params.max_count is not None and len(items) >= params.max_count:
                break
    finally:
        try:
            client.quit()
        except Exception:
            pass

    return items


# =========================================================
# 전체 편집본 생성
# =========================================================
def build_mail_bundle_for_llm(mails: List[MailItem]) -> str:
    blocks = []
    for idx, m in enumerate(mails, start=1):
        dt = m.date_obj.strftime("%Y-%m-%d %H:%M") if m.date_obj else m.date_str
        category = get_mail_category(m.subject)
        cleaned_subject = clean_subject_for_title(m.subject)
        compact_summary = summarize_text(m.body, 320)
        key_points = extract_key_points(m.body, 3)
        key_points_text = "\n".join(f"- {point}" for point in key_points) if key_points else "- 핵심 포인트 추출 실패"
        block = f"""
[메일 {idx}]
카테고리: {category}
제목: {cleaned_subject}
발신자: {m.sender}
일시: {dt}
본문 요약:
{compact_summary}
핵심 포인트:
{key_points_text}
"""
        blocks.append(block.strip())
    return "\n\n".join(blocks)


def build_fallback_plan(mails: List[MailItem], editor_note: str) -> Dict[str, Any]:
    if not mails:
        return {
            "paper_title": get_newsletter_title(),
            "paper_subtitle": "수집된 메일이 없어 편집본을 생성하지 못했습니다.",
            "top_story": {
                "headline": "수집된 메일 없음",
                "subheadline": "",
                "summary": "",
                "bullets": [],
                "related_mail_indexes": []
            },
            "sections": [],
            "editor_note": editor_note
        }

    top_mail = mails[0]
    issue_articles = []
    for idx, mail in enumerate(mails[1:5], start=2):
        issue_articles.append({
            "headline": mail.subject,
            "summary": clean_text(mail.body)[:220],
            "bullets": [],
            "related_mail_indexes": [idx]
        })

    return {
        "paper_title": get_newsletter_title(),
        "paper_subtitle": f"최근 {DEFAULT_LOOKBACK_DAYS}일 기준 주요 메일 {len(mails)}건 요약",
        "top_story": {
            "headline": top_mail.subject,
            "subheadline": clean_text(top_mail.sender),
            "summary": clean_text(top_mail.body)[:360],
            "bullets": [],
            "related_mail_indexes": [1]
        },
        "sections": [
            {
                "section_name": "주요 메일",
                "articles": issue_articles
            }
        ],
        "editor_note": editor_note
    }


def build_category_bridge_articles(mails: List[MailItem], covered_categories: Optional[set] = None) -> List[Dict[str, Any]]:
    if covered_categories is None:
        covered_categories = set()

    grouped: Dict[str, List[tuple]] = {}
    for idx, mail in enumerate(mails, start=1):
        category = get_mail_category(mail.subject)
        grouped.setdefault(category, []).append((idx, mail))

    articles = []
    for category in FILTER_KEYWORDS:
        if category not in grouped or category in covered_categories:
            continue
        lead_idx, lead_mail = grouped[category][0]
        style = CATEGORY_STYLES.get(category, CATEGORY_STYLES["기타"])
        articles.append({
            "headline": f"{style['label']} 관련 주요 내용",
            "summary": summarize_text(lead_mail.body, 260) or lead_mail.subject,
            "bullets": [f"{len(grouped[category])}건 메일 반영", lead_mail.subject[:100]],
            "related_mail_indexes": [lead_idx]
        })
    return articles


def ensure_category_coverage(plan: Dict[str, Any], mails: List[MailItem]) -> Dict[str, Any]:
    covered_categories = set()

    top_indexes = plan.get("top_story", {}).get("related_mail_indexes", []) or []
    for idx in top_indexes:
        if 1 <= idx <= len(mails):
            covered_categories.add(get_mail_category(mails[idx - 1].subject))

    for sec in plan.get("sections", []) or []:
        for article in sec.get("articles", []) or []:
            for idx in article.get("related_mail_indexes", []) or []:
                if 1 <= idx <= len(mails):
                    covered_categories.add(get_mail_category(mails[idx - 1].subject))

    missing_articles = build_category_bridge_articles(mails, covered_categories)
    if not missing_articles:
        return plan

    sections = plan.get("sections", []) or []
    sections.append({
        "section_name": "카테고리 브리핑",
        "articles": missing_articles
    })
    plan["sections"] = sections
    return plan


def clean_subject_for_title(subject: str) -> str:
    title = clean_text(subject)
    while True:
        updated = re.sub(r"(?i)^\s*(?:fw|fwd|re)\s*:\s*", "", title)
        updated = re.sub(r"(?i)^\s*\(\d+\)\s*", "", updated)
        updated = re.sub(r"^\s*\[[^\]]+\]\s*", "", updated)
        updated = clean_text(updated)
        if updated == title:
            break
        title = updated
    return title


def contains_english_title(text: str) -> bool:
    if not text:
        return False
    latin_count = len(re.findall(r"[A-Za-z]", text))
    korean_count = len(re.findall(r"[가-힣]", text))
    return latin_count > 0 and latin_count >= korean_count


def build_balanced_headline(related_indexes: List[int], mails: List[MailItem]) -> str:
    for idx in related_indexes or []:
        if 1 <= idx <= len(mails):
            subject = clean_subject_for_title(mails[idx - 1].subject)
            if subject:
                if contains_english_title(subject):
                    english_terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9+._/-]*", subject)
                    if english_terms:
                        return f"{' '.join(english_terms[:4])} 관련 이슈"
                return subject
    return "주요 이슈"


def localize_plan_titles(plan: Dict[str, Any], mails: List[MailItem]) -> Dict[str, Any]:
    top_story = plan.get("top_story") or {}
    top_story["headline"] = clean_subject_for_title(top_story.get("headline", ""))
    top_story["subheadline"] = clean_subject_for_title(top_story.get("subheadline", ""))
    if contains_english_title(top_story.get("headline", "")):
        top_story["headline"] = build_balanced_headline(top_story.get("related_mail_indexes", []), mails)
    if contains_english_title(top_story.get("subheadline", "")):
        top_story["subheadline"] = ""
    plan["top_story"] = top_story

    for sec in plan.get("sections", []) or []:
        sec["section_name"] = clean_subject_for_title(sec.get("section_name", ""))
        if contains_english_title(sec.get("section_name", "")):
            sec["section_name"] = "주요 기사"
        for article in sec.get("articles", []) or []:
            article["headline"] = clean_subject_for_title(article.get("headline", ""))
            if contains_english_title(article.get("headline", "")):
                article["headline"] = build_balanced_headline(article.get("related_mail_indexes", []), mails)
    return plan


def normalize_plan(data: Dict[str, Any], mails: List[MailItem]) -> Dict[str, Any]:
    top = data.get("top_story") or {}
    sections = data.get("sections") or []
    if not isinstance(sections, list):
        sections = []

    normalized_sections = []
    for sec in sections[:4]:
        if not isinstance(sec, dict):
            continue
        articles = sec.get("articles") or []
        if not isinstance(articles, list):
            articles = []
        normalized_articles = []
        for article in articles[:6]:
            if not isinstance(article, dict):
                continue
            normalized_articles.append({
                "headline": str(article.get("headline") or "제목 없음").strip(),
                "summary": clean_text(str(article.get("summary") or ""))[:400],
                "bullets": [clean_text(str(b))[:120] for b in (article.get("bullets") or []) if str(b).strip()][:4],
                "related_mail_indexes": [int(i) for i in (article.get("related_mail_indexes") or []) if isinstance(i, int)]
            })
        if normalized_articles:
            normalized_sections.append({
                "section_name": str(sec.get("section_name") or "주요 기사").strip(),
                "articles": normalized_articles
            })

    normalized = {
        "paper_title": get_newsletter_title(),
        "paper_subtitle": clean_text(str(data.get("paper_subtitle") or f"최근 {DEFAULT_LOOKBACK_DAYS}일 메일 요약"))[:160],
        "top_story": {
            "headline": str(top.get("headline") or (mails[0].subject if mails else "오늘의 주요 이슈")).strip(),
            "subheadline": clean_text(str(top.get("subheadline") or ""))[:180],
            "summary": clean_text(str(top.get("summary") or (mails[0].body[:300] if mails else "")))[:500],
            "bullets": [clean_text(str(b))[:120] for b in (top.get("bullets") or []) if str(b).strip()][:5],
            "related_mail_indexes": [int(i) for i in (top.get("related_mail_indexes") or []) if isinstance(i, int)]
        },
        "sections": normalized_sections,
        "editor_note": clean_text(str(data.get("editor_note") or "주요 이슈를 주제별로 재정리했습니다."))[:220]
    }
    normalized = ensure_category_coverage(normalized, mails)
    return localize_plan_titles(normalized, mails)


def try_parse_plan_json(raw_content: str) -> Optional[Dict[str, Any]]:
    candidates = [
        raw_content,
        extract_json_block(raw_content),
        extract_outer_json_object(raw_content),
    ]

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def repair_plan_json(raw_content: str) -> Optional[Dict[str, Any]]:
    repair_system_prompt = """
당신은 깨진 JSON을 복구하는 도우미입니다.
입력 내용을 보고 반드시 유효한 JSON 객체 하나만 출력하세요.
설명, 코드블록, 주석은 금지입니다.
"""
    repair_user_prompt = f"""
아래 콘텐츠를 유효한 JSON 객체로 복구하세요.
누락된 값은 문맥상 최소한으로만 보완하고, 스키마는 유지하세요.

{extract_outer_json_object(raw_content)}
"""
    repaired = call_gpt_oss(
        prompt=repair_user_prompt,
        system_prompt=repair_system_prompt,
        temperature=0.0,
        max_tokens=2200
    )
    if "error" in repaired:
        return None
    repaired_content = repaired.get("choices", [{}])[0].get("message", {}).get("content", "")
    return try_parse_plan_json(repaired_content)


def generate_newspaper_plan(mails: List[MailItem]) -> Optional[Dict[str, Any]]:
    bundle = build_mail_bundle_for_llm(mails)

    system_prompt = """
당신은 사내 메일 편집국 에디터입니다.
여러 개의 메일을 읽고, 중복되거나 비슷한 주제는 하나의 이슈로 묶어서
'사내 뉴스 신문 편집본' JSON으로 재구성하세요.

반드시 JSON만 출력하세요.
설명문, 마크다운, 코드블록 없이 JSON만 출력하세요.

출력 스키마:
{
  "paper_title": "신문 이름 또는 오늘자 헤드라인",
  "paper_subtitle": "오늘 메일 브리핑 한 줄 설명",
  "top_story": {
    "headline": "",
    "subheadline": "",
    "summary": "",
    "bullets": ["", "", ""],
    "related_mail_indexes": [1, 3]
  },
  "sections": [
    {
      "section_name": "주요 이슈",
      "articles": [
        {
          "headline": "",
          "summary": "",
          "bullets": ["", ""],
          "related_mail_indexes": [2, 5]
        }
      ]
    },
    {
      "section_name": "단신",
      "articles": [
        {
          "headline": "",
          "summary": "",
          "bullets": ["", ""],
          "related_mail_indexes": [4]
        }
      ]
    }
  ],
  "editor_note": "전체 흐름을 한두 문장으로 정리"
}

규칙:
- 비슷한 메일은 related_mail_indexes로 묶기
- top_story는 가장 중요한 이슈 1개
- sections는 최소 2개
- 기사 문체는 간결하고 신문형
- 과장 금지, 원문 기반
- 없는 내용 지어내지 말 것
- 중요도 판단 기준은 일정 영향, 생산/수율 영향, 고객/출하 영향, 리스크, 의사결정 필요성, 긴급 요청 여부
- 단순 참고 공지보다 실행 필요 항목, 이슈, 변화, 지연, 원인/대응이 드러나는 메일을 우선 반영
- summary는 원문 재복붙이 아니라 핵심 의미를 2~4문장으로 재구성
- bullets는 수치, 일정, 리스크, 요청, 조치 중 핵심만 짧게 정리
- 모든 문자열은 JSON 규칙에 맞게 큰따옴표 내부에만 작성
- JSON 바깥 텍스트 절대 출력 금지
- 기사 headline, subheadline, section_name은 자연스럽고 읽기 쉬운 제목으로 작성
- FW:, RE:, RE:(5) 같은 메일 접두어는 제목에 절대 포함하지 말 것
- 제목은 메일 원문 제목을 그대로 복사하지 말고, 핵심만 정리한 신문형 제목으로 다듬을 것
- 어색한 직역체 표현(예: 차기 위험 발생) 금지, 자연스러운 업무 보고 문장으로 정리
- 단, 메일 본문에 포함된 제품명, 시스템명, 약어, 기술용어의 영어 표기는 임의로 번역하지 말고 원문을 유지
- 제목에서도 AWS, HBM, EDP 같은 약어/제품명은 원문 유지 가능
- summary와 bullets에서도 원문 영어 용어를 억지로 한글화하지 말 것
"""

    user_prompt = f"""
아래 메일 묶음은 최근 {DEFAULT_LOOKBACK_DAYS}일 동안 수집된 전체 메일 {len(mails)}건입니다.
모든 메일을 빠짐없이 훑고, 반복되는 주제는 합치되 특정 카테고리나 후반부 메일이 누락되지 않게 편집하세요.
각 메일에 포함된 '핵심 포인트'를 우선 참고하고, 공지성 문구보다 실제 이슈와 액션이 드러나도록 정리하세요.
오늘의 사내 신문 편집본 JSON을 생성하세요.

{bundle}
"""

    last_error = ""
    for attempt in range(1, LLM_PLAN_MAX_ATTEMPTS + 1):
        result = call_gpt_oss(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=2800
        )

        if "error" in result:
            last_error = result["error"]
        else:
            raw_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = try_parse_plan_json(raw_content)
            if parsed is None:
                parsed = repair_plan_json(raw_content)
            if parsed is not None:
                return normalize_plan(parsed, mails)
            last_error = "자동 편집 형식을 복구하지 못했습니다."

        print(f"[WARN] LLM 편집 실패 ({attempt}/{LLM_PLAN_MAX_ATTEMPTS}): {last_error}")
        if attempt < LLM_PLAN_MAX_ATTEMPTS:
            print(f"[INFO] {LLM_RETRY_DELAY_SEC}초 후 재시도합니다...")
            time.sleep(LLM_RETRY_DELAY_SEC)

    return None


# =========================================================
# HTML 렌더링
# =========================================================
def esc(v) -> str:
    return html.escape(str(v or ""))


def esc_br(v) -> str:
    return esc(v).replace("\n", "<br>")







def render_article_card(article: Dict[str, Any], mails: List[MailItem]) -> str:
    bullets_html = render_bullet_block(article.get("bullets", []) or [], 4)
    source_html = render_related_sources(article.get("related_mail_indexes", []), mails)

    return f"""

    """


def render_newspaper_html_step2(plan: Dict[str, Any], mails: List[MailItem], output_path: str):
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    top = plan.get("top_story", {}) or {}
    top_bullets = render_bullet_block(top.get("bullets") or [], 5)
    top_sources = render_related_sources(top.get("related_mail_indexes", []), mails)
    detail_sections_html = render_detail_table(mails)

    sections_html = ""
    for sec in plan.get("sections", []) or []:
        articles_html = "".join(render_article_card(a, mails) for a in (sec.get("articles") or []))
        sections_html += f"""
        <tr>
            <td style="padding:0 24px 24px 24px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:3px solid #222222;">
                    <tr>
                        <td style="padding:14px 0 16px 0;font-size:22px;line-height:1.3;font-weight:700;color:#1d1d1d;">
                            {esc(sec.get("section_name"))}
                        </td>
                    </tr>
                    {articles_html}
                </table>
            </td>
        </tr>
        """

    html_text = f"""

"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_text)


def send_generated_news_mail(plan: Dict[str, Any], html_path: str):
    with open(html_path, "r", encoding="utf-8") as f:
        html_contents = f.read()

    subject = get_newsletter_title()
    recipients = build_mail_recipients(MAIL_RECIPIENT_IDS)

    return send_mail_api(
        sender_id=MAIL_SENDER_ID,
        subject=subject,
        contents=html_contents,
        content_type="HTML",
        doc_secu_type="PERSONAL",
        recipients=recipients
    )

