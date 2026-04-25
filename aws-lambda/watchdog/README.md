# Cloud Watchdog (AWS Lambda)

**Layer 4 close framework** per Strategy v3.2. Independent monitoring
robotí compliance s primary close deadline (20:55 CET / 20:45 CET Fri).

## Status

🟡 **NOT DEPLOYED.** Code complete, deploy task #13 (Day 13-14, ~7.5.2026).

## Architektura

```
+----------+         +------------+         +-----------+
| Lambda   |  HTTPS  | VPS bot    |   ←     | EventBridge
| watchdog |  ←----  | /status    |  cron 5m |
| eu-central-1       | (FastAPI)  |         +-----------+
+----------+         +------------+
    |
    +-- Discord webhook (#emergency / #alerts)
    +-- Twilio SMS (Pavel)
    +-- AWS SES email
```

## Triggers

EventBridge schedule:
- `cron(*/5 17-20 ? * MON-FRI *)` — every 5 min, UTC 17:00–20:00 = CEST 19:00–22:00
- Mon-Fri only

## Logic

1. GET `BOT_STATUS_URL` with `Bearer BOT_AUTH_TOKEN`
2. Parse `{open_positions_count, last_heartbeat_age_sec, last_close_attempt_at}`
3. Decide:
   - VPS unreachable → Discord #emergency + email + (if past deadline) SMS
   - Heartbeat stale > 90 s → Discord #alerts
   - Position open + past deadline (20:55 + 5 min) → **Discord emergency + email + SMS**
4. Default: log "ok" status, no notifications

## Cost estimate

| Service | Usage | Cost/měs |
|---|---|---|
| Lambda | ~36 invokations × 5 days × 4 weeks ≈ 720/měs | $0.00 (free tier) |
| EventBridge | 720 events/měs | $0.00 (free tier) |
| CloudWatch logs | ~1 MB/měs | $0.00 (free tier) |
| SES email | ≤ 50 emails/měs | $0.00 (62K free tier) |
| Twilio SMS | ≤ 5 SMS/měs alerts | $0.05 (US numbers) |

**Total: ~$0.05–0.50/měs**, prakticky zdarma.

## Deploy steps (Day 13-14)

```bash
# 1. AWS account + IAM user with programmatic access
aws configure --profile dax-ftmo

# 2. Install serverless framework
npm i -g serverless serverless-python-requirements

# 3. Set secrets in .env (NEpushovat do Gitu)
export BOT_STATUS_URL=https://vps.example.com/status
export BOT_AUTH_TOKEN=<random-32-char>
export DISCORD_EMERGENCY_WEBHOOK=<webhook>
export DISCORD_ALERTS_WEBHOOK=<webhook>
export TWILIO_ACCOUNT_SID=<sid>
export TWILIO_AUTH_TOKEN=<token>
export TWILIO_FROM=+14155551234
export SMS_TO=+420...
export SES_FROM=watchdog@yourdomain.com   # SES verified
export EMAIL_TO=cernytech@gmail.com

# 4. Deploy
serverless deploy --aws-profile dax-ftmo

# 5. Test
serverless invoke --aws-profile dax-ftmo -f watchdog
# Expected: {"status":"ok"} (if VPS responds + no open positions)
# Or: {"status":"alert","reason":"vps-unreachable"} (during dev before VPS up)
```

## SES setup (one-time)

Před deploy musí být SES email verified:
1. AWS Console → SES → Email Addresses → Verify a New Email
2. Confirm via email link (in `EMAIL_TO`)
3. Move out of sandbox (request production access — instant for low volume)

## Twilio setup (one-time)

1. Register https://www.twilio.com (free trial $15 credit)
2. Buy phone number ($1/měs)
3. Verify destination number (Pavel's mobile)
4. Note Account SID + Auth Token from console

## Manual test (local)

```bash
cd aws-lambda/watchdog
export BOT_STATUS_URL=http://localhost:8000/status  # local mock
export DISCORD_ALERTS_WEBHOOK=<dev-webhook>
python handler.py
```

## TODO before deploy

- [ ] Implement `/status` endpoint on bot (FastAPI route)
- [ ] Bearer token auth on /status (32-char random, store in .env both ends)
- [ ] AWS account + IAM user
- [ ] SES email verified + out of sandbox
- [ ] Twilio account + phone numbers
- [ ] DST handling: cron currently fixed UTC 17-20 (CEST). For winter need 18-21 OR proper TZ-aware schedule.
- [ ] Test failure modes: VPS down, slow response, malformed JSON
