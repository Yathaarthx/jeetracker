# JEE Main Response Sheet Monitor

Small Flask app that checks the NTA JEE Main site every 10 minutes and sends a Telegram notification when response sheet/answer key keywords appear.

## What it does
- Monitors:
  - https://jeemain.nta.nic.in/
- Looks for keywords like "response sheet" and "answer key"
- Sends a single notification when a match is detected to subscribed Telegram chat IDs
- Shows status in a simple web UI

## Local run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```
Then open `http://localhost:8000`.

## Notifications (Telegram)
1. Create a bot with @BotFather and copy the bot token.
2. Add `TELEGRAM_BOT_TOKEN` to `.env`.
3. Send any message to your bot from Telegram.
4. Find your `chat_id` by opening:
   - `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. Enter that `chat_id` in the web UI to subscribe.

## Deploy (Docker)
```bash
docker build -t jee-monitor .
docker run --env-file .env -p 8000:8000 jee-monitor
```

## Deploy (Render/Railway)
- Use the Dockerfile, or set start command to:
  - `gunicorn -w 1 -b 0.0.0.0:$PORT app:app`
- Set environment variables from `.env.example`.
- Keep `WEB_CONCURRENCY=1` to avoid duplicate schedulers.

## Notes
- The app only notifies once per detected match. To re-arm, delete `data/state.json`.
- Subscribed chat IDs are stored in `data/subscribers.json`.
- You can change `MONITOR_URLS`, `KEYWORDS`, and `CHECK_INTERVAL_MIN` in `.env`.
