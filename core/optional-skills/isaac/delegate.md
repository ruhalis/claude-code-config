# Isaac Lab 3.0 rules for agents working without the isaac skill

Read this before you write, check or run Isaac code in this project. The project's `CLAUDE.md` (and the
Isaac subproject's own `CLAUDE.md`, if it has one) wins where it is more specific.

**Targets.** Isaac Lab 3.0.0, Isaac Sim 6.2.0 (Kit path only), Python 3.12, rsl-rl-lib 5.x. Confirm the pin
in the Isaac subproject's `pyproject.toml`/`uv.lock`; if it differs, stop and report it. Most Isaac code on
the web and in your training data is 2.x and wrong here.

**3.0 facts that 2.x habits get wrong**
- Quaternions are **xyzw** in all Lab code and `.data`; identity `(0, 0, 0, 1)`. A 2.x `(1, 0, 0, 0)` is a
  180° turn and raises no error. Raw `isaacsim.core.experimental` is still wxyz, and so may be a project's
  own contract (aquila's obs contract is w, x, y, z): convert at the boundary.
- `.data.*` returns `ProxyArray`: use `.torch`. Writers are `write_*_to_sim_index(..., env_ids=)` or
  `write_*_to_sim_mask(..., env_mask=)`; joint targets go through
  `robot.actuators.target_command.set_*_index(...)`; `root_physx_view` is `root_view`.
- Launch with `add_launcher_args` + `with launch_simulation(env_cfg, args_cli):`, not `AppLauncher`.
  `omni.*`, `isaacsim.*` and `carb` imports go inside that block (they exist only with Kit).
- The physics backend is a `PresetCfg` in `SimulationCfg(physics=...)`, picked with `physics=<name>`.
- Actuator limits: `joint_effort_limit` / `joint_velocity_limit`, not `effort_limit_sim` / `velocity_limit_sim`.
- PPO cfg: `actor`/`critic` `RslRlMLPModelCfg`, not `policy=RslRlPpoActorCriticCfg`.
- Task packages only `gym.register` lazy strings and stay importable without Isaac Lab; the CLI finds them
  through the `isaaclab.tasks` entry point.
- CLI: `isaaclab train|play|zero_agent|list_envs --rl_library rsl_rl`. There is no `--headless` (headless is
  the default; `--viz none|kit|newton_gl`), no `--enable_cameras`, no `--resume`/`--load_run` (use
  `--checkpoint <path|run dir|latest>`), no per-library `train.py`.

**Running**
- Run from the Isaac subproject's directory (aquila: `isaac/`, berkley: `lab/`) in its uv env. On the Linux
  box every `uv run` takes the extra the env was synced with, or `--no-sync`, as that project's CLAUDE.md
  says: a bare `uv run` re-syncs and silently swaps torch or numpy under Isaac Sim. `isaaclab.sh` and
  Isaac Sim's `python.sh` are the only launchers outside `uv`.
- Anything that starts Kit or imports `isaacsim` needs `OMNI_KIT_ACCEPT_EULA=YES` on a headless box. That
  includes every berkley run, whose default backend is `isaacsim_physx`; aquila is Newton-only (no PhysX
  presets or imports).
- The Isaac extras are Linux-only. On the Mac, don't sync them or import `isaaclab`.

**Hard limits**
- Never launch Isaac Lab or Isaac Sim just to test an edit. Check statically, unless your brief explicitly
  asks for a run on the box:
  `python3 "$(git rev-parse --show-toplevel)/.claude/skills/isaac/scripts/check_isaac_code.py" <files or dirs>`
  Exit 0 is clean; fix each `path:line: ISCnnn` finding or say why it is a false positive. Use python3 3.12
  or newer, or 3.12-only syntax may be flagged.
- Training runs, sweeps and anything that holds the GPU past a smoke test happen only when the brief asks
  for them, one GPU job at a time.
- Never edit an installed or vendored Isaac Lab (`site-packages/isaaclab*`, a checkout, `external/`,
  `third_party/`). Extend it in the project package.
- Don't install, add or re-sync packages in the Isaac env (`uv add`, `uv sync --extra ...`, `pip`) unless
  the brief says to.

**Report** the checker's result, any API you could not confirm against the 3.0.0 source, and every command
you ran on the box.
