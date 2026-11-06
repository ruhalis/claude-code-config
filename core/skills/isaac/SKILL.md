---
name: isaac
description: Use this skill whenever the user is writing, modifying, debugging, or running Python code that targets NVIDIA Isaac Lab or NVIDIA Isaac Sim. Triggers include any mention of Isaac Lab, Isaac Sim, Newton or PhysX in Isaac, Omniverse Kit, launch_simulation, AppLauncher, SimulationApp, DirectRLEnv, ManagerBasedRLEnv, PresetCfg, the isaaclab CLI (isaaclab train / play / zero_agent), isaaclab.sh, python.sh, USD stages with omni.usd/pxr, RL training in Isaac, porting Isaac Lab 2.x or omni.isaac code, or files that import from isaaclab, isaaclab_tasks, isaaclab_assets, isaaclab_rl, isaaclab_newton, isaaclab_physx, isaacsim, omni.isaac, or omni.usd. Also use when the user asks to spawn robots, configure scenes, set up RL environments, or run training/play in Isaac. Targets Isaac Lab 3.0.0 (Python 3.12, kit-less Newton by default) with Isaac Sim 6.2.0 for the Kit path; if the project is on another version, surface the difference before generating code.
compatibility: Runs on Linux (x86_64 or aarch64) with an NVIDIA GPU (Turing or newer, driver 580.65+) and Isaac Lab 3.0.0 in a Python 3.12 uv environment, plus Isaac Sim 6.2.0 only for the Kit path; on macOS, author and check statically only.
metadata:
  isaac-lab-version: "3.0.0"
  isaac-sim-version: "6.2.0"
---

# Isaac Lab & Isaac Sim

This skill targets **Isaac Lab 3.0.0** with **Isaac Sim 6.2.0** (last verified against upstream source: 2026-11-06). Lab 3.0 is a different API from 2.x: kit-less Newton physics by default, xyzw quaternions, `ProxyArray` data, `_index`/`_mask` writers, the `isaaclab` CLI. Most tutorials, answers and examples on the web are still 2.x and wrong here.

The pin, the uv extras, the task package, the physics backend and the robot facts come from the project's `CLAUDE.md`, `pyproject.toml`/`uv.lock` and `STATUS.md`. Read those first; never guess.

## Boundaries (fixed decisions)

- **GPU jobs only when asked.** Start training, sweeps, demo collection or anything that holds the GPU longer than a smoke test only on the user's request, and first state the task, `--num_envs`, `--max_iterations` and the expected wall time.
- **Don't change the Isaac environment unasked.** Isaac Lab 3.0.0 pins torch 2.11.0 (cu130) and Isaac Sim pins numpy, urllib3 and more; the project's `pyproject.toml` carries the overrides that make them resolve. No `uv add`, `uv sync --extra ...`, `uv pip install` or `pip install` into it unless the user asks. On the Linux box, pass the extra the env was synced with to every `uv run` (e.g. `uv run --extra isaacsim ...`) or use `--no-sync`: a bare `uv run` re-syncs to the lockfile without that extra and can change packages under Isaac Sim.
- **No installer workflows unasked**: `isaaclab --install`/`-i`, `./isaaclab.sh -i`, `isaaclab --new` (it writes a new project and repo).
- **Never edit a pinned or installed Isaac Lab** (a checkout, a submodule, `site-packages/isaaclab*`). Extend it in the project package: subclassed cfgs, own `mdp` terms, own `PresetCfg`s. Bumping the pin is the user's call.
- **Keep the code-execution server (Step 8) on 127.0.0.1.** It runs any Python it receives. From the Mac, tunnel to it: `ssh -N -L 8226:127.0.0.1:8226 <linux-box>`.

## Step 0 — Detect the environment first

Before writing or running anything, find out what the project pins and what is installed. Run this once per session from the project root (read-only, safe in bash and zsh):

```bash
# 1. Project pin: docs, uv project, lockfile
grep -n -i -E 'isaac ?(sim|lab)[^0-9]{0,6}[0-9]+\.[0-9]' CLAUDE.md STATUS.md 2>/dev/null | head -20
grep -n -E 'isaaclab|isaacsim|rsl-rl|newton|requires-python|conflicts' pyproject.toml 2>/dev/null | head -20
grep -A1 -E '^name = "(isaaclab|isaacsim|torch|rsl-rl-lib|newton)"$' uv.lock 2>/dev/null | grep -v '^--$'
# 2. A source checkout, if the project uses one
cat .gitmodules 2>/dev/null
for lab in . IsaacLab third_party/IsaacLab external/IsaacLab "$HOME/IsaacLab"; do
  [ -d "$lab/source/isaaclab" ] && echo "$lab: $(cat "$lab/VERSION" 2>/dev/null) $(git -C "$lab" describe --tags 2>/dev/null)"
done
# 3. Installed versions in the project env (on the Mac the Isaac packages are normally absent)
for v in "${VIRTUAL_ENV:-}" .venv; do
  [ -n "$v" ] && [ -x "$v/bin/python" ] && "$v/bin/python" -c 'import importlib.metadata as m, sys
for d in ("isaaclab", "isaacsim", "torch", "rsl-rl-lib", "newton"):
    try: print(sys.prefix, d, m.version(d))
    except m.PackageNotFoundError: print(sys.prefix, d, "not installed")'
done
echo "ISAACSIM_PATH=${ISAACSIM_PATH:-unset}"; [ -n "${ISAACSIM_PATH:-}" ] && cat "$ISAACSIM_PATH/VERSION" 2>/dev/null
# 4. Which OS
uname -s
```

**Where this runs.** Isaac Lab 3.0 runs on Linux x86_64 or aarch64 with an NVIDIA GPU (Turing or newer, driver ≥ 580.65.06; the default stack is CUDA 13). macOS is not a supported platform. On macOS (`uname -s` prints `Darwin`), do not sync the Isaac extras, import `isaaclab`/`isaacsim` or launch anything: write the code, check it statically against the pinned source, and hand the user the exact commands to run on the Linux box.

**Check APIs against the pinned source and cite `file:line`.** Grep the Lab source for every class, cfg field, kwarg and flag you use, and cite it (e.g. `source/isaaclab/isaaclab/app/sim_launcher.py:595`). On the Linux box the installed package under `.venv/lib/python3.12/site-packages/` is that source; a project checkout works too. Otherwise clone the pinned tags into a temp dir (never `git submodule update` in the user's repo unasked):

```bash
SRC="${TMPDIR:-/tmp}/isaac-src"; mkdir -p "$SRC"
[ -d "$SRC/IsaacLab-3.0.0" ] || git clone -q --depth 1 --branch v3.0.0 https://github.com/isaac-sim/IsaacLab "$SRC/IsaacLab-3.0.0"
# Isaac Sim (only for raw isaacsim.* code) is large: sparse clone, then add only the extensions you need
[ -d "$SRC/IsaacSim-6.2.0" ] || git clone -q --depth 1 --branch v6.2.0 --filter=blob:none --sparse https://github.com/isaac-sim/IsaacSim "$SRC/IsaacSim-6.2.0"
git -C "$SRC/IsaacSim-6.2.0" sparse-checkout add source/extensions/isaacsim.core.experimental.prims
```

**Upstream agent skills.** The v3.0.0 checkout ships 17 user skills in `skills/user/*/SKILL.md` (git only, not in the wheel). They route to the docs under `docs/source/` in the same checkout. Read the matching one from the clone when the task goes deeper than this skill: `install-isaac-lab`, `migrate-2x-to-3x`, `migrate-from-isaac-gym`, `create-environments`, `convert-direct-to-manager`, `select-backends`, `use-presets`, `prepare-assets-for-newton`, `isaaclab-transferring-policies-sim-to-sim`, `use-sensors-actuators`, `domain-randomization-events`, `train-rl-agents`, `train-multi-gpu`, `debug-rl-training`, `diagnose-joint-poses`, `plan-manipulation-tasks`, `setup-troubleshooting`. Where they or the docs disagree with the source, the source wins. Known stale spots: `docs/source/isaaclab/migrating.rst` and `concepts/visualization.rst` still show `--headless`/`--enable_cameras`, and `train-rl-agents/examples.md` shows `--resume --load_run`; 3.0.0 has none of these (Step 5).

**Docs (pinned).** Isaac Lab 3.0.0: https://isaac-sim.github.io/IsaacLab/v3.0.0/index.html · Isaac Sim 6.2.0: https://docs.isaacsim.omniverse.nvidia.com/6.2.0/index.html. Never `main` or `latest`, which drift past the pin.

**Version gate.** If the project or machine is **not** on Lab 3.0.0 (and Sim 6.2.0 where Kit is used; Lab 3.0.0 supports no other Sim), stop and tell the user: code written for one major version fails on the other. A 2.x project is ported, not patched: use `reference/import-migration.md`, the upstream `migrate-2x-to-3x` skill and `docs/source/isaaclab/migrating.rst`; `<IsaacLab>/scripts/tools/find_quaternions.py` in the checkout finds wxyz literals. Ask only when both the project and the machine give no answer.

## Step 1 — Pick the right execution model

| Model | When to use | Entry point |
|---|---|---|
| **`isaaclab` CLI** | Train, play, smoke test, list tasks | `uv run isaaclab <cmd>`; no script to write |
| **Isaac Lab script** | Custom eval, demo collection, a bounded test on a registered task | `add_launcher_args` + `with launch_simulation(env_cfg, args_cli):` (`templates/lab_app_script.py`) |
| **Raw Isaac Sim** | Scene authoring, sensor or USD tests with no Lab | `from isaacsim import SimulationApp` (Kit; needs Isaac Sim 6.2) (`templates/standalone_isaac.py`) |
| **Inside running Kit** | Script Editor, live experimentation (Step 8) | none, Kit is already loaded |

**Kit vs kit-less.** `launch_simulation` reads the cfg and starts Omniverse Kit only when something needs it: Isaac Sim PhysX (`physics=isaacsim_physx`), a Kit/RTX camera renderer, `--viz kit`, `--livestream`, `--experience`, XR. Newton physics (`newton_mjwarp`, the default of the stock tasks) with the Newton Warp renderer runs kit-less, with Isaac Sim not even installed (`source/isaaclab/isaaclab/app/sim_launcher.py:595`). OvPhysX/OVRTX are kit-less only and can't share a process with Kit. `AppLauncher` still exists as a deprecated adapter that always forces Kit; don't use it in new code.

**Import order (Lab scripts).** Safe before the launch: `isaaclab`, `isaaclab.app`, `isaaclab.sim`, `isaaclab.utils` (incl. `.assets`), `isaaclab_tasks` and `isaaclab_tasks.utils`, cfg modules, and task packages whose `__init__.py` only `gym.register`s lazy strings. Upstream entrypoints import `isaaclab_tasks` before launching. After the launch, inside the `with` block: `gym.make` (it imports the concrete env module), and every `omni.*`, `isaacsim.*` and `carb` import. Those exist only with Kit, so Kit-only code also breaks a kit-less Newton run. For an extension, call `isaaclab.sim.utils.enable_extension("<ext>")` first. **Raw `SimulationApp` scripts** keep the old hard rule: nothing but `from isaacsim import SimulationApp` above `simulation_app = SimulationApp(...)`, `pxr` included.

Copy the matching template; don't write launch boilerplate from memory.

## Step 2 — Use version-correct imports

Always emit 3.0 / 6.2 names. Code that uses `omni.isaac.*`, `omni.isaac.lab*`, `AppLauncher`-first boilerplate, wxyz quaternions or `scripts/reinforcement_learning/<lib>/train.py` is 2.x or older and needs porting (`reference/import-migration.md`).

**Isaac Lab 3.0:**
```python
from isaaclab.app import add_launcher_args, launch_simulation     # AppLauncher is deprecated
import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg   # backend-neutral factories
from isaaclab.envs import DirectRLEnv, DirectRLEnvCfg, ManagerBasedRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAACLAB_NUCLEUS_DIR             # kit-less safe in 3.0
from isaaclab_tasks.utils import PresetCfg, parse_env_cfg          # backend presets, cfg from the registry
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg     # Newton (kit-less)
from isaaclab_physx.physics import PhysxCfg                        # Isaac Sim PhysX (needs Kit)
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg, RslRlMLPModelCfg
from isaaclab_assets.robots.cartpole import CARTPOLE_CFG           # stock robot cfgs (both backends)
```
Sensor cfgs, their backend support (Newton, PhysX, kit-less) and the backend presets are in `reference/common-cfgs.md`.

**Isaac Sim 6.2 (raw standalone):** `isaacsim.core.api` (World, objects) is deprecated since 6.0; use `isaacsim.core.experimental.*`. Its quaternions are **wxyz**, unlike Lab.
```python
from isaacsim import SimulationApp                                  # entry point, first
import isaacsim.core.experimental.utils.app as app_utils            # play(), no World.step()
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import Cube, DistantLight, GroundPlane
from isaacsim.core.experimental.prims import GeomPrim, RigidPrim
from isaacsim.storage.native import get_assets_root_path            # Nucleus assets, raw Sim only
import omni.usd
from pxr import UsdGeom, Gf, UsdLux, Sdf
```

**Things that did NOT rename** (use them with confidence): `omni.usd`, `omni.kit.*`, `carb`, `pxr`, `warp`.

## Step 3 — Direct vs Manager-based RL envs

Lab 3.0 keeps both workflows. Pick deliberately:

- **`DirectRLEnv`**: one class; you write `_pre_physics_step`, `_apply_action`, `_get_observations`, `_get_rewards`, `_get_dones`, `_reset_idx`. The scene can live entirely in the scene cfg, so `_setup_scene` is optional. Best for: custom physics logic, tight performance needs. Task ids end in `-Direct`.
- **`ManagerBasedRLEnv`**: decomposed into managers (observation, reward, termination, event, action), each declared as configclass entries; the env class is Lab's own. Best for: standard locomotion and manipulation with recognizable terms.

Follow whatever the project already uses. Either way the physics backend is data: a `PresetCfg` subclass in `SimulationCfg(physics=...)` with one field per backend and a `default`, picked on the command line with `physics=<name>`. A single-backend project assigns its cfg directly. Templates: `templates/direct_rl_env.py`, `templates/manager_based_env.py`. Decorate every Cfg class with `@configclass` (trap 9).

## Step 4 — Task registration

A Lab task is a `gymnasium.register()` call in a task package's `__init__.py`, all lazy strings, so importing it needs only gymnasium (`templates/task_register.py`):

```python
import gymnasium as gym

from . import agents

gym.register(
    id="Isaac-MyTask-Direct",                       # 3.0 ids carry no -v0
    entry_point=f"{__name__}.my_task_direct_env:MyTaskEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.my_task_direct_env:MyTaskEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:MyTaskPPORunnerCfg",
        "default_agent": "rsl_rl",                  # lets the CLI skip --rl_library
    },
)
# Manager-based: entry_point="isaaclab.envs:ManagerBasedRLEnv", env_cfg_entry_point -> your ManagerBasedRLEnvCfg
```

The id must be unique across the gym registry; by convention it starts with `Isaac-`. Agent cfgs live in a sibling `agents/` package (with an `__init__.py`): `rsl_rl_ppo_cfg.py` (`templates/agents/rsl_rl_ppo_cfg.py`; rsl-rl-lib 5.5.1 style, `actor`/`critic` `RslRlMLPModelCfg`, not the deprecated `policy=RslRlPpoActorCriticCfg`), or YAML files for the other libraries (`rl_games`, `skrl`, `sb3`, `torchrl`), named `<lib>_cfg_entry_point`.

**Discovery.** Declare the project's task module once as an entry point, and its `tasks/__init__.py` imports the task packages:

```toml
[project.entry-points."isaaclab.tasks"]
my_project = "my_project.tasks"
```

`isaaclab train|play|zero_agent|random_agent|list_envs` and the stock `<IsaacLab>/scripts/reinforcement_learning/{train,play}.py` load every `isaaclab.tasks` entry point before looking up the id (`source/isaaclab/isaaclab/cli/__init__.py:39`). No wrapper script is needed. A plain `import isaaclab_tasks`, your own script, and `<IsaacLab>/scripts/environments/zero_agent.py` run directly do not load entry points: import your task package there (or call `isaaclab.cli.load_external_tasks()`). The entry-point module must stay importable without Isaac Lab installed.

**New project or task:** the generator is `uv run isaaclab --new` (interactive; also `--non_interactive --project_path --name --workflow --rl_library ...`). It writes a new uv project with the NVIDIA index, the dependency overrides and the entry point, and starts a git repo. Don't run it yourself: hand the user the command for the Linux box and what to pick (workflow and RL library matching the project).

## Step 5 — Run commands

Run inside the project's uv environment (Python 3.12), never with the system python. Add the extra the env was synced with (Boundaries). `./isaaclab.sh` is deprecated in 3.0 (it prints a warning and forwards to the same CLI; removal in 3.1); use `uv run isaaclab`. Prefix anything that starts Kit or imports `isaacsim` on a headless/SSH box with `OMNI_KIT_ACCEPT_EULA=YES`, or the EULA prompt crashes on EOF.

```bash
# --- Isaac Sim standalone (no Lab) ---
OMNI_KIT_ACCEPT_EULA=YES uv run --extra isaacsim python my_scene.py   # binary install: $ISAACSIM_PATH/python.sh my_scene.py

# --- Isaac Lab ---
uv run isaaclab list_envs --keyword MyTask --show_presets      # is the task registered, which presets exist

# Smoke test: zero / random actions. These default to the newton_gl window, so --viz none on a headless box
uv run isaaclab zero_agent   --task Isaac-MyTask-Direct --num_envs 16 --max_steps 200 --viz none
uv run isaaclab random_agent --task Isaac-MyTask-Direct --num_envs 16 --max_steps 200 --viz none

# Train (headless unless --viz is given)
uv run isaaclab train --rl_library rsl_rl --task Isaac-MyTask-Direct --num_envs 4096 --max_iterations 1500 --seed 42
# Other backend: a Hydra token, no dashes; isaacsim_physx needs the isaacsim extra (Kit)
OMNI_KIT_ACCEPT_EULA=YES uv run --extra isaacsim isaaclab train --rl_library rsl_rl --task Isaac-MyTask physics=isaacsim_physx

# Play a trained policy (--checkpoint: a path, a run dir, latest, best or pretrained)
uv run isaaclab play --rl_library rsl_rl --task Isaac-MyTask-Direct --num_envs 32 --checkpoint latest --viz newton_gl

# Record video while headless
uv run isaaclab train --rl_library rsl_rl --task Isaac-MyTask-Direct --video --video_length 200 --video_interval 2000
```

rsl_rl runs land in `logs/rsl_rl/<experiment_name>/<timestamp>[_<run_name>]/` under the current directory, with the resolved cfgs in `params/env.yaml` and `params/agent.yaml`. When starting or changing a training run, also apply rl-advisor's record step (record the exact command, reward terms, seed).

**Flags worth knowing:**
- `--viz kit|newton_gl|newton_rtx|rerun|viser|none` (comma-separated). Without it, the cfg's visualizers are used (stock: none, i.e. headless). **There is no `--headless`**: the 3.0 launcher rejects it (`source/isaaclab_physx/test/app/test_kit_launcher.py:227`). `--viz kit` is the only Kit viewport.
- **No `--enable_cameras`** either: cameras are enabled automatically when the cfg has them; `--video` turns them on too. `--video` without `--viz` creates a headless Kit visualizer to record from, so it needs Kit (the isaacsim extra) unless the env cfg sets `video_recorders` from a scene sensor (`isaaclab_rl/entrypoints/common.py:1049`).
- `--num_envs N`, `--seed N` (`-1` = random), `--max_iterations N`, `--device cuda:0|cpu` (default `cuda:0`).
- Resume: `train ... --checkpoint <path|run dir|latest|best>`. `--resume`, `--load_run` and `--use_pretrained_checkpoint` are gone; Hydra `agent.load_run=<dir>` still picks a run for play when no `--checkpoint` is given.
- rsl_rl: `--experiment_name`, `--run_name`, `--logger wandb|tensorboard|neptune`, `--log_project_name`.
- Hydra overrides after the flags, no dashes: `physics=<name>`, `renderer=<name>`, `presets=a,b`, `env.scene.num_envs=64`, `agent.seed=1`. Physics names: `newton_mjwarp`, `newton_kamino`, `newton_vbd`, `isaacsim_physx` (Kit), `physx` (Isaac Sim PhysX if Kit runs, else OvPhysX), `ovphysx` (its extra, no Kit).
- `--kit_args "--ext-folder=<dir> --enable <ext>"`: raw Kit flags, only when Kit runs.

Leftover arguments the CLI doesn't know go to Hydra as overrides, so a mistyped flag fails there or is silently ignored. Check the printed cfg.

## Step 6 — Verify before handing off

Before giving the user commands for the Linux box, check every file you wrote or changed. It is static and runs on the Mac; nothing imports Isaac. `${CLAUDE_SKILL_DIR}` is this skill's directory:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/check_isaac_code.py" path/to/changed_file.py path/to/task_pkg
```

It compiles each file from its bytes as py_compile does, in memory (no `__pycache__`; needs python3 ≥ 3.11), then applies the 3.0 rules `--help` lists (removed and deprecated APIs, Kit imports before the launch, `--headless`/`--enable_cameras`, per-library script paths, wxyz identity quaternions). Exit 0 clean, 1 findings (`path:line: ISCnnn message`), 2 usage error. Fix each finding or say why it is a false positive (`# isaac-check: ignore` silences a line).

Then hand over a smoke test for the Linux box. It passes when it prints the Gym observation and action spaces and steps to `--max_steps` without a traceback. Hand over the train command only after that:

```bash
uv run isaaclab list_envs --keyword <id>                                   # registered?
uv run isaaclab zero_agent --task <id> --num_envs 16 --max_steps 200 --viz none
# Kit path (PhysX backend or Kit cameras):
OMNI_KIT_ACCEPT_EULA=YES uv run --extra isaacsim isaaclab zero_agent --task <id> --num_envs 16 --max_steps 200 --viz none physics=isaacsim_physx
```

## Step 7 — Common traps

1. **Kit imports in the wrong place.** Symptom: `ModuleNotFoundError: No module named 'omni'`, `'carb'` or `'isaacsim.<ext>'`. Fix: move `omni.*`/`isaacsim.*`/`carb` imports inside `with launch_simulation(...)` (or below `SimulationApp(...)`), and keep Kit-only code off the kit-less Newton path entirely.

2. **wxyz quaternions.** Lab 3.0 is **xyzw** everywhere: init-state `rot=`, `isaaclab.utils.math`, all `.data` fields; identity is `(0, 0, 0, 1)`. A 2.x identity `(1, 0, 0, 0)` is now a 180° rotation, and nothing errors. Raw Isaac Sim 6.2 `isaacsim.core.experimental` is still wxyz: convert at that boundary.

3. **2.x asset API.** `.data.*` returns `ProxyArray`: use `.torch` (zero-copy) or `.warp`. Writers are keyword-only `write_*_to_sim_index(..., env_ids=)` / `write_*_to_sim_mask(..., env_mask=)`. Joint targets go through `robot.actuators.target_command.set_*_index(value=, joint_ids=)`. `root_physx_view` → `root_view` (a backend-specific type). The old forms mostly still run with a DeprecationWarning, but code that works by accident breaks in 3.1. Full table: `reference/import-migration.md`.

4. **Actuator limit names.** `effort_limit_sim` → `joint_effort_limit`, `velocity_limit_sim` → `joint_velocity_limit`, `effort_limit` → `actuator_effort_limit` (rated). The old names are accepted until 3.1. Explicit actuators no longer lift the solver's effort limit to 1e9, so set `joint_effort_limit` when you need headroom.

5. **Wrong environment.** Lab 3.0 is Python 3.12 only, in the project's uv env. A bare `uv run` in a project synced with an extra re-syncs it (Boundaries); system python sees nothing.

6. **Backend assumptions.** Not every sensor, asset feature or `isaaclab_contrib` class works on every backend: check `reference/common-cfgs.md` or the upstream `select-backends` skill before using one on Newton. `physics=isaacsim_physx` needs the isaacsim extra; `ovphysx`/OVRTX in a Kit process fails with "Invalid backend combination".

7. **`num_envs` in cfg vs CLI.** The CLI overrides `env_cfg.scene.num_envs` with `--num_envs`; a custom script must pass it itself (`parse_env_cfg(task, num_envs=...)`, as `templates/lab_app_script.py` does).

8. **`DirectRLEnv` reward with shape `(num_envs, 1)` instead of `(num_envs,)`.** The RL wrappers expect 1D. Squeeze the last dim or return a 1D tensor.

9. **`@configclass` decorator missing.** Without it, subclass overrides silently revert to the parent defaults; `validate()` fails at env creation, or the parent values are used. Always decorate Cfg classes.

10. **Decimation.** `sim.dt` is the physics step and `decimation` is how many physics steps run per *policy* step: 60 Hz control with `dt=1/120` means `decimation=2`. Episode length: `episode_length_s = max_episode_steps * decimation * dt`.

11. **USD prim paths must start with `/`.** `World/Robot` silently finds nothing. Use `/World/Robot`.

12. **Asset paths.** In Lab code use `ISAACLAB_NUCLEUS_DIR` / `ISAAC_NUCLEUS_DIR` from `isaaclab.utils.assets` (kit-less safe in 3.0; the root comes from `ISAACSIM_ASSET_ROOT` or the app `.kit` default; fetching remote USD still needs network). `get_assets_root_path()` from `isaacsim.storage.native` is for raw Isaac Sim scripts only. Never hardcode `omniverse://localhost/...`.

13. **Reading sim state from USD.** Mid-simulation the USD stage does not track the physics state (PhysX writes to Fabric, `use_fabric=True` by default; Newton keeps state on the GPU). Read poses from the asset data (`robot.data.root_pos_w.torch`, ...), not from USD attributes.

14. **Video.** `gym.wrappers.RecordVideo` is unsupported in 3.0; use `--video` or `VideoRecorderCfg` on `env_cfg.video_recorders`.

15. **Removed helpers.** `hydra_task_config` is gone (`isaaclab_tasks.utils.resolve_task_config` / `parse_env_cfg`); `SimulationCfg.physx` is `SimulationCfg.physics`; per-library `train.py`/`play.py` are gone (Step 5).

16. **ROS 2 bridge.** Isaac Sim 6.2 runs Python 3.12 and bundles ROS 2 libraries for the default interfaces (Jazzy on Ubuntu 24.04 recommended, Humble on 22.04). Custom interfaces need a Python 3.12 build; don't source a system ROS built for another Python in the shell that launches Isaac.

17. **Process exit with Kit.** `launch_simulation` closes Kit when the `with` block ends; Kit's fast shutdown flushes stdio and can end the process right there, and a 120 s watchdog (`shutdown_watchdog_timeout` in the `SimulationApp` config) force-exits a stuck teardown. Write files inside the block.

## Step 8 — Live experimentation (script a running sim, Kit only)

To script into a running Isaac Sim without restarting it for every change, launch it with the Python code-execution server (Isaac Sim 6.2: `isaacsim.code_editor.python_server`; `isaacsim.code_editor.vscode` depends on it):

```bash
$ISAACSIM_PATH/isaac-sim.sh --enable isaacsim.code_editor.python_server                                     # binary install
OMNI_KIT_ACCEPT_EULA=YES uv run --extra isaacsim isaacsim isaacsim.exp.full --enable isaacsim.code_editor.python_server   # pip install
# inside a Lab run that starts Kit: add --kit_args "--enable isaacsim.code_editor.python_server"
```

The server listens on `127.0.0.1:8226` (keep it there, Boundaries). Each connection takes UTF-8 Python source (or a JSON envelope starting with `{`: `code`, `auth_token`, `context`, `timeout`, ...), **runs it only after EOF**, so the client must half-close, and answers once with JSON `{status, output}`, plus `traceback`, `ename`, `evalue` on error. Globals persist per `context` (shared by default); top-level `await` works. From another terminal (on the Mac, through the SSH tunnel):

```bash
python3 - <<'EOF'
import json, socket
CODE = "import omni.usd; print([str(p.GetPath()) for p in omni.usd.get_context().get_stage().Traverse()])"
try:
    s = socket.create_connection(("127.0.0.1", 8226), timeout=10)
except OSError as e:  # refused or timed out
    raise SystemExit(f"cannot connect ({e}): is Isaac Sim up with isaacsim.code_editor.python_server (from the Mac: the SSH tunnel)?")
s.sendall(CODE.encode())
s.shutdown(socket.SHUT_WR)  # 6.x runs the code on EOF; without this it waits forever
buf = b""
try:
    while chunk := s.recv(4096):
        buf += chunk
except socket.timeout:
    raise SystemExit("no reply within 10 s: the code is still running or the sim is busy (raise the timeout for long code)")
if not buf:
    raise SystemExit("no reply: the server closed the connection")
r = json.loads(buf)
print("status:", r["status"])
if r.get("output"):
    print(r["output"])
if r["status"] == "error":
    print(f"{r.get('ename')}: {r.get('evalue')}")
    print("".join(r.get("traceback") or []))
    raise SystemExit(1)
EOF
```

- `print()` what you want back. A synchronous payload can't be interrupted by the server's `timeout`, so keep long work in a file on the box and send `exec(open("/path/on/box.py").read())`.
- `require_auth` is off by default. When it's on, start the source with `# isaacsim-python-server-token: <token>` (printed at startup) or put `auth_token` in the JSON envelope.

## Files in this skill

- `SKILL.md`: this file.
- `templates/standalone_isaac.py`: raw Isaac Sim 6.2 script (`SimulationApp`, `isaacsim.core.experimental`).
- `templates/lab_app_script.py`: Lab 3.0 custom script (`add_launcher_args`, `parse_env_cfg`, `with launch_simulation`, `gym.make`, a bounded zero-action loop).
- `templates/direct_rl_env.py`, `templates/manager_based_env.py`: minimal Lab 3.0 `DirectRLEnv` / `ManagerBasedRLEnvCfg` tasks with a physics `PresetCfg`.
- `templates/task_register.py`: `gym.register` boilerplate, plus the `isaaclab.tasks` entry-point recipe.
- `templates/agents/__init__.py`, `templates/agents/rsl_rl_ppo_cfg.py`: the `agents/` package with an rsl-rl-lib 5.x PPO runner cfg.
- `reference/import-migration.md`: old-name → new-name tables (`omni.isaac.*`, `omni.isaac.lab*`, Lab 2.x → 3.0).
- `reference/common-cfgs.md`: common Cfg snippets (assets, sensors, terrain, physics presets) with their backend support.
- `scripts/check_isaac_code.py`: the stdlib static checker run in Step 6 (`--help` lists the rules). `scripts/test_check_isaac_code.py` is its regression test (`python3 scripts/test_check_isaac_code.py`).
