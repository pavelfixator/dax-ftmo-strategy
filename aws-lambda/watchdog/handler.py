"""AWS Lambda Cloud Watchdog — Layer 4 close framework.

Per Strategy v3.2 ÚKOL spec:
- Provider: AWS Lambda, region eu-central-1 (Frankfurt)
- Trigger: EventBridge schedule, every 5 min during 19:00-22:00 CET
- Cost: ~$0.50/month (well within free tier)

Logic:
  1. HTTPS GET to bot status webhook (auth via Bearer token)
  2. Parse open_positions_count + last_heartbeat_age_sec
  3. If positions > 0 AND now > deadline_threshold (configured per weekday/Friday/holiday):
     - Send SMS via Twilio (10 USD/month, $0.01/SMS)
     - Send email via SES (free tier 62K emails/month)
     - Send Discord webhook (#emergency / #alerts fallback)
  4. If webhook unreachable (VPS down):
     - HIGH priority alert: "VPS UNREACHABLE"

Deploy: terraform / serverless framework — see serverless.yml + README.md.
NOT YET DEPLOYED — code only, deployment task #13 (Day 13-14).
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# Environment vars (set in Lambda config / serverless.yml)
BOT_STATUS_URL = os.environ.get("BOT_STATUS_URL", "")
BOT_AUTH_TOKEN = os.environ.get("BOT_AUTH_TOKEN", "")
DISCORD_EMERGENCY_WEBHOOK = os.environ.get("DISCORD_EMERGENCY_WEBHOOK", "")
DISCORD_ALERTS_WEBHOOK = os.environ.get("DISCORD_ALERTS_WEBHOOK", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "")
SMS_TO = os.environ.get("SMS_TO", "")
SES_FROM = os.environ.get("SES_FROM", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")

# Thresholds (CET)
PRIMARY_CLOSE_HOUR = 20  # 20:55 CET Mon-Thu, 20:45 CET Fri
PRIMARY_CLOSE_MIN_MONTHU = 55
PRIMARY_CLOSE_MIN_FRI = 45
DEADLINE_BUFFER_MIN = 5  # alert if position open more than 5 min past primary close

# Weekday: Mon=0..Sun=6
FRIDAY = 4

# CET timezone (CEST in summer = UTC+2, CET in winter = UTC+1)
# Lambda runs in UTC; we compute CET offset via known DST rules
CET_OFFSET_HOURS = 2  # CEST default (assuming summer); for winter need +1 logic


def now_cet() -> datetime:
    """Return current time in CET/CEST. Naive datetime for simplicity."""
    utc_now = datetime.now(timezone.utc)
    # Simplified: in late April 2026 we're in CEST (UTC+2)
    # For production add proper DST handling via zoneinfo
    return utc_now + timedelta(hours=CET_OFFSET_HOURS)


def get_deadline(now: datetime) -> datetime:
    """Compute primary close deadline + buffer for current day."""
    if now.weekday() == FRIDAY:
        deadline = now.replace(hour=PRIMARY_CLOSE_HOUR, minute=PRIMARY_CLOSE_MIN_FRI, second=0, microsecond=0)
    else:
        deadline = now.replace(hour=PRIMARY_CLOSE_HOUR, minute=PRIMARY_CLOSE_MIN_MONTHU, second=0, microsecond=0)
    return deadline + timedelta(minutes=DEADLINE_BUFFER_MIN)


def fetch_bot_status() -> dict | None:
    """GET bot status webhook with Bearer auth. Return dict or None on failure."""
    if not BOT_STATUS_URL:
        return None
    req = urllib.request.Request(BOT_STATUS_URL)
    if BOT_AUTH_TOKEN:
        req.add_header("Authorization", f"Bearer {BOT_AUTH_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"bot status fetch failed: {e}")
        return None


def post_discord(webhook: str, content: str):
    if not webhook:
        print(f"discord webhook empty, skip")
        return
    payload = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(webhook, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=5)
        print(f"discord posted ({len(content)} chars)")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"discord post failed: {e}")


def send_twilio_sms(body: str):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM and SMS_TO):
        print("twilio config incomplete, skip SMS")
        return
    import base64
    auth = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()).decode()
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    body_data = f"To={SMS_TO}&From={TWILIO_FROM}&Body={body}".encode()
    req = urllib.request.Request(url, data=body_data, method="POST")
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        urllib.request.urlopen(req, timeout=5)
        print("SMS sent")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"SMS failed: {e}")


def send_ses_email(subject: str, body: str):
    """Send email via SES — uses boto3 (Lambda runtime includes it)."""
    if not (SES_FROM and EMAIL_TO):
        print("SES config incomplete, skip email")
        return
    try:
        import boto3
        ses = boto3.client("ses", region_name="eu-central-1")
        ses.send_email(
            Source=SES_FROM,
            Destination={"ToAddresses": [EMAIL_TO]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        print("SES email sent")
    except Exception as e:
        print(f"SES failed: {e}")


def lambda_handler(event, context):
    """EventBridge scheduled invocation entry point.

    Triggered every 5 min in 19:00-22:00 CET window via cron.
    """
    cet_now = now_cet()
    hour = cet_now.hour
    minute = cet_now.minute
    print(f"watchdog tick: {cet_now.isoformat()} (CET, hour={hour}, min={minute})")

    # Skip outside watch window (cron should already handle, but defensive)
    if hour < 19 or hour > 22:
        print("outside watch window, skip")
        return {"status": "skipped", "reason": "outside-window"}

    deadline = get_deadline(cet_now)
    past_deadline = cet_now > deadline

    status = fetch_bot_status()
    if status is None:
        # VPS unreachable — high-priority alert
        msg = (f"🚨 **VPS UNREACHABLE**\n"
               f"watchdog @ {cet_now.isoformat()} CET cannot reach bot status webhook.\n"
               f"Possible causes: VPS down, network issue, bot crashed, auth invalid.\n"
               f"Action: connect to VPS (RDP/SSH), check service status, restart if needed.")
        post_discord(DISCORD_EMERGENCY_WEBHOOK or DISCORD_ALERTS_WEBHOOK, msg)
        send_ses_email("VPS UNREACHABLE — DAX FTMO bot watchdog", msg)
        if past_deadline:
            send_twilio_sms(f"VPS UNREACHABLE @ {cet_now.strftime('%H:%M')} past close deadline {deadline.strftime('%H:%M')}")
        return {"status": "alert", "reason": "vps-unreachable"}

    # Parse status
    open_count = status.get("open_positions_count", 0)
    heartbeat_age = status.get("last_heartbeat_age_sec", 0)
    last_close_attempt = status.get("last_close_attempt_at", "")

    print(f"  open_positions={open_count}, heartbeat_age_sec={heartbeat_age}")

    # Check 1: heartbeat stale (> 90 sec) → bot is unresponsive
    if heartbeat_age > 90:
        msg = (f"⚠️ **Bot heartbeat stale**\n"
               f"Last heartbeat: {heartbeat_age:.0f} sec ago.\n"
               f"Bot may be hung. Check process / logs.")
        post_discord(DISCORD_ALERTS_WEBHOOK, msg)

    # Check 2: positions open past deadline
    if open_count > 0 and past_deadline:
        msg = (f"🚨 **POSITION OPEN PAST DEADLINE**\n"
               f"watchdog @ {cet_now.isoformat()} CET\n"
               f"deadline: {deadline.isoformat()} CET (+ {DEADLINE_BUFFER_MIN} min buffer)\n"
               f"open positions: {open_count}\n"
               f"last close attempt: {last_close_attempt}\n"
               f"This means in-process close framework (Layer 3a-d) FAILED.\n"
               f"ACTION: connect to VPS / MT5, force close manually.")
        post_discord(DISCORD_EMERGENCY_WEBHOOK or DISCORD_ALERTS_WEBHOOK, msg)
        send_ses_email("POSITION OPEN PAST DEADLINE — DAX FTMO bot", msg)
        send_twilio_sms(f"DAX bot pos OPEN past {deadline.strftime('%H:%M')} ({open_count}). Force close NOW.")
        return {"status": "alert", "reason": "position-past-deadline"}

    # All clear
    return {
        "status": "ok",
        "cet_time": cet_now.isoformat(),
        "open_positions": open_count,
        "heartbeat_age_sec": heartbeat_age,
    }


if __name__ == "__main__":
    # Local test
    print(lambda_handler({}, None))
