"""
Minimal Isaac Lab 3.0 custom script: resolve the task cfg, launch only the runtime it needs, build the env with
gym.make, step it with zero actions for a bounded number of steps.

# Based on scripts/tutorials/03_envs/run_cartpole_rl_env.py and
# isaaclab_rl/entrypoints/simple_agents.py @ Isaac Lab v3.0.0

Model for a custom script on a registered task (bounded smoke test, eval, demo collection). For a plain zero
or random rollout you do not need a script at all: `isaaclab zero_agent --task <ID> --num_envs 16`.

Run (inside an Isaac Lab project; the isaacsim extra is needed only for PhysX/Kit, Newton runs kit-less):
    uv run python lab_app_script.py --task Isaac-MyTask-Direct --num_envs 16 --steps 200
    uv run --extra isaacsim python lab_app_script.py --task Isaac-MyTask-Direct physics=isaacsim_physx
Trailing key=value arguments (physics=..., presets=...) are Hydra-style overrides for the task cfg.
Launcher flags come from add_launcher_args: --device, --viz (default: no window; --viz kit opens one),
--livestream, --kit_args, --verbose. There is no --headless or --enable_cameras flag in 3.0; cameras are
enabled automatically when the cfg has Kit camera sensors. Unknown flags are NOT rejected here (they land in
the overrides list), so check typos in the printed cfg.
"""

import argparse

from isaaclab.app import add_launcher_args, launch_simulation

# --- 1. CLI: your flags + the launcher's. This is plain Python, no Kit has started. ---
parser = argparse.ArgumentParser(description="Isaac Lab 3.0 script template")
parser.add_argument("--task", type=str, required=True, help="Registered gym id, e.g. Isaac-MyTask-Direct")
parser.add_argument("--num_envs", type=int, default=None, help="Override cfg.scene.num_envs")
parser.add_argument("--steps", type=int, default=200, help="Env steps to run before exiting")
add_launcher_args(parser)
args_cli, hydra_overrides = parser.parse_known_args()

# --- 2. Task registration and cfg resolution also run before the launch (cfgs are plain data). ---
# What must wait for the launch: isaacsim.*, omni.*, carb and pxr imports (they exist only inside Kit).
# Importing isaaclab, isaaclab_tasks and your task package before it is fine, Kit-less runs have no Kit at all.
import gymnasium as gym
import torch

from isaaclab_tasks.utils import parse_env_cfg  # importing isaaclab_tasks registers the upstream tasks

# REPLACE: your task package (registers its gym ids; lazy strings, so no Kit needed). When the project is
# pip/uv installed with an `isaaclab.tasks` entry point, `isaaclab list_envs` already sees it, but a plain
# `python script.py` does not load entry points: import the package here (or call
# `from isaaclab.cli import load_external_tasks; load_external_tasks()`).
import my_project.tasks  # noqa: F401


def main():
    # cfg from the registry (env_cfg_entry_point), with --device / --num_envs / overrides applied
    env_cfg = parse_env_cfg(
        args_cli.task, device=args_cli.device, num_envs=args_cli.num_envs, overrides=hydra_overrides
    )

    # --- 3. Start exactly the runtime the cfg needs (Kit for PhysX / Kit cameras / --viz kit, nothing for Newton).
    # Everything that touches the simulator runs inside the with block; it closes the runtime on exit.
    with launch_simulation(env_cfg, args_cli):
        env = gym.make(args_cli.task, cfg=env_cfg)
        print(f"[INFO] observation space: {env.observation_space}  action space: {env.action_space}")

        env.reset()
        for step in range(args_cli.steps):
            if not env.unwrapped.sim.is_running():  # visualizer window closed
                break
            with torch.inference_mode():
                actions = torch.zeros(env.action_space.shape, device=env.unwrapped.device)
                _, reward, terminated, truncated, _ = env.step(actions)
            if step % 50 == 0:
                done = (terminated | truncated).sum().item()
                print(f"[INFO] step={step} mean_reward={reward.mean().item():.4f} resets={done}")
        env.close()
    # Kit (when it was started) is closed by launch_simulation, which flushes stdio and may end the process
    # itself (fast shutdown): do your own file writes inside the with block, before env.close().


if __name__ == "__main__":
    main()
