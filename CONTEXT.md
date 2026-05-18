# Strava Leaderboard Bot

A weekly Strava club leaderboard bot that generates leaderboard images and sends them to a Telegram group chat.

## Language

**Cookie Health Check**:
A proactive check that periodically fetches the club leaderboard to detect session expiry before the weekly run. On 302/401 responds by alerting all Bot Owners immediately. On other errors, uses a two-strike rule: logs on first failure, alerts on second consecutive failure. A successful 200 clears the strike counter.
_Avoid_: Expiry detector

**Health Check Interval**:
The period in minutes between consecutive cookie health checks. Configurable via `COOKIE_CHECK_INTERVAL_MINUTES`.
Default: 180 (3 hours)
_Avoid_: Check frequency, poll interval

**Bot Owner**:
A person who maintains the bot and is notified when the Strava session cookie expires. Owners are configured as a comma-separated list of Telegram chat IDs.
_Avoid_: Admin, maintainer

**Leaderboard Failure Message**:
A text sent to the group chat when the weekly leaderboard fetch fails due to an expired cookie. Configured via `LEADERBOARD_FAILURE_MESSAGE` in `.env`.
Default: "К сожалению, токен Strava истёк, и админы ещё не обновили его. Лидерборд на этой неделе не сформирован. Свяжитесь с админами, чтобы исправить."
_Avoid_: Error text

## Relationships

- A **Cookie Health Check** detects session expiry and alerts all **Bot Owners** via Telegram DM
- On expiry, the weekly run sends a **Leaderboard Failure Message** to the group chat
- A **Bot Owner** receives expiry alerts directly via Telegram DM and is expected to refresh the cookie

## Example dialogue

> **Dev:** "Who gets notified when the cookie expires?"
> **Domain expert:** "All the **Bot Owners**. They're listed in `TELEGRAM_ALERT_IDS` — anyone in that list can refresh the cookie."