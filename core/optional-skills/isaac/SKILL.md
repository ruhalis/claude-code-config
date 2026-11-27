---
name: isaac
description: Isaac Lab 3.0.0 / Isaac Sim 6.2.0 rules for writing, porting, checking or running this project's Isaac code (isaaclab imports, DirectRLEnv, ManagerBasedRLEnv, PresetCfg, the isaaclab CLI, SimulationApp). Most Isaac material is 2.x and wrong for 3.0. Use this, not the nvidia-skills Isaac or Newton skills, for this project's Isaac Lab code.
compatibility: Isaac runs on Linux with an NVIDIA GPU (Turing or newer, driver 580.65+) in a Python 3.12 uv environment, with Isaac Sim 6.2.0 only for the Kit path. On macOS, author and check statically only.
metadata:
  isaac-lab-version: "3.0.0"
  isaac-sim-version: "6.2.0"
---

# Isaac Lab 3.0 / Isaac Sim 6.2

Lab 3.0 is a different API from 2.x: kit-less Newton physics by default, xyzw quaternions, `ProxyArray` data, `_index`/`_mask` writers, the `isaaclab` CLI. Most tutorials, answers and examples are still 2.x, and so is much of what you remember, so check names against the pinned source (last verified 2026-11-06). Several facts here, the launch lines and the code-server client among them, were read from the source and not yet confirmed on the box; say so when one of them matters.

## The two projects

Both pin `isaaclab==3.0.0` and `isaacsim 6.2.0.0` (with newton 1.6.1, rsl-rl-lib 5.5.1, torch 2.11.0 cu130) in an Isaac subproject that is its own uv project. Their `CLAUDE.md` files hold the details and win over this table; read them first.

| | aquila | berkley |
|---|---|---|
| Isaac subproject | `isaac/` (`isaac_l2f`, `isaac_city`), rules in `isaac/CLAUDE.md` | `lab/` (`bhl_lab`), rules in the root `CLAUDE.md` |
| Extras on the box | `isaac` (Newton, no Kit) or `isaacsim` (Kit, RTX render), mutually exclusive | `isaacsim` only |
| Every `uv run` on the box | `--extra <synced one>` or `--no-sync` | `--extra isaacsim --no-sync` |
| Backend | Newton only (`newton_mjwarp`): no PhysX presets or imports | Preset default `isaacsim_physx` (Kit, so every run needs the EULA variable); `physics=newton_mjwarp` selectable; Kit RTX for recording |

If either project moves off 3.0.0 / 6.2.0, stop and say so before generating code: code written for one major version fails on the other. A 2.x codebase is ported, not patched (`reference/import-migration.md`).

## Boundaries

- **Isaac is not launched to test an edit.** Check statically (Verify, below). Run on the box only when the user or the brief asks for it. Training runs, sweeps and demo collection go to the `verifier` agent or the user; before one starts, state the task, `--num_envs`, `--max_iterations` and the expected wall time.
- **Don't change the Isaac environment unasked.** Lab 3.0.0 pins torch 2.11.0 (cu130) and Isaac Sim pins numpy, urllib3 and more; the subproject's `pyproject.toml` carries the overrides that make them resolve. No `uv add`, `uv sync --extra ...`, `pip install` or installer workflow (`isaaclab --install`, `isaaclab --new`, which writes a new repo) unless asked. A bare `uv run` on the box re-syncs to the default extras and swaps packages under Isaac Sim, which is why every project passes `--extra`/`--no-sync`.
- **Never edit an installed or vendored Isaac Lab** (`site-packages/isaaclab*`, a checkout, a submodule such as berkley's `external/`). Extend it in the project package: subclassed cfgs, own `mdp` terms, own `PresetCfg`s. Bumping the pin is the user's call.
- **Keep the code-execution server on 127.0.0.1** (Live Kit, below). It runs any Python it receives.
- **The Mac never runs Isaac.** Isaac Lab 3.0 is Linux-only (x86_64 or aarch64, CUDA 13 by default). On the Mac, write the code, check it statically and hand over the commands for the box; don't sync the Isaac extras or import `isaaclab`/`isaacsim`.

## When delegating

Subagents that write, check or run Isaac code can't load this skill. Tell the agent to read `.claude/skills/isaac/delegate.md` (at the repo root of aquila or berkley) before it starts; it carries the version targets, the 3.0 facts 2.x habits get wrong, the launch rules, the static checker and the hard limits. Name in the brief whether a run on the box is wanted: without that, the agent checks statically only.

## Checking APIs against the source

Grep the Lab source for every class, cfg field, kwarg and flag you use, and cite `file:line` (e.g. `source/isaaclab/isaaclab/app/sim_launcher.py:595`). On the box the installed package under `.venv/lib/python3.12/site-packages/` is that source. Otherwise clone the pinned tags into a temp dir, not into the user's repo:

```bash
SRC="${TMPDIR:-/tmp}/isaac-src"; mkdir -p "$SRC"
[ -d "$SRC/IsaacLab-3.0.0" ] || git clone -q --depth 1 --branch v3.0.0 https://github.com/isaac-sim/IsaacLab "$SRC/IsaacLab-3.0.0"
# Isaac Sim (only for raw isaacsim.* code) is large: sparse clone, then add the extensions you need
[ -d "$SRC/IsaacSim-6.2.0" ] || git clone -q --depth 1 --branch v6.2.0 --filter=blob:none --sparse https://github.com/isaac-sim/IsaacSim "$SRC/IsaacSim-6.2.0"
```

The checkout's `skills/user/` (upstream agent skills) and `docs/source/` go deeper than this skill; where they disagree with the source, the source wins (some pages still show `--headless`, `--enable_cameras`, `--resume --load_run`). Pinned docs: https://isaac-sim.github.io/IsaacLab/v3.0.0/index.html and https://docs.isaacsim.omniverse.nvidia.com/6.2.0/index.html (not `main` or `latest`, which drift past the pin).

## Execution model

Train, play, smoke tests and task listing need no script: `uv run isaaclab <cmd>`. A custom eval, recording or bounded run on a registered task is a Lab script (`add_launcher_args` + `with launch_simulation(env_cfg, args_cli):`, `templates/lab_app_script.py`); scene or USD work with no Lab is raw Isaac Sim (`from isaacsim import SimulationApp`, `templates/standalone_isaac.py`). Copy the template rather than writing launch boilerplate from memory.

**Kit vs kit-less.** `launch_simulation` starts Omniverse Kit only when the cfg needs it: Isaac Sim PhysX (`physics=isaacsim_physx`), a Kit/RTX camera renderer, `--viz kit`, `--livestream`, `--experience`, XR. Newton (`newton_mjwarp`, the stock default) with the Newton Warp renderer runs without Isaac Sim installed (`sim_launcher.py:595`). OvPhysX/OVRTX are kit-less only and can't share a process with Kit. `AppLauncher` is a deprecated adapter that always forces Kit.

**Import order.** Before the launch: `isaaclab`, `isaaclab.app`, `isaaclab.sim`, `isaaclab.utils` (incl. `.assets`, kit-less safe in 3.0), `isaaclab_tasks`, cfg modules and task packages that only `gym.register` lazy strings. Inside the `with` block: `gym.make` and every `omni.*`, `isaacsim.*` and `carb` import; those exist only with Kit, so Kit-only code also breaks a kit-less Newton run. Raw `SimulationApp` scripts keep the old rule: nothing but `from isaacsim import SimulationApp` above `SimulationApp(...)`, `pxr` included.

## Version-correct imports

```python
from isaaclab.app import add_launcher_args, launch_simulation     # not AppLauncher
import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg   # backend-neutral
from isaaclab.envs import DirectRLEnv, DirectRLEnvCfg, ManagerBasedRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAACLAB_NUCLEUS_DIR
from isaaclab_tasks.utils import PresetCfg, parse_env_cfg
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg     # Newton (kit-less)
from isaaclab_physx.physics import PhysxCfg                        # Isaac Sim PhysX (Kit); never in aquila
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg, RslRlMLPModelCfg
```

Stock `isaaclab_assets` robot cfgs import `isaaclab_physx` schema fragments since 3.0.0, so a Newton-only project declares its assets itself. Raw Isaac Sim 6.2: `isaacsim.core.api` (World) is deprecated, use `isaacsim.core.experimental.*`, whose quaternions are **wxyz**. `omni.usd`, `omni.kit.*`, `carb`, `pxr` and `warp` did not rename. Sensor cfgs and their backend support: `reference/common-cfgs.md`. Old → new names: `reference/import-migration.md`.

## Envs and task registration

Follow whichever workflow the project uses: `DirectRLEnv` (one class; `_setup_scene` optional when the scene cfg holds everything; ids end in `-Direct`) or `ManagerBasedRLEnv` (managers declared as configclass terms). The backend is data: a `PresetCfg` subclass in `SimulationCfg(physics=...)` with one field per backend and a `default`, picked with `physics=<name>`. Templates: `templates/direct_rl_env.py`, `templates/manager_based_env.py`.

A task is a `gym.register()` in the task package's `__init__.py`, all lazy strings, with `env_cfg_entry_point`, `rsl_rl_cfg_entry_point` and `default_agent: "rsl_rl"` (lets the CLI skip `--rl_library`); 3.0 ids carry no `-v0` (`templates/task_register.py`). Agent cfgs sit in a sibling `agents/` package in rsl-rl-lib 5.x style: `actor`/`critic` `RslRlMLPModelCfg`, not `policy=RslRlPpoActorCriticCfg` (`templates/agents/rsl_rl_ppo_cfg.py`).

Discovery is the `isaaclab.tasks` entry point in `pyproject.toml` (both projects have one). `isaaclab train|play|zero_agent|random_agent|list_envs` load every entry point before the id lookup (`isaaclab/cli/__init__.py:39`); a plain `import isaaclab_tasks` or your own script does not, so import the task package there or call `isaaclab.cli.load_external_tasks()`. The entry-point module must stay importable without Isaac Lab.

## Run commands (on the box)

Run from the Isaac subproject in its uv env, with the `--extra`/`--no-sync` the project names. `./isaaclab.sh` is deprecated in 3.0 and forwards to the same CLI. Anything that starts Kit or imports `isaacsim` needs `OMNI_KIT_ACCEPT_EULA=YES` on a headless box, or the EULA prompt crashes on EOF. Examples with berkley's task, whose default backend starts Kit:

```bash
cd lab   # berkley's Isaac subproject; aquila's is isaac/
export OMNI_KIT_ACCEPT_EULA=YES
uv run --extra isaacsim --no-sync isaaclab list_envs --keyword BHL --show_presets
uv run --extra isaacsim --no-sync isaaclab zero_agent --task Isaac-Velocity-Flat-BHL-Biped --num_envs 16 --max_steps 200 --viz none
uv run --extra isaacsim --no-sync isaaclab train --rl_library rsl_rl --task Isaac-Velocity-Flat-BHL-Biped --num_envs 4096 --max_iterations 1500 --seed 42
uv run --extra isaacsim --no-sync isaaclab play --rl_library rsl_rl --task Isaac-Velocity-Flat-BHL-Biped --num_envs 32 --checkpoint latest --viz kit
# Another backend: a Hydra token after the flags, no dashes
uv run --extra isaacsim --no-sync isaaclab train --rl_library rsl_rl --task Isaac-Velocity-Flat-BHL-Biped physics=newton_mjwarp
```

A smoke test passes when `zero_agent` prints the observation and action spaces and steps to `--max_steps` without a traceback; hand over the train command only after that. rsl_rl runs land in `logs/rsl_rl/<experiment_name>/<timestamp>[_<run_name>]/` with the resolved cfgs in `params/`. Starting or changing a training run also follows `rl-advisor`'s record step and the project's run log.

**Flags.**
- `--viz kit|newton_gl|newton_rtx|rerun|viser|none`; default is the cfg's visualizers (stock: none). **No `--headless`**: the 3.0 parser rejects it. **No `--enable_cameras`**: cameras turn on when the cfg has them or with `--video`. `--video` without `--viz` creates a headless Kit visualizer, so it needs Kit unless the env cfg sets `video_recorders` from a scene sensor. `gym.wrappers.RecordVideo` is unsupported.
- `--num_envs`, `--seed` (`-1` random), `--max_iterations`, `--device cuda:0|cpu`. The CLI overrides `env_cfg.scene.num_envs`; a custom script passes it itself (`parse_env_cfg(task, num_envs=...)`).
- Resume: `--checkpoint <path|run dir|latest|best>`. `--resume`, `--load_run` and `--use_pretrained_checkpoint` are gone.
- Hydra overrides after the flags, no dashes: `physics=newton_mjwarp|newton_kamino|newton_vbd|isaacsim_physx|physx|ovphysx`, `presets=a,b`, `env.scene.num_envs=64`, `agent.seed=1`. Unknown arguments go to Hydra, so a mistyped flag fails there or is ignored: check the printed cfg.

## Verify before handing off

Check every file you wrote or changed. It is static, runs on the Mac and imports nothing from Isaac:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_isaac_code.py" path/to/changed_file.py path/to/task_pkg
```

Use python3 3.12 or newer. Exit 0 clean, 1 findings (`path:line: ISCnnn message`), 2 usage error; `--help` lists the rules. Fix each finding or say why it is a false positive (`# isaac-check: ignore` silences a line).

## 3.0 traps that run without error

1. **wxyz quaternions.** Lab 3.0 is xyzw everywhere (init-state `rot=`, `isaaclab.utils.math`, `.data`); identity `(0, 0, 0, 1)`. A 2.x `(1, 0, 0, 0)` is a 180° rotation, and nothing errors. Raw `isaacsim.core.experimental` is still wxyz, and so is aquila's obs contract: convert at the boundary.
2. **2.x asset API.** `.data.*` is `ProxyArray` (`.torch` zero-copy, `.warp`). Writers are `write_*_to_sim_index(..., env_ids=)` / `write_*_to_sim_mask(..., env_mask=)`; joint targets go through `robot.actuators.target_command.set_*_index(value=, joint_ids=)`; `root_physx_view` → `root_view`. The old forms mostly still run with a DeprecationWarning and break in 3.1.
3. **Actuator limit names.** `effort_limit_sim` → `joint_effort_limit`, `velocity_limit_sim` → `joint_velocity_limit`, `effort_limit` → `actuator_effort_limit`. Explicit actuators no longer lift the solver's effort limit to 1e9, so set `joint_effort_limit` when you need headroom.
4. **Backend assumptions.** Not every sensor, asset feature or `isaaclab_contrib` class works on Newton (`reference/common-cfgs.md`); aquila also avoids `isaaclab_contrib` Multirotor/Thruster, which are PhysX-only. `ovphysx`/OVRTX in a Kit process fails with "Invalid backend combination".
5. **Reading state from USD.** Mid-simulation the stage does not track physics (PhysX writes to Fabric, Newton keeps state on the GPU). Read poses from asset data (`robot.data.root_pos_w.torch`).
6. **Removed helpers.** `hydra_task_config` is gone (`resolve_task_config` / `parse_env_cfg`); `SimulationCfg.physx` is `SimulationCfg.physics`; per-library `scripts/reinforcement_learning/<lib>/train.py` is gone.
7. **Process exit with Kit.** `launch_simulation` closes Kit when the `with` block ends, and Kit's fast shutdown can end the process right there (a 120 s watchdog force-exits a stuck teardown). Write files inside the block.
8. **`@configclass` missing.** Without the decorator a Cfg subclass's overrides silently revert to the parent defaults. Decorate every Cfg class.
9. **`DirectRLEnv` reward shaped `(num_envs, 1)`.** The RL wrappers expect `(num_envs,)`: squeeze the last dim.
10. **Prim path without a leading `/`.** `World/Robot` silently finds nothing; write `/World/Robot`.

## Live Kit (script a running sim)

To script into a running Isaac Sim without restarting it, launch it with the code-execution server `isaacsim.code_editor.python_server`, e.g. `OMNI_KIT_ACCEPT_EULA=YES uv run --extra isaacsim --no-sync isaacsim isaacsim.exp.full --enable isaacsim.code_editor.python_server`, or add `--kit_args "--enable isaacsim.code_editor.python_server"` to a Lab run that starts Kit. It listens on `127.0.0.1:8226`; from the Mac, open `ssh -N -L 8226:127.0.0.1:8226 <linux-box>` first. Then send code with `python3 "${CLAUDE_SKILL_DIR}/scripts/kit_exec.py" '<code>'` (`--file`, `-` for stdin, `--token` when the server requires auth; `--help` for the protocol). `print()` what you want back, and keep long work in a file on the box sent as `exec(open(...).read())`, since the server can't interrupt a synchronous payload.

## Files

- `delegate.md`: the rules for subagents that can't load this skill (When delegating).
- `templates/`: `lab_app_script.py` (Lab custom script with a bounded zero-action loop), `standalone_isaac.py` (raw Isaac Sim 6.2), `direct_rl_env.py` and `manager_based_env.py` (minimal tasks with a physics `PresetCfg`), `task_register.py` (`gym.register` and the entry-point recipe), `agents/rsl_rl_ppo_cfg.py` (rsl-rl-lib 5.x PPO runner).
- `reference/import-migration.md`: read when porting 2.x or `omni.isaac*` code, or when a name looks old.
- `reference/common-cfgs.md`: read when writing asset, sensor, terrain, physics-preset or manager-term cfgs, or when unsure whether something works on Newton.
- `scripts/check_isaac_code.py`: the static checker (Verify); `scripts/test_check_isaac_code.py` is its test.
- `scripts/kit_exec.py`: client for the live Kit code server.
