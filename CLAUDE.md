# The Circle — Discord Bot Project

## What This Is
A custom Discord bot called **"Keeper"** for a social server called **"The Circle"**. Built in Python (discord.py) with SQLite, deployed on a Raspberry Pi 5. Keeper is a scientifically-designed engagement machine with a 6-layer scoring engine, 100-tier rank progression, 46 feature cogs, variable reward psychology, social graph engineering, seasonal battle passes, and multi-dimensional anti-churn systems. ~17,000 lines of code.

**Target audience:** Mixed 18-35 demographic. Dark luxury branding. Gamified social community.

## Discord Links & IDs
- **Server Name:** The Circle
- **Guild/Server ID:** `1489120401098276896`
- **Bot Application ID:** `1489119042479329320`
- **Bot Name:** Keeper#4569
- **Bot Token:** Stored in `.env` file (never commit this)
- **Bot Invite URL:** `https://discord.com/oauth2/authorize?client_id=1489119042479329320&permissions=268560464&integration_type=0&scope=bot`
- **Developer Portal:** https://discord.com/developers/applications (search "Keeper")
- **Required Intents:** Message Content, Server Members, Presences (all enabled)
- **Bot Permissions:** Manage Roles, Manage Channels, Send Messages, Embed Links, Attach Files, Read Message History, Add Reactions, Manage Messages

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
- **Hosting:** Raspberry Pi 5
- **Bot Token:** stored in `.env` (not committed)
- **Total Cogs:** 46 (all loaded successfully)
- **Total DB Tables:** ~50

## Raspberry Pi Access
- **IP:** `192.168.10.177`
- **Username:** `pi5`
- **Password:** `insanebeef45`
- **Project Path:** `/home/pi5/discord/`
- **Service Name:** `circle-bot` (systemd, auto-starts on boot)
- **IMPORTANT:** Pi also runs Pi-hole for ad blocking -- don't touch anything outside ~/discord

### SSH Commands (copy-paste ready)
```bash
# Connect to Pi
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177

# Push ALL project files to Pi
tar czf - bot.py config.py database.py scoring.py ranks.py setup_server.py cogs/*.py | SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "cd ~/discord && tar xzf -"

# Restart Keeper
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S systemctl restart circle-bot"

# Check service status
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S systemctl status circle-bot"

# View logs (last 30 lines)
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S journalctl -u circle-bot --no-pager -n 30"

# View live logs (follow mode)
SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S journalctl -u circle-bot -f"

# Full deploy (push + restart + verify)
tar czf - bot.py config.py database.py scoring.py ranks.py setup_server.py cogs/*.py | SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "cd ~/discord && tar xzf -" && SSHPASS='insanebeef45' sshpass -e ssh -o PreferredAuthentications=password pi5@192.168.10.177 "echo 'insanebeef45' | sudo -S systemctl restart circle-bot 2>&1 && sleep 3 && echo 'insanebeef45' | sudo -S journalctl -u circle-bot --no-pager -n 10"
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
- Comeback: 3x (7-29d inactive), 5x (30-59d), 3x (60+d) + welcome-back coin gift
- Streak: 1.1x (3d) to 4.0x (365d)
- Catch-up: Rookie/Regular +40%, Certified/Respected +20%, Veteran/OG +10%
- Faction winner: 1.1x
- Prestige: +5% per level (max +25% at prestige 5)
- **Hard cap:** 20.0x max

### Layer 6: Dynamic Daily Cap
- Ranks 1-30: 500 pts/day | 31-60: 750 | 61-90: 1000 | 91-100: 1500

### Post-Score Integrations (all wired in scoring_handler.py)
- **Surprise 2x XP window:** If `VariableRewards.is_double_xp` is active, all points doubled
- **Personal XP boosts:** Checks `active_boosts` table for shop/wheel-granted multipliers
- **Season XP:** 50% of message score flows to `season_pass.add_season_xp()`
- **Variable rewards delegation:** Jackpot contribution + mystery drops via `variable_rewards.on_scored_message()`
- **Welcome-back gift:** Comeback users get 50-500 Circles scaling with days absent

### Anti-Spam
- 15s cooldown between scored messages
- 5 msgs in 10s = 5 min scoring pause
- Duplicate message detection (5 min window)

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

Score thresholds are exponential (RuneScape-style): Rookie I = 0, Immortal X ~ 2,000,000.

---

## CHANNEL STRUCTURE
```
📋 WELCOME & INFO -- #welcome (RO), #info (RO), #rules (RO), #announcements (RO)
💬 SOCIAL -- #general, #memes, #dating
🏋️ SERIOUS -- #politics, #work, #fitness
📊 MEDIA & STATS -- #media-feed (RO), #leaderboard (RO), #rank-ups (RO)
🎭 ENGAGEMENT -- #introductions, #confessions (RO), #confession-discussion, #hall-of-fame (RO)
⚔️ FACTIONS -- #faction-war (RO), #team-inferno, #team-frost, #team-venom, #team-volt
🤖 BOT -- #bot-commands
🌙 EXCLUSIVE -- #vip-lounge (Respected+), #after-hours (Veteran+, NO scoring)
```

Excluded from scoring: welcome, info, rules, announcements, media-feed, leaderboard, rank-ups, bot-commands, confessions, hall-of-fame, faction-war, after-hours.

---

## ALL 45 COGS

### Phase 1: Core (14 cogs)
| Cog | File | Purpose |
|---|---|---|
| Streaks | `cogs/streaks.py` | Original daily streak tracking (legacy, coexists with v2) |
| Achievements | `cogs/achievements.py` | 30+ one-time badge unlocks |
| Scoring Handler | `cogs/scoring_handler.py` | **6-layer scoring engine**, anti-spam, rank-ups, critical hits, bonus drops, 2x XP window integration, active boost integration, season XP, variable rewards delegation, **first-message instant feedback**, parent_message_id tracking |
| Leaderboard | `cogs/leaderboard.py` | Auto-updating hourly embed + !rank, !top, !stats |
| Media Feed | `cogs/media_feed.py` | Scrapes all channels for media -> mirrors to #media-feed |
| Welcome | `cogs/welcome.py` | Rich embed on member join |
| Invites | `cogs/invites.py` | Tracks who invited who, validates after 24h + 5 msgs |
| Comeback | `cogs/comeback.py` | Graduated decay (legacy decay logic) |
| Reactions | `cogs/reactions.py` | Points for receiving reactions |
| Voice XP | `cogs/voice_xp.py` | Points for time in voice channels + **voice co-presence** feeds social graph friendship scores |
| Daily Prompts | `cogs/daily_prompts.py` | Auto-posts discussion question daily at 6pm UTC (UGC-first, then config fallback) |
| Weekly Recap | `cogs/weekly_recap.py` | **Sunday Ceremony**: multi-embed weekly recap (stats + streaks + social bonds + faction standings) |
| Info | `cogs/info.py` | Posts guide embeds to #info via !postinfo |
| Setup | `setup_server.py` | Creates all channels, categories, 100 rank roles via !setup |

### Phase 2: Engagement (17 cogs)
| Cog | File | Purpose |
|---|---|---|
| Onboarding | `cogs/onboarding.py` | Basic DM on join + 24h check-in |
| Introductions | `cogs/introductions.py` | First intro = 50 pts + badge |
| Confessions | `cogs/confessions.py` | Anonymous posting, 6h cooldown, discussion channel, **content filtering** (regex blocklist, 1000 char max), `!report` command (3 reports = auto-delete) |
| Starboard | `cogs/starboard.py` | Hall of Fame, dynamic reaction thresholds |
| Invite Reminders | `cogs/invite_reminders.py` | 2-3x/week rotating templates + monthly race |
| Growth Nudges | `cogs/growth_nudges.py` | Rank teasers at 80% + stagnation nudges at 14 days |
| Engagement Triggers | `cogs/engagement_triggers.py` | Random tips, social proof, cliffhangers |
| Economy | `cogs/economy.py` | Circles currency (1 per scored message) |
| Shop | `cogs/shop.py` | 5 permanent items + **rotating daily shop** (3 limited-time items from pool of 8) + **mystery box** (10-item loot table with streak freezes, XP boosts, rank shields) |
| Auto Events | `cogs/auto_events.py` | 6-day event calendar (Mon-Sat) |
| Trivia | `cogs/trivia.py` | Tuesday auto-trivia, 20 questions |
| Server Goals | `cogs/server_goals.py` | Member milestones + weekly message targets |
| Profiles | `cogs/profiles.py` | Custom bio, color, banner via !profile |
| Factions | `cogs/factions.py` | 4 teams, unlock at rank 31, weekly competition |
| ~~Smart DM~~ | `cogs/smart_dm.py` | **DISABLED** — Superseded by `reengagement.py`. No longer loaded. |
| Buddy System | `cogs/buddy_system.py` | Mentor pairing, 10-msg goal in 48h |
| Daily Rewards | `cogs/daily_rewards.py` | Escalating login rewards, streak reset on miss |

### Phase 3: Ultimate Engagement Engine (15 cogs)
| Cog | File | Purpose |
|---|---|---|
| Onboarding v2 | `cogs/onboarding_v2.py` | **7-day staged pipeline**: T+5s quest DM (4 quests with endowed progress — joining counts as #1), T+2hr progress, T+4hr streak anchor, T+24h check-in, T+48h momentum, T+72h milestone tease, Day 6 report card (positive framing), Day 7 graduation ceremony + Survivor badge + 100 Circles. **Fallback:** posts in #general if DMs disabled. T+5min nudge removed (too aggressive). |
| Streaks v2 | `cogs/streaks_v2.py` | **5 streak types** (daily/weekly/social/voice/creative), freeze tokens, grace periods, paired streaks, division leaderboard |
| Re-engagement | `cogs/reengagement.py` | **8-tier unified pipeline**: Day 1 server callout, Day 2 loss aversion DM, Day 3 social proof, Day 5 competitive loss, Day 7 urgency, Day 14 active loss, Day 30 nostalgia, Day 60 closure (then opt-out) |
| Loss Aversion | `cogs/loss_aversion.py` | Graduated decay (0.5%-5%/day by inactivity length), **rank demotion** (3-day grace), streak-at-risk notifications (10 PM UTC, streaks ≥7 only, 1 DM/day), competitive displacement alerts (50+ members only), faction relegation (80+ members only) |
| Variable Rewards | `cogs/variable_rewards.py` | **Progressive jackpot** (0.05% trigger, pot builds 0.5/msg), surprise 2x XP windows (random 15-30 min every 4-8h), mystery drops every 100 server msgs, critical hits (2% chance = 2x), bonus drops (2% chance = 2-10x on next msg), near-miss messages (3%) |
| Daily Wheel | `cogs/daily_wheel.py` | `!spin` -- free once/day, animated reveal, 11 weighted segments (5-500 Circles, XP boosts, streak freeze, jackpot trigger) |
| Social Graph | `cogs/social_graph.py` | **Friendship score** tracking (replies*3 + mentions*2 + reactions*1 + voice*0.5), 5% weekly decay, `!friends` top 5, `!bestfriend` mutual detection, `!rival @user` 4-week rivalry, **icebreaker matchmaking** (finds lonely new members every 12h, creates Connection Quests) |
| Circles | `cogs/circles.py` | Friend groups (3-8 members), Certified+ rank required, 200 Circles to create, weekly Circle leaderboard, top Circle gets role color + 50 Circles/member |
| Content Engine | `cogs/content_engine.py` | **Quick Fire** rounds (3x/day random timing, first 5 replies get bonus), **dead zone detection** (45 min silence = auto-content), **UGC pipeline** (`!submit prompt/hottake/trivia`, admin approval, auto-approve after 3), **trending topics** (word frequency detection) |
| Debates | `cogs/debates.py` | `!debate start <topic>`, reaction voting, minority side gets 2x points, MVP Debater award, **safety thermostat** (heat > 15 = warning, > 25 = slow mode, > 35 = lock) |
| Season Pass | `cogs/season_pass.py` | **8-week seasons**, 50 tiers, exponential XP curve, free rewards every 5 tiers, premium tier (5000 Circles), weekly challenges (3/week) + daily challenges (1/day), early bird 2x for first 48h, end-of-season ceremony + rankings |
| Prestige | `cogs/prestige.py` | **Endgame reset** at rank 41+: reset score/rank, keep coins/badges/faction, earn permanent +5% per level (max +25% at prestige 5), 5 prestige levels with escalating coin rewards (2k-50k) |
| Engagement Ladder | `cogs/engagement_ladder.py` | Tracks user tiers: lurker -> newcomer -> casual -> regular -> power_user -> evangelist. Weekly recalculation, DMs on tier transitions, `!ladder` command |
| Health Check | `cogs/healthcheck.py` | Automated self-test: 23 checks (DB, tables, cogs, channels, categories, background tasks, scoring engine, config, data health, permissions). Runs every 6h + `!healthcheck` command |
| Oracle | `cogs/oracle.py` | Evening prediction ritual — Keeper's Oracle posts daily at 9 PM UTC with cryptic predictions. 200+ templates, 7-day no-repeat. `!oracle` command |
| Metrics | `cogs/metrics.py` | Retention analytics dashboard — DAU/MAU, D1/D7/D30 cohort retention, churn rate, **onboarding funnel tracking** (joined→welcomed→messaged→graduated). Daily snapshots to `metrics_daily` table. `!metrics` admin command |

---

## BOT COMMANDS

### User Commands
| Command | Cog | Description |
|---|---|---|
| `!rank` | leaderboard | See your rank, score, progress bar |
| `!top` | leaderboard | Top 10 leaderboard |
| `!stats @user` | leaderboard | View someone's stats |
| `!profile` | profiles | Full profile with bio, badges, faction, stats |
| `!streak` | streaks | Daily streak info |
| `!allstreaks` | streaks_v2 | All 5 streak types in one embed |
| `!streakboard` | streaks_v2 | Streak leaderboard by division |
| `!badges` | achievements | View your achievement badges |
| `!daily` | daily_rewards | Claim daily login reward |
| `!spin` | daily_wheel | Daily wheel spin (animated) |
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

### Admin Commands
| Command | Cog | Description |
|---|---|---|
| `!setup` | setup_server | Creates all channels, categories, 100 rank roles |
| `!postinfo` | info | Posts guide embeds to #info |
| `!reset @user` | leaderboard | Reset a user's score |
| `!setrank @user <tier>` | leaderboard | Set a user's rank |
| `!recap` | weekly_recap | Manually trigger weekly recap |
| `!debate start <topic>` | debates | Start a structured debate |
| `!approve <id>` / `!reject <id>` | content_engine | Approve/reject UGC submissions |
| `!healthcheck` / `!hc` | healthcheck | Run 23 system checks, show full diagnostic |
| `!cleanup` | setup_server | Fix orphaned channels, remove duplicate categories |
| `!purgeall` | setup_server | Delete ALL messages in ALL text channels (irreversible) |
| `!metrics` | metrics | Show retention dashboard (DAU/MAU, D1/D7/D30 retention) |

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
| Progressive Jackpot | 0.05% per message (min pot 100) | Win entire pot (avg 500-1000 Circles) |
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

## ANTI-CHURN SYSTEMS

### Onboarding (7-Day Pipeline)
T+5s -> T+2hr -> T+4hr -> T+24h -> T+48h -> T+72h -> Day 6 -> Day 7 graduation

### Re-engagement (8-Tier, Day 1-60)
Day 1 server callout -> Day 2 DM -> Day 3 DM -> Day 5 DM -> Day 7 DM -> Day 14 DM -> Day 30 DM -> Day 60 final DM

### Loss Aversion
- Graduated decay: 0.5%/day at 30d -> 5%/day at 90d
- Rank demotion after 3 days below threshold
- Streak-at-risk DM at 10 PM UTC (streaks ≥7 only, max 1/day)
- Competitive displacement alerts (50+ members only)
- Faction relegation (80+ members only, last-place team loses channel for 24h)

---

## FACTION SYSTEM

4 teams: Inferno (red), Frost (blue), Venom (green), Volt (yellow)
- Unlock at rank 31 (Respected I), permanent choice
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

## DATABASE TABLES (~55 total)

**Phase 1:** users, messages, daily_scores, rank_history, invites, streaks, achievements, voice_sessions, reactions_received

**Phase 2:** economy, shop_purchases, shop_rotating, confessions, starboard, factions, faction_scores, buddies, profiles, login_rewards, smart_dm_log, trivia_scores, invite_reminders_log, monthly_invite_race, server_milestones, weekly_goals, rank_tease_log, stagnation_log, engagement_trigger_log, introductions

**Phase 3:** jackpot, daily_spins, bonus_drops, demotion_watch, streak_freezes, displacement_log, onboarding_state, reengagement_state, streaks_v2, paired_streaks, social_graph, circles, circle_members, content_submissions, debate_scores, trending_topics, faction_wars, faction_territories, faction_treasury, faction_loyalty, seasons, season_progress, season_challenges, season_challenge_completions, season_rewards, prestige, user_engagement_tier, legacy_events, mod_reputation, combo_tracker, channel_diversity, kudos, rivals, time_capsules, active_boosts

**Audit Fix:** metrics_daily, oracle_log, connection_quests, quick_fire_log, quick_fire_replies, confession_reports

---

## FILE STRUCTURE
```
discord/
├── bot.py              -- Main entry, loads 45 cogs
├── config.py           -- All constants (~800 lines), scoring weights, engagement params
├── database.py         -- SQLite schema (~50 tables) + async CRUD helpers
├── scoring.py          -- 6-layer scoring engine (pure logic, no Discord deps)
├── ranks.py            -- 100 rank definitions + helpers
├── setup_server.py     -- !setup cog (creates channels, roles)
├── cogs/               -- 44 feature cogs
│   ├── __init__.py
│   ├── achievements.py
│   ├── auto_events.py
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
│   ├── onboarding.py
│   ├── onboarding_v2.py    -- NEW: 7-day staged pipeline
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
│   ├── weekly_recap.py
│   └── welcome.py
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

1. **Legacy cog overlap:** `streaks.py` + `streaks_v2.py` coexist (v2 commands renamed to `!allstreaks`/`!streakboard`). Eventually remove old `streaks.py` and rename v2 commands back.
2. ~~**Legacy DM overlap:**~~ **FIXED** — `smart_dm.py` disabled, `reengagement.py` is the sole pipeline. Onboarding/re-engagement pipelines deduplicated.
3. **Factions warfare 2.0:** The plan includes territory control, treasury, loyalty, traitor mechanics. The current `factions.py` is basic. The config constants exist in `config.py` (FACTION_WAR_CHALLENGE_CYCLE, FACTION_TERRITORY_BONUS, etc.) but the cog hasn't been rewritten yet.
4. ~~**Enhanced weekly recap:**~~ **BUILT** — `weekly_recap.py` now posts a multi-embed "Sunday Ceremony" with stats overview, streak hall (daily + paired), social bonds (best friend pair + voice hours), and faction standings (conditional).
5. **Enhanced profiles:** Plan calls for display titles, legacy timeline, activity crown. Config exists (DISPLAY_TITLES, RANK_PERKS) but not wired into profiles.py.
6. ~~**Oracle system:**~~ **BUILT** — `cogs/oracle.py` posts daily at 9 PM UTC, 200+ templates, 7-day no-repeat, `!oracle` command.
7. **Time capsules:** Quarterly `!timecapsule <message>` with reveal 3 months later. Table exists, cog not built.
8. **Hidden moderation layer:** Invisible reputation score (config exists: MOD_REPUTATION_*). Not yet implemented.
9. ~~**First-reply detection:**~~ **FIXED** — `parent_message_id` column added to messages table. `is_first_reply_to_message()` now does a real DB lookup instead of the 30% random heuristic. `log_message()` stores parent_message_id for replies.
10. ~~**XP boost not fully wired:**~~ **FIXED** — scoring_handler now checks `active_boosts` table AND `VariableRewards.is_double_xp` for surprise 2x windows. Season XP also wired (50% of message score). Variable rewards delegation (mystery drops) connected.

---

## CRITICAL: Standing Instructions for Every Session

### 1. Always Deploy to Raspberry Pi
**The bot runs on the Pi, not locally.** After ANY code changes:
1. Push all modified files via tar over SSH
2. Restart the circle-bot systemd service
3. Check logs to verify ALL 46 cogs loaded successfully
4. If any cog fails to load, fix it before ending the session

### 2. Keep Documentation Updated
After making changes, update:
- **CLAUDE.md** -- This file. A fresh chat should have 100% accurate context.
- **cogs/info.py** -- If new user-facing features were added, update !postinfo embeds.

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
