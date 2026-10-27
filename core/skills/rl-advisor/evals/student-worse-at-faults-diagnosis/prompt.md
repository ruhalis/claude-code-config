---
tags: [rl-advisor]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

Working in ~/projects/aquila. I want to make the GRU student more robust to motor faults, so my plan is to re-distill it with per-episode rotor-effectiveness faults up to 0.4 switched on during the DAgger rollouts, using the clean teacher bank. Before I burn 4 GPU hours: is this likely to work, and why or why not? Give me the RL reasoning and what our own evidence says.
