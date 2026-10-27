---
tags: [rl-advisor]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

I'm in ~/projects/aquila. Someone on the team wants to drop the target-network polyak averaging in our SAC teachers (verro/verro/rl/sac.py) and just bootstrap from the live critics to "speed up learning". Explain what that risks, with the theory behind it from Sutton and Barto, and tell me what in our pipeline is currently holding that risk in check. Keep it to what I need to push back in a review.
