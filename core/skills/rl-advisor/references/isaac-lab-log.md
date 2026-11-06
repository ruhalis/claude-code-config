# Run log for Isaac Lab and repos without a ledger: entry template, run dirs, the Changed check

Used by SKILL.md's record step when the repo keeps no ledger of its own (no `## Experiments` section in CLAUDE.md
and no `Decision ledger`), typically an Isaac Lab rsl_rl / skrl run (cooper, berkley). aquila does not use this
template: its record step is `aquila-map.md` §13 (manifest + gate file → ledger row + EVIDENCE §9). The rules that
apply to every repo (one variable, task metric, noise floor, sim-to-real entry, frozen verdicts) are in SKILL.md;
this file holds the template and the Isaac Lab mechanics.

Contents: 1 Start entry · 2 Code, run-id and run dir · 3 Filling and checking it from the config dump · 4 Result block · 5 Isaac Lab rules · 6 Example (cooper) · 7 Remote host

## 1. Start entry

Add one entry to the resolved log:

```
## <run-id> — <YYYY-MM-DD HH:MM> — <one-line hypothesis>
- Base: <previous run-id or "fresh">
- Changed: <exactly what differs from base, config as env.<path>: old → new — reward term/weight/params or reward code, obs, curriculum, domain rand, hyperparam, inputs, stack>
- Code: <task repo>@<git rev-parse --short HEAD>[-dirty] (<branch>)[; uncommitted edits in <run dir>/task_repo.diff]
- Stack: Isaac Sim <x> / Isaac Lab <tag|commit> / rsl-rl-lib <ver> (no Isaac: torch <ver>)
- Inputs: <init checkpoint path + producing run-id or sha256 | scratch>; dataset path (e.g. datasets/expert_demos.npz); reference motion as the resolved W&B artifact version (:vN, never :latest)
- Env: <task name>, num_envs, episode length, sim dt / decimation
- Obs/Act (optional): <obs terms + dim; action type + scale>
- Algo: <PPO/SAC/…> + key hparams as named in the config; for BC/DAgger: N demos, epochs, val loss
- Reward terms: name → weight {non-default params} (full list, even unchanged)
- Curriculum: <term: what ramps, from→to, over which steps>
- DR: <term: range>
- Seed(s):
- Command: <exact train command, including every env var the launcher reads, e.g. BC_CKPT=… BC_INIT_STD=0.1 BC_GRIP_STD=1.0 …; redact secrets such as WANDB_API_KEY>
- Run dir: <host>:<absolute run dir>[; W&B <entity>/<project>, run <name>]
- Expected: <what task metric should move, by how much, by which iteration>
```

## 2. Code, run-id and run dir

Code is the task repo as checked out on the training host, not Isaac Lab; add `-dirty` when `git status --porcelain` is not empty. A dirty tree's code edits (function bodies, the constants they read, new files) reach neither params/ nor git, so right after launch, before touching the tree, save them: `git -C <repo> diff HEAD > <run dir>/task_repo.diff; git -C <repo> status --porcelain > <run dir>/task_repo.status` (untracked files show there by name only; commit or copy them). rsl_rl's own `<run dir>/git/*.diff` covers only Isaac Lab and rsl_rl. Stack also comes from the training host: `<venv>/bin/python -m pip list | grep -iE '^(isaacsim|rsl-rl-lib|skrl|torch) '`, plus `VERSION` and `git rev-parse --short HEAD` in the Isaac Lab checkout that venv imports (`python -c 'import isaaclab; print(isaaclab.ISAACLAB_EXT_DIR)'` prints its `source/isaaclab`).

The run-id is `<short-task-slug>-<NNN>` (e.g. `pick-ik-004`), where NNN is the highest number already in that log plus 1. Put it in the run dir's name:
- rsl_rl: `--run_name <run-id>` gives `logs/rsl_rl/<experiment_name>/<YYYY-MM-DD_HH-MM-SS>_<run-id>` under the launch directory. With `--logger wandb` the W&B run takes that directory's name, the project is `--log_project_name` (agent.yaml `wandb_project`), the entity `$WANDB_USERNAME` or the account default.
- skrl: the Hydra override `agent.agent.experiment.experiment_name=<run-id>` gives `logs/skrl/<experiment.directory>/<timestamp>_<algo>_<ml_framework>_<run-id>`.
- A custom trainer (e.g. aquila's, which records differently: `aquila-map.md` §13): Run dir is wherever it writes.

## 3. Filling and checking it from the config dump

Fill Env through Seed(s) from the run's own config dump, not by walking the cfg inheritance chain: Isaac Lab's train.py writes `<run dir>/params/env.yaml` (`rewards:`, `curriculum:`, `events:`, `scene.num_envs`, `sim.dt`, `decimation`, `episode_length_s`, `seed`) and `params/agent.yaml` (Algo) at launch. Their `!!python/tuple` and `!!python/object/apply:builtins.slice` tags make `yaml.safe_load` and `yaml.full_load` (Isaac Lab's own `load_yaml`) fail, so read them as text or run `scripts/rl_log_entry.py <run dir> [--base <base run dir>] [--ignore seed]`, which prints the lines they can fill and, with `--base`, the Changed line. It needs PyYAML, which the Isaac Lab venv has and the Mac's system python3 lacks (exit 3), so pipe it to the training host: `ssh <host> '<venv>/bin/python - <run dir> --base <base run dir>' < "${CLAUDE_SKILL_DIR}/scripts/rl_log_entry.py"` (`${CLAUDE_SKILL_DIR}` is the rl-advisor skill's directory). It is validated only on synthetic run dirs written by Isaac Lab 2.3.2's own dump code; check its first real output against the yaml.

Once the run dir exists, check that Changed is the only difference from Base: `diff -u <base run dir>/params/env.yaml <new run dir>/params/env.yaml` and the same for agent.yaml (dumped in cfg order, so the lines pair up), or `rl_log_entry.py <new run dir> --base <base run dir>`, plus `git -C <task repo> diff --stat <base sha>..<new sha>` from the two Code lines. A `-dirty` side's config edits show only in the params diff and its code edits in neither, so also `diff` the two runs' task_repo.diff files. Ignore log_dir, run_name, the logging backend (logger, wandb_project, neptune_project; skrl: experiment.directory, experiment_name, write_interval, wandb, wandb_kwargs), which the script leaves out, and seed when the seed is the declared change. Unless the entry is a declared sweep, every other difference goes on a `- Confounded: <each undeclared difference>` line under Changed, and the Verdict then judges the bundle, never the declared change alone.

An entry is open until it has a Verdict. Fill its result block under its own heading, not at the end of the file, replacing any `pending` values once the numbers arrive. After the Verdict it is frozen; corrections go in a new entry with `Base: <run-id> (correction)`.

## 4. Result block

Fill in under the entry's own heading:

```
- Result: <task metric that does not depend on reward weights (success/lift rate, Metrics/<cmd>/error_*, gate return under a fixed eval reward), with the exact logged tag and iteration or the eval output line, the checkpoint (final/best), and the eval protocol (N episodes, play env, deterministic, seed)>; wall time, GPU; train mean_reward is secondary only
- Verdict: keep / discard / inconclusive — one sentence why
- Next: <the single next change>
```

If asked to summarise, produce a table of run-id | changed | key metric | verdict from the log, where key metric is the task metric from Result, then a short read of the trend.

## 5. Isaac Lab rules

- A stack bump (Isaac Sim, Isaac Lab, rsl-rl-lib/skrl, torch) is its own run: Changed is the bump and nothing else, Base is the last run on the old stack.
- Never compare Train/mean_reward or Episode_Reward/* across runs whose reward weights or params differ; Isaac Lab multiplies each term by its weight before logging. The Verdict must cite the task metric; if the run is closed without one, the Verdict is inconclusive.
- Before proposing a reward change, check the log for the last time that term was touched (a params-only change counts) and what happened. If no log entry covers the term, check `git log -L '/[^_[:alnum:]]<term>[^_[:alnum:]].*=/,/^ *)/:<reward/env cfg file>'` (the range ends at the term's closing paren) (`git log -S'<term>'` only finds where the term was added or removed), the comments next to the term, and the project ledger before proposing.

## 6. Example (cooper)

A filled entry from cooper's history, before it kept a log (abridged; run-ids illustrative, `?` = not recorded at the time). The recorded run also changed the curriculum, so it shows the Confounded line too:

```
## pick-rl-003 — 2026-06-?? — halving grasp_object makes parking unprofitable, so PPO lifts
- Base: ? (a grasp_object 2.0 run: rollout VERDICT EXPLORATION, 0/32 lifted)
- Changed: env.rewards.grasp_object.weight: 2.0 → 1.0
- Confounded: same launch changed the grasp-state reset curriculum (base ?: attempt 1 had none, attempt 2 injected aloft with a fast anneal; now table level, HELD_* re-measured, anneal to iter 1125)
- Code: cooper@2cf7f32-dirty (main); task_repo.diff not saved
- Stack: Isaac Sim 5.1 / Isaac Lab v2.3.2 (37ddf62) / rsl-rl-lib 3.1.2
- Inputs: scratch
- Env: Isaac-Pick-MyCobot280-RL-v0, 2048 envs, 5.0 s, sim dt 0.005 / decimation 4
- Algo: PPO, learning_rate 5e-5 adaptive (desired_kl 0.01), entropy_coef 0.006, clip 0.2, gamma 0.98, lam 0.95, 24 steps × 1500 it, 5 epochs × 4 mini-batches, [256, 128, 64] elu, log std
- Reward terms: reaching_object_fine → 4.0 {std 0.025}; grasp_object → 1.0 {threshold 0.03}; object_lift_progress → 8.0 {rest_height 0.02, max_height 0.15, threshold 0.06}; + the 6 inherited Lift terms (abridged here)
- Curriculum: lift_height minimal_height 0.04 → 0.075 over steps 1500 → 9000; Lift penalty ramps off; grasp-state injection annealed out by iter 1125
- DR: robot + object friction (30, 30) at startup; cube reset x/y ±0.03 m
- Seed(s): ? (42 without --seed), one run
- Command: OMNI_KIT_ACCEPT_EULA=YES ~/isaac/venv/bin/python sim/rl/train_rl.py --task Isaac-Pick-MyCobot280-RL-v0 --headless --num_envs 2048 --run_name pick-rl-003
- Run dir: ?:/home/rassul_pc/cooper/logs/rsl_rl/mycobot280_pick/2026-06-??_??-??-??_pick-rl-003
- Expected: rollout "envs that EVER lifted" above 0/32 by the final checkpoint
- Result: sim/diagnostics/rollout_pick_policy.py, model_?.pt, Play env, 32 envs × 260 steps, deterministic: "envs that EVER lifted cube >50mm : 0/32" (Episode_Reward/lifting_object 0.28 while injecting, 0.009 after); wall ?, RTX 5080
- Verdict: inconclusive — confounded, one seed, 0/32 on both sides
- Next: IL warm start (scripted IK expert → BC → PPO fine-tune)
```

## 7. Remote host

- Run artifacts on a remote training host: ask the user for the run-dir listing, the final scalars and `git -C <repo> rev-parse --short HEAD && git -C <repo> status --porcelain` from the host, or rsync the run's config dump and logs (Isaac Lab: `params/` + `events.out.tfevents.*`). Never invent numbers; write `Result: pending (on <host>:<path>)` and leave the entry open. Without the host's sha, write `Code: unknown (local <sha>)`.
- Task metric never evaluated and the run is being closed anyway: Next is the eval to run.
