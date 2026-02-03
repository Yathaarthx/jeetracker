import json
import os
from datetime import datetime

from dotenv import load_dotenv

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, redirect, render_template, request, url_for

from monitor import SUBSCRIBERS_PATH, check_sites


def _load_subscribers():
    if not os.path.exists(SUBSCRIBERS_PATH):
        return []
    with open(SUBSCRIBERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_subscribers(emails):
    os.makedirs(os.path.dirname(SUBSCRIBERS_PATH), exist_ok=True)
    with open(SUBSCRIBERS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(set(emails)), f, indent=2)

CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", "10"))

load_dotenv()

app = Flask(__name__)

scheduler = BackgroundScheduler(daemon=True)


def scheduled_job():
    check_sites()


scheduler.add_job(scheduled_job, "interval", minutes=CHECK_INTERVAL_MIN)


_scheduler_started = False


@app.before_request
def _start_scheduler():
    global _scheduler_started
    if not _scheduler_started:
        scheduler.start()
        _scheduler_started = True


@app.route("/")
def index():
    status = check_sites()
    status["interval_min"] = CHECK_INTERVAL_MIN
    return render_template("index.html", status=status)


@app.route("/check")
def check_now():
    check_sites()
    return redirect(url_for("index"))


@app.route("/subscribe", methods=["POST"])
def subscribe():
    email = request.form.get("email", "").strip().lower()
    if email:
        emails = _load_subscribers()
        emails.append(email)
        _save_subscribers(emails)
    return redirect(url_for("index"))


@app.route("/unsubscribe", methods=["POST"])
def unsubscribe():
    email = request.form.get("email", "").strip().lower()
    emails = [e for e in _load_subscribers() if e != email]
    _save_subscribers(emails)
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        "interval_min": CHECK_INTERVAL_MIN,
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
