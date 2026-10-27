---
tags: [rl-advisor]
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

Quick sanity check on an RL result before I put it in the weekly update. I trained a PPO locomotion policy in Isaac Lab with the new reward weights, saved a checkpoint every 100 iterations, evaluated all 20 checkpoints, and the best one gets 0.86 success vs the old policy's 0.78 (the old number is from its final checkpoint, single eval). Each eval is 32 episodes. Can I say the new reward is better? If not, what do I need to run?
