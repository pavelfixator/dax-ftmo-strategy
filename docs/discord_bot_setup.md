# Discord Bot Setup — Phase 1 GO/SKIP Workflow

**Účel:** Bot listener detekuje ✅ / ❌ reakce na signal posty v `#signaly`,
aktualizuje `experiments/signals.jsonl` (status `confirmed_go` / `confirmed_skip`),
co umožní live trading bot reagovat na Pavlovy GO/SKIP rozhodnutí.

---

## Prerequisites (Pavel již udělal)

1. **Discord Developer Portal**
   - https://discord.com/developers/applications
   - New Application → "DAX FTMO Bot"
   - Bot tab → Add Bot
   - **Privileged Gateway Intents:** zapnout všechny tři (Presence, Members, Message Content)
   - Copy bot token (uložen v Notepadu — viz krok 2 níže)

2. **OAuth2 Invite URL**
   - OAuth2 → URL Generator → scope `bot`
   - Bot Permissions: `Read Messages`, `Read Message History`, `Add Reactions`, `Send Messages`
   - Pozvat bota na server "DAX FTMO System"

---

## Setup kroky pro Pavla (provést teď)

### Krok 1 — Přidat token do `.env`

Otevřít `dax-ftmo-bot/.env` a přidat:
```
DISCORD_BOT_TOKEN=<token z Notepadu>
DISCORD_GUILD_ID=<ID DAX FTMO serveru>     # volitelné, doporučeno
```

`DISCORD_GUILD_ID` zjistit: Discord → User Settings → Advanced → Developer Mode ON,
pak pravým klikem na server "DAX FTMO System" → Copy ID.

### Krok 2 — Spustit daemon (manuálně, foreground test)

```powershell
cd "C:\Users\AOS Server\dax-ftmo-bot"
python scripts\run_discord_bot_daemon.py
```

Očekávaný output:
```
2026-04-28 10:30:00 [INFO] dax.daemon: starting Discord Bot listener (signals=...)
2026-04-28 10:30:02 [INFO] dax.discord_bot: Bot online: user=DAX FTMO Bot#1234 id=...
```

Pokud see "Bot online" → daemon běží OK. **Nech terminal otevřený**, jdi na krok 3.

### Krok 3 — End-to-end test workflow

V druhém terminal okně:
```powershell
cd "C:\Users\AOS Server\dax-ftmo-bot"
python scripts\test_discord_bot.py
```

Test pošle 2 signály do `#signaly`. Pavel:
1. Otevři Discord → `#signaly`
2. Reaguj **✅** na test signal #1 (do 60s)
3. Reaguj **✅** na test signal #2 (do 60s)

Output při PASS:
```
[test] STEP 1: POST signal #1 to #signaly (wait=true)
[test] signal #1 posted: msg_id=..., signal_id=TEST-...
[test] STEP 2: waiting up to 60s for ✅ reaction...
[test] PASS signal #1 → status=confirmed_go

[test] STEP 3: POST signal #2 to #signaly
[test] PASS signal #2 → status=confirmed_go

[test] ============================================================
[test] PHASE 1 GO/SKIP WORKFLOW READY
[test] ============================================================
```

### Krok 4 — Po úspěšném testu: registrovat Win Scheduled Task

```powershell
cd "C:\Users\AOS Server\dax-ftmo-bot"
.\scripts\install_discord_bot_task.ps1
```

Task `DAX-Discord-Bot-Listener` se registruje:
- Trigger: At system startup
- Restart on failure: 3× s 5min delay
- User scope (no admin required)

Spustit hned:
```powershell
Start-ScheduledTask -TaskName 'DAX-Discord-Bot-Listener'
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `DISCORD_BOT_TOKEN not set` | Token chybí v `.env` | Přidej `DISCORD_BOT_TOKEN=...` |
| `LoginFailure: Improper token` | Token expired/wrong | Re-generate v Discord Developer Portal → Bot → Reset Token |
| Bot online but reactions ignored | Privileged Intents OFF | Discord Dev Portal → Bot → Enable all 3 Intents |
| Bot online, signál posted, status=pending | Bot v jiném guildu | Set `DISCORD_GUILD_ID` to DAX FTMO server ID |
| Auto-skip nikdy nepošle status=timeout | Test bot s low timeout? | `auto_skip_timeout_s=180` default; upravit v `discord_bot.py` |

---

## Architektura

```
┌─────────────────────┐         ┌──────────────────────────┐
│ run_phase0_backtest │ POST    │ Discord webhook /signaly │
│ (or live signal)    │────────▶│ (returns message_id JSON)│
└──────────┬──────────┘         └──────────┬───────────────┘
           │ append signal                  │
           ▼                                │
   experiments/signals.jsonl                │
   (status=pending)                         │
           ▲                                │
           │ update status                  │ Pavel reagne ✅/❌
           │                                ▼
┌──────────┴──────────────────┐    ┌────────────────────┐
│ DAXDiscordBot (daemon)      │◀───│ Discord guild      │
│ on_raw_reaction_add(payload)│    │ message+reactions  │
│ + auto_skip_loop (3min)     │    └────────────────────┘
└─────────────────────────────┘
```

---

## Files

```
src/notifier/
  discord_notifier.py       — webhook POST helper (now with wait=true support)
  signal_log.py             — JSONL persistence (append/update/find)
  discord_bot.py            — DAXDiscordBot listener class
scripts/
  run_discord_bot_daemon.py — daemon entry point (loads .env, starts bot)
  install_discord_bot_task.ps1 — Win Task registrar (DON'T run until token set)
  test_discord_bot.py       — end-to-end workflow test
tests/
  test_signal_log.py        — 11 tests
  test_discord_bot.py       — 10 tests (mocked, no real Discord connection)
experiments/
  signals.jsonl             — append-only signal log (created on first signal)
logs/
  discord_bot.log           — daemon rotating log (5 MB × 3 backups)
```

---

## Phase 1 status

- ✅ Bot setup (Discord Dev Portal + privileged intents + invite)
- ✅ Implementation (this commit)
- ⏳ Pavel kroky 1-4 (token, daemon, test, Win Task)
- ⏳ Po PASS: live signál bot → discord_notifier.post(wait=true) + signal_log.append → bot listener → status update → execution layer reacts on confirmed_go
