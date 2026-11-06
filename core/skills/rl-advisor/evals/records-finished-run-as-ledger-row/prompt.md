---
tags: [rl-advisor]
max_turns: 25
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash]
---

I'm in ~/projects/aquila. Two teacher runs just finished on the box: the baseline wave and the same wave with a new teacher action-noise lever from branch `teacher-actnoise` (not merged). Here are the bits of the two gate files that matter:

baseline, box `~/aquila/verro/runs/actnoise_base/gate_wave0.json` (mean of the per-teacher `returns_mean`: 571.2): `{"gate_return": 300.0, "gate_episodes": 100, "num_passed": 61, "num_total": 64, "num_dead": 0, "provenance": {"git_sha": "3f2a9c1", "git_branch": "teacher-actnoise", "git_dirty": false, "hostname": "ruhalis-home", "argv": ["scripts/train_teachers.py", "--wave", "0", "--seed", "0", "--cuda-graph", "full", "--fused-adam", "--out", "runs/actnoise_base"]}}`

lever, box `~/aquila/verro/runs/actnoise_on/gate_wave0.json` (mean of the per-teacher `returns_mean`: 586.4): `{"gate_return": 300.0, "gate_episodes": 100, "num_passed": 63, "num_total": 64, "num_dead": 0, "provenance": {"git_sha": "3f2a9c1", "git_branch": "teacher-actnoise", "git_dirty": true, "hostname": "ruhalis-home", "argv": ["scripts/train_teachers.py", "--wave", "0", "--seed", "0", "--cuda-graph", "full", "--fused-adam", "--teacher-act-noise", "0.05", "--out", "runs/actnoise_on"]}}`

The run finished, produce the ledger row and its EVIDENCE entry so I can paste them. Don't edit any files, just give me the text.
