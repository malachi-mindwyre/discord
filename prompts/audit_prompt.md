# Engagement Audit — Initiation Prompt

Use this prompt to start a new Claude Code chat that audits the engagement systems:

---

Read @CLAUDE.md thoroughly first — it contains the complete documentation of this Discord bot project (48 cogs, 6-layer scoring engine, ~18,000 lines of code).

Then read @prompts/engagement_prompt.md — this is the expert system prompt defining what a world-class engagement system looks like, covering 12 domains with behavioral science, math, and anti-churn requirements.

Then read @prompts/audit_prompt.md for the full audit instructions.

Current status: all 48 cogs loaded, all 23 health checks passing, all background tasks running, bot is live on Raspberry Pi. Zero errors in logs.

Now audit the actual implementation. Read these core files to understand what's actually built:
- @scoring.py (6-layer scoring formula)
- @config.py (all 900 lines of constants and engagement parameters)
- @cogs/scoring_handler.py (scoring context, Welcome Wagon, conversation starter, mega event integration)
- @cogs/variable_rewards.py (dopamine engine + scaled jackpot for small servers)
- @cogs/onboarding_v2.py (7-day onboarding pipeline + DM coordinator)
- @cogs/reengagement.py (8-tier anti-churn pipeline, corrected comeback multiplier copy)
- @cogs/loss_aversion.py (decay, demotion, displacement + DM coordinator)
- @cogs/social_graph.py (friendship tracking, rivals, icebreakers)
- @cogs/streaks_v2.py (5 streak types + freezes + pairs)
- @cogs/season_pass.py (battle pass, rebalanced XP curve)
- @cogs/content_engine.py (Quick Fire, UGC, trending, dead zone + quiet mode)
- @cogs/weekly_recap.py (Sunday Ceremony, suppressed empty sections)
- @cogs/mega_events.py (monthly: The Purge, Circle Games, Community Build)
- @cogs/time_capsules.py (90-day sealed messages)
- @dm_coordinator.py (cross-cog DM rate limiting: 1/12h, 3/7d)

**Previous audit findings that have been fixed (do NOT re-report these):**
- Comeback multiplier DMs now correctly show 3x/5x/3x per tier (not all "5x")
- Day 14 DM no longer falsely claims score is decaying (decay starts Day 30)
- Season pass XP curve rebalanced (base 1.045, completable in 8 weeks)
- Season XP uses pre-diminishing-returns score so active users aren't penalized
- Global DM coordinator prevents cross-cog DM fatigue (1/12h, 3/7d limits)
- Dead zone detection has quiet mode at <15 members (requires 2+ recent users)
- Weekly recap suppresses empty sections (social bonds <25, factions <2 active teams)
- Jackpot trigger rate doubles at <100 members for faster first jackpot
- Welcome Wagon: +10 pts for replying to new members' first messages
- Conversation Starter: +25 pts retroactive bonus when messages spark 3+ replies
- Monthly mega events implemented (The Purge, Circle Games, Community Build)
- Time capsule system built (!timecapsule, !capsules, 90-day reveal)

Then produce a comprehensive audit report:

1. **Coverage Assessment:** Map every system in the codebase against the 12 domains in the engagement prompt. What's covered? What's missing? What's partially implemented?

2. **Behavioral Science Gaps:** For each implemented system, assess whether the behavioral principle is correctly applied. Are there psychology mistakes? Missed opportunities? Systems that could backfire?

3. **Mathematical Critique:** Evaluate the scoring formula, progression curve, reward probabilities, and timing parameters. Are the numbers well-tuned or do any feel off? Would the diminishing returns curve feel punishing? Is the jackpot trigger rate too low/high?

4. **Interaction Effects:** Which systems amplify each other well? Which might conflict? Are there perverse incentives (e.g., ways to game the system)?

5. **Cold Start Problem:** With 10-50 members, which systems will feel alive and which will feel empty? What needs to change for small populations?

6. **Top 10 Highest-Impact Improvements:** Ranked by expected retention impact, what should be built or changed next? Be specific with implementation details.

7. **Known Issues Check:** CLAUDE.md lists known issues. Which are the most critical to fix first?

Be ruthlessly honest. The goal is to find every weakness before real users do.
