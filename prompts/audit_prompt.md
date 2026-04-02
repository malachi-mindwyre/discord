# Engagement Audit — Initiation Prompt

Use this prompt to start a new Claude Code chat that audits the engagement systems:

---

Read @CLAUDE.md thoroughly first — it contains the complete documentation of this Discord bot project (44 cogs, 6-layer scoring engine, ~16,000 lines of code).

Then read @prompts/engagement_prompt.md — this is the expert system prompt defining what a world-class engagement system looks like, including the 12 domains that must be covered and the quality bar (behavioral principles, math, anti-churn integration, interaction effects).

Now audit the actual implementation. Read these core files to understand what's actually built:
- @scoring.py (6-layer scoring formula)
- @config.py (all 800+ lines of constants and engagement parameters)
- @cogs/scoring_handler.py (how scoring context is gathered)
- @cogs/variable_rewards.py (dopamine engine)
- @cogs/onboarding_v2.py (7-day onboarding pipeline)
- @cogs/reengagement.py (8-tier anti-churn pipeline)
- @cogs/loss_aversion.py (decay, demotion, displacement)
- @cogs/social_graph.py (friendship tracking, rivals, icebreakers)
- @cogs/streaks_v2.py (5 streak types + freezes + pairs)
- @cogs/season_pass.py (battle pass)
- @cogs/content_engine.py (Quick Fire, UGC, trending, dead zone)

Then produce a comprehensive audit report:

1. **Coverage Assessment:** Map every system in the codebase against the 12 domains in the engagement prompt. What's covered? What's missing? What's partially implemented?

2. **Behavioral Science Gaps:** For each implemented system, assess whether the behavioral principle is correctly applied. Are there psychology mistakes? Missed opportunities? Systems that could backfire?

3. **Mathematical Critique:** Evaluate the scoring formula, progression curve, reward probabilities, and timing parameters. Are the numbers well-tuned or do any feel off? Would the diminishing returns curve feel punishing? Is the jackpot trigger rate too low/high?

4. **Interaction Effects:** Which systems amplify each other well? Which might conflict? Are there perverse incentives (e.g., ways to game the system)?

5. **Cold Start Problem:** With 10-50 members, which systems will feel alive and which will feel empty? What needs to change for small populations?

6. **Top 10 Highest-Impact Improvements:** Ranked by expected retention impact, what should be built or changed next? Be specific with implementation details.

7. **Known Issues Check:** CLAUDE.md lists 10 known issues. Which are the most critical to fix first?

Be ruthlessly honest. The goal is to find every weakness before real users do.
