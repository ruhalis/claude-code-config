"""
Minimal Isaac Lab 3.0 ManagerBasedRLEnv template (scene, MDP managers and env cfg in one file).

# Based on isaaclab_tasks/core/cartpole/cartpole_manager_env_cfg.py @ v3.0.0
# (physics presets from cartpole_common.py; terms from isaaclab.envs.mdp)

Use this style when your task naturally decomposes into independent reward terms,
observation groups, and randomization events (the default for new single-agent tasks).
For tightly-coupled custom physics or bespoke step/reset control, use DirectRLEnv (see direct_rl_env.py).

Layout convention (generator layout: `isaaclab --new`):
    src/<your_project>/tasks/<your_task>/
        __init__.py                  # gym.register(..., entry_point="isaaclab.envs:ManagerBasedRLEnv")
        my_task_manager_env_cfg.py   # this file
        agents/
            __init__.py
            rsl_rl_ppo_cfg.py        # see agents/rsl_rl_ppo_cfg.py
        mdp/                         # your own terms; re-export the stock ones next to them
            __init__.py              #   from isaaclab.envs.mdp import *   # noqa: F403
            rewards.py, observations.py, terminations.py, events.py

3.0 conventions: robot cfgs are copied with isaaclab.utils.replace, the physics backend is a PresetCfg
selected by `physics=<name>`, quaternions in cfgs (init_state.rot, light orientation) are XYZW, and custom
term functions read `env.scene["robot"].data.<prop>.torch` (ProxyArray -> torch).
"""

from __future__ import annotations

import math

from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg
from isaaclab_physx.physics import PhysxCfg

import isaaclab.envs.mdp as mdp  # stock MDP terms; swap for `from . import mdp` once you have your own
import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg
from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.utils import configclass, replace

from isaaclab_tasks.utils import PresetCfg

# REPLACE: a robot cfg from isaaclab_assets, or your own ArticulationCfg (see the comment in direct_rl_env.py)
from isaaclab_assets.robots.cartpole import CARTPOLE_CFG


@configclass
class MyTaskPhysicsCfg(PresetCfg):
    """Physics backend presets, selected on the command line with physics=<name>."""

    isaacsim_physx: PhysxCfg = PhysxCfg()  # needs the isaacsim extra (Kit)
    newton_mjwarp: NewtonCfg = NewtonCfg(
        solver_cfg=MJWarpSolverCfg(njmax=5, nconmax=3, cone="pyramidal", impratio=1, integrator="implicitfast"),
        num_substeps=1,
        debug_mode=False,
        use_cuda_graph=True,
    )
    default: NewtonCfg = newton_mjwarp  # used when no physics= override is given


# --- Scene ---
@configclass
class MyTaskSceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg(size=(100.0, 100.0)))
    robot: ArticulationCfg = replace(CARTPOLE_CFG, prim_path="{ENV_REGEX_NS}/Robot")  # {ENV_REGEX_NS} -> env_.*
    dome_light = AssetBaseCfg(
        prim_path="/World/DomeLight", spawn=sim_utils.DomeLightCfg(color=(0.9, 0.9, 0.9), intensity=500.0)
    )


# --- Action manager ---
@configclass
class ActionsCfg:
    joint_effort = mdp.JointEffortActionCfg(asset_name="robot", joint_names=["slider_to_cart"], scale=100.0)


# --- Observation manager ---
@configclass
class ObservationsCfg:
    @configclass
    class PolicyCfg(ObsGroup):
        joint_pos_rel = ObsTerm(func=mdp.joint_pos_rel)
        joint_vel_rel = ObsTerm(func=mdp.joint_vel_rel)

        def __post_init__(self):
            self.enable_corruption = False
            self.concatenate_terms = True

    policy: PolicyCfg = PolicyCfg()


# --- Event manager (resets, randomization) ---
@configclass
class EventsCfg:
    reset_cart_position = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=["slider_to_cart"]),
            "position_range": (-1.0, 1.0),
            "velocity_range": (-0.5, 0.5),
        },
    )
    reset_pole_position = EventTerm(
        func=mdp.reset_joints_by_offset,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=["cart_to_pole"]),
            "position_range": (-0.25 * math.pi, 0.25 * math.pi),
            "velocity_range": (-0.25 * math.pi, 0.25 * math.pi),
        },
    )


# --- Reward manager ---
@configclass
class RewardsCfg:
    alive = RewTerm(func=mdp.is_alive, weight=1.0)
    terminating = RewTerm(func=mdp.is_terminated, weight=-2.0)
    pole_pos = RewTerm(
        func=mdp.joint_pos_target_l2,
        weight=-1.0,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["cart_to_pole"]), "target": 0.0},
    )
    cart_vel = RewTerm(
        func=mdp.joint_vel_l1,
        weight=-0.01,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["slider_to_cart"])},
    )
    # add task-specific terms here: RewTerm(func=my_mdp.forward_vel, weight=1.0), with
    # def forward_vel(env) -> torch.Tensor: return env.scene["robot"].data.root_lin_vel_b.torch[:, 0]


# --- Termination manager ---
@configclass
class TerminationsCfg:
    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    cart_out_of_bounds = DoneTerm(
        func=mdp.joint_pos_out_of_manual_limit,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=["slider_to_cart"]), "bounds": (-3.0, 3.0)},
    )


# --- Top-level env config ---
@configclass
class MyTaskEnvCfg(ManagerBasedRLEnvCfg):
    scene: MyTaskSceneCfg = MyTaskSceneCfg(num_envs=4096, env_spacing=4.0)
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    events: EventsCfg = EventsCfg()
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()

    def __post_init__(self):
        self.decimation = 2
        self.episode_length_s = 5.0
        self.sim.dt = 1 / 120
        self.sim.render_interval = self.decimation
        self.sim.physics = MyTaskPhysicsCfg()
