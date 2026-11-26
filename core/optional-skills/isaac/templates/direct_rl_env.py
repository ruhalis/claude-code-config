"""
Minimal Isaac Lab 3.0 DirectRLEnv template (env class + cfg in one file).

# Based on isaaclab_tasks/core/cartpole/cartpole_direct_env.py and cartpole_direct_env_cfg.py @ v3.0.0
# (cfg physics presets from cartpole_common.py)

Save as:
    src/<your_project>/tasks/<your_task>/my_task_direct_env.py
Register the task in the sibling __init__.py (see task_register.py); the runner cfg
goes in agents/ (see agents/rsl_rl_ppo_cfg.py).

Run with (the project installed with an `isaaclab.tasks` entry point, see task_register.py):
    uv run isaaclab train --rl_library rsl_rl --task Isaac-MyTask-Direct --num_envs 4096
    uv run --extra isaacsim isaaclab train --rl_library rsl_rl --task Isaac-MyTask-Direct physics=isaacsim_physx

3.0 conventions in this file: data properties are ProxyArray (append .torch), writes are *_index / *_mask
(here *_index with env_ids), quaternions are XYZW (identity (0, 0, 0, 1)), the physics backend is a PresetCfg
selected by `physics=<name>`, and the scene lives entirely in the scene cfg (no _setup_scene override needed).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import torch
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg
from isaaclab_physx.physics import PhysxCfg

import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg
from isaaclab.envs import DirectRLEnv, DirectRLEnvCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim import SimulationCfg
from isaaclab.utils import configclass, replace
from isaaclab.utils.math import sample_uniform

from isaaclab_tasks.utils import PresetCfg

# REPLACE: a robot cfg from isaaclab_assets, or your own ArticulationCfg. Own USD + effort control, for example:
#   from isaaclab.actuators import ImplicitActuatorCfg
#   MY_ROBOT_CFG = ArticulationCfg(
#       spawn=sim_utils.UsdFileCfg(usd_path="REPLACE_WITH_YOUR_USD_PATH"),
#       init_state=ArticulationCfg.InitialStateCfg(pos=(0.0, 0.0, 0.5)),
#       actuators={  # effort control needs stiffness=0, damping=0 (no actuator group = efforts never apply)
#           "all": ImplicitActuatorCfg(joint_names_expr=[".*"], stiffness=0.0, damping=0.0, joint_effort_limit=100.0),
#       },
#   )
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
    # Drop the variants you do not support; one backend needs no PresetCfg, assign its cfg to SimulationCfg.physics.


@configclass
class MyTaskSceneCfg(InteractiveSceneCfg):
    """Assets of the scene, cloned per environment."""

    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg())
    robot: ArticulationCfg = replace(CARTPOLE_CFG, prim_path="{ENV_REGEX_NS}/Robot")  # {ENV_REGEX_NS} -> env_.*
    light = AssetBaseCfg(
        prim_path="/World/Light", spawn=sim_utils.DomeLightCfg(intensity=2000.0, color=(0.75, 0.75, 0.75))
    )


@configclass
class MyTaskEnvCfg(DirectRLEnvCfg):
    # --- Episode / control rate: policy rate = 1 / (sim.dt * decimation) ---
    decimation = 2  # policy step = 2 physics steps
    episode_length_s = 5.0

    # --- Spaces: declare sizes, the gym spaces are built for you ---
    action_space = 1  # one effort command
    observation_space = 4  # = 2 * num_joints, must equal the concatenated obs width
    state_space = 0  # 0 = no privileged critic state

    # --- Simulation ---
    sim: SimulationCfg = SimulationCfg(dt=1 / 120, render_interval=decimation, physics=MyTaskPhysicsCfg())

    # --- Scene ---
    scene: MyTaskSceneCfg = MyTaskSceneCfg(num_envs=4096, env_spacing=4.0, replicate_physics=True)

    # --- Task tunables (free-form) ---
    actuated_joint_names = ["slider_to_cart"]  # joints that receive the action
    action_scale = 100.0  # [N]
    max_joint_pos = 3.0  # an actuated joint beyond +-this value terminates the episode
    reward_scale_alive = 1.0
    reward_scale_terminated = -2.0
    reset_joint_pos_range = (-0.25 * math.pi, 0.25 * math.pi)  # added to the default joint pos on reset


class MyTaskEnv(DirectRLEnv):
    cfg: MyTaskEnvCfg

    def __init__(self, cfg: MyTaskEnvCfg, render_mode: str | None = None, **kwargs):
        super().__init__(cfg, render_mode, **kwargs)  # builds the scene from cfg.scene
        self.robot = self.scene["robot"]
        act_ids, _ = self.robot.find_joints(self.cfg.actuated_joint_names)
        self._act_ids = torch.tensor(act_ids, device=self.device)  # device indices avoid per-step host uploads
        self.actions = torch.zeros(self.num_envs, len(act_ids), device=self.device)
        # ProxyArray -> torch view. Zero-copy and live, so the cached view follows later updates.
        self.joint_pos = self.robot.data.joint_pos.torch
        self.joint_vel = self.robot.data.joint_vel.torch

    # Per policy step (once per `decimation` physics steps) -------------------
    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        self.actions = self.cfg.action_scale * actions.clone()

    # Per physics step ----------------------------------------------------------
    def _apply_action(self) -> None:
        self.robot.actuators.target_command.set_effort_index(value=self.actions, joint_ids=self._act_ids)

    # Observations: dict of groups, "policy" is required --------------------------
    def _get_observations(self) -> dict:
        joint_pos_rel = self.joint_pos - self.robot.data.default_joint_pos.torch
        joint_vel_rel = self.joint_vel - self.robot.data.default_joint_vel.torch
        obs = torch.cat((joint_pos_rel, joint_vel_rel), dim=-1)
        # Root state, if you need it (.torch each time you read): robot.data.root_pos_w.torch,
        # root_quat_w.torch (XYZW), root_lin_vel_b.torch, root_ang_vel_b.torch
        return {"policy": obs}

    # Rewards: shape (num_envs,) ------------------------------------------------
    def _get_rewards(self) -> torch.Tensor:
        alive = self.cfg.reward_scale_alive * (1.0 - self.reset_terminated.float())
        died = self.cfg.reward_scale_terminated * self.reset_terminated.float()
        return (alive + died) * self.step_dt

    # Termination: failures and timeouts are returned separately ---------------
    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        self.joint_pos = self.robot.data.joint_pos.torch
        self.joint_vel = self.robot.data.joint_vel.torch
        time_out = self.episode_length_buf >= self.max_episode_length
        out_of_bounds = torch.any(torch.abs(self.joint_pos[:, self._act_ids]) > self.cfg.max_joint_pos, dim=1)
        return out_of_bounds, time_out

    # Reset selected envs -----------------------------------------------------------
    def _reset_idx(self, env_ids: Sequence[int] | None):
        if env_ids is None:
            env_ids = torch.arange(self.num_envs, device=self.device, dtype=torch.int32)  # as DirectRLEnv.reset does
        super()._reset_idx(env_ids)

        joint_pos = self.robot.data.default_joint_pos.torch[env_ids].clone()
        joint_pos += sample_uniform(
            self.cfg.reset_joint_pos_range[0], self.cfg.reset_joint_pos_range[1], joint_pos.shape, joint_pos.device
        )
        joint_vel = self.robot.data.default_joint_vel.torch[env_ids].clone()

        # keep the sampled state inside the joint limits (soft limits are the ones the RL tasks use)
        limits = self.robot.data.soft_joint_pos_limits.torch[env_ids]
        joint_pos = joint_pos.clamp_(limits[..., 0], limits[..., 1])

        # default root pose is (x, y, z, qx, qy, qz, qw); offset by the env origin so envs do not overlap
        root_pose = self.robot.data.default_root_pose.torch[env_ids].clone()
        root_pose[:, :3] += self.scene.env_origins[env_ids]
        root_vel = self.robot.data.default_root_vel.torch[env_ids].clone()

        self.joint_pos[env_ids] = joint_pos  # keep the cached buffers in sync for _get_rewards in this step
        self.joint_vel[env_ids] = joint_vel

        self.robot.write_root_pose_to_sim_index(root_pose=root_pose, env_ids=env_ids)
        self.robot.write_root_velocity_to_sim_index(root_velocity=root_vel, env_ids=env_ids)
        self.robot.write_joint_position_to_sim_index(position=joint_pos, env_ids=env_ids)
        self.robot.write_joint_velocity_to_sim_index(velocity=joint_vel, env_ids=env_ids)
