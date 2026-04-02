"""
The Circle — Configuration
All scoring weights, rank thresholds, channel definitions, colors, and bot settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Bot Settings ───────────────────────────────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
BOT_PREFIX = "!"
BOT_NAME = "Keeper"

# ─── Embed Colors ───────────────────────────────────────────────────────────
EMBED_COLOR_PRIMARY = 0x1A1A2E      # Deep navy (sidebar)
EMBED_COLOR_ACCENT = 0xE94560       # Hot red (accent)
EMBED_COLOR_SUCCESS = 0x2ECC71      # Green
EMBED_COLOR_WARNING = 0xF1C40F      # Gold
EMBED_COLOR_ERROR = 0xE74C3C        # Red

# ─── Scoring Weights v2 (6-Layer Formula) ─────────────────────────────────
# Layer 1: Base (Quality-Aware)
SCORE_BASE_MESSAGE = 1.0            # Base points per text message
SCORE_PER_WORD = 0.15               # Bonus per word (reduced from 0.2 — quality > volume)
SCORE_MEDIA_POST = 5.0              # Points for posting media
SCORE_LINK_BONUS = 2.0              # Points for sharing a link
SCORE_INVITE_BONUS = 25.0           # Points per valid invite
SCORE_QUALITY_PUNCTUATION = 0.1     # +10% for proper punctuation
SCORE_QUALITY_QUESTION = 0.15       # +15% for asking questions (drives replies)
SCORE_QUALITY_VOCAB_WEIGHT = 0.4    # Weight for vocabulary diversity bonus

# Layer 2: Social (Interaction Multiplier)
SCORE_REPLY_MULTIPLIER = 2.5        # Multiplier when replying (down from 3.0)
SCORE_MENTION_MULTIPLIER = 2.0      # Multiplier when @mentioning (down from 4.0)
SCORE_REPLY_MENTION_SYNERGY = 6.0   # Reply + mention together = synergy bonus
SCORE_CHAIN_DEPTH_BONUS = 0.1       # +10% per thread depth level
SCORE_CHAIN_DEPTH_MAX = 5           # Max depth levels counted
SCORE_FIRST_MOVER_BONUS = 1.5       # Bonus for first reply within 5 min
SCORE_FIRST_MOVER_WINDOW_SECONDS = 300  # Window for first-mover detection
SCORE_SOCIAL_MULT_CAP = 12.0        # Hard cap on social multiplier

# Layer 3: Temporal (Time-of-Day)
TIME_MULTIPLIERS = {
    0: 1.3,   1: 1.4,   2: 1.4,   3: 1.5,   # Late night (off-peak)
    4: 1.5,   5: 1.4,   6: 1.3,   7: 1.1,   # Early morning
    8: 1.0,   9: 1.0,  10: 1.0,  11: 1.0,   # Morning baseline
   12: 1.1,  13: 1.1,  14: 1.1,  15: 1.2,   # Afternoon
   16: 1.2,  17: 1.3,  18: 1.3,  19: 1.2,   # Evening peak
   20: 1.2,  21: 1.2,  22: 1.3,  23: 1.3,   # Night peak
}
WEEKEND_BONUS_MULT = 1.15           # +15% on Saturday/Sunday

# Layer 4: Engagement (Diminishing Returns + Diversity + Combo)
DIMINISHING_RETURNS_TIERS = [       # (max_messages, multiplier)
    (20, 1.0),                       # First 20 msgs = full value
    (50, 0.5),                       # 21-50 = half value
    (100, 0.25),                     # 51-100 = quarter value
]
DIMINISHING_RETURNS_FLOOR = 0.10    # 101+ messages = 10% value
CHANNEL_DIVERSITY_BONUS_PER = 0.08  # +8% per extra channel
CHANNEL_DIVERSITY_MAX_CHANNELS = 6  # Max channels counted for bonus
COMBO_BONUS_PER_STACK = 0.1         # +10% per combo stack
COMBO_MAX_STACKS = 5                # Max 5 combo stacks (+50%)
COMBO_WINDOW_SECONDS = 600          # 10 min combo window

# Layer 5: Meta (Comeback + Streak + Catch-up + Faction + Prestige)
CATCHUP_TIERS = [                   # (max_rank_tier, bonus_multiplier)
    (20, 1.4),                       # Rookie/Regular: +40%
    (40, 1.2),                       # Certified/Respected: +20%
    (60, 1.1),                       # Veteran/OG: +10%
]
CATCHUP_DEFAULT = 1.0               # Elite+ = no catch-up bonus
META_MULT_CAP = 20.0                # Absolute hard cap on meta multiplier

# Layer 6: Dynamic Daily Cap
DAILY_CAP_TIERS = [                 # (max_rank_tier, daily_cap)
    (30, 500),                       # Rookie-Certified: 500/day
    (60, 750),                       # Respected-OG: 750/day
    (90, 1000),                      # Elite-Icon: 1000/day
]
DAILY_CAP_DEFAULT = 1500             # Immortal: 1500/day

# ─── Anti-Spam (Relaxed) ───────────────────────────────────────────────────
COOLDOWN_SECONDS = 15               # Seconds between scored messages
DAILY_POINT_CAP = 1500              # Legacy fallback — use DAILY_CAP_TIERS instead
DUPLICATE_WINDOW_SECONDS = 300      # Same message within 5 min = 0 pts
SPAM_MESSAGE_COUNT = 5              # Messages in spam window triggers pause
SPAM_WINDOW_SECONDS = 10            # Window for spam detection
SPAM_PAUSE_SECONDS = 300            # How long scoring pauses after spam (5 min)

# ─── Comeback Mechanic ─────────────────────────────────────────────────────
COMEBACK_INACTIVE_DAYS = 7          # Days inactive before comeback bonus
COMEBACK_BONUS_MULTIPLIER = 5.0     # Score multiplier on return
COMEBACK_DM_DAYS = 14               # Days before Keeper DMs the user
COMEBACK_DECAY_DAYS = 30            # Days before score decay starts
COMEBACK_DECAY_RATE = 0.02          # 2% per day score decay

# ─── Invite Validation ─────────────────────────────────────────────────────
INVITE_MIN_STAY_HOURS = 24          # Invitee must stay this long
INVITE_MIN_MESSAGES = 5             # Invitee must send this many messages

# ─── Streaks ───────────────────────────────────────────────────────────────
STREAK_BONUS_MULTIPLIER = {         # Streak length -> bonus multiplier on all points
    3: 1.1,                         # 3-day streak = 10% bonus
    7: 1.25,                        # 7-day streak = 25% bonus
    14: 1.5,                        # 14-day streak = 50% bonus
    30: 2.0,                        # 30-day streak = 100% bonus (DOUBLE)
    60: 2.5,                        # 60-day streak = 150% bonus
    100: 3.0,                       # 100-day streak = 200% bonus (TRIPLE)
}

# ─── Reaction Scoring ─────────────────────────────────────────────────────
REACTION_POINTS_PER = 0.5           # Points author earns per reaction received
REACTION_DAILY_CAP = 100            # Max reaction points per day per user
REACTION_SELF_EXCLUDED = True       # Can't earn points from your own reactions

# ─── Voice XP ──────────────────────────────────────────────────────────────
VOICE_POINTS_PER_MINUTE = 0.2      # Points per minute in voice
VOICE_SESSION_CAP_MINUTES = 480    # Max 8 hours per session
VOICE_AFK_CHANNEL_EXCLUDED = True  # Don't earn in AFK channel

# ─── Daily Prompts ─────────────────────────────────────────────────────────
DAILY_PROMPT_HOUR = 10              # Hour (UTC) to post daily prompt
DAILY_PROMPT_CHANNEL = "general"    # Channel to post prompts in

# ─── Weekly Recap ──────────────────────────────────────────────────────────
WEEKLY_RECAP_DAY = 6                # Day of week (0=Mon, 6=Sun)
WEEKLY_RECAP_HOUR = 18              # Hour (UTC) to post recap
WEEKLY_RECAP_CHANNEL = "general"    # Channel to post recap in

# ─── Leaderboard ───────────────────────────────────────────────────────────
LEADERBOARD_TOP_COUNT = 25          # How many users on the leaderboard
LEADERBOARD_REFRESH_MINUTES = 60    # How often the embed refreshes

# ─── Channel Definitions ───────────────────────────────────────────────────
# Categories and their channels. Read-only channels have send_messages=False for @everyone.
CHANNEL_STRUCTURE = {
    "📋 WELCOME & INFO": {
        "welcome": {"read_only": True, "topic": "New souls enter here. Keeper watches."},
        "info": {"read_only": True, "topic": "Everything you need to know about The Circle."},
        "rules": {"read_only": True, "topic": "The law of The Circle."},
        "announcements": {"read_only": True, "topic": "Words from above."},
    },
    "💬 SOCIAL": {
        "general": {"read_only": False, "topic": "The main hangout. Talk about anything."},
        "memes": {"read_only": False, "topic": "If it's funny, post it."},
        "dating": {"read_only": False, "topic": "Advice, stories, and the dating game."},
    },
    "🏋️ SERIOUS": {
        "politics": {"read_only": False, "topic": "Debates, news, and hot takes."},
        "work": {"read_only": False, "topic": "Career, hustle, and the grind."},
        "fitness": {"read_only": False, "topic": "Gains, goals, and gym talk."},
    },
    "📊 MEDIA & STATS": {
        "media-feed": {"read_only": True, "topic": "Auto-curated media from all channels. Keeper collects."},
        "leaderboard": {"read_only": True, "topic": "The worthy rise. The silent fall."},
        "rank-ups": {"read_only": True, "topic": "Witness the ascension."},
    },
    "🎭 ENGAGEMENT": {
        "introductions": {"read_only": False, "topic": "Introduce yourself! 50 pts + badge for your first post."},
        "confessions": {"read_only": True, "topic": "Anonymous confessions. DM Keeper with !confess."},
        "confession-discussion": {"read_only": False, "topic": "Discuss the confessions here."},
        "hall-of-fame": {"read_only": True, "topic": "The best messages, chosen by The Circle."},
    },
    "⚔️ FACTIONS": {
        "faction-war": {"read_only": True, "topic": "Team standings and weekly competition."},
        "team-inferno": {"read_only": False, "topic": "🔴 Inferno — Burn bright."},
        "team-frost": {"read_only": False, "topic": "🔵 Frost — Stay cold."},
        "team-venom": {"read_only": False, "topic": "🟢 Venom — Strike silent."},
        "team-volt": {"read_only": False, "topic": "🟡 Volt — Stay charged."},
    },
    "🤖 BOT": {
        "bot-commands": {"read_only": False, "topic": "Talk to Keeper here. !rank !top !stats !shop !profile !spin !help"},
    },
    "🌙 EXCLUSIVE": {
        "vip-lounge": {"read_only": False, "topic": "Respected+ members only. The inner circle."},
        "after-hours": {"read_only": False, "topic": "Veteran+ only. No scoring. Just vibes."},
    },
}

# Channels excluded from scoring
EXCLUDED_CHANNELS = {
    "welcome", "info", "rules", "announcements", "media-feed", "leaderboard",
    "rank-ups", "bot-commands", "confessions", "hall-of-fame", "faction-war",
    "after-hours",  # Veteran+ decompression zone — no scoring by design
}

# ─── Rank Group Definitions ────────────────────────────────────────────────
# Each group: (name, start_hex, end_hex, tagline)
RANK_GROUPS = [
    ("Rookie",    0x696969, 0xA9A9A9, "You found the WiFi password."),
    ("Regular",   0x228B22, 0x2ECC71, "Your screen time is concerning."),
    ("Certified", 0x1E6FD9, 0x5BA3F5, "Your mom would be worried."),
    ("Respected", 0xCC6600, 0xE67E22, "Therapist: 'And the Discord?'"),
    ("Veteran",   0xB22222, 0xE74C3C, "You've seen things."),
    ("OG",        0x6A0DAD, 0x9B59B6, "Touch grass? Never heard of it."),
    ("Elite",     0x008B8B, 0x1ABC9C, "Your keyboard fears you."),
    ("Legend",    0xB8860B, 0xF1C40F, "Some say they never log off."),
    ("Icon",      0xC71585, 0xFF1493, "Are you okay? Genuinely."),
    ("Immortal",  0xD4D4D4, 0xFFFFFF, "This IS your grass."),
]

# Roman numeral labels for sub-ranks
ROMAN_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

# ─── Keeper's Voice Lines ──────────────────────────────────────────────────
KEEPER_WELCOME = (
    "Another soul enters The Circle. {mention}, your journey begins now...\n\n"
    "The Circle watches. Type `!rank` to see where you stand."
)

KEEPER_COMEBACK = (
    "A familiar presence returns... {mention}, The Circle remembers you.\n"
    "⚡ 5x blessing granted. Make it count."
)

KEEPER_COMEBACK_DM = (
    "The Circle grows quiet without you, {username}.\n"
    "Your rank slips... others rise.\n"
    "Return, before The Circle forgets."
)

KEEPER_RANKUP = (
    "The Circle has spoken.\n"
    "⚡ {mention} ascends to **{rank_name}**.\n"
    "*\"{tagline}\"*"
)

KEEPER_RANKUP_INLINE = "⚡ {mention} ascends to **{rank_name}**."

KEEPER_LEADERBOARD_HEADER = "The worthy rise. The silent fall.\nBehold this week's chosen."

KEEPER_HELP = (
    "You seek guidance? Very well.\n\n"
    "**📊 Stats & Rankings**\n"
    "🏆 `!rank` — See where you stand\n"
    "📊 `!top` — The top 10 chosen ones\n"
    "👤 `!profile` — Your full profile\n"
    "👀 `!stats @user` — Peer into another's journey\n"
    "📨 `!invites` — The recruiters' ledger\n\n"
    "**🔥 Engagement**\n"
    "🔥 `!streak` — Check your daily streak\n"
    "🏅 `!badges` — See your achievements\n"
    "📅 `!daily` — Claim daily login reward\n"
    "📊 `!goal` — Weekly community goal\n\n"
    "**🪙 Economy**\n"
    "💰 `!balance` — Check your Circles\n"
    "🏪 `!shop` — Browse the shop\n"
    "🛒 `!buy <item>` — Purchase an item\n\n"
    "**⚔️ Social**\n"
    "⚔️ `!faction` — Faction standings\n"
    "🔮 `!confess <text>` — Anonymous confession\n"
    "✏️ `!setbio <text>` — Set profile bio\n\n"
    "The Circle rewards those who speak, share, reply, and tag.\n"
    "Solo whispers earn little. Connections earn everything."
)

# ─── Achievement Definitions ──────────────────────────────────────────────
# key: (emoji, name, description, check_description)
ACHIEVEMENTS = {
    "first_message":     ("💬", "First Words",       "Send your first message"),
    "streak_3":          ("🔥", "Warming Up",        "Reach a 3-day streak"),
    "streak_7":          ("🔥", "On Fire",           "Reach a 7-day streak"),
    "streak_14":         ("🔥", "Unstoppable",       "Reach a 14-day streak"),
    "streak_30":         ("🔥", "Addicted",          "Reach a 30-day streak"),
    "streak_100":        ("💀", "No Life",           "Reach a 100-day streak"),
    "media_first":       ("📸", "Shutterbug",        "Post your first media"),
    "media_50":          ("🎬", "Content Creator",   "Post 50 media messages"),
    "replies_50":        ("↩️", "Conversationalist", "Reply to 50 messages"),
    "replies_500":       ("🗣️", "Chatterbox",       "Reply to 500 messages"),
    "tags_50":           ("🏷️", "Name Dropper",     "Tag people 50 times"),
    "reactions_100":     ("❤️", "Crowd Pleaser",    "Receive 100 reactions"),
    "reactions_1000":    ("🌟", "Fan Favorite",      "Receive 1,000 reactions"),
    "voice_60":          ("🎤", "Voice Actor",       "Spend 60 minutes in voice"),
    "voice_600":         ("🎧", "DJ Booth",          "Spend 10 hours in voice"),
    "invite_1":          ("📨", "Recruiter",         "Invite your first member"),
    "invite_5":          ("📨", "Talent Scout",      "Invite 5 members"),
    "invite_25":         ("👑", "Ambassador",        "Invite 25 members"),
    "rank_regular":      ("🟢", "Regular",           "Reach Regular rank"),
    "rank_certified":    ("🔵", "Certified",         "Reach Certified rank"),
    "rank_respected":    ("🟠", "Respected",         "Reach Respected rank"),
    "rank_veteran":      ("🔴", "Veteran",           "Reach Veteran rank"),
    "rank_og":           ("🟣", "OG",                "Reach OG rank"),
    "rank_elite":        ("🩵", "Elite",             "Reach Elite rank"),
    "rank_legend":       ("🟡", "Legend",            "Reach Legend rank"),
    "rank_icon":         ("🩷", "Icon",              "Reach Icon rank"),
    "rank_immortal":     ("⚪", "Immortal",          "Reach Immortal rank"),
    "score_1000":        ("📈", "Climbing",          "Reach 1,000 total points"),
    "score_10000":       ("📈", "Dedicated",         "Reach 10,000 total points"),
    "score_100000":      ("📈", "Obsessed",          "Reach 100,000 total points"),
    # Phase 2 achievements
    "introduced":        ("👋", "Introduced",        "Post your first introduction"),
    "mentor":            ("🤝", "Mentor",             "Successfully guide a new member"),
    "login_30":          ("📅", "Dedicated",          "Claim daily rewards for 30 days"),
    "confessor":         ("🔮", "Confessor",          "Submit your first confession"),
    "hall_of_fame":      ("⭐", "Famous",             "Get a message on the Hall of Fame"),
    "faction_joined":    ("⚔️", "Faction Member",    "Join a faction"),
    "shopper":           ("🛒", "Shopper",            "Buy your first shop item"),
    "trivia_5":          ("🧠", "Trivia Buff",        "Answer 5 trivia questions correctly"),
}

# ─── Economy / Shop ────────────────────────────────────────────────────────
ECONOMY_COIN_PER_MESSAGE = 1           # Circles earned per scored message
ECONOMY_COIN_DAILY_LOGIN = 10          # Base daily login coins
ECONOMY_CURRENCY_NAME = "Circles"
ECONOMY_CURRENCY_EMOJI = "🪙"

SHOP_ITEMS = {
    "nickname_color":  {"name": "Custom Nickname Color", "cost": 100, "desc": "Pick any hex color for your name", "emoji": "🎨"},
    "nickname_change": {"name": "Nickname Change",       "cost": 50,  "desc": "Change your server nickname",      "emoji": "✏️"},
    "xp_boost":        {"name": "XP Boost (2x, 1hr)",   "cost": 75,  "desc": "Double all points for 60 min",     "emoji": "⚡"},
    "mystery_box":     {"name": "Mystery Box",           "cost": 150, "desc": "Random: coins, XP boost, or badge", "emoji": "🎁"},
    "profile_banner":  {"name": "Profile Banner",        "cost": 200, "desc": "Custom banner on your !profile",   "emoji": "🖼️"},
}

# ─── Confessions ──────────────────────────────────────────────────────────
CONFESSION_COOLDOWN_HOURS = 6          # Hours between confessions per user
CONFESSION_CHANNEL = "confessions"
CONFESSION_DISCUSSION_CHANNEL = "confession-discussion"
CONFESSION_AUTO_REACTIONS = ["🔥", "😂", "😱"]

# ─── Starboard ────────────────────────────────────────────────────────────
STARBOARD_CHANNEL = "hall-of-fame"
STARBOARD_EMOJI = "⭐"
STARBOARD_THRESHOLDS = {              # member_count -> required reactions
    0: 3,
    50: 5,
    200: 10,
    1000: 15,
}

# ─── Factions ─────────────────────────────────────────────────────────────
FACTION_UNLOCK_RANK = 31              # Respected I
FACTION_TEAMS = {
    "Inferno": {"color": 0xE74C3C, "emoji": "🔴", "motto": "Burn bright."},
    "Frost":   {"color": 0x3498DB, "emoji": "🔵", "motto": "Stay cold."},
    "Venom":   {"color": 0x2ECC71, "emoji": "🟢", "motto": "Strike silent."},
    "Volt":    {"color": 0xF1C40F, "emoji": "🟡", "motto": "Stay charged."},
}
FACTION_WIN_BONUS = 1.1               # 10% point bonus for winning team

# ─── Buddy System ─────────────────────────────────────────────────────────
BUDDY_MIN_RANK = 21                   # Certified I
BUDDY_MENTEE_MSG_GOAL = 10            # Messages mentee must send
BUDDY_TIME_LIMIT_HOURS = 48           # Time window
BUDDY_REWARD_POINTS = 50              # Points for both on completion

# ─── Onboarding ───────────────────────────────────────────────────────────
ONBOARDING_DM_DELAY_SECONDS = 5       # Delay after join before DM
ONBOARDING_CHECKIN_HOURS = 24         # Hours before 24h check-in DM
INTRO_POINTS_REWARD = 50              # Points for posting an introduction

# ─── Invite Reminders ─────────────────────────────────────────────────────
INVITE_REMINDER_DAYS = [1, 3, 5]      # Days of week to post (Mon=0)
INVITE_REMINDER_HOUR = 16             # Hour (UTC) to post
INVITE_LINK = "discord.gg/thecircle"  # Default invite link (updated via !setinvite)

INVITE_REMINDER_TEMPLATES = [
    "📨 Know someone who'd fit in? Share The Circle: `{link}` — You earn 25 pts per invite.",
    "📈 The Circle is growing. **{member_count}** members and climbing. Bring 1 friend = 25 pts. `{link}`",
    "🏆 This week's top recruiter: **{top_inviter}** with {invite_count} invites. Can you beat that? `{link}`",
    "💡 Did you know? Every friend you bring earns you **25 points**. That's almost a full rank level. `{link}`",
    "🔥 **{recent_joins}** people joined this week. The Circle is getting louder. Help it grow: `{link}`",
    "📨 Your invite link is your secret weapon. Share it → they join → you earn 25 pts → everyone wins. `{link}`",
    "🏅 Invite milestones: 1 invite = Recruiter badge. 5 = Talent Scout. 25 = Ambassador. Where are you? `{link}`",
    "🚀 Every new member makes The Circle stronger. Drop the link to a friend: `{link}`",
    "👑 The top recruiter this month wins **500 coins** + exclusive role. Current leader: **{top_inviter}**. `{link}`",
    "💬 More members = better conversations = more points for YOU. Share: `{link}`",
]

# ─── Growth Nudges ─────────────────────────────────────────────────────────
RANK_TEASE_COOLDOWN_DAYS = 3          # Days between teasers per user
RANK_TEASE_THRESHOLD = 0.80           # Show teaser when 80%+ to next group
STAGNATION_NUDGE_DAYS = 14            # Days at same rank before nudge
STAGNATION_NUDGE_COOLDOWN_DAYS = 14   # Days between nudges per user

# ─── Engagement Triggers ──────────────────────────────────────────────────
ENGAGEMENT_MAX_PER_DAY = 2            # Max trigger messages per channel per day
ENGAGEMENT_TIP_CHANCE = 0.05          # 5% chance to show tip after message

ENGAGEMENT_TIPS = [
    "💡 Did you know? Replying to someone earns **3x** more points than posting alone.",
    "💡 Pro tip: Tagging someone in a reply = **12x** your base score.",
    "💡 Voice channels earn you points too. Just hanging out = free XP.",
    "💡 Reacting to someone's post gives THEM points. Spread the love.",
    "💡 Your daily streak multiplies ALL your points. Don't break it!",
    "💡 Media posts (images, videos, links) earn **+5 bonus** points.",
    "💡 The longer your message, the more points. +0.2 per word adds up fast.",
]

ENGAGEMENT_SOCIAL_PROOF = [
    "📊 **{rankup_count}** members ranked up this week. Did you?",
    "🔥 **{active_count}** members were active today. The Circle never sleeps.",
    "💬 **{msg_count}** messages were sent today. You were part of **{user_count}** of them.",
    "⭐ **{streak_count}** members have active streaks right now. Are you one of them?",
]

ENGAGEMENT_CLIFFHANGERS = [
    "👀 Tomorrow's daily prompt is going to be WILD.",
    "🔮 Something special is brewing in The Circle...",
    "⚡ Big things coming. Stay tuned.",
    "🎯 A milestone is within reach. The Circle can feel it.",
]

# ─── Auto Events ──────────────────────────────────────────────────────────
AUTO_EVENT_HOUR = 12                   # Hour (UTC) to post events

# ─── Server Goals ─────────────────────────────────────────────────────────
MEMBER_MILESTONES = {
    25:   {"reward": "50 coins for everyone",       "coins": 50},
    50:   {"reward": "24h double XP for all",       "coins": 0},
    100:  {"reward": "Mystery box for every member", "coins": 0},
    250:  {"reward": "New #vip-lounge unlocked",    "coins": 0},
    500:  {"reward": "Community emoji vote",        "coins": 0},
    1000: {"reward": "Server-wide event + Day One badge", "coins": 0},
}
WEEKLY_GOAL_MESSAGE_TARGET = 5000     # Default weekly message target

# ─── Smart DMs ────────────────────────────────────────────────────────────
SMART_DM_MAX_PER_WEEK = 1             # Max DMs per user per week
SMART_DM_TIERS = {
    3:  "🔥 Your **{streak}**-day streak is about to end. One message saves it.",
    7:  "The Circle misses you. **#{top_channel}** has been going off. Come back for **5x bonus**.",
    14: "Your rank is decaying. You've dropped from **{old_rank}** to **{new_rank}**. Return now.",
    30: "The Circle is moving on. Your **{rank}** status won't last forever.",
}

# ─── Daily Login Rewards ──────────────────────────────────────────────────
LOGIN_REWARD_SCHEDULE = {
    1: {"coins": 10,  "label": "10 🪙"},
    2: {"coins": 15,  "label": "15 🪙"},
    3: {"coins": 20,  "label": "20 🪙"},
    4: {"coins": 25,  "label": "25 🪙"},
    5: {"coins": 30,  "label": "30 🪙"},
    6: {"coins": 40,  "label": "40 🪙"},
    7: {"coins": 75,  "label": "75 🪙 + Mystery Box"},
    14: {"coins": 100, "label": "100 🪙 + Rare Color"},
    30: {"coins": 500, "label": "500 🪙 + Badge"},
}

# ─── Trivia ───────────────────────────────────────────────────────────────
TRIVIA_POINTS_CORRECT = 10            # Points for correct answer
TRIVIA_QUESTIONS_PER_ROUND = 10       # Questions per Tuesday trivia
TRIVIA_ANSWER_SECONDS = 30            # Seconds to answer

TRIVIA_QUESTIONS = [
    {"q": "What is the largest planet in our solar system?", "a": "Jupiter", "options": ["Saturn", "Jupiter", "Neptune", "Uranus"]},
    {"q": "In what year did the Titanic sink?", "a": "1912", "options": ["1905", "1912", "1918", "1923"]},
    {"q": "What element has the chemical symbol 'Au'?", "a": "Gold", "options": ["Silver", "Gold", "Aluminum", "Argon"]},
    {"q": "Which country has the most time zones?", "a": "France", "options": ["Russia", "USA", "France", "China"]},
    {"q": "What is the smallest bone in the human body?", "a": "Stapes", "options": ["Stapes", "Femur", "Ulna", "Patella"]},
    {"q": "Who painted the Mona Lisa?", "a": "Leonardo da Vinci", "options": ["Michelangelo", "Leonardo da Vinci", "Raphael", "Donatello"]},
    {"q": "What is the speed of light in km/s (approximately)?", "a": "300,000", "options": ["150,000", "300,000", "500,000", "1,000,000"]},
    {"q": "Which planet is known as the Red Planet?", "a": "Mars", "options": ["Venus", "Mars", "Jupiter", "Mercury"]},
    {"q": "What year did World War II end?", "a": "1945", "options": ["1943", "1944", "1945", "1946"]},
    {"q": "What is the hardest natural substance on Earth?", "a": "Diamond", "options": ["Diamond", "Quartz", "Topaz", "Ruby"]},
    {"q": "How many hearts does an octopus have?", "a": "3", "options": ["1", "2", "3", "4"]},
    {"q": "What is the capital of Australia?", "a": "Canberra", "options": ["Sydney", "Melbourne", "Canberra", "Brisbane"]},
    {"q": "Who wrote '1984'?", "a": "George Orwell", "options": ["Aldous Huxley", "George Orwell", "Ray Bradbury", "Kurt Vonnegut"]},
    {"q": "What is the most spoken language in the world?", "a": "Mandarin Chinese", "options": ["English", "Mandarin Chinese", "Spanish", "Hindi"]},
    {"q": "How many bones are in the adult human body?", "a": "206", "options": ["196", "206", "216", "226"]},
    {"q": "What animal can sleep for 3 years?", "a": "Snail", "options": ["Bear", "Snail", "Sloth", "Tortoise"]},
    {"q": "What is the largest ocean on Earth?", "a": "Pacific", "options": ["Atlantic", "Indian", "Pacific", "Arctic"]},
    {"q": "In which year did the Berlin Wall fall?", "a": "1989", "options": ["1987", "1988", "1989", "1990"]},
    {"q": "What is the rarest blood type?", "a": "AB-negative", "options": ["O-negative", "AB-negative", "B-negative", "A-negative"]},
    {"q": "Which planet has the most moons?", "a": "Saturn", "options": ["Jupiter", "Saturn", "Uranus", "Neptune"]},
]

# ─── Daily Prompts Pool ───────────────────────────────────────────────────
DAILY_PROMPTS = [
    # General / Social
    "What's the most overrated thing that everyone seems to love? 🤔",
    "If you could master one skill overnight, what would it be?",
    "What's a hill you'll die on? Drop your hottest take. 🔥",
    "What's the best purchase you've made under $50?",
    "What's something you changed your mind about recently?",
    "You get $10 million but you can never use the internet again. Do you take it?",
    "What's a compliment someone gave you that you still think about?",
    "What show or movie do you quote the most?",
    "What's a green flag that people overlook in friendships?",
    "If your life had a theme song, what would it be? 🎵",
    # Fitness
    "What's your current workout split? Drop it below. 💪",
    "Most underrated exercise? Go.",
    "What's your gym pet peeve? We all have one. 😤",
    "Bulking or cutting right now? How's it going?",
    "What fitness advice would you give your younger self?",
    # Dating
    "What's the biggest ick you've ever experienced? 😬",
    "Best first date idea that isn't dinner and a movie?",
    "What's a dating red flag you learned the hard way?",
    "Hot take: what's an unpopular dating opinion you have?",
    "What's the funniest thing that's happened to you on a date?",
    # Work
    "What do you do for work, and do you actually enjoy it?",
    "Best career advice you've ever received?",
    "What's a job you'd never do, no matter the pay? 💀",
    "Side hustle check — anyone working on something outside their 9-5?",
    "What skill has made you the most money?",
    # Memes / Fun
    "Drop the last meme you saved. No context. 😂",
    "What's a trend you don't understand at all?",
    "What app do you spend the most screen time on? Be honest.",
    "If you could live in any fictional universe, which one?",
    "What's something that's normal now but will be weird in 50 years?",
    # Politics / Society
    "What's one thing you wish more people understood about the world?",
    "What's a law that makes no sense to you?",
    "If you could change one thing about your country overnight, what would it be?",
    "What's a cause you actually care about? And why?",
    "Technology: making life better or worse? Honest answer only.",
    # Would You Rather
    "Would you rather know when you'll die or how you'll die?",
    "Would you rather have unlimited money or unlimited time?",
    "Would you rather be famous but hated, or unknown but loved?",
    "Would you rather relive the same day forever or fast-forward 10 years?",
    "Would you rather lose all your memories or never make new ones?",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PHASE 3 — ULTIMATE ENGAGEMENT ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ─── Variable Rewards (Dopamine Engine) ───────────────────────────────────
CRITICAL_HIT_CHANCE = 0.02           # 2% chance of 2x on any message
NEAR_MISS_CHANCE = 0.03              # 3% chance of "almost" message
BONUS_DROP_CHANCE = 0.02             # 2% chance your NEXT msg gets hidden multiplier
BONUS_DROP_MULTIPLIERS = [           # (multiplier, weight)
    (2.0, 50),                        # 50% chance of 2x
    (3.0, 30),                        # 30% chance of 3x
    (5.0, 15),                        # 15% chance of 5x
    (10.0, 5),                        # 5% chance of 10x
]

# Progressive Jackpot
JACKPOT_CONTRIBUTION_PER_MESSAGE = 0.5  # Coins added to pot per scored message
JACKPOT_TRIGGER_CHANCE = 0.0005      # 0.05% per message (1 in 2000)
JACKPOT_MIN_POT = 100                # Won't trigger until pot reaches 100
JACKPOT_SEED = 50                    # Pot resets to this after a win

# Surprise 2x Windows
SURPRISE_2X_MIN_INTERVAL_HOURS = 4
SURPRISE_2X_MAX_INTERVAL_HOURS = 8
SURPRISE_2X_DURATION_MIN = 15        # Minutes
SURPRISE_2X_DURATION_MAX = 30        # Minutes

# Daily Wheel Spin
WHEEL_SEGMENTS = [
    {"label": "5 🪙",         "coins": 5,    "weight": 25, "type": "coins"},
    {"label": "10 🪙",        "coins": 10,   "weight": 20, "type": "coins"},
    {"label": "25 🪙",        "coins": 25,   "weight": 18, "type": "coins"},
    {"label": "50 🪙",        "coins": 50,   "weight": 12, "type": "coins"},
    {"label": "100 🪙",       "coins": 100,  "weight": 8,  "type": "coins"},
    {"label": "2x XP 30m",    "coins": 0,    "weight": 7,  "type": "xp_boost_30"},
    {"label": "250 🪙",       "coins": 250,  "weight": 4,  "type": "coins"},
    {"label": "Streak Freeze", "coins": 0,   "weight": 3,  "type": "streak_freeze"},
    {"label": "500 🪙",       "coins": 500,  "weight": 2,  "type": "coins"},
    {"label": "JACKPOT!",     "coins": 0,    "weight": 1,  "type": "jackpot"},
]

# Mystery Box (redesigned loot table)
MYSTERY_BOX_LOOT_TABLE = [
    {"name": "25 Circles",          "coins": 25,   "weight": 25, "type": "coins"},
    {"name": "50 Circles",          "coins": 50,   "weight": 20, "type": "coins"},
    {"name": "100 Circles",         "coins": 100,  "weight": 15, "type": "coins"},
    {"name": "2x XP (30 min)",      "coins": 0,    "weight": 12, "type": "xp_boost_30"},
    {"name": "250 Circles",         "coins": 250,  "weight": 8,  "type": "coins"},
    {"name": "2x XP (1 hour)",      "coins": 0,    "weight": 6,  "type": "xp_boost_60"},
    {"name": "Streak Freeze Token", "coins": 0,    "weight": 5,  "type": "streak_freeze"},
    {"name": "Rank Shield (24h)",   "coins": 0,    "weight": 4,  "type": "rank_shield"},
    {"name": "500 Circles JACKPOT", "coins": 500,  "weight": 3,  "type": "coins"},
    {"name": "Empty box...",        "coins": 0,    "weight": 2,  "type": "nothing"},
]

NEAR_MISS_MESSAGES = [
    "You were **2 points** away from a bonus drop! So close...",
    "The jackpot almost triggered... **{jackpot_amount}** 🪙 slipped away.",
    "A mystery box appeared... and vanished. Next time. 👀",
    "You rolled a **98** on the bonus wheel. You needed 99. Painful.",
    "A rare badge was within reach... keep going.",
]

# ─── Loss Aversion ────────────────────────────────────────────────────────
GRADUATED_DECAY_SCHEDULE = {         # days_inactive -> daily_decay_rate
    30: 0.005,                        # 0.5% per day (gentle start)
    37: 0.01,                         # 1.0% per day
    44: 0.02,                         # 2.0% per day (old rate)
    60: 0.03,                         # 3.0% per day (panic zone)
    90: 0.05,                         # 5.0% per day (devastation)
}
RANK_DEMOTION_GRACE_DAYS = 3         # Days below threshold before demotion
RANK_DEMOTION_ENABLED = True
DISPLACEMENT_PROXIMITY = 5           # Alert if within top N positions
DISPLACEMENT_COOLDOWN_HOURS = 12     # Max 1 alert per N hours
FACTION_LOSING_PENALTY = 0.95        # 5% reduction for last-place faction

# Streak Insurance
STREAK_FREEZE_COST = 200             # Circles to buy a freeze token
STREAK_FREEZE_MAX_HELD = 3           # Max tokens a user can hold
STREAK_FREEZE_AUTO_USE = True        # Auto-use on missed day
STREAK_RECOVERY_COSTS = {            # streak_length -> cost to recover
    30: 500,
    60: 1000,
    100: 2000,
}
STREAK_GRACE_MIN_LENGTH = 14         # Min streak for free grace period

# Tiered Comeback Bonus
COMEBACK_BONUS_TIERS = {             # max_days_inactive -> multiplier
    29: 5.0,                          # 7-29 days = 5x
    59: 3.0,                          # 30-59 days = 3x
    9999: 2.0,                        # 60+ days = 2x
}

# ─── Onboarding v2 ───────────────────────────────────────────────────────
ONBOARDING_QUEST_INTRO_POINTS = 50
ONBOARDING_QUEST_FIRST_REPLY_BONUS = True
ONBOARDING_QUEST_DAILY_CLAIM = True
ONBOARDING_GRADUATION_COINS = 100
ONBOARDING_GRADUATION_BADGE = "survivor_7d"

# ─── Re-engagement Pipeline ──────────────────────────────────────────────
REENGAGEMENT_TIERS = {
    1:  {"channel": "server", "type": "streak_risk"},
    2:  {"channel": "dm",     "type": "loss_aversion"},
    3:  {"channel": "dm",     "type": "social_proof"},
    5:  {"channel": "dm",     "type": "competitive_loss"},
    7:  {"channel": "dm",     "type": "urgency"},
    14: {"channel": "dm",     "type": "active_loss"},
    30: {"channel": "dm",     "type": "nostalgia"},
    60: {"channel": "dm",     "type": "closure"},
}

# ─── Streaks v2 (Multi-Dimensional) ──────────────────────────────────────
STREAK_TYPES = {
    "daily":    {"requirement": "any_activity",       "milestones": [3, 7, 14, 30, 60, 100, 180, 365]},
    "weekly":   {"requirement": "5_of_7_days",        "milestones": [4, 8, 12, 26, 52]},
    "social":   {"requirement": "reply_3_unique",     "milestones": [3, 7, 14, 30]},
    "voice":    {"requirement": "15_min_voice",       "milestones": [3, 7, 14]},
    "creative": {"requirement": "post_media",         "milestones": [3, 7, 14]},
}
STREAK_BONUS_MULTIPLIER_V2 = {      # Extended from original
    3: 1.1, 7: 1.25, 14: 1.5, 30: 2.0, 60: 2.5, 100: 3.0, 180: 3.5, 365: 4.0,
}
PAIRED_STREAK_MAX_PAIRS = 3
PAIRED_STREAK_BONUS_PER = 0.05      # +5% per active pair
PAIRED_STREAK_MILESTONES = {7: 50, 14: 150, 30: 500, 60: 1000}

# ─── Social Graph ────────────────────────────────────────────────────────
FRIENDSHIP_DECAY_WEEKLY = 0.05       # 5% weekly decay on zero-interaction pairs
FRIENDSHIP_MIN_CONNECTIONS = 3       # Target connections within 7 days
ICEBREAKER_CHECK_HOURS = 12          # How often to check for lonely members
ICEBREAKER_REPLY_GOAL = 3            # Replies needed to complete connection quest
ICEBREAKER_REWARD_POINTS = 25
ICEBREAKER_REWARD_COINS = 10

# Best Friend / Rival
BEST_FRIEND_REPLY_BONUS = 0.05      # +5% when replying to best friend
RIVAL_COST = 50                      # Circles to declare a rival
RIVAL_DURATION_WEEKS = 4
RIVAL_WINNER_COINS = 25              # Weekly winner reward

# Circles (Friend Groups)
CIRCLE_MIN_RANK = 21                 # Certified I
CIRCLE_CREATE_COST = 200
CIRCLE_MIN_MEMBERS = 3
CIRCLE_MAX_MEMBERS = 8
CIRCLE_WEEKLY_WINNER_COINS = 50      # Per member of top Circle

# ─── Content Engine ──────────────────────────────────────────────────────
UGC_SUBMIT_COST = 20                 # Circles to submit content
UGC_USED_REWARD_COINS = 100
UGC_AUTO_APPROVE_THRESHOLD = 3       # Approvals needed for auto-trust

QUICK_FIRE_PER_DAY = 3               # Quick fires per day
QUICK_FIRE_MIN_GAP_HOURS = 3
QUICK_FIRE_FIRST_N_BONUS = 5         # First N replies get bonus
QUICK_FIRE_BONUS_POINTS = 5

DEAD_ZONE_MINUTES = 45               # Minutes of silence before auto-content
TRENDING_WINDOW_HOURS = 6
TRENDING_MIN_MENTIONS = 10
TRENDING_MIN_USERS = 3

# Debates
DEBATE_DURATION_HOURS = 4
DEBATE_MINORITY_BONUS = 2.0          # 2x points for minority side
DEBATE_MVP_COINS = 50
HEAT_THRESHOLD_WARN = 15
HEAT_THRESHOLD_SLOW = 25
HEAT_THRESHOLD_LOCK = 35
HEAT_SLOW_MODE_SECONDS = 30
HEAT_SLOW_MODE_DURATION = 900        # 15 min

QUICK_FIRE_PROMPTS = [
    "This or That: Coffee or Tea? React ☕ or 🍵",
    "Rate the last thing you ate 1-10. Go.",
    "Hot or Not: Pineapple on pizza 🍕",
    "Finish this sentence: The worst thing about Monday is...",
    "One word to describe your week so far?",
    "Your go-to comfort food? 🍔",
    "Early bird or night owl? React 🌅 or 🌙",
    "Best streaming platform? Netflix, Hulu, Disney+, or other?",
    "Dogs or cats? This is a personality test. 🐕 🐈",
    "What's the last song you listened to? Drop it.",
    "Gym in the morning or evening? 💪",
    "iPhone or Android? Choose wisely.",
    "If you could only eat one cuisine forever?",
    "Your most-used emoji? Drop it below.",
    "Current mood in one word?",
]

# ─── Faction Warfare 2.0 ─────────────────────────────────────────────────
FACTION_WAR_CHALLENGE_CYCLE = [
    {"name": "Message Blitz",       "type": "messages",    "desc": "Most total messages wins."},
    {"name": "Quality Over Quantity","type": "starboard",   "desc": "Most Hall of Fame entries wins."},
    {"name": "Recruitment Drive",   "type": "invites",     "desc": "Most valid invites wins."},
    {"name": "Trivia Showdown",     "type": "trivia",      "desc": "Best trivia scores win."},
    {"name": "Voice Dominance",     "type": "voice",       "desc": "Most voice minutes wins."},
    {"name": "Social Web",          "type": "social",      "desc": "Highest friendship growth wins."},
]
FACTION_TERRITORY_BONUS = 0.05       # 5% bonus in controlled channels
FACTION_TREASURY_WAR_REWARD = 200    # Auto-deposit for weekly winner
FACTION_TEAM_BOOST_COST = 500
FACTION_SABOTAGE_COST = 300
FACTION_RECRUITMENT_COST = 200
FACTION_LOYALTY_THRESHOLDS = {50: "colored_name", 100: "strategy_channel", 200: "champion_badge", 500: "leader_nomination"}
FACTION_TRAITOR_COST = 1000
FACTION_TRAITOR_ROLE_DAYS = 7
FACTION_TRAITOR_LOCKOUT_DAYS = 14
FACTION_UNDERDOG_THRESHOLD = 0.6     # < 60% of largest = underdog
FACTION_UNDERDOG_BONUS = 0.15        # +15% bonus

# ─── Season Pass ─────────────────────────────────────────────────────────
SEASON_LENGTH_WEEKS = 8
SEASON_PASS_TIERS = 50
SEASON_PASS_PREMIUM_COST = 5000      # Circles (earned only)
SEASON_EARLY_BIRD_HOURS = 48
SEASON_EARLY_BIRD_MULT = 2.0

SEASON_FREE_REWARDS = {
    5:  {"type": "coins",  "value": 100},
    10: {"type": "badge",  "value": "season_badge"},
    15: {"type": "coins",  "value": 250},
    20: {"type": "banner", "value": "season_banner"},
    25: {"type": "coins",  "value": 500},
    30: {"type": "title",  "value": "season_title"},
    35: {"type": "coins",  "value": 750},
    40: {"type": "color",  "value": "season_color"},
    45: {"type": "coins",  "value": 1000},
    50: {"type": "badge",  "value": "season_champion"},
}

# ─── Prestige System ─────────────────────────────────────────────────────
PRESTIGE_MIN_RANK = 41               # Veteran I
PRESTIGE_MAX_LEVEL = 5
PRESTIGE_REWARDS = {
    1: {"coins": 2000,  "permanent_bonus": 0.05},
    2: {"coins": 5000,  "permanent_bonus": 0.10},
    3: {"coins": 10000, "permanent_bonus": 0.15},
    4: {"coins": 20000, "permanent_bonus": 0.20},
    5: {"coins": 50000, "permanent_bonus": 0.25},
}

# ─── Rank Perks (Status = Power) ─────────────────────────────────────────
RANK_PERKS = {
    "Rookie":    ["!profile", "!rank", "!daily", "!spin"],
    "Regular":   ["Poll voting", "Prompt submissions", "!setbio"],
    "Certified": ["Create Circles", "Be a mentor", "!setcolor (free first)", "Trivia submissions"],
    "Respected": ["Faction access", "!poll", "Hot Take submissions", "#vip-lounge"],
    "Veteran":   ["Declare rivals", "Spotlight nominations", "4h confession cooldown", "Prestige eligible"],
    "OG":        ["Profile frames", "Pin messages", "Named in announcements"],
    "Elite":     ["Host flash events", "2x mystery box odds", "Create 1 emoji/month"],
    "Legend":    ["Custom role name", "Permanent +5% bonus", "Legends Corner feature"],
    "Icon":      ["Personal text channel", "Custom Keeper greeting"],
    "Immortal":  ["Permanent Hall of Fame", "Set daily prompt 1x/month"],
}

# ─── Engagement Ladder ───────────────────────────────────────────────────
ENGAGEMENT_TIERS_DEFINITION = {
    "lurker":     {"msgs_week": 0,   "description": "Joined but silent"},
    "newcomer":   {"msgs_week": 5,   "description": "Finding their voice"},
    "casual":     {"msgs_week": 15,  "description": "Dropping in regularly"},
    "regular":    {"msgs_week": 50,  "description": "Part of the furniture"},
    "power_user": {"msgs_week": 100, "description": "The backbone"},
    "evangelist": {"msgs_week": 100, "description": "Spreading the word", "invites_min": 3},
}

# ─── Display Titles (Earned) ─────────────────────────────────────────────
DISPLAY_TITLES = {
    "the_confessor":  {"requirement": "25+ confessions",           "emoji": "🔮"},
    "silver_tongue":  {"requirement": "Top 3 debate score",        "emoji": "🗣️"},
    "the_connector":  {"requirement": "10+ strong friendships",    "emoji": "🤝"},
    "war_hero":       {"requirement": "4+ consecutive war wins",   "emoji": "⚔️"},
    "circle_builder": {"requirement": "10+ valid invites",         "emoji": "🏗️"},
    "the_immortal":   {"requirement": "Reach rank 91+",            "emoji": "👑"},
    "early_bird":     {"requirement": "Most 'First to Rise' in a month", "emoji": "🌅"},
    "meme_lord":      {"requirement": "Win Meme Friday bracket",   "emoji": "😂"},
}

# ─── Oracle Predictions (Evening Ritual) ─────────────────────────────────
ORACLE_PREDICTIONS = [
    "Tomorrow, a Frost member will surprise everyone.",
    "The Circle sees conflict in #politics. Prepare yourselves.",
    "Someone will break a personal record tomorrow. Will it be you?",
    "A confession will shake The Circle this week.",
    "The leaderboard will shift dramatically. Watch closely.",
    "A new friendship will form where you least expect it.",
    "The Circle grows stronger. But so does the competition.",
    "An old face returns. The Circle remembers.",
    "Tomorrow's prompt will divide The Circle. Choose wisely.",
    "A streak will break. The Circle mourns in advance.",
    "Inferno burns brighter this week. Or does it?",
    "The jackpot grows heavy. Someone will claim it soon.",
    "A meme of legendary proportions approaches.",
    "The top 3 should watch their backs tomorrow.",
    "Voice channels will be louder than usual. Join or miss out.",
    "A mystery box holds something special today. Trust the odds.",
    "The Circle sees a newcomer destined for greatness.",
    "Two rivals will clash. The server will watch.",
    "The weekly goal is within reach. Push harder.",
    "Something unprecedented happens tomorrow. Keeper has spoken.",
]

# ─── Hidden Moderation ───────────────────────────────────────────────────
MOD_REPUTATION_START = 100.0
MOD_REPUTATION_MAX = 150.0
MOD_REPUTATION_WARN_THRESHOLD = 70
MOD_REPUTATION_SLOW_THRESHOLD = 50
MOD_REPUTATION_MUTE_THRESHOLD = 30
MOD_REPUTATION_MUTE_HOURS = 1

# ─── Monthly Mega Events ─────────────────────────────────────────────────
MEGA_EVENT_ROTATION = [
    {"name": "The Purge",        "week": 1,  "duration_days": 3},
    {"name": "The Circle Games", "week": 2,  "duration_days": 5},
    {"name": "Community Build",  "week": 3,  "duration_days": 7},
]

# ─── Seasonal Themes ─────────────────────────────────────────────────────
SEASONAL_THEMES = {
    1: {"name": "The Awakening", "focus": "goal-setting"},
    2: {"name": "The Rivalry",   "focus": "faction-wars"},
    3: {"name": "The Gathering", "focus": "social-voice"},
    4: {"name": "The Reckoning", "focus": "annual-awards"},
}
