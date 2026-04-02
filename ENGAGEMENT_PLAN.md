# The Circle — Ultimate Engagement Overhaul Plan

> **STATUS (April 2026):** This plan is largely COMPLETE. All 15 original features have been built,
> plus 13 additional Phase 3 systems (variable rewards, social graph, battle pass, prestige, etc.).
> See **CLAUDE.md** for the authoritative, up-to-date documentation of everything that exists.
> This file is kept for historical reference of the original plan.

## Goal
Make The Circle the most addictive, visually polished, and engagement-optimized Discord server possible. Minimize churn, maximize LTV, automate everything.

---

## PHASE 1: Visual Branding (First Impressions)
**Why:** You never get a second chance at a first impression. Server icon and banner are the first thing people see on listing sites.

### Tasks:
1. **Server Icon** — Glowing circle/ring on dark `#1a1a2e` background with `#e94560` red glow. Clean, premium, recognizable at small sizes.
2. **Server Banner** — Wide dark gradient, "THE CIRCLE" in clean sans-serif, subtle ring motif, particle/ember effects. 960×540px.
3. **Custom Emoji Set (30+)** — Branded emoji for ranks, teams, badges, reactions:
   - Rank emojis: `:rookie:` `:regular:` `:certified:` `:respected:` `:veteran:` `:og:` `:elite:` `:legend:` `:icon:` `:immortal:`
   - Team emojis: `:inferno:` `:frost:` `:venom:` `:volt:`
   - Engagement emojis: `:streak:` `:levelup:` `:coins:` `:badge:` `:fire:` `:crown:`
   - Reaction emojis: `:upvote:` `:downvote:` `:goat:` `:W:` `:L:`
4. **Channel Icons** — Use emoji in channel names for visual hierarchy (already done in categories)
5. **Role Icons** — Premium feature (requires server boost level 2) — assign icons to each rank group

### How to create assets:
- Use Canva Pro or Midjourney for icon/banner
- Use emoji.gg or custom pixel art for emoji set
- Match ALL colors to the `#1a1a2e` / `#e94560` palette

---

## PHASE 2: Enhanced Onboarding (First 5 Minutes)
**Why:** 70% of Discord churn happens in the first 24 hours. The onboarding must be frictionless and immediately rewarding.

### New Member Flow:
```
0:00 → Joins server
0:01 → Welcome embed in #welcome (already built)
0:02 → Keeper DMs: personal welcome + server guide + "reply with your interests"
0:03 → Reaction role selection in #pick-your-roles (interests + notifications)
0:05 → Prompted to post intro in #introductions (50 pts + badge)
0:10 → Auto-sorted as Rookie I, first achievement unlocked ("First Words")
1:00 → Buddy assigned (active Certified+ member DM'd to welcome them)
24:00 → Keeper DM: "How's your first day? Here's what you missed..."
```

### New Channels:
- **#pick-your-roles** — Reaction roles for interests (fitness, gaming, memes, dating, politics, work) + notification preferences
- **#introductions** — Incentivized intro posts (50 pts + "Introduced" badge + template from Keeper)

### New Cogs:
- **`cogs/onboarding.py`** — DM guide on join, reaction role setup, 24h check-in DM
- **`cogs/buddy_system.py`** — Auto-pairs new members with active Certified+ mentors, tracks if mentee sends 10 msgs, awards both 50 pts + "Mentor" badge
- **`cogs/introductions.py`** — Monitors #introductions, awards 50 pts on first post, unlocks badge

---

## PHASE 3: Economy System (Coins + Shop)
**Why:** Virtual currency creates a secondary motivation loop. People grind not just for rank but for purchasing power.

### Currency: "Circles" (🪙)
Earned passively alongside score points:
- Every scored message: +1 Circle
- Daily login: +10-50 Circles (escalating)
- Streak milestones: bonus Circles
- Mystery box rewards
- Achievement unlocks: bonus Circles

### Shop (`!shop`):
**Permanent Stock:**
| Item | Cost | Description |
|---|---|---|
| Custom nickname color | 100 🪙 | Pick any hex color for your name |
| Nickname change | 50 🪙 | Change your server nickname |
| XP Boost (2x for 1hr) | 75 🪙 | Double all points for 60 min |
| Mystery Box | 150 🪙 | Random: coins, XP boost, temp role, or rare badge |
| Profile banner | 200 🪙 | Custom banner on your !profile |

**Weekly Rotating (3-day availability):**
- Exclusive role colors that aren't available in the rank system
- Animated name effects (if server has boosts)
- "VIP" temp role (access to hidden #vip-lounge for 7 days)

**Monthly Exclusive (limited quantity):**
- Crown role (👑 next to name) — only 3 available/month — 1000 🪙
- Custom emoji submission — your emoji added to the server — 2000 🪙

### New Cogs:
- **`cogs/economy.py`** — Currency tracking, earning, spending
- **`cogs/shop.py`** — Shop UI, purchasing, rotating stock, mystery boxes
- **`cogs/daily_rewards.py`** — Enhanced login rewards: Day 1→10→25→50→150→mystery box→rare role→500+badge

---

## PHASE 4: Confessions Channel
**Why:** Anonymous posting creates drama, curiosity, and "I can't look away" energy. One of the stickiest features on any Discord server.

### How it works:
- Members DM Keeper: `!confess I secretly hate pineapple on pizza`
- OR use `/confess` slash command in any channel (message auto-deleted)
- Keeper posts in **#confessions** (read-only) as anonymous numbered entry
- Separate **#confession-discussion** channel for reactions and debate
- Confessions get 🔥 😂 😱 reactions automatically added by Keeper
- Weekly "Confession of the Week" — most-reacted confession gets highlighted

### Anti-abuse:
- Cooldown: 1 confession per user per 6 hours
- Admin can trace confessions if needed (stored in DB with user_id, hidden from public)
- Word filter for slurs/harassment

### New Cog:
- **`cogs/confessions.py`**

---

## PHASE 5: Starboard / Hall of Fame
**Why:** Everyone wants to be featured. This rewards quality content and gives people goals beyond just messaging volume.

### Dynamic threshold:
- Under 50 members: **3 reactions** to get featured
- 50-200 members: **5 reactions**
- 200-1000 members: **10 reactions**
- 1000+: **15 reactions**

### #hall-of-fame channel:
- Read-only, auto-populated
- Keeper reposts the message as a beautiful embed with the original content, author, reaction count, and source channel
- Monthly "Hall of Fame Champions" — top 3 most-reacted posts of the month

### New Cog:
- **`cogs/starboard.py`**

---

## PHASE 6: Teams / Factions (Unlock at Respected — Rank 31)
**Why:** Tribal loyalty is the strongest retention mechanic in gaming and communities. Once someone identifies with a team, leaving = betraying their team.

### 4 Teams:
| Team | Color | Emoji | Motto |
|---|---|---|---|
| 🔴 Inferno | Red | `:inferno:` | "Burn bright." |
| 🔵 Frost | Blue | `:frost:` | "Stay cold." |
| 🟢 Venom | Green | `:venom:` | "Strike silent." |
| 🟡 Volt | Yellow | `:volt:` | "Stay charged." |

### How it works:
- Unlocks when you reach **Respected I (Rank 31)**
- Keeper announces: "You've proven yourself. Choose your allegiance."
- Pick via reaction in a DM from Keeper (one-time, permanent choice)
- Each team gets:
  - **Private team channel** (strategy, coordination)
  - **Team role** with accent color
  - **Team leaderboard** (sum of all members' weekly scores)
  - **Weekly winning team** gets 10% bonus points for the next week

### New Channels:
- **#team-inferno** (private)
- **#team-frost** (private)
- **#team-venom** (private)
- **#team-volt** (private)
- **#faction-war** (public — shows team standings)

### New Cog:
- **`cogs/factions.py`**

---

## PHASE 7: Full Auto-Event Calendar
**Why:** Automated events solve the "empty server" problem. There's always something happening without admin effort.

### Weekly Schedule:
| Day | Event | Channel | Description |
|---|---|---|---|
| Monday | 💪 Motivation Monday | #fitness, #work | Keeper posts workout/career prompt |
| Tuesday | 🧠 Trivia Tuesday | #general | 10 auto-posted trivia questions, first correct answer wins pts |
| Wednesday | 🔮 Confession Wednesday | #confessions | Keeper reminds members to submit confessions |
| Thursday | 🔥 Hot Take Thursday | #politics, #general | Keeper posts controversial poll, most engaging take wins |
| Friday | 😂 Meme Friday | #memes | Best meme competition — most reactions wins. Winner gets "Meme Lord" role for a week |
| Saturday | 🎤 VC Saturday | voice channels | Keeper pings: "Voice channels are open. Pull up." |
| Sunday | 📊 Weekly Recap | #general | Already built — enhanced with team standings and event winners |

### New Cog:
- **`cogs/auto_events.py`** — Replaces/enhances daily_prompts with full calendar
- **`cogs/trivia.py`** — Auto trivia with question bank, scoring, leaderboard

---

## PHASE 8: Member Profiles (!profile)
**Why:** Investment in a profile = investment in staying. The more customized your identity, the harder it is to leave.

### Profile Command:
```
!profile @user
```
Shows: Avatar, rank, score, team, streak, coins, badges (with emoji), bio, voice time, invite count, join date, top channels, progress bar.

### Customization:
- `!setbio <text>` — Set your profile bio (max 100 chars)
- `!setcolor <hex>` — Set profile accent color (costs 100 Circles)
- `!setbanner <url>` — Set profile banner image (costs 200 Circles)

### New Cog:
- **`cogs/profiles.py`**

---

## PHASE 9: Smart Re-engagement DMs
**Why:** Generic "come back" messages get ignored. Personalized ones that reference what the member cares about actually work.

### Logic:
- Track each user's top 3 channels by message count
- Track their friends (people they reply to / tag most)

### DM Tiers:
| Inactive Days | DM Content |
|---|---|
| 3 days | "🔥 Your {streak}-day streak is about to end. One message saves it." |
| 7 days | "The Circle misses you. #{top_channel} has been going off — {X} messages about {topic}. @{friend} asked about you. Come back for 5x bonus." |
| 14 days | "Your rank is decaying. You've dropped from {old_rank} to {new_rank}. Return now before you lose more." |
| 30 days | Final DM: "The Circle is moving on. Your {rank} status won't last forever." |

### Rules:
- Max 1 DM per week per user
- Never DM someone who has DMs disabled (graceful fail)
- Track DM send dates to prevent spam

### Enhancement to:
- **`cogs/comeback.py`** — Major rewrite with personalized logic

---

## PHASE 10: Third-Party Bots
**Why:** Some features are better handled by established bots with years of polish.

### Add these bots:
1. **Mudae** — Character collecting game. People check in HOURLY to roll for characters. One of the stickiest bots on Discord. Creates its own economy and trading.
2. **Wick** — Anti-raid protection + verification system. Essential as server grows. Prevents bot raids.
3. **Tatsu** — Beautiful visual rank cards. Complements our scoring with gorgeous !rank images.

### New Channels:
- **#mudae** — For character rolling (keeps it contained)
- **#bot-games** — General bot game channel

---

## PHASE 11: Buddy/Mentor System
**Why:** A human connection in the first hour is the #1 predictor of whether someone stays.

### How it works:
1. New member joins
2. Keeper selects a random online member who is Certified+ rank and was active in last 48h
3. Keeper DMs the buddy: "A new soul has entered. @NewUser is yours to guide. Help them send 10 messages within 48h and you both earn 50 pts + Mentor badge."
4. Keeper DMs new member: "@Buddy has been assigned as your guide in The Circle. Say hi!"
5. If new member sends 10+ messages within 48h: both get 50 pts, buddy gets "Mentor" badge (first time) or "Mentor" counter incremented

### New Cog:
- **`cogs/buddy_system.py`**

---

## Implementation Order (Priority)
1. **Visual branding** (icon, banner, emoji) — immediate, non-code
2. **Enhanced onboarding** (DM flow, #introductions, #pick-your-roles) — highest impact on churn
3. **Confessions** — instant engagement magnet
4. **Starboard** — encourages quality + reactions
5. **Economy + Shop** — secondary motivation loop
6. **Auto-events calendar** — fills dead air automatically
7. **Profiles** — deepens identity investment
8. **Factions** — long-term tribal retention
9. **Smart DMs** — reduces churn for established members
10. **Buddy system** — requires enough active members to work
11. **Third-party bots** — add once server has 20+ members
12. **Daily login rewards** — enhancement to economy

---

## New File Structure (additions)
```
cogs/
├── (existing 12 cogs)
├── onboarding.py       # Enhanced welcome DM flow + 24h check-in
├── introductions.py    # #introductions channel + incentives
├── buddy_system.py     # Auto-pair new members with mentors
├── confessions.py      # Anonymous confession system
├── starboard.py        # Hall of fame auto-posting
├── economy.py          # Currency (Circles) tracking
├── shop.py             # Shop UI + rotating stock + mystery boxes
├── daily_rewards.py    # Enhanced login rewards beyond streaks
├── factions.py         # 4 teams, team channels, weekly competition
├── auto_events.py      # Full weekly event calendar
├── trivia.py           # Auto trivia game
├── profiles.py         # Rich member profiles + customization
└── smart_dm.py         # Personalized re-engagement DMs
```

## PHASE 12: Growth Engine — Invite Reminders & Recruitment
**Why:** Organic growth is the lifeblood of any server. Members won't invite people unless you constantly remind them AND make it effortless.

### Smart Invite Reminders (2-3x/week, rotating templates)
Keeper posts in #general with a **one-click invite link** and varied messaging:

**20+ rotating templates (never the same twice in a row):**
- "📨 Know someone who'd fit in? Share The Circle: `discord.gg/XXXXXX` — You earn 25 pts per invite."
- "📈 The Circle is growing. {member_count} members and climbing. Bring 1 friend = 25 pts. Bring 5 = Talent Scout badge. `discord.gg/XXXXXX`"
- "🏆 This week's top recruiter: @{top_inviter} with {count} invites. Can you beat that? `discord.gg/XXXXXX`"
- "💡 Did you know? Every friend you bring earns you 25 points. That's almost a full rank level. `discord.gg/XXXXXX`"
- "🔥 {count} people joined this week. The Circle is getting louder. Help it grow: `discord.gg/XXXXXX`"
- "📨 Your invite link is your secret weapon. Share it → they join → you earn 25 pts → they earn points → everyone wins."
- "🏅 Invite milestones: 1 invite = Recruiter badge. 5 = Talent Scout. 25 = Ambassador. Where are you? `discord.gg/XXXXXX`"

### Invite Link Management:
- Keeper auto-generates a permanent server invite link on startup
- Stores it in config so it's always the same link in every reminder
- Admins can update via `!setinvite <url>`

### Monthly Recruiter Race:
- Keeper announces on the 1st of each month
- Weekly progress updates with standings
- End of month: Top inviter gets exclusive "Top Recruiter" role + 500 coins + featured on leaderboard + badge (first win)
- Resets monthly

### New Cog:
- **`cogs/invite_reminders.py`** — Rotating reminders, monthly competition, auto-link

---

## PHASE 13: Rank Teasers & Stagnation Nudges
**Why:** People quit when they can't see what's next. Teasers create anticipation. Nudges prevent stalling.

### Rank Teasers (within 20% of next tier group):
After a scored message, Keeper occasionally whispers:
```
👀 You're 200 pts from Certified. Here's what's waiting:

 🔵 Blue name color
 🏅 3 new badges available
 💬 New tagline: "Your mom would be worried."
 💰 50 coin bonus on arrival

 Keep pushing.
```

**Special teasers for major unlocks:**
- Approaching Respected (31): "🔓 FACTION ACCESS is 340 pts away. Choose your allegiance: Inferno / Frost / Venom / Volt"
- Approaching any new tier group: Preview the color, tagline, and any new perks

**Rules:**
- Max 1 teaser per user per 3 days (not spammy)
- Only shows after THEIR message (feels natural)
- Only at tier group boundaries (every 10 ranks)

### Stagnation Nudges (14+ days same rank):
After their message, Keeper posts a motivating nudge:
```
💭 @Mike, you've been Regular IV for 2 weeks.
You're only 340 pts from Regular V.

Quick wins:
 • Reply to 3 people (3x pts each)
 • Post a meme with a tag
 • Drop into voice for 30 min

The next rank is right there.
```

**Rules:**
- Max once per 14 days per user
- Only shows after THEIR message
- Never shaming, always motivating
- Includes actionable tips

### New Cog:
- **`cogs/growth_nudges.py`** — Rank teasers + stagnation nudges

---

## PHASE 14: Server-Wide Milestone Goals
**Why:** Collective goals create shared purpose. When the whole server benefits, everyone recruits and engages harder.

### Member Milestones:
| Members | Reward |
|---|---|
| 25 | Everyone gets 50 🪙 |
| 50 | 24h double XP for all |
| 100 | Mystery box for every member |
| 250 | New exclusive channel unlocked (e.g., #vip-lounge) |
| 500 | Community emoji vote — members submit, top 5 get added |
| 1,000 | Server-wide event + exclusive "Day One" badge for current members |

### Weekly Community Goals:
Keeper posts Monday:
```
📊 THIS WEEK'S COMMUNITY GOAL
━━━━━━━━━━━━━━━━━━━━━

Target: 5,000 total messages this week
Reward: 2x points weekend for EVERYONE

Progress: ██████░░░░ 62% (3,100 / 5,000)

Every message counts. Tag a friend.
```

Daily progress updates. If goal is hit, Keeper announces and activates the reward.

### New Cog:
- **`cogs/server_goals.py`** — Member milestones, weekly goals, progress tracking, reward distribution

---

## PHASE 15: YouTube-Style Psychological Triggers
**Why:** Every major platform uses these. They work because they tap into fundamental human psychology.

### Cliffhangers (build anticipation):
- "Tomorrow's daily prompt is going to be WILD. 👀"
- "Confession Wednesday starts in 6 hours. Get yours ready."
- "This week's Meme Friday theme will be announced at noon..."
- "A special announcement is coming to The Circle tonight. Stay tuned."

### Social Proof (show others are active):
- "12 members ranked up this week. Did you?"
- "47 confessions submitted this month. The Circle has no secrets."
- "@Sarah just hit a 30-day streak. Only 4 people have done that."
- "23 people were in voice channels this weekend."
- "{X} messages were sent in The Circle today. You were part of {Y} of them."

### Loss Aversion (fear of missing out/losing progress):
- "You're 50 pts from Regular. Don't stop now."
- "Your streak ends at midnight. One message saves it."
- "Your rank is decaying. You've dropped from Veteran III to Veteran II."
- "The weekly shop resets in 12 hours. Midnight Purple is almost gone."
- "Only 2 Crown roles left this month. 1,000 coins."

### Countdowns (create urgency):
- "Meme Friday starts in 3 hours. Get your best memes ready."
- "Trivia Tuesday begins in 1 hour. Study up."
- "Monthly recruiter race ends in 3 days. @Mike leads with 7 invites."

### Public Celebrations (make success visible):
- "🎉 THE CIRCLE HITS 50 MEMBERS! 2x points for 24 hours!"
- "💯 100th confession submitted. The Circle remembers everything."
- "🔥 @Sarah hit a 30-DAY STREAK. Only 3 people have ever done this."
- "🏆 FIRST VETERAN IN THE CIRCLE! @Jay made history."
- "📨 @Mike just became an Ambassador (25 invites). Legend."
- "⚡ @Kim ranked up 5 times in ONE DAY. Absolute grind."

### Engagement Tip Drops (teach members how to earn more):
Randomly after messages, Keeper occasionally drops tips:
- "💡 Did you know? Replying to someone earns 3x more points than posting alone."
- "💡 Pro tip: Tagging someone in a reply = 12x your base score."
- "💡 Voice channels earn you points too. Just hanging out = free XP."
- "💡 Reacting to someone's post gives THEM points. Spread the love."

**Rules for all triggers:**
- Max 2 trigger messages per day in any channel (never spammy)
- Rotate through all types so it never feels repetitive
- Only post when there's genuine activity (don't post to dead channels)

### New Cog:
- **`cogs/engagement_triggers.py`** — Cliffhangers, social proof, loss aversion, countdowns, celebrations, tip drops

---

## Updated Implementation Order (Full Priority List)
1. **Visual branding** (icon, banner, emoji) — non-code, immediate
2. **Enhanced onboarding** (DM flow, #introductions, #pick-your-roles)
3. **Confessions** — instant engagement magnet
4. **Starboard / Hall of Fame** — encourages quality + reactions
5. **Invite reminders + monthly competition** — growth engine
6. **Rank teasers + stagnation nudges** — prevents plateaus
7. **Engagement triggers** (cliffhangers, social proof, countdowns)
8. **Economy + Shop** — secondary motivation loop
9. **Auto-events calendar** — fills dead air
10. **Server-wide milestone goals** — collective motivation
11. **Profiles** — deepens identity
12. **Factions** — tribal loyalty (needs 30+ members)
13. **Smart DMs** — personalized re-engagement
14. **Buddy system** — needs enough active mentors
15. **Daily login rewards** — economy enhancement
16. **Third-party bots** — add at 20+ members

## Updated New Cog List
```
cogs/
├── (existing 14 cogs)
├── onboarding.py         # Enhanced DM flow + 24h check-in
├── introductions.py      # Incentivized intro posts
├── buddy_system.py       # Auto-pair mentors with new members
├── confessions.py        # Anonymous confession system
├── starboard.py          # Hall of fame auto-posting
├── economy.py            # Currency (Circles) tracking
├── shop.py               # Shop + rotating stock + mystery boxes
├── daily_rewards.py      # Enhanced login rewards
├── factions.py           # 4 teams + competition
├── auto_events.py        # Full weekly event calendar
├── trivia.py             # Auto trivia game
├── profiles.py           # Rich member profiles
├── smart_dm.py           # Personalized re-engagement
├── invite_reminders.py   # Rotating invite promos + monthly race
├── growth_nudges.py      # Rank teasers + stagnation nudges
├── server_goals.py       # Community milestones + weekly goals
└── engagement_triggers.py # Social proof, FOMO, countdowns, tips
```

---

## New Database Tables Needed
- **economy** — user_id, coins, total_earned, total_spent
- **shop_purchases** — user_id, item_key, purchased_at
- **shop_rotating** — item_key, available_until, stock_remaining
- **confessions** — id, user_id (hidden), content, number, timestamp, reaction_count
- **starboard** — message_id, author_id, channel_id, star_count, starboard_message_id
- **factions** — user_id, team_name, joined_at
- **faction_scores** — team_name, week, total_score
- **buddies** — mentor_id, mentee_id, assigned_at, completed, mentee_msg_count
- **profiles** — user_id, bio, accent_color, banner_url
- **login_rewards** — user_id, current_day, last_claim_date
- **smart_dm_log** — user_id, dm_type, sent_at
- **trivia_scores** — user_id, correct_count, total_played
- **invite_reminders_log** — message_id, template_index, posted_at
- **monthly_invite_race** — user_id, month, invite_count, winner
- **server_milestones** — milestone_key, reached_at, rewarded
- **weekly_goals** — week, target_type, target_value, current_value, completed
- **rank_tease_log** — user_id, teased_rank, sent_at
- **stagnation_log** — user_id, nudged_at, rank_at_nudge
- **engagement_trigger_log** — trigger_type, channel_id, posted_at

---

## Success Metrics to Track
- **Day 1 retention:** % of new members who send at least 1 message
- **Day 7 retention:** % still active after a week
- **Day 30 retention:** % still active after a month
- **Messages per active user per day**
- **Streak participation rate**
- **Faction participation rate** (of eligible members)
- **Shop purchase rate**
- **Confession submission rate**
- **Starboard feature rate**
- **Voice channel usage hours**
- **Invite conversion rate**
- **Invite reminder → actual invite rate**
- **Rank teaser → rank-up conversion rate**
- **Stagnation nudge → rank-up within 7 days rate**
- **Weekly goal completion rate**
- **Monthly recruiter race participation**
- **Buddy system mentee retention (7-day)**
- **Confession submission frequency**
- **Average time to first message (new members)**
- **Introduction post rate (new members)**
