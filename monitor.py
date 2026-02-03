import hashlib
import json
import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Dict, Tuple

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
STATE_PATH = os.getenv("STATE_PATH", "data/state.json")
SUBSCRIBERS_PATH = os.getenv("SUBSCRIBERS_PATH", "data/subscribers.json")

DEFAULT_URLS = [
    "https://jeemain.nta.nic.in/",
]

DEFAULT_KEYWORDS = [
    "response sheet",
    "answer key",
    "challenge",
    "response sheet download",
    "response sheet link",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_state() -> Dict:
    if not os.path.exists(STATE_PATH):
        return {
            "last_hash": "",
            "last_check": None,
            "last_match": None,
            "last_match_excerpt": None,
            "last_notified": None,
        }
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(state: Dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _load_subscribers() -> list:
    if not os.path.exists(SUBSCRIBERS_PATH):
        return []
    with open(SUBSCRIBERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_subscribers(subscribers: list) -> None:
    os.makedirs(os.path.dirname(SUBSCRIBERS_PATH), exist_ok=True)
    with open(SUBSCRIBERS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(set(subscribers)), f, indent=2)


def _get_env_list(name: str, default: list) -> list:
    value = os.getenv(name, "")
    if not value.strip():
        return default
    return [v.strip() for v in value.split(",") if v.strip()]


def _fetch_page_text(url: str) -> str:
    resp = requests.get(url, timeout=25, headers={"User-Agent": "JEE-Monitor/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _find_keywords(text: str, keywords: list) -> Tuple[bool, str]:
    lowered = text.lower()
    for kw in keywords:
        kw_l = kw.lower()
        idx = lowered.find(kw_l)
        if idx != -1:
            start = max(0, idx - 80)
            end = min(len(text), idx + 160)
            return True, text[start:end]
    return False, ""


def _send_email(subject: str, body: str, recipients: list) -> None:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    mail_from = os.getenv("SMTP_FROM", user)

    if not host or not recipients:
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(msg)


def _send_telegram(subject: str, body: str, subscribers: list) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not subscribers:
        return
    for chat_id in subscribers:
        chat_id = str(chat_id).strip()
        if not chat_id:
            continue
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": f"{subject}\n\n{body}",
        }
        try:
            requests.post(url, json=payload, timeout=20)
        except Exception:
            continue


def check_sites() -> Dict:
    urls = _get_env_list("MONITOR_URLS", DEFAULT_URLS)
    keywords = _get_env_list("KEYWORDS", DEFAULT_KEYWORDS)
    subscribers = _load_subscribers()

    texts = []
    errors = []
    for url in urls:
        try:
            texts.append(_fetch_page_text(url))
        except Exception as exc:
            errors.append(f"{url}: {exc}")

    combined = "\n".join(texts)
    page_hash = _hash_text(combined) if combined else ""
    matched, excerpt = _find_keywords(combined, keywords)

    state = _load_state()
    changed = page_hash and page_hash != state.get("last_hash")

    state["last_hash"] = page_hash
    state["last_check"] = _now_iso()

    if matched:
        state["last_match"] = _now_iso()
        state["last_match_excerpt"] = excerpt

    notified = False
    if matched and state.get("last_notified") is None and subscribers:
        subject = "JEE Main: Response sheet/answer key update detected"
        body = "Update detected on monitored pages.\n\n"
        if excerpt:
            body += f"Excerpt: {excerpt}\n\n"
        body += "Sources:\n" + "\n".join(urls)
        _send_telegram(subject, body, subscribers)
        state["last_notified"] = _now_iso()
        notified = True

    _save_state(state)
    return {
        "checked_at": state.get("last_check"),
        "matched": matched,
        "notified": notified,
        "changed": changed,
        "errors": errors,
        "excerpt": excerpt,
        "urls": urls,
        "keywords": keywords,
        "subscribers": subscribers,
        "state": state,
    }
