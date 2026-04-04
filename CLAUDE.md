# The Circle — Discord Bot Project

## What This Is
A custom Discord bot called **"Keeper"** for a social server called **"The Circle"**. Built in Python (discord.py) with SQLite, deployed on a Raspberry Pi 5. Keeper is a scientifically-designed engagement machine with a 6-layer scoring engine, 100-tier rank progression, 49 feature cogs (46 active), variable reward psychology, social graph engineering, seasonal battle passes, and multi-dimensional anti-churn systems. ~20,000 lines of code.

**Target audience:** Mixed 18-35 demographic. Dark luxury branding. Gamified social community.

## Discord Links & IDs
- **Server Name:** The Circle
- **Guild/Server ID:** `1489120401098276896`
- **Bot Application ID:** `1489119042479329320`
- **Bot Name:** Keeper#4569
- **Bot Token:** Stored in `.env` file (never commit this)
- **Bot Invite URL:** `https://discord.com/oauth2/authorize?client_id=1489119042479329320&permissions=1099780188272&integration_type=0&scope=bot`
- **Developer Portal:** https://discord.com/developers/applications (search "Keeper")
- **Required Intents:** Message Content, Server Members, Presences (all enabled)
- **Bot Permissions:** Manage Server, Manage Roles, Manage Channels, Send Messages, Embed Links, Attach Files, Read Message History, Add Reactions, Manage Messages, Moderate Members

## Server Listings (all live)
- **Disboard:** https://disboard.org — tags: community, leveling, social, memes, active. Bump up to 4x/day.
- **Discord.me:** https://discord.me/jointhecircle — vanity URL: `jointhecircle`
- **Top.gg:** https://top.gg — listed as server, 12 categories selected.

### Disboard Bump Schedule (UTC -> PDT)
- 00:00-05:59 UTC = 5:00 PM PDT
- 06:00-11:59 UTC = 11:00 PM PDT
- 12:00-17:59 UTC = 5:00 AM PDT
- 18:00-23:59 UTC = 11:00 AM PDT

## Architecture
- **Language:** Python 3.11 (Pi) / 3.9 (local Mac -- needs `from __future__ import annotations`)
- **Framework:** discord.py 2.7+
- **Database:** SQLite via aiosqlite (file: `circle.db`)
- **Hosting:** Raspberry Pi 5 (**SINGLE INSTANCE ONLY** — never run bot.py locally while Pi is running; same token = duplicate everything)
- **Bot Token:** stored in `.env` (not committed)
- **Bot Owner ID:** `1170038287465971926` (jack_rosely) — all admin commands restricted to this user via `@commands.is_owner()`
- **Total Cogs:** 51 defined, 48 active. Disabled: `streaks.py` (→ streaks_v2), `welcome.py` (→ onboarding_v2), `onboarding.py` (→ onboarding_v2), `smart_dm.py` (→ reengagement)
- **Total DB Tables:** ~50

## Raspberry Pi Access
- **LAN IP:** `192.168.10.177` (use when on home WiFi)
- **Tailscale IP:** `100.107.165.3` (use when on cellular/remote — hostname `pihole5`)
- **Username:** `pi5`
- **Password:** `insanebeef45`
- **Project Path:** `/home/pi5/discord/`
- **Service Name:** `circle-bot` (systemd, auto-starts on boot)
- **IMPORTANT:** Pi also runs Pi-hole for ad blocking -- don't touch anything outside ~/discord
- **NOTE:** If LAN IP times out, switch to Tailscale IP. Run `tailscale status` to verify connectivity.

### SSH Commands (copy-paste ready)
```bash
# Connect to Pi
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177

# Push ALL project files to Pi
tar czf - bot.py config.py database.py scoring.py ranks.py setup_server.py dm_coordinator.py cogs/*.py | SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "cd ~/discord && tar xzf -"

# Restart Keeper
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S systemctl restart circle-bot"

# Check service status
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S systemctl status circle-bot"

# View logs (last 30 lines)
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S journalctl -u circle-bot --no-pager -n 30"

# View live logs (follow mode)
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S journalctl -u circle-bot -f"

# Full deploy (push + restart + verify)
tar czf - bot.py config.py database.py scoring.py ranks.py setup_server.py dm_coordinator.py cogs/*.py | SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "cd ~/discord && tar xzf -" && SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S systemctl restart circle-bot 2>&1 && sleep 3 && echo 'insanebeef45' | sudo -S journalctl -u circle-bot --no-pager -n 10"
```

## Bot Personality -- "Keeper"
Mysterious ancient guardian who speaks with modern slang. Cryptic, all-knowing, occasionally funny. Self-aware ironic humor for rank taglines.

**Voice examples:**
- Rank-up: "The Circle has spoken. @Mike ascends to Veteran III. The path only gets harder."
- Comeback: "A familiar presence returns... @Sarah, The Circle remembers you."
- Welcome: "Another soul enters The Circle. Your journey begins now..."
- Critical Hit: "CRITICAL HIT -- 2x points!"
- Oracle: "The Circle sees conflict in #politics. Prepare yourselves."

## Visual Style
- **Embeds:** Dark & sleek -- sidebar `#1a1a2e` (deep navy), accent `#e94560` (hot red)
- **Emoji:** Heavy usage -- fire, skull, crown, lightning, target, eyes, rocket
- **Titles:** ALL CAPS with line dividers
- **Vibe:** Premium, exclusive, nightclub

---

## SCORING ENGINE v2 (6-Layer Formula)

```
final_score = BASE * SOCIAL * TEMPORAL * ENGAGEMENT * META
```

### Layer 1: BASE (Quality-Aware)
| Component | Value |
|---|---|
| Base message | 1.0 pt |
| Per word | +0.15 pt (capped at 200 words) |
| Media post | +5.0 pt |
| Link share | +2.0 pt |
| Vocabulary diversity | Up to +20% (unique/total word ratio) |
| Question bonus | +15% if contains `?` |
| Punctuation bonus | +10% for proper sentences |

### Layer 2: SOCIAL (Interaction Multiplier)
| Action | Multiplier |
|---|---|
| Reply | 2.5x |
| @mention | 2.0x |
| Reply + mention synergy | 6.0x |
| Thread depth bonus | +10% per level (max 5 = +50%) |
| First reply within 5 min | 1.5x |
| **Hard cap** | 12.0x max |

### Layer 3: TEMPORAL (Time-of-Day)
- Off-peak (UTC 0-6): 1.3-1.5x (incentivize seeding)
- Peak (UTC 17-23): 1.2-1.3x (reward social density)
- Baseline (UTC 8-12): 1.0x
- Weekend bonus: +15%

### Layer 4: ENGAGEMENT (Diminishing Returns + Diversity + Combo)
- Messages 1-15/day: 1.0x | 16-30: 0.75x | 31-50: 0.5x | 51-75: 0.25x | 76+: 0.10x
- Channel diversity: +8% per extra channel (max +40% at 6 channels)
- Combo: consecutive social msgs within 10 min = +10% per stack (max +50%)

### Layer 5: META (Comeback + Streak + Catch-up + Faction + Prestige)
- Comeback: 5x (7-14d — reward fast returns!), 3x (15-29d), 2x (30-59d), 1.5x (60+d) + welcome-back coin gift
- Streak: 1.1x (3d) to 4.0x (365d)
- Catch-up: Rookie/Regular +40%, Certified/Respected +20%, Veteran/OG +10%
- Faction winner: 1.1x
- Prestige: +5% per level (max +25% at prestige 5)
- **Hard cap:** 20.0x max

### Layer 6: Dynamic Daily Cap
- Ranks 1-30: 500 pts/day | 31-60: 750 | 61-90: 1000 | 91-100: 1500
- **Post-score multiplier cap:** `POST_SCORE_MULT_CAP = 10.0` — cumulative post-score multipliers (comeback × event × 2x × boost × drop × crit) capped at 10x
- Daily cap re-enforced AFTER all post-score multipliers — prevents single-message exploits

### Post-Score Integrations (all wired in scoring_handler.py)
- **Surprise 2x XP window:** If `VariableRewards.is_double_xp` is active, all points doubled
- **Personal XP boosts:** Checks `active_boosts` table for shop/wheel-granted multipliers
- **Season XP:** 50% of raw score (pre-diminishing-returns) flows to `season_pass.add_season_xp()`
- **Variable rewards delegation:** Jackpot contribution + mystery drops via `variable_rewards.on_scored_message()`
- **Welcome-back gift:** Comeback users get 50-500 Circles scaling with days absent

### Anti-Spam (Scoring)
- 15s cooldown between scored messages
- 5 msgs in 10s = 5 min scoring pause
- Duplicate message detection (5 min window)
- Scoring handler skips any message deleted by moderation cog

### Anti-Spam (Moderation — 3 layers)
**Layer 1: Discord Permissions** (prevents pings from firing at all)
- `mention_everyone` stripped from all roles except owner's (via `!lockdown`)
- @everyone/@here physically cannot fire for non-owner users

**Layer 2: Discord AutoMod** (blocks message BEFORE it's sent — no notification)
- Messages with 7+ user/role mentions blocked entirely + 10min timeout
- Created via `!lockdown`. Owner + bot exempt.

**Layer 3: Bot Moderation Cog** (deletes + timeouts for anything that slips through)
- @everyone/@here in message content: delete + 5min timeout
- 7+ user mentions in one message: delete + 10min timeout
- 4+ messages-with-mentions within 60s (rapid ping spam): delete + 10min timeout
- 4+ messages within 8s (rate limit): delete + 10min timeout
- 2+ duplicate messages within 60s: delete + 10min timeout
- `!purge @user [minutes]`: delete user's messages (no time cap)
- `!nuke [minutes]`: delete all spam patterns (no time cap)
- Note: Discord API limits bulk delete to messages <14 days old

---

## STREAK SYSTEM (Multi-Dimensional)

### 5 Streak Types (tracked in `streaks_v2` table)
| Type | Requirement | Milestones |
|---|---|---|
| Daily | Any activity (message/reaction/voice) | 3/7/14/30/60/100/180/365 days |
| Weekly | Active 5+ of 7 days | 4/8/12/26/52 weeks |
| Social | Reply to 3+ different people/day | 3/7/14/30 days |
| Voice | 15+ minutes in voice/day | 3/7/14 days |
| Creative | Post media daily | 3/7/14 days |

### Streak Multipliers (Daily)
3d: 1.1x | 7d: 1.25x | 14d: 1.5x | 30d: 2.0x | 60d: 2.5x | 100d: 3.0x | 180d: 3.5x | 365d: 4.0x

### Streak Insurance
- Freeze tokens: 200 Circles each, max 3 held, auto-consumed on missed day
- Grace period: first-ever break of 14+ day streak = free 24h recovery (one-time)
- Streak recovery: within 48h, pay 500-2000 Circles to restore (minus 3 days)

### Paired Streaks
- `!pairstreak @user` -- both must be active each day or BOTH lose it
- Max 3 pairs, +5% bonus per active pair
- Milestones: 7/14/30/60 days with shared coin rewards

---

## 100 RANK TIERS (10 Groups x 10 Sub-Ranks)

| Tiers | Group | Color | Tagline | Unlocks |
|---|---|---|---|---|
| 1-10 | Rookie | Gray | "You found the WiFi password." | Basic access, !spin, !profile |
| 11-20 | Regular | Green | "Your screen time is concerning." | Poll voting, !setbio, prompt submissions |
| 21-30 | Certified | Blue | "Your mom would be worried." | Create Circles, be mentor, !setcolor, trivia submissions |
| 31-40 | Respected | Orange | "Therapist: 'And the Discord?'" | Factions, !poll, Hot Takes, #vip-lounge |
| 41-50 | Veteran | Red | "You've seen things." | Rivals, spotlight nominations, 4h confession cooldown, prestige |
| 51-60 | OG | Purple | "Touch grass? Never heard of it." | Profile frames, pin messages, named in announcements |
| 61-70 | Elite | Teal | "Your keyboard fears you." | Host flash events, 2x mystery box odds, create emoji |
| 71-80 | Legend | Gold | "Some say they never log off." | Custom role name, +5% permanent bonus, Legends Corner |
| 81-90 | Icon | Hot Pink | "Are you okay? Genuinely." | Personal text channel, custom Keeper greeting |
| 91-100 | Immortal | White | "This IS your grass." | Permanent Hall of Fame, set daily prompt 1x/month |

Score thresholds: linear 50 pts/rank for early tiers, then exponential (RuneScape-style). Rookie I = 0, Rookie II = 50, Regular I = 500, Certified I = 1,062, Immortal X ~ 2,000,000. Minimum gap of 50 pts per rank prevents instant multi-rank jumps.

---

## CHANNEL STRUCTURE
```
📋 WELCOME & INFO -- #welcome (RO), #info (RO), #rules (RO), #announcements (RO)
💬 SOCIAL -- #general, #memes, #dating
🏋️ SERIOUS -- #politics, #work, #fitness
📊 MEDIA & STATS -- #media-feed (RO), #leaderboard (RO), #rank-ups (RO), #achievements (RO)
🎭 ENGAGEMENT -- #introductions, #confessions (RO), #confession-discussion, #hall-of-fame (RO)
⚔️ FACTIONS -- #faction-war (RO), #team-inferno, #team-frost, #team-venom, #team-volt
🤖 BOT -- #bot-commands (OWNER-ONLY, hidden from all other users), #keeper-logs (OWNER-ONLY, error/health logs)
🌙 EXCLUSIVE -- #vip-lounge (Respected+), #after-hours (Veteran+, NO scoring)
```

Excluded from scoring: welcome, info, rules, announcements, media-feed, leaderboard, rank-ups, achievements, bot-commands, keeper-logs, confessions, hall-of-fame, faction-war, after-hours.

---

## ALL 48 COGS

### Phase 1: Core (14 cogs)
| Cog | File | Purpose |
|---|---|---|
| ~~Streaks~~ | `cogs/streaks.py` | **DISABLED** — Superseded by `streaks_v2.py`. Commands renamed: `!streak` → v2, `!streaks` → v2. |
| Achievements | `cogs/achievements.py` | 30+ one-time badge unlocks. Announcements post to **#achievements** channel (not inline). |
| Scoring Handler | `cogs/scoring_handler.py` | **6-layer scoring engine**, anti-spam, rank-ups (**#rank-ups only, group boundaries only**), critical hits, bonus drops, 2x XP window integration, active boost integration, season XP, variable rewards delegation, **first-message instant feedback**, parent_message_id tracking, **message ID dedup**, **POST_SCORE_MULT_CAP (10x)**, **daily cap re-enforcement after multipliers** |
| Leaderboard | `cogs/leaderboard.py` | Auto-updating hourly embed + !rank, !top, !stats. **Edits existing embed on restart** (searches channel history, no duplicate posts). |
| Media Feed | `cogs/media_feed.py` | Scrapes all channels for media -> mirrors to #media-feed. **Message ID dedup** prevents double posts. **Auto-cleanup:** deleting original message also deletes its #media-feed mirror (single + bulk delete). |
| ~~Welcome~~ | `cogs/welcome.py` | **DISABLED** — Superseded by `onboarding_v2.py` which handles #welcome embed + DM + role assignment. |
| Invites | `cogs/invites.py` | Tracks who invited who, validates after 24h + 5 msgs |
| Comeback | `cogs/comeback.py` | Graduated decay (legacy decay logic) |
| Reactions | `cogs/reactions.py` | Points for receiving reactions |
| Voice XP | `cogs/voice_xp.py` | Points for time in voice channels + **voice co-presence** feeds social graph friendship scores. **AFK detection:** requires 2+ non-bot users, 50% penalty if muted+deafened >10 min. |
| Daily Prompts | `cogs/daily_prompts.py` | Auto-posts discussion question daily at 6pm UTC (UGC-first, then config fallback) |
| Weekly Recap | `cogs/weekly_recap.py` | **Sunday Ceremony**: multi-embed weekly recap (stats + streaks + social bonds + faction standings) |
| Info | `cogs/info.py` | Posts guide embeds to #info via !postinfo |
| Setup | `setup_server.py` | Creates all channels, categories, 100 rank roles via !setup |

### Phase 2: Engagement (17 cogs)
| Cog | File | Purpose |
|---|---|---|
| ~~Onboarding~~ | `cogs/onboarding.py` | **DISABLED** — Superseded by `onboarding_v2.py`. Was causing duplicate DMs on join. |
| Introductions | `cogs/introductions.py` | First intro = 50 pts + badge. Announcement posts to **#achievements** (not inline). |
| Confessions | `cogs/confessions.py` | Anonymous posting, 6h cooldown, discussion channel, **content filtering** (regex blocklist, 1000 char max), `!report` command (3 reports = auto-delete) |
| Starboard | `cogs/starboard.py` | Hall of Fame. Counts **unique users** who reacted (not total emojis). Author excluded. Threshold: 5 unique users (scales with server size). |
| Invite Reminders | `cogs/invite_reminders.py` | 2-3x/week rotating templates + monthly race |
| Growth Nudges | `cogs/growth_nudges.py` | Rank teasers at 80% + stagnation nudges at 14 days |
| Engagement Triggers | `cogs/engagement_triggers.py` | Random tips, social proof, cliffhangers |
| Economy | `cogs/economy.py` | Circles currency (1 per scored message) + **`!give` trading** (10% tax, 500/day max) |
| Shop | `cogs/shop.py` | 5 permanent items + **rotating daily shop** (3 limited-time items from pool of 8) + **mystery box** (10-item loot table with streak freezes, XP boosts, rank shields) |
| Auto Events | `cogs/auto_events.py` | **Themed daily events** (Meme Monday, Trivia Tuesday, Wisdom Wednesday, Hot Take Thursday, Flex Friday, Social Saturday) |
| Trivia | `cogs/trivia.py` | Tuesday auto-trivia, 20 questions |
| Server Goals | `cogs/server_goals.py` | Member milestones + weekly message targets |
| Profiles | `cogs/profiles.py` | Custom bio, color, banner via !profile. **Display titles** auto-derived from achievements. **Prestige level** shown. |
| Factions | `cogs/factions.py` | 4 teams, unlock at rank 21 (lowered from 31), weekly competition |
| ~~Smart DM~~ | `cogs/smart_dm.py` | **DISABLED** — Superseded by `reengagement.py`. No longer loaded. |
| Buddy System | `cogs/buddy_system.py` | Mentor pairing, 10-msg goal in 48h |
| Daily Rewards | `cogs/daily_rewards.py` | Escalating login rewards, streak reset on miss |

### Phase 3: Ultimate Engagement Engine (18 cogs)
| Cog | File | Purpose |
|---|---|---|
| Onboarding v2 | `cogs/onboarding_v2.py` | **THE sole welcome/onboarding handler.** Posts #welcome embed, assigns Rookie I role, sends quest DM, runs 7-day pipeline. T+5s quest DM (4 quests with endowed progress — joining counts as #1), T+2hr progress, T+4hr streak anchor, T+24h check-in, T+48h momentum, T+72h milestone tease, Day 6 report card (positive framing), Day 7 graduation ceremony + Survivor badge + 100 Circles. **Fallback:** posts in #general if DMs disabled. **Two-layer dedup:** (1) in-memory set for rapid re-fires, (2) DB check via `onboarding_state` table for cross-restart persistence. |
| Streaks v2 | `cogs/streaks_v2.py` | **5 streak types** (daily/weekly/social/voice/creative), freeze tokens, grace periods, paired streaks, division leaderboard |
| Re-engagement | `cogs/reengagement.py` | **8-tier unified pipeline**: Day 1 server callout, Day 2 loss aversion DM, Day 3 social proof, Day 5 competitive loss, Day 7 urgency, Day 14 active loss, Day 30 nostalgia, Day 60 closure (then opt-out) |
| Loss Aversion | `cogs/loss_aversion.py` | Graduated decay (0.5%-5%/day by inactivity length), **rank demotion** (3-day grace), streak-at-risk notifications (10 PM UTC, streaks ≥7 only, 1 DM/day), competitive displacement alerts (50+ members only), faction relegation (80+ members only) |
| Variable Rewards | `cogs/variable_rewards.py` | **Progressive jackpot** (0.05% trigger, pot builds 0.5/msg), surprise 2x XP windows (random 15-30 min every 4-8h), mystery drops every 100 server msgs, critical hits (2% chance = 2x), bonus drops (2% chance = 2-10x on next msg), near-miss messages (3%) |
| Daily Wheel | `cogs/daily_wheel.py` | `!spin` -- free once/day, animated reveal, 11 weighted segments (5-500 Circles, XP boosts, streak freeze, jackpot trigger) |
| Social Graph | `cogs/social_graph.py` | **Friendship score** tracking (replies*3 + mentions*2 + reactions*1 + voice*0.5), 5% weekly decay, `!friends` top 5, `!bestfriend` mutual detection, `!rival @user` 4-week rivalry, **icebreaker matchmaking** (finds lonely new members every 12h, creates Connection Quests) |
| Circles | `cogs/circles.py` | Friend groups (3-8 members), Certified+ rank required, 200 Circles to create, weekly Circle leaderboard, top Circle gets role color + 50 Circles/member |
| Content Engine | `cogs/content_engine.py` | **Quick Fire** rounds (always in #general, 3x/day random timing, first 5 replies get bonus), **dead zone detection** (45 min silence = auto-content), **UGC pipeline** (`!submit prompt/hottake/trivia`, admin approval, auto-approve after 3), **trending topics** (word frequency detection) |
| Debates | `cogs/debates.py` | `!debate start <topic>`, reaction voting, minority side gets 2x points, MVP Debater award, **safety thermostat** (heat > 15 = warning, > 25 = slow mode, > 35 = lock) |
| Season Pass | `cogs/season_pass.py` | **8-week seasons**, 50 tiers, exponential XP curve, free rewards every 5 tiers, premium tier (5000 Circles), weekly challenges (3/week) + daily challenges (1/day), early bird 2x for first 48h, end-of-season ceremony + rankings |
| Prestige | `cogs/prestige.py` | **Endgame reset** at rank 41+: reset score/rank, keep coins/badges/faction, earn permanent +5% per level (max +25% at prestige 5), 5 prestige levels with escalating coin rewards (2k-50k) |
| Engagement Ladder | `cogs/engagement_ladder.py` | Tracks user tiers: lurker -> newcomer -> casual -> regular -> power_user -> evangelist. Weekly recalculation, DMs on tier transitions, `!ladder` command |
| Health Check | `cogs/healthcheck.py` | Automated self-test: 23 checks (DB, tables, cogs, channels, categories, background tasks, scoring engine, config, data health, permissions). Runs every 6h + `!healthcheck` command |
| Oracle | `cogs/oracle.py` | Evening prediction ritual — Keeper's Oracle posts daily at 9 PM UTC with cryptic predictions. 200+ templates, 7-day no-repeat. `!oracle` command |
| Metrics | `cogs/metrics.py` | Retention analytics dashboard — DAU/MAU, D1/D7/D30 cohort retention, churn rate, **onboarding funnel tracking** (joined→welcomed→messaged→graduated). Daily snapshots to `metrics_daily` table. `!metrics` admin command. **Auto-alerts** in admin channel if D7 retention < 30% or DAU/MAU < 0.25. |
| Mega Events | `cogs/mega_events.py` | **Monthly mega events**: The Purge (no DR, 1.5x), Circle Games (2x social, 3x Quick Fire), Community Build (3x invites). One per month, 3-7 days. `active_event_multiplier` property for scoring. |
| Time Capsules | `cogs/time_capsules.py` | `!timecapsule <message>` sealed for 90 days, then revealed via DM + #general announcement. Max 3 per user. `!capsules` to view active capsules. |
| Keeper Personality | `cogs/keeper_personality.py` | **Ambient Keeper messages** 2-4x/day in #general. Contextual reactions to recent messages, cryptic observations, streak reminders. Makes bot feel alive at small scale. |
| Moderation | `cogs/moderation.py` | **3-layer anti-spam.** (1) @everyone/@here: delete + 5min timeout. (2) Mass mentions: 7+ pings = delete + 10min timeout. (3) Rapid mention spam: 4+ mention-messages in 60s = delete + 10min timeout. (4) Rate limit: 4+ msgs in 8s = 10min timeout. (5) Duplicate: 2+ similar in 60s = timeout. Scoring handler skips moderation-deleted msgs. `!purge @user [min]` and `!nuke [min]` — no time cap. Owner-only. |
| Bot Logger | `cogs/bot_logger.py` | **Observability & error logging.** Loaded FIRST. Global `on_command_error` handler, event listener error catching, background task crash monitor (auto-restart), cog load failure alerts, daily health summary (6 AM UTC), error-rate spike detection (10 errors in 5 min), buffered posting to #keeper-logs. `!logs` and `!errors` admin commands. |

---

## BOT COMMANDS

### User Commands
| Command | Cog | Description |
|---|---|---|
| `!rank` | leaderboard | See your rank, score, progress bar |
| `!top` | leaderboard | Top 10 leaderboard |
| `!stats @user` | leaderboard | View someone's stats |
| `!profile` | profiles | Full profile with bio, badges, faction, stats |
| `!streak` | streaks_v2 | All 5 streak types in one embed (alias: `!allstreaks`) |
| `!streaks` | streaks_v2 | Streak leaderboard by division (alias: `!streakboard`) |
| `!badges` | achievements | View your achievement badges |
| `!daily` | daily_rewards | Claim daily login reward |
| `!spin` | daily_wheel | Daily wheel spin (animated) |
| `!give @user <amt>` | economy | Send Circles to another user (10% tax, 500/day max) |
| `!balance` | economy | Check your Circles |
| `!shop` | shop | Browse items |
| `!buy <item>` | shop | Purchase an item |
| `!buyfreeze` | streaks_v2 | Buy streak freeze token (200 Circles) |
| `!friends` | social_graph | Top 5 connections by friendship score |
| `!bestfriend` / `!bf` | social_graph | Your #1 connection |
| `!rival @user` | social_graph | Declare a 4-week rivalry (50 Circles) |
| `!pairstreak @user` | streaks_v2 | Start a paired streak |
| `!acceptpair @user` | streaks_v2 | Accept a paired streak |
| `!circle create/invite/leave/info/leaderboard` | circles | Friend group management |
| `!confess <text>` | confessions | Anonymous confession (content-filtered, max 1000 chars) |
| `!report <number>` | confessions | Report a confession (3 reports = auto-delete) |
| `!submit prompt/hottake/trivia <text>` | content_engine | Submit user-generated content (20 Circles) |
| `!season` | season_pass | Current season info + your tier |
| `!season buy` | season_pass | Purchase premium pass (5000 Circles) |
| `!challenges` | season_pass | View active weekly/daily challenges |
| `!prestige` | prestige | View prestige info |
| `!prestige confirm` | prestige | Execute prestige (resets rank, keeps coins) |
| `!ladder` | engagement_ladder | Your engagement tier |
| `!goal` | server_goals | Weekly community goal progress |
| `!invites` | leaderboard | Invite leaderboard |
| `!voicetime` | voice_xp | Voice minutes stats |
| `!setbio <text>` | profiles | Set profile bio |
| `!setcolor <hex>` | profiles | Set profile accent color |
| `!help` | leaderboard | Full command reference |
| `!faction` | factions | Faction standings |
| `!oracle` | oracle | Today's Oracle prediction |
| `!timecapsule <msg>` | time_capsules | Seal a message for 90 days |
| `!capsules` | time_capsules | View your active time capsules |
| `!dms` / `!dms off` / `!dms on` | onboarding_v2 | Toggle bot DMs on/off. Every DM also has a 🔕 button. |

### Admin Commands
| Command | Cog | Description |
|---|---|---|
| `!admin` | leaderboard | List all admin commands in a single embed. Owner only. |
| `!setup` | setup_server | Creates all channels, categories, 100 rank roles + runs lockdown |
| `!lockdown` | setup_server | Strip mention_everyone from roles, hide #bot-commands/#keeper-logs, create AutoMod mention-spam rule |
| `!postinfo` | info | Posts guide embeds to #info |
| `!reset @user` | leaderboard | Reset a user's score + strip rank roles + assign Rookie I |
| `!setrank @user <tier>` | leaderboard | Set a user's rank + update Discord role to match |
| `!recap` | weekly_recap | Manually trigger weekly recap |
| `!debate start <topic>` | debates | Start a structured debate |
| `!approve <id>` / `!reject <id>` | content_engine | Approve/reject UGC submissions |
| `!healthcheck` / `!hc` | healthcheck | Run 23 system checks, show full diagnostic |
| `!cleanup` | setup_server | Fix orphaned channels, remove duplicate categories |
| `!purgeall` | setup_server | Delete ALL messages in ALL text channels (irreversible) |
| `!metrics` | metrics | Show retention dashboard (DAU/MAU, D1/D7/D30 retention) |
| `!fixroles` | leaderboard | Scan all members, ensure Discord role matches DB rank (fixes missing/stale roles) |
| `!purge @user [min]` | moderation | Delete all messages from a user in the last N minutes (default 30, no cap) |
| `!nuke [min]` | moderation | Delete all detected spam across all channels in the last N minutes (no cap) |
| `!logs [N]` | bot_logger | Show last N error entries (default 10, max 50). Owner only. |
| `!errors` | bot_logger | Show error frequency by category in current tracking period. Owner only. |

---

## ECONOMY SYSTEM

- **Currency:** Circles (emoji: 🪙)
- **Earning:** 1 Circle per scored message, daily login (10-500), wheel spin, event rewards, welcome-back gift (50-500 scaling with days absent)
- **Spending:** Shop items (50-200), streak freezes (200), Circle creation (200), rival declaration (50), UGC submission (20), premium season pass (5000)
- **Progressive Jackpot:** Builds 0.5 per message, 0.05% trigger chance, avg payout ~500-1000 Circles

---

## VARIABLE REWARD MECHANICS (Dopamine Engine)

| Mechanic | Trigger | Effect |
|---|---|---|
| Critical Hit | 2% per message | 2x points on that message |
| Near Miss | 1% per message (Regular+ only) | "Almost got a bonus!" message (auto-deletes) |
| Bonus Drop | 2% per message | Next message gets hidden 2-10x multiplier |
| Progressive Jackpot | 0.05% per message (0.1% at <100 members) | Win entire pot (avg 500-1000 Circles) |
| Surprise 2x Window | Random every 4-8 hours | 15-30 min server-wide double XP |
| Mystery Drop | Every 100 server messages | Random reward to the 100th sender |
| Daily Wheel | `!spin` once/day | Coins, XP boosts, streak freeze, or jackpot |
| Mystery Box | `!buy mystery_box` (150 Circles) | 10-item weighted loot table |

---

## SOCIAL GRAPH

- **Friendship Score:** `(replies * 3) + (mentions * 2) + (reactions * 1) + (voice_overlap * 0.5)`
- **Decay:** 5% weekly on zero-interaction pairs
- **Best Friends:** Mutual #1 detected every 6h, announced publicly
- **Rivals:** 4-week declared rivalry, weekly score comparison, winner gets 25 Circles
- **Icebreakers:** New members with < 3 connections get matched every 12h with Connection Quests
- **Circles:** Friend groups of 3-8, weekly competition, top Circle wins role color + coins

---

## DM COORDINATOR (Cross-Cog Rate Limiter)

All DM-sending cogs check `dm_coordinator.py` before sending:
- **Max 1 DM per 12 hours** from any cog (skipped for priority callers)
- **Max 3 DMs per 7 days** total across all cogs (5 for priority callers)
- **Priority mode:** `can_dm(user_id, cog, priority=True)` — used by `reengagement.py` to ensure anti-churn DMs aren't blocked
- Wired into: `onboarding_v2`, `reengagement` (priority), `loss_aversion`
- Welcome DM (T+5s) bypasses the coordinator — always goes through
- Auto-cleans entries older than 30 days

---

## WELCOME WAGON & CONVERSATION STARTER

### Welcome Wagon
- First 3 users who reply to a new member's first message get **+10 pts + 5 Circles**
- New member also gets **+5 pts** per welcome reply received
- New member = joined < 48h + score < 50
- Reply gets a 👋 reaction as visual feedback

### Conversation Starter
- If your message receives **3+ replies within 1 hour**, you get a retroactive **+25 pts + 10 Circles**
- Replies must be **3+ words** to count (prevents "." farming)
- Public announcement in channel: "CONVERSATION STARTER — @user's message sparked a discussion!"

---

## MONTHLY MEGA EVENTS

| Event | Week | Duration | Effect |
|---|---|---|---|
| The Purge | Week 1 | 3 days | No diminishing returns, 1.5x everything |
| The Circle Games | Week 2 | 5 days | Social multipliers 2x, Quick Fire 3x |
| Community Build | Week 3 | 7 days | Invite bonuses 3x, milestones halved |

- One event per month max
- `MegaEvents.active_event_multiplier` checked by scoring_handler
- Dramatic announcement + summary embeds

---

## TIME CAPSULES

- `!timecapsule <message>` — seal a message for 90 days (max 500 chars, max 3 per user)
- `!capsules` — view your active capsules and reveal dates
- Background task checks every 6h for capsules to reveal
- Reveal: DM to user with nostalgia embed + brief #general announcement

---

## ANTI-CHURN SYSTEMS

### Onboarding (7-Day Pipeline)
T+5s -> T+2hr -> T+4hr -> T+24h -> T+48h -> T+72h -> Day 6 -> Day 7 graduation

### Re-engagement (8-Tier, Day 1-60)
Day 1 server callout -> Day 2 DM -> Day 3 DM -> Day 5 DM -> Day 7 DM (5x window) -> Day 14 DM (3x, decay warning) -> Day 30 DM (2x, nostalgia) -> Day 60 final DM (1.5x, opt-out)
- Uses `priority=True` with DM coordinator to bypass 12h rate limit

### Loss Aversion
- Graduated decay: 0.5%/day at 30d -> 5%/day at 90d
- Rank demotion after 3 days below threshold
- Streak-at-risk DM at 10 PM UTC (streaks ≥7 only, max 1/day)
- Competitive displacement alerts (50+ members only)
- Faction relegation (80+ members only, last-place team loses channel for 24h)

---

## FACTION SYSTEM

4 teams: Inferno (red), Frost (blue), Venom (green), Volt (yellow)
- Unlock at rank 21 (Certified I, lowered from 31), permanent choice
- Weekly competition with 10% winner bonus
- Team channels, treasury system, loyalty scores
- Traitor mechanic: 1000 Circles to switch, public "BETRAYAL" announcement

---

## SEASONAL BATTLE PASS

- 8-week seasons, 50 tiers, 1-week off-season gap
- Season XP earned alongside regular scoring + challenge completions
- Free rewards every 5 tiers (coins, badges, banners, titles)
- Premium tier: 5000 Circles (earned currency only)
- 3 weekly challenges + 1 daily challenge (auto-tracked)
- Early bird: 2x Season XP for first 48 hours
- End-of-season: top 3 get Legend role + coins, top 25% get Veteran badge

---

## PRESTIGE SYSTEM (Endgame)

- Requires rank 41+ (Veteran I) to prestige
- Resets: score, rank, personal streaks
- Keeps: coins, achievements, faction, profile, buddy streaks
- 5 levels with permanent bonuses: +5% / +10% / +15% / +20% / +25% on all scoring
- Coin rewards: 2,000 / 5,000 / 10,000 / 20,000 / 50,000

---

## DATABASE TABLES (~56 total)

**Phase 1:** users, messages, daily_scores, rank_history, invites, streaks, achievements, voice_sessions, reactions_received

**Phase 2:** economy, shop_purchases, shop_rotating, confessions, starboard, factions, faction_scores, buddies, profiles, login_rewards, smart_dm_log, trivia_scores, invite_reminders_log, monthly_invite_race, server_milestones, weekly_goals, rank_tease_log, stagnation_log, engagement_trigger_log, introductions

**Phase 3:** jackpot, daily_spins, bonus_drops, demotion_watch, streak_freezes, displacement_log, onboarding_state, reengagement_state, streaks_v2, paired_streaks, social_graph, circles, circle_members, content_submissions, debate_scores, trending_topics, faction_wars, faction_territories, faction_treasury, faction_loyalty, seasons, season_progress, season_challenges, season_challenge_completions, season_rewards, prestige, user_engagement_tier, legacy_events, mod_reputation, combo_tracker, channel_diversity, kudos, rivals, time_capsules, active_boosts

**Audit Fix:** metrics_daily, oracle_log, connection_quests, quick_fire_log, quick_fire_replies, confession_reports

**Audit Fix 2:** dm_coordinator, mega_events, time_capsules

**Audit Fix 4 (2026-04-02):** social_streak_cache, coin_transfers

---

## OBSERVABILITY SYSTEM (Bot Logger)

The `cogs/bot_logger.py` cog provides comprehensive error logging and health monitoring, posting to the private `#keeper-logs` channel (owner-only, hidden from all users).

### Features
1. **Global command error handler** (`on_command_error`) — catches ALL command exceptions. User-facing errors get clean messages; internal errors get "Something went wrong" + full traceback in #keeper-logs.
2. **Event listener error handler** (`on_error`) — catches exceptions in `on_message`, `on_member_join`, etc.
3. **Background task crash monitor** — checks all `@tasks.loop` tasks every 5 min. Posts crash details + auto-restarts.
4. **Cog load failure alerts** — posts startup summary showing which cogs loaded/failed.
5. **Daily health summary** (6 AM UTC) — uptime, error count by category, cog status, task status, DB health, memory usage.
6. **Error spike detection** — if 10+ errors in 5 minutes, posts alert with most common error category.
7. **Buffered posting** — batches rapid errors into single embeds to avoid Discord rate limits.
8. **`!logs [N]`** — show last N errors (default 10, max 50). Owner only.
9. **`!errors`** — show error frequency by category. Owner only.

### Config Constants
- `LOGGER_CHANNEL = "keeper-logs"` — target channel
- `ERROR_SPIKE_THRESHOLD = 10` — errors to trigger spike alert
- `ERROR_SPIKE_WINDOW = 300` — 5-minute window
- `DAILY_SUMMARY_HOUR = 6` — UTC hour for daily summary
- `LOG_BUFFER_FLUSH_INTERVAL = 5` — seconds between flushes
- `LOG_MAX_BUFFER_SIZE = 10` — force-flush at this count
- `LOG_HISTORY_MAX = 500` — max in-memory error history

### Log Levels
- **ERROR** (red embed) — command failures, task crashes, event errors
- **WARNING** (yellow embed) — stopped tasks, non-critical issues
- **INFO** (blue embed) — startup summaries, task restarts

---

## FILE STRUCTURE
```
discord/
├── bot.py              -- Main entry, loads 48 extensions (47 active cogs + setup_server). bot_logger loaded FIRST. 3 cogs disabled: streaks, welcome, onboarding
├── config.py           -- All constants (~950 lines), scoring weights, engagement params, display titles, keeper personality
├── database.py         -- SQLite schema (~56 tables) + async CRUD helpers + migrations
├── scoring.py          -- 6-layer scoring engine (pure logic, no Discord deps)
├── ranks.py            -- 100 rank definitions + helpers
├── setup_server.py     -- !setup cog (creates channels, roles)
├── cogs/               -- 45 feature cogs
│   ├── __init__.py
│   ├── achievements.py
│   ├── auto_events.py
│   ├── bot_logger.py       -- NEW: Observability, error logging, health summaries → #keeper-logs
│   ├── buddy_system.py
│   ├── circles.py          -- NEW: Friend groups
│   ├── comeback.py
│   ├── confessions.py
│   ├── content_engine.py   -- NEW: Quick Fire, UGC, trending, dead zone
│   ├── daily_prompts.py
│   ├── daily_rewards.py
│   ├── daily_wheel.py      -- NEW: !spin mechanic
│   ├── debates.py          -- NEW: Structured debates + thermostat
│   ├── economy.py
│   ├── engagement_ladder.py -- NEW: Lurker-to-evangelist pipeline
│   ├── healthcheck.py      -- NEW: Self-test + !healthcheck (23 checks)
│   ├── engagement_triggers.py
│   ├── factions.py
│   ├── growth_nudges.py
│   ├── info.py
│   ├── introductions.py
│   ├── invite_reminders.py
│   ├── invites.py
│   ├── leaderboard.py
│   ├── loss_aversion.py    -- NEW: Decay, demotion, displacement
│   ├── metrics.py          -- NEW: Retention analytics dashboard
│   ├── media_feed.py
│   ├── oracle.py           -- NEW: Evening prediction ritual
│   ├── onboarding.py       -- DISABLED (superseded by onboarding_v2)
│   ├── onboarding_v2.py    -- SOLE welcome/onboarding handler (embed + DM + role + 7-day pipeline)
│   ├── prestige.py         -- NEW: Prestige system
│   ├── profiles.py
│   ├── reactions.py
│   ├── reengagement.py     -- NEW: 8-tier re-engagement
│   ├── scoring_handler.py  -- REWRITTEN: 6-layer engine integration
│   ├── season_pass.py      -- NEW: Battle pass
│   ├── server_goals.py
│   ├── shop.py             -- UPDATED: New mystery box loot table
│   ├── smart_dm.py         -- DISABLED (superseded by reengagement.py)
│   ├── social_graph.py     -- NEW: Friendship tracking, rivals
│   ├── starboard.py
│   ├── streaks.py
│   ├── streaks_v2.py       -- NEW: 5 streak types + freezes + pairs
│   ├── trivia.py
│   ├── variable_rewards.py -- NEW: Jackpot, crits, bonus drops
│   ├── voice_xp.py
│   ├── mega_events.py      -- NEW: Monthly mega events (The Purge, etc.)
│   ├── time_capsules.py    -- NEW: !timecapsule sealed 90 days
│   ├── keeper_personality.py -- NEW: Ambient Keeper personality messages
│   ├── weekly_recap.py     -- UPDATED: Personal highlight DMs
│   └── welcome.py          -- DISABLED (superseded by onboarding_v2)
├── dm_coordinator.py   -- NEW: Cross-cog DM rate limiter (1/12h, 3/7d)
├── deploy/             -- circle-bot.service (systemd)
├── prompts/            -- LLM prompts for engagement design
├── requirements.txt    -- discord.py, python-dotenv, aiosqlite
├── .env                -- Bot token + guild ID (not committed)
├── .gitignore
├── CLAUDE.md           -- THIS FILE (complete project context)
└── ENGAGEMENT_PLAN.md  -- Legacy plan (most features now built, see status below)
```

---

## ENGAGEMENT_PLAN.md STATUS

The original `ENGAGEMENT_PLAN.md` contained 17 planned features. Here is their current status:

| # | Feature | Status | Cog(s) |
|---|---------|--------|--------|
| 1 | Enhanced onboarding | **BUILT** (v1 + v2) | onboarding.py, onboarding_v2.py |
| 2 | Confessions | **BUILT** | confessions.py |
| 3 | Starboard / Hall of Fame | **BUILT** | starboard.py |
| 4 | Invite reminders | **BUILT** | invite_reminders.py |
| 5 | Rank teasers + stagnation nudges | **BUILT** | growth_nudges.py |
| 6 | Engagement triggers | **BUILT** | engagement_triggers.py |
| 7 | Economy system | **BUILT** | economy.py, shop.py |
| 8 | Auto-events calendar | **BUILT** | auto_events.py |
| 9 | Server-wide milestone goals | **BUILT** | server_goals.py |
| 10 | Member profiles | **BUILT** | profiles.py |
| 11 | Factions | **BUILT** | factions.py |
| 12 | Smart re-engagement DMs | **BUILT** (v2 only) | reengagement.py (smart_dm.py disabled) |
| 13 | Buddy/mentor system | **BUILT** | buddy_system.py |
| 14 | Daily login rewards | **BUILT** | daily_rewards.py |
| 15 | Third-party bots | **NOT STARTED** | N/A (add at 20+ members) |

**Beyond the original plan, Phase 3 added 15 entirely new systems:**
Variable rewards, daily wheel, loss aversion, streaks v2, social graph, circles, content engine, debates, season pass, prestige, engagement ladder, onboarding v2, unified re-engagement, oracle, metrics.

---

## KNOWN ISSUES / FUTURE WORK

1. ~~**Triple/double welcome + rank-up messages (2026-04-02):**~~ **FIXED** — Root cause: multiple bot instances (2 local Mac + 1 Pi) sharing same token. Killed local processes. Added DB-backed dedup to onboarding_v2. See Audit Fix 7.
2. ~~**Legacy cog overlap:**~~ **FIXED** — `streaks.py` disabled, `streaks_v2.py` commands renamed to `!streak`/`!streaks` (old names kept as aliases).
2. ~~**Legacy DM overlap:**~~ **FIXED** — `smart_dm.py` disabled, `reengagement.py` is the sole pipeline. Onboarding/re-engagement pipelines deduplicated.
3. **Factions warfare 2.0:** The plan includes territory control, treasury, loyalty, traitor mechanics. The current `factions.py` is basic. The config constants exist in `config.py` (FACTION_WAR_CHALLENGE_CYCLE, FACTION_TERRITORY_BONUS, etc.) but the cog hasn't been rewritten yet.
4. ~~**Enhanced weekly recap:**~~ **BUILT** — `weekly_recap.py` now posts a multi-embed "Sunday Ceremony" with stats overview, streak hall (daily + paired), social bonds (best friend pair + voice hours), and faction standings (conditional).
5. ~~**Enhanced profiles (partial):**~~ **PARTIALLY DONE** — Display titles auto-derived from achievements + prestige level shown in `!profile`. Legacy timeline and activity crown still not built.
6. ~~**Oracle system:**~~ **BUILT** — `cogs/oracle.py` posts daily at 9 PM UTC, 200+ templates, 7-day no-repeat, `!oracle` command.
7. ~~**Time capsules:**~~ **BUILT** — `cogs/time_capsules.py` implements `!timecapsule` and `!capsules`. 90-day seal, DM reveal + #general announcement.
8. **Hidden moderation layer:** Invisible reputation score (config exists: MOD_REPUTATION_*). Not yet implemented.
9. ~~**First-reply detection:**~~ **FIXED** — `parent_message_id` column added to messages table. `is_first_reply_to_message()` now does a real DB lookup instead of the 30% random heuristic. `log_message()` stores parent_message_id for replies.
10. ~~**XP boost not fully wired:**~~ **FIXED** — scoring_handler now checks `active_boosts` table AND `VariableRewards.is_double_xp` for surprise 2x windows. Season XP also wired (50% of message score). Variable rewards delegation (mystery drops) connected.

**Audit Fix 3 (2026-04-02) — 19 issues fixed across 8 files:**
- ~~**Comeback multiplier never applied:**~~ **FIXED** — `scoring_handler.py` now applies `comeback_mult` to `final_points` before DB write.
- ~~**Mega event multiplier not persisted:**~~ **FIXED** — Moved mega event multiplier before `update_user_score()` so it's saved to DB.
- ~~**Rivalry weekly scoring never incremented:**~~ **FIXED** — `social_graph.py` now tracks rival scores on every message and runs weekly winner check on Mondays.
- ~~**Displacement alert logic inverted:**~~ **FIXED** — Changed `position < new_position` to `position <= new_position` in `loss_aversion.py`.
- ~~**Weekly streak detection broken:**~~ **FIXED** — `streaks_v2.py` now queries `messages` table for distinct active days instead of broken `streaks_v2` query.
- ~~**Reengagement pipeline stuck on DM failure:**~~ **FIXED** — `reengagement.py` now advances tier even when DM send fails.
- ~~**Best friend announcements re-trigger on restart:**~~ **FIXED** — Persisted to `best_friend_announcements` DB table instead of in-memory set.
- ~~**Faction relegation unlock lost on restart:**~~ **FIXED** — Stored in `faction_relegation_unlock` DB table, checked on startup.
- ~~**Quick Fire cache lost on restart:**~~ **FIXED** — `content_engine.py` restores `_active_fires` from DB on ready.
- ~~**Social reply cache never cleaned:**~~ **FIXED** — `streaks_v2.py` cleans stale date keys in daily check.
- ~~**Demotion grace period gameable:**~~ **FIXED** — Uses `first_seen` timestamp; requires sustained recovery above threshold before clearing watch.
- ~~**UGC submissions no rate limit:**~~ **FIXED** — Max 3 submissions per 24 hours per user.
- ~~**Dead NUDGE_5M handler:**~~ **FIXED** — Removed from dispatcher and deleted method.
- ~~**'90% ahead' fabricated claim:**~~ **FIXED** — Replaced with honest copy.
- ~~**Unused BEST_FRIEND_REPLY_BONUS:**~~ **FIXED** — Removed.
- ~~**Icebreaker quest orphans:**~~ **FIXED** — Expired quests cleaned in matchmaking loop.
- ~~**Dead zone off-by-one:**~~ **FIXED** — Peak hours now correctly include 03:00 UTC.
- ~~**Challenge completion early return:**~~ **FIXED** — Multiple challenges can now complete per action.

**Audit Fix 4 (2026-04-02) — 16 improvements across 18 files:**
- ~~**Comeback multiplier double-applied:**~~ **FIXED** — `scoring.py` no longer applies 5.0x (was stacking with handler's tiered multiplier). Only handler applies tiered comeback.
- ~~**Comeback rewards long absence:**~~ **FIXED** — Inverted tiers: 5x (7-14d), 3x (15-29d), 2x (30-59d), 1.5x (60+). Fast returns rewarded most.
- ~~**Factions locked too deep:**~~ **FIXED** — Unlock lowered from rank 31 to 21 (Certified I). Accessible in ~3-4 weeks.
- ~~**Near-miss excludes new users:**~~ **FIXED** — Min rank lowered from 11 to 3. New users see jackpot teases.
- ~~**DM coordinator blocks re-engagement:**~~ **FIXED** — `can_dm()` now accepts `priority=True` (skips 12h check, 5/7d cap). Re-engagement uses priority.
- ~~**Voice AFK farming:**~~ **FIXED** — Require 2+ non-bot users in VC. 50% XP penalty if muted+deafened >10 min.
- ~~**Legacy streaks.py overlap:**~~ **FIXED** — Disabled old cog. V2 commands renamed: `!streak`, `!streaks`. Old names kept as aliases.
- ~~**Social streak cache lost on restart:**~~ **FIXED** — Persisted to `social_streak_cache` DB table. Restored on cog load.
- ~~**Bonus drop memory leak:**~~ **FIXED** — Added 30-min cleanup task. Drops expire after 1 hour.
- **NEW:** `!give @user <amount>` — Coin transfers with 10% tax, 500/day limit. New `coin_transfers` DB table.
- **NEW:** Keeper Personality cog — 2-4 ambient messages/day in #general. Contextual + random. Cold-start essential.
- **NEW:** Themed content days — Meme Monday, Wisdom Wednesday, Flex Friday, Social Saturday.
- **NEW:** Personal highlight DMs — Sunday recap sends personalized stats to active users.
- **NEW:** Event-exclusive badges — Participation badges awarded at end of mega events (Purge Survivor, Games Veteran, Community Builder).
- **NEW:** Enhanced profiles — Display titles auto-derived from achievements. Prestige level shown.
- **NEW:** Display title system — Config-driven title priority from event badges and milestone achievements.

**Audit Fix 5 (2026-04-02) — 8 fixes across 7 files:**
- ~~**Daily cap bypass by post-score multipliers:**~~ **FIXED** — Added `POST_SCORE_MULT_CAP = 10.0` (caps cumulative post-score multipliers at 10x). Re-enforces daily cap AFTER all multipliers applied. Previously a single message could earn 90,000+ pts.
- ~~**Stale re-engagement DM copy:**~~ **FIXED** — All 4 DM tiers updated to match inverted comeback curve: Day 7 → "5x", Day 14 → "3x", Day 30 → "2x", Day 60 → "1.5x".
- ~~**Conversation starter gameable:**~~ **FIXED** — Replies must be 3+ words to count toward the 3-reply threshold. Prevents single-character farming.
- ~~**Personal highlight DMs bypass coordinator:**~~ **FIXED** — `weekly_recap.py` now calls `record_dm()` after each personal DM so other cogs see it.
- ~~**Welcome wagon ignores new member:**~~ **FIXED** — New members now get +5 pts when someone welcomes them (replier still gets +10 pts + 5 coins).
- ~~**Content engine column bug:**~~ **FIXED** — `quick_fire_log` restore query changed from `started_at` to `posted_at` (matching actual table schema).
- **NEW:** Metrics alert system — If D7 retention < 30% or DAU/MAU < 0.25, auto-posts warning embed in admin/mod channel.
- **NEW:** Config constants: `POST_SCORE_MULT_CAP`, `METRICS_ALERT_D7_THRESHOLD`, `METRICS_ALERT_DAU_MAU_THRESHOLD`.

**Audit Fix 6 (2026-04-02) — Live user testing fixes, 12 issues across 12 files:**
- ~~**Double/triple welcome messages:**~~ **FIXED** — Disabled `welcome.py` and `onboarding.py`. `onboarding_v2.py` is now the SOLE handler for on_member_join (posts #welcome embed, assigns Rookie I role, sends quest DM). Member ID dedup added to prevent Discord double-firing events.
- ~~**Rank-up spam in #general:**~~ **FIXED** — Inline rank-up messages removed entirely. Rank-ups now post ONLY to #rank-ups channel, and ONLY at group boundaries (Rookie→Regular, Regular→Certified, etc. — every 10th tier). Sub-rank changes are silent.
- ~~**Ranks flying by too fast:**~~ **FIXED** — Raised minimum threshold gap from 1 to 50 pts per rank. Rookie II now requires 50 pts (was 11). Early ranks are linear (50 pts each) before transitioning to exponential at ~tier 17.
- ~~**10 database.py schema mismatches:**~~ **FIXED** — `database.py` and cog files had different column names for same tables (e.g., `current_count` vs `current_streak`). Aligned all schemas to match what cogs expect. Dropped and recreated affected tables: `streaks_v2`, `season_progress`, `circles`, `circle_members`, `content_submissions`, `trending_topics`, `demotion_watch`, `displacement_log`, `daily_spins`, `streak_freezes`, `active_boosts`, `quick_fire_log`, `quick_fire_replies`.
- ~~**get_or_create_user race condition:**~~ **FIXED** — Changed to `INSERT OR IGNORE` to handle concurrent calls from multiple cogs on member join.
- ~~**Duplicate leaderboard posts on restart:**~~ **FIXED** — Leaderboard now searches channel history for existing bot embed and edits it, instead of always posting new.
- ~~**Triple media feed posts:**~~ **FIXED** — Added message ID dedup set to media_feed.py. Same message can only be mirrored once.
- ~~**Double/triple scoring per message:**~~ **FIXED** — Added message ID dedup to scoring_handler. Discord can re-deliver on_message events; now only first delivery is scored.
- ~~**Achievements posting inline in channels:**~~ **FIXED** — Routed all achievement/badge announcements to new #achievements channel. Introduction rewards also route there.
- ~~**Quick Fire posting in random channels:**~~ **FIXED** — Quick Fire now always posts to #general instead of most-active channel. Prevents gym prompts in #politics etc.
- **NEW:** #achievements channel added to CHANNEL_STRUCTURE for badge/intro reward announcements.
- **IMPORTANT PATTERN:** Discord fires `on_member_join` and `on_message` events multiple times in some conditions. ALL cogs that respond to these events MUST implement message/member ID dedup to prevent duplicate bot output. Use in-memory sets with bounded size.

**Audit Fix 7 (2026-04-02) — Triple welcome & double rank-up messages:**
- ~~**Triple welcome messages persisting after all code dedup:**~~ **ROOT CAUSE FOUND** — Two local `python bot.py` processes were running on the Mac ALONGSIDE the Pi instance, all sharing the same bot token. Three bot instances = three responses to every event. The "📍 THE CHAMBERS" embed content that couldn't be found in any code was from an older/uncommitted local version. **FIX:** Killed local processes. Added DB-backed dedup to `onboarding_v2.py` (checks `onboarding_state` table before posting, survives restarts). In-memory dedup alone is insufficient because it's lost on bot restart.
- ~~**Double rank-up messages:**~~ **SAME ROOT CAUSE** — Multiple bot instances all firing scoring + rank-up logic for the same messages. Identical rank-up embeds posted 22ms apart.
- **CRITICAL LESSON:** NEVER run `python bot.py` locally while the Pi instance is running. Multiple instances with the same token will ALL receive and respond to every Discord event, causing duplicate messages, duplicate scoring, and duplicate DB writes. The Pi is the ONLY production instance.
- **Debugging approach that worked:** Decoded Discord message snowflake IDs to timestamps, fetched message content via Discord REST API to compare embeds, checked `ps aux` on both Mac and Pi to find rogue processes.
- **Dedup layers now in onboarding_v2:** (1) In-memory set for rapid Discord re-fires, (2) DB check via `get_onboarding_state()` for cross-restart persistence.
- ~~**Healthcheck false warning:**~~ **FIXED** — Removed disabled cogs (Streaks, Welcome, Onboarding) from expected list. Added missing Phase 3 cogs (MegaEvents, TimeCapsules, KeeperPersonality). Now 23/23 green.

**Audit Fix 8 (2026-04-03) — Spam incident, moderation system, admin lockdown:**
- **Spam incident:** Two users (Beamer, BIG DAWG) spammed hundreds of "@everyone AAAAAAA" messages across #general, #memes, #dating farming points. 549 spam messages deleted. Both users' scores reset to 0.
- **NEW: Moderation cog** (`cogs/moderation.py`) — Auto-deletes @everyone/@here from non-owner + 60s timeout. Rate limiter (7+ msgs/10s = delete + 5min timeout). Duplicate detector (4+ similar msgs/30s = delete + timeout). `!purge @user [min]` and `!nuke [min]` admin commands.
- **Admin lockdown:** ALL admin commands switched from `has_permissions(administrator=True)` to `@commands.is_owner()`. Only `BOT_OWNER_ID` (1170038287465971926, jack_rosely) can run admin commands. No other users, even with Discord admin perms.
- **DM opt-out:** Users can now `!dms off` or tap 🔕 button on any bot DM to stop all bot DMs. Persisted in `dm_optout` table.
- **Season tier spam:** Announcements reduced to every 10th tier only. XP curve steepened (base 150*1.065^t).
- **!postinfo idempotent:** Now purges existing bot messages before reposting.
- **Keeper personality:** 11 new ambient messages nudging users toward #info, !help, !rank, !daily, name colors.
- **98 custom emojis uploaded:** 50 animated + 48 static Pepe emojis. 2 static slots remaining.

**Audit Fix 9 (2026-04-03) — Comprehensive moderation overhaul, 3-layer mention protection:**
- **Spam incident:** User "employeeofthemonth" spammed mass-mentions (pinging every member individually) to bypass the @everyone filter. Key insight: deleting messages AFTER the fact doesn't stop Discord notifications — must prevent at the permission/AutoMod level.
- **NEW: 3-layer mention protection:**
  - **Layer 1 (Permissions):** `!lockdown` strips `mention_everyone` from all roles except owner's. Users physically cannot @everyone/@here.
  - **Layer 2 (Discord AutoMod):** `!lockdown` creates AutoMod rule blocking messages with 7+ mentions BEFORE they're sent (no notification fires). 10min timeout. Owner + bot exempt.
  - **Layer 3 (Bot moderation cog):** Mass mentions (7+), rapid mention spam (4+ mention-messages in 60s), rate limiting, duplicate detection. All with delete + timeout.
- **Scoring handler cross-check** — scoring_handler now checks `Moderation.deleted_message_ids` and skips any message already deleted by moderation.
- **NEW: `!lockdown` command** — Runs all 3 layers: strip mention perms, hide #bot-commands, create AutoMod rule. Also wired into `!setup`.
- **#bot-commands hidden** — Only visible to bot owner + bot. Admin commands like `!reset @user` won't notify the target or be visible to other users.
- **`!purge` and `!nuke` uncapped** — Removed 120-minute and 500-message-per-channel limits. Pass any number of minutes.
- **`!reset` now updates roles** — Strips all rank roles and assigns Rookie I. Previously only updated DB, leaving stale colored roles.
- **`!setrank` now updates roles** — Strips old rank role and assigns the new one to match.
- **Bot re-invited with expanded permissions** — Added Manage Server (for AutoMod) and Moderate Members (for timeouts). New permissions value: `1099780188272`.
- **Config constants:** `MOD_MASS_MENTION_LIMIT = 7`, `MOD_MASS_MENTION_TIMEOUT = 600`, `MOD_MENTION_SPAM_WINDOW = 60`, `MOD_MENTION_SPAM_COUNT = 4`.
- **Tailscale fallback:** When off home LAN (cellular), use Tailscale IP `100.107.165.3` instead of `192.168.10.177`.
- **Hall of Fame now counts unique users** — One user adding 5 emojis = 1 vote, not 5. Post author's own reactions excluded. Minimum threshold raised to 5 unique users at all server sizes.
- **Media feed auto-cleanup** — When any message with media is deleted (by mod, bot, or manually), its mirror in #media-feed is automatically deleted. Works for single and bulk deletes (`!purge`).

---

## CRITICAL: Standing Instructions for Every Session

### 0. NEVER Run the Bot Locally
**The bot runs on the Pi, not locally.** NEVER run `python bot.py` on the Mac while the Pi is running. Multiple instances with the same token = duplicate messages, duplicate scoring, data corruption. Check with `ps aux | grep bot.py` if in doubt. Kill any local processes before deploying.

### 1. Always Deploy to Raspberry Pi
**The bot runs on the Pi, not locally.** After ANY code changes:
1. Push all modified files via tar over SSH
2. Restart the circle-bot systemd service
3. Check logs to verify ALL 46 active cogs loaded successfully
4. If any cog fails to load, fix it before ending the session

### 2. ALWAYS Update Documentation + Commit + Push After EVERY Change
**This is mandatory and automatic — do NOT wait for the user to ask.**
After ANY code changes, BEFORE reporting completion:
1. Update **CLAUDE.md** — this file must always reflect the current state. A fresh chat should have 100% accurate context. Update cog descriptions, command tables, config values, audit fix entries, and any other affected sections.
2. Update **cogs/info.py** — if new user-facing features were added, update !postinfo embeds.
3. **Commit and push ALL changes** (code + docs) to GitHub. Every deploy must be followed by a commit+push.

### 3. Test After Deploy
- Check systemd status shows `active (running)`
- Check logs show all cogs loaded with checkmarks
- If there are errors, fix them immediately

### 4. Python Version Note
Pi runs Python 3.11. Local Mac runs Python 3.9. Always use `from __future__ import annotations` in new files.

### 5. Remind the User of Manual Steps
At end of every session where code changed:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 YOUR MANUAL TODO (after this session)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ Run !setup in Discord (creates new channels/roles)
□ Run !postinfo in Discord (refreshes #info guide)
□ Test new commands in #bot-commands
□ Check #welcome, #info, #leaderboard look correct
□ Bump on Disboard (https://disboard.org)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
