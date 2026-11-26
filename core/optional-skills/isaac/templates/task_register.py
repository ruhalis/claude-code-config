"""
Task registration boilerplate for an Isaac Lab 3.0 project.

# Based on tools/template/templates/tasks/__init__task and isaaclab_tasks/core/cartpole/__init__.py @ v3.0.0

Place this code in the __init__.py of your task package, e.g.:
    src/my_project/tasks/my_task/__init__.py
with the runner cfgs in a sibling agents/ package (agents/__init__.py +
agents/rsl_rl_ppo_cfg.py, see templates/agents/).

Everything here is a lazy string, so importing the package needs only gymnasium and is safe before Kit starts.

Discovery: `isaaclab train|play|zero_agent|random_agent|list_envs` and the stock scripts/reinforcement_learning
train.py/play.py load every `isaaclab.tasks` entry point (isaaclab.cli.load_external_tasks) before looking up the
task id, so an installed project needs no wrapper script and no `import my_project.tasks` in a train script.
Declare the entry point once in the project's pyproject.toml; it points at a MODULE that imports the task
packages (so repeated discovery hits the import cache):

    [project.entry-points."isaaclab.tasks"]
    my_project = "my_project.tasks"

and src/my_project/tasks/__init__.py imports the task packages:

    from . import my_task  # noqa: F401  (runs this file's gym.register calls)

Then (after `uv sync` / `uv pip install -e .`):
    uv run isaaclab list_envs --show_presets
    uv run isaaclab train --rl_library rsl_rl --task Isaac-MyTask-Direct --num_envs 4096 physics=newton_mjwarp
    uv run --extra isaacsim isaaclab train --rl_library rsl_rl --task Isaac-MyTask physics=isaacsim_physx

Ids: upstream 3.0 ids carry no -v0 suffix (Isaac-Cartpole, Isaac-Cartpole-Direct); keep the -Direct suffix for
DirectRLEnv tasks and use suffixless ids on the command line.
An uninstalled checkout only needs `import my_project.tasks` in your own script (see lab_app_script.py).
"""

import gymnasium as gym

from . import agents

# Direct workflow: entry_point is the env class
gym.register(
    id="Isaac-MyTask-Direct",
    entry_point=f"{__name__}.my_task_direct_env:MyTaskEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.my_task_direct_env:MyTaskEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:MyTaskPPORunnerCfg",
        # lets `isaaclab train --task ...` pick the library without --rl_library
        "default_agent": "rsl_rl",
        # Other frameworks read YAML files you must add to agents/ (copy from a similar
        # upstream task's agents/ folder), then uncomment:
        # "rl_games_cfg_entry_point": f"{agents.__name__}:rl_games_direct_ppo_cfg.yaml",
        # "skrl_cfg_entry_point": f"{agents.__name__}:skrl_direct_ppo_cfg.yaml",
        # "sb3_cfg_entry_point": f"{agents.__name__}:sb3_ppo_cfg.yaml",
    },
)

# Manager-based workflow: entry_point is always the stock env class, the cfg carries the task
gym.register(
    id="Isaac-MyTask",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.my_task_manager_env_cfg:MyTaskEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:MyTaskPPORunnerCfg",
        "default_agent": "rsl_rl",
    },
)

# Kit needs extra flags (extension folders, extensions)? Pass them through the launcher on any command:
#   --kit_args "--ext-folder=<dir> --enable <ext>"
