# Task: Build a Comprehensive Observability & Error Logging System for Keeper

## Context
Keeper is a Discord bot with 47 active cogs, ~20,000 lines of code, running on a Raspberry Pi 5. We have zero visibility into errors — commands fail silently, background tasks crash without notification, and we only discover problems when users complain. The `!healthcheck` cog runs every 6h but only checks structural health (tables exist, cogs loaded, tasks running). It does NOT catch runtime errors like the `NameError: ALL_RANKS not imported` bug that silently broke 3 commands for an unknown amount of time.

## What Exists Today
- **Logging**: 20+ cogs use `logging.getLogger()` but output goes only to journalctl (systemd). Nobody monitors journalctl in real time.
- **Healthcheck**: 9 structural checks every 6h (DB, tables, cogs loaded, tasks running, permissions). No runtime error detection.
- **Metrics alerts**: Posts to admin/mod channel if D7 retention < 30% or DAU/MAU < 0.25. This is the ONLY thing that posts to Discord on failure.
- **Command error handler**: NONE. No `on_command_error`. Commands that throw exceptions just silently fail — the user sees nothing, the admin sees nothing.
- **Background task crashes**: Detected 15s after startup only. If a task crashes AFTER startup, nobody knows until healthcheck runs (up to 6h later).
- **Silent exception swallowing**: Several `except discord.HTTPException: pass` blocks hide real failures (DM send failures, role update failures, embed post failures).

## What We Need: A `#keeper-logs` Channel System

### 1. Create a `#keeper-logs` private channel (owner-only, like #bot-commands)
- Add to `!setup` and `!lockdown` — hidden from all users except owner + bot
- This is where ALL error/warning/info logs go

### 2. Global Command Error Handler (`on_command_error`)
- Catch ALL command exceptions
- Post to #keeper-logs with: command name, user who ran it, full traceback, timestamp
- For user-facing errors (missing args, permission denied), send a clean error message to the user
- For internal errors (NameError, TypeError, DB errors), send "Something went wrong" to user + full details to #keeper-logs

### 3. Background Task Crash Monitor
- When any `@tasks.loop` task throws an exception, post to #keeper-logs immediately (not 6h later)
- Include: task name, cog name, full traceback, how long the task had been running
- Attempt to restart the task automatically if possible

### 4. Cog Load Failure Alerts
- When a cog fails to load on startup, post to #keeper-logs (not just print to stdout)
- Include: cog name, full traceback
- Post a summary after all cogs load: "46/47 cogs loaded. FAILED: cogs.leaderboard (NameError: ALL_RANKS)"

### 5. Event Listener Error Logging
- Wrap key event listeners (on_message, on_member_join, on_raw_reaction_add) with error catching
- Any exception in an event listener should post to #keeper-logs with context (which event, what message/member triggered it)

### 6. Daily Health Summary
- Every 24h (e.g., 6 AM UTC), post a summary embed to #keeper-logs:
  - Uptime since last restart
  - Total errors in last 24h (by category: command errors, task crashes, event errors)
  - Cog status (all loaded? any tasks stopped?)
  - DB health (user count, messages today, any negative scores)
  - Memory/resource usage if available
- This is SEPARATE from healthcheck — healthcheck is structural, this is operational

### 7. Upgrade Existing Error Handling
- Search for all `except discord.HTTPException: pass` and `except discord.Forbidden: pass` patterns
- Add logging to each one: what failed, what was being attempted, for which user
- Don't change behavior (still catch the exception), just make failures visible in #keeper-logs
- Priority targets: role assignment (scoring_handler rank-ups, onboarding, reset/setrank), DM sends (onboarding_v2, reengagement, loss_aversion), embed posts (leaderboard, weekly_recap)

### 8. Error Rate Alerting
- If more than 10 errors occur in 5 minutes, send a special alert embed to #keeper-logs: "ERROR SPIKE: 15 errors in last 5 minutes" with the most common error
- This catches cascading failures (e.g., DB locked, Discord API down)

## Implementation Approach

Build this as a single new cog: `cogs/logger.py` (or `cogs/bot_logger.py` to avoid conflicts with Python's logging module)

The cog should:
- Provide a `LogService` that other cogs can optionally use directly, but primarily hooks into discord.py's built-in error dispatch
- Be the FIRST cog loaded (move to top of COG_EXTENSIONS in bot.py) so it catches errors from all other cogs
- Use an in-memory buffer + periodic flush to avoid rate-limiting on the Discord API (batch multiple errors into one embed if they happen rapidly)
- Categorize log entries: ERROR (red embed), WARNING (yellow), INFO (blue)
- Include a `!logs` admin command to show the last N errors
- Include a `!errors` admin command that shows error frequency by type in the last 24h

## Quality Standards
- Every error embed must include enough context to diagnose the issue WITHOUT needing to SSH into the Pi and read journalctl
- The logger itself must NEVER crash the bot — wrap everything in try/except with fallback to print()
- Do not modify the behavior of any existing cog — only ADD visibility
- Test every error path: deliberately trigger a command error, a task crash, a cog load failure, a permission error, and verify each one appears in #keeper-logs
- All code will be reviewed by 5 senior engineers — write clean, well-structured, documented code

## Files to Modify
- `bot.py` — Add bot_logger to COG_EXTENSIONS (first position), add global on_command_error
- `config.py` — Add LOGGER_CHANNEL, ERROR_SPIKE_THRESHOLD, ERROR_SPIKE_WINDOW, DAILY_SUMMARY_HOUR constants
- `setup_server.py` — Add #keeper-logs to channel creation + lockdown
- `cogs/bot_logger.py` — NEW: The main observability cog
- `CLAUDE.md` — Update with new cog, channel, and commands

## After Implementation
- Deploy to Pi and restart
- Test each error category by deliberately triggering it
- Verify #keeper-logs shows all expected entries
- Run !healthcheck to confirm no regressions
- Update CLAUDE.md with full documentation
- Commit and push
