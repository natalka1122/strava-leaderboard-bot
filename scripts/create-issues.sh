#!/usr/bin/env bash
# Requires: gh CLI installed & `gh auth login`
# Run with: bash scripts/create-issues.sh
set -euo pipefail
REPO="natalka1122/strava-leaderboard-bot"

create() {
  local title="$1" label="$2" body="$3"
  echo "→ $title"
  gh issue create --repo "$REPO" --title "$title" --label "$label" --body "$body"
}

# 1 – Cron
create "Migrate to cron-based execution" enhancement "$(cat <<'BODY'
## Problem
Bot runs a 24/7 polling loop inside the container, which is unnecessary overhead.

## Goal
Bot runs on-demand (once) and exits. Scheduling is handled by **system cron** or a wrapper script.

## Tasks
- [ ] Remove infinite while loop from `bot.py`
- [ ] Bot runs once: fetch → generate image → send telegram → exit
- [ ] Add cron example to README (simple weekly Monday 00:05)
- [ ] Update Dockerfile / docker-compose if needed
BODY
)"

# 2 – Design
create "Rework & Improve Leaderboard Image Design" enhancement "$(cat <<'BODY'
## Goal
Explore better layout, typography, color palette, and alternative rendering approaches for the leaderboard PNG.

## Ideas
- Better visual hierarchy (rank, name, stats)
- Alternative rendering (SVG,cairo/Matrix image libraries)
- Dark mode toggle
- Mini charts / sparklines for stats above
- Dynamic row spacing based on data
- Try different font families and sizes
BODY
)"

# 3 – Validation
create "Add .env / startup validation (fail fast)" enhancement "$(cat <<'BODY'
## Problem
Bot silently fails if required env vars are missing.

## Goal
Check required vars at boot and exit with a clear `Error: missing env: STRAVA_SESSION_COOKIE` message.

## Required vars (non-optional)
- `STRAVA_SESSION_COOKIE`
- `STRAVA_CLUB_ID`
BODY
)"

# 4 – Dry run
create "Add --dry-run flag (skip Telegram posting)" enhancement "$(cat <<'BODY'
## Problem
Hard to test locally without triggering real Telegram sends.

## Goal
Add `--dry-run` / `DRY_RUN=true` flag: fetches data, generates image, skips Telegram posting.

## Tasks
- Add `--dry-run` CLI flag or `DRY_RUN` env var
- Skip Telegram posting when dry-run
- Example: `docker compose run --rm strava-bot --dry-run`
BODY
)"

# 5 – Healthcheck
create "Add Docker healthcheck" enhancement "$(cat <<'BODY'
## Problem
Container health reporting for orchestration and monitoring.

## Goal
Add a `HEALTHCHECK` to the Dockerfile. Simple HTTP endpoint and return `0` or HTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 CMD curl -f http://localhost:8081/health || exit.`
BODY
)"

# 6 – Cookie expiry alert
create "Detect expired Strava session & alert owner directly" enhancement "$(cat <<'BODY'
## Problem
`_strava4_session` cookie expires every 2-4 weeks. Bot silently fails.

## Goal
Detect expiracy (401 response) → alert the bot owner personally (NOT the group).

## Tasks
- Detect 401/cookie-expired responses
- Send warning to a separate personal Telegram chat (DM, not the group)
- Mention the exact error in the alert
- Log the error with clear next steps
```
BODY
)"

# 7 – API key alternative
create "Explore obtaining leaderboard via Strava API + Activity Streams (no cookie)" enhancement "$(cat <<'BODY'
## Problem
Current approach relies on `_strava4_session` cookie (web scraping). Fragile: expires and requires manual refresh.

## Goal
Explore getting leaderboard using the official Strava API + OAuth + Activity Streams. Calculate leaderboard manually from club members' activities.

## Tasks
- Research Strava API limits and OAuth flow
- Compare API rate limits vs cookie refresh
- Prototype: fetch club members → fetch their activities → calculate stats
- Compare accuracy with cookie-based approach
BODY
)"

echo "✅ All issues created."
