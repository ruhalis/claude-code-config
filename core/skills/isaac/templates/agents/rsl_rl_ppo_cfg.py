"""
RSL-RL PPO runner cfg for an Isaac Lab 3.0 task (rsl-rl-lib 5.5.1, pinned by isaaclab[rsl-rl]).

# Based on isaaclab_tasks/core/cartpole/agents/rsl_rl_ppo_cfg.py and tools/template/templates/agents/rsl_rl_ppo_cfg @ v3.0.0

Place this under:
    <your_task>/agents/rsl_rl_ppo_cfg.py        (next to agents/__init__.py)
and point the registration at it:
    "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:MyTaskPPORunnerCfg"

rsl-rl >= 4 uses separate actor/critic model cfgs (RslRlMLPModelCfg). The old single `policy =
RslRlPpoActorCriticCfg(...)` with `empirical_normalization` / `actor_obs_normalization` is deprecated: use
`obs_normalization` on each model and a `distribution_cfg` on the actor (init_std replaces init_noise_std).
Every field set below is MISSING in isaaclab_rl.rsl_rl; leave none out. obs_groups maps the rsl_rl observation
sets to the env's observation groups (the env returns {"policy": ...}); add groups here for a privileged critic.
Checkpoints land in logs/rsl_rl/<experiment_name>/<timestamp>/model_<iter>.pt under the cwd.
"""

from isaaclab.utils import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class MyTaskPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 16
    max_iterations = 150  # --max_iterations overrides
    save_interval = 50
    experiment_name = "my_task"
    obs_groups = {"actor": ["policy"], "critic": ["policy"]}
    actor = RslRlMLPModelCfg(
        hidden_dims=[32, 32],
        activation="elu",
        obs_normalization=False,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[32, 32],
        activation="elu",
        obs_normalization=False,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.005,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )
