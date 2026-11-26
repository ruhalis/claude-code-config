# Import migration: old names → Isaac Sim 6.2 / Isaac Lab 3.0

Target: Isaac Lab 3.0.0 pairs with Isaac Sim 6.2.0.0 (Lab `pyproject.toml` `isaacsim` extra), Python 3.12.
Use this file to port old code forward; never write 2.x or pre-2025 names.

- `omni.isaac.*` (Sim): renamed to `isaacsim.*` in 4.5. No shim ships in 6.2 (its tree holds no `omni.isaac.*` API
  module), so the old import fails with `ModuleNotFoundError`.
- `omni.isaac.lab*` (Lab): renamed to `isaaclab*` in Lab 2.0, no shim either.
- Many `isaacsim.*` modules in the Sim tables below are themselves deprecated in 6.x. They still import and log a
  warning; prefer the Lab in-tree API when Lab provides one, else the `isaacsim.*.experimental.*` module.
- Upstream: Sim rename table `https://docs.isaacsim.omniverse.nvidia.com/5.1.0/overview/extensions_renaming.html`;
  Sim 5.1 → 6.x audit tool `source/tools/isaac_sim_migration/audit_isaac_sim_6_0.py` (Sim repo, not in the wheel).

## Isaac Sim rename rules

"6.2" = state of the target in Sim 6.2 (extension.toml `[deprecation]`).

| Old (≤ 4.2)                          | New name (4.5+)                              | 6.2 status and what to use                     |
|--------------------------------------|----------------------------------------------|------------------------------------------------|
| `omni.isaac.kit.SimulationApp`       | `isaacsim.SimulationApp` (`isaacsim.simulation_app`) | current. In Lab scripts do not construct it: `add_launcher_args` + `launch_simulation` |
| `omni.isaac.core`                    | `isaacsim.core.api`                          | deprecated since 6.0 → `isaacsim.core.experimental.*` |
| `omni.isaac.core.utils.*`            | `isaacsim.core.utils.*`                      | deprecated → Lab `isaaclab.sim.utils.{stage,prims,queries,transforms,semantics}`, else `isaacsim.core.experimental.utils` |
| `omni.isaac.core.objects`            | `isaacsim.core.api.objects`                  | deprecated → `isaacsim.core.experimental.objects` |
| `omni.isaac.core.robots`             | `isaacsim.core.api.robots`                   | deprecated → Lab `Articulation`, or `isaacsim.core.experimental.prims.Articulation` |
| `omni.isaac.core.prims`              | `isaacsim.core.prims` (classes renamed, below) | deprecated → `isaacsim.core.experimental.prims`; Lab: `isaaclab.sim.views.FrameView` for xform views |
| `omni.isaac.core.articulations`      | `isaacsim.core.prims` (`Articulation`/`ArticulationView`); `ArticulationSubset`, `ArticulationGripper` in `isaacsim.core.api.articulations` | deprecated, same replacements |
| `omni.isaac.cloner`                  | `isaacsim.core.cloner`                       | extension still present; Lab code uses `isaaclab.cloner` |
| `omni.isaac.core.utils.nucleus`      | `isaacsim.storage.native`                    | current. Lab asset roots: `isaaclab.utils.assets` (`ISAAC_NUCLEUS_DIR`, `ISAACLAB_NUCLEUS_DIR`) |
| `omni.isaac.sensor`                  | `isaacsim.sensors.physics`, `.camera`, `.rtx` (split by class) | all three deprecated → `isaacsim.sensors.experimental.physics` / `.rtx`; Lab: `isaaclab.sensors` |
| `omni.isaac.range_sensor`            | `isaacsim.sensors.physx`                     | deprecated → `isaacsim.sensors.experimental.physics` (`RaycastSensor`) |
| `omni.isaac.dynamic_control`         | none                                         | no replacement; use Lab `Articulation` or `isaacsim.core.experimental.prims` |
| `omni.isaac.motion_generation`       | `isaacsim.robot_motion.motion_generation`    | deprecated → `isaacsim.robot_motion.experimental.motion_generation`, `isaacsim.robot_motion.cumotion` |
| `omni.isaac.manipulators`            | `isaacsim.robot.manipulators`                | deprecated, no replacement; maintained examples: `isaacsim.robot_motion.examples` |
| `omni.isaac.franka`                  | `isaacsim.robot.manipulators.examples.franka` | deprecated with `manipulators`; Lab: `isaaclab_assets.robots.franka` |
| `omni.isaac.wheeled_robots`          | `isaacsim.robot.wheeled_robots`              | deprecated → `isaacsim.robot.experimental.wheeled_robots` (OmniGraph nodes: `isaacsim.robot.wheeled_robots.nodes`) |
| `omni.importer.urdf`                 | `isaacsim.asset.importer.urdf`               | current, but the Kit-command/`_urdf` API is gone (3.x importer is Python); Lab: `UrdfConverter` |
| `omni.importer.mjcf`                 | `isaacsim.asset.importer.mjcf`               | current, new `MJCFImporter`; Lab: `MjcfConverter` |
| `omni.isaac.ros2_bridge`             | `isaacsim.ros2.bridge`                       | current; saved ROS 2 publisher graphs need review (audit rules) |
| `omni.isaac.gym`                     | none                                         | removed; use Isaac Lab |
| `omni.physics.tensors.impl.api`      | `omni.physics.tensors.api`                   | module path moved in recent Sim (class identities unchanged) |

Direct `isaacsim.*` import in Lab code: start the app first, then
`from isaaclab.sim.utils import enable_extension; enable_extension("<ext>")` before the first import from that
extension (stock Lab Kit apps no longer preload them). Do not import `enable_extension` from
`isaacsim.core.experimental.utils.app`.

### Class renames in `isaacsim.core.prims` (deprecated module)

The old single-prim name now means the batched view class, so a module-only rename silently changes semantics.

| Old (`omni.isaac.core.*`) | New (`isaacsim.core.prims`) |
|---------------------------|-----------------------------|
| `Articulation`            | `SingleArticulation`        |
| `ArticulationView`        | `Articulation`              |
| `RigidPrim`               | `SingleRigidPrim`           |
| `RigidPrimView`           | `RigidPrim`                 |
| `XFormPrim`               | `SingleXFormPrim`           |
| `XFormPrimView`           | `XFormPrim`                 |
| `GeometryPrim`            | `SingleGeometryPrim`        |
| `GeometryPrimView`        | `GeometryPrim`              |

`isaacsim.core.experimental.prims` (the 6.x target) has no single-prim classes: `Articulation`, `RigidPrim`,
`XformPrim` (lowercase f), `GeomPrim`, `Prim`, `DeformablePrim`, all multi-prim, Warp-array in and out.

## Things that were NOT renamed

Stable across Isaac Sim 4.x / 5.x / 6.x:

- `omni.usd` — USD context, stage helpers
- `omni.kit.*` — Kit framework (`omni.kit.app`, `omni.kit.commands`, `omni.kit.viewport.utility`, ...)
- `omni.physx.*` — PhysX low-level APIs
- `carb`, `pxr` (`UsdGeom`, `UsdLux`, `UsdPhysics`, `Gf`, `Sdf`, `Vt`, ...), `warp`

Exception: `omni.physics.tensors.impl.api` → `omni.physics.tensors.api` (table above).

## Isaac Lab rename rules

| Old (≤ 1.4)                                     | New (2.0+, unchanged in 3.0)              |
|-------------------------------------------------|-------------------------------------------|
| `omni.isaac.lab`                                | `isaaclab`                                |
| `omni.isaac.lab.sim`                            | `isaaclab.sim`                            |
| `omni.isaac.lab.assets`                         | `isaaclab.assets`                         |
| `omni.isaac.lab.envs`                           | `isaaclab.envs`                           |
| `omni.isaac.lab.envs.mdp`                       | `isaaclab.envs.mdp`                       |
| `omni.isaac.lab.scene`                          | `isaaclab.scene`                          |
| `omni.isaac.lab.terrains`                       | `isaaclab.terrains`                       |
| `omni.isaac.lab.sensors`                        | `isaaclab.sensors`                        |
| `omni.isaac.lab.actuators`                      | `isaaclab.actuators`                      |
| `omni.isaac.lab.controllers`                    | `isaaclab.controllers`                    |
| `omni.isaac.lab.managers`                       | `isaaclab.managers`                       |
| `omni.isaac.lab.utils`                          | `isaaclab.utils`                          |
| `omni.isaac.lab.app`                            | `isaaclab.app` (then see AppLauncher below) |
| `omni.isaac.lab_assets`                         | `isaaclab_assets` (split into `.robots` and `.sensors`) |
| `omni.isaac.lab_assets.anymal`                  | `isaaclab_assets.robots.anymal`           |
| `omni.isaac.lab_tasks`                          | `isaaclab_tasks`                          |
| `omni.isaac.lab_tasks.utils.wrappers.<lib>` (RL wrappers) | `isaaclab_rl.<lib>` (`rsl_rl`, `rl_games`, `skrl`, `sb3`) |

## Lab 2.x → 3.0

Verified against the v3.0.0 clone (`LAB3`). Everything else: `LAB3/docs/source/isaaclab/migrating.rst`
(authoritative, section order = migration order) and `LAB3/skills/user/migrate-2x-to-3x/` (router, checks).
Old code often keeps running through deprecation shims (warns, removed in 3.1/3.2/4.0); write the new form.

### Install, launch, CLI, tasks

| Old (2.x) | New (3.0) | Note |
|---|---|---|
| conda, Python 3.11, `./isaaclab.sh -i` | `uv run [--extra isaacsim] isaaclab ...`, Python `>=3.12,<3.13` | `./isaaclab.sh train ...` still works; Sim extra pins Sim 6.2.0.0 |
| `./isaaclab.sh -p scripts/reinforcement_learning/<lib>/train.py --task X` | `uv run isaaclab train --rl_library <lib> --task X` | `rsl_rl`, `rl_games`, `skrl`, `sb3`, `rlinf`; per-library scripts removed; also `play`, `train_multigpu`, `zero_agent`, `random_agent`, `list_envs`, `benchmark` (`cli/__init__.py:185-194`) |
| `--resume --load_run R`, `--use_pretrained_checkpoint` | `--checkpoint <path\|latest\|best\|pretrained>` | one flag for train, resume, play |
| `--headless` (flag) | no such flag in `add_launcher_args` (`kit_launcher.py:340-440`); no `--viz` = headless | `--viz kit` opens a viewport; `--viz none` disables all; `--headless` no longer suppresses visualizers |
| `--enable_cameras` | auto-set when the scene has Kit camera sensors | `sim_launcher.py:643-649`; `--video` sets it |
| `--video` + `gym.wrappers.RecordVideo` | `env_cfg.video_recorders = [VideoRecorderCfg(source="visualizer", ...)]` | `isaaclab.envs.utils.video_recorder_cfg`; `recording_hooks` removed |
| `AppLauncher(args).app`, `simulation_app.close()` | `add_launcher_args(parser)`; `with launch_simulation(cfg, args_cli):` | `from isaaclab.app import add_launcher_args, launch_simulation`; `AppLauncher` is a deprecated adapter (`app_launcher.py`); Lab modules import before Kit now |
| `@hydra_task_config(task, agent_entry)` | `isaaclab train` / `isaaclab play`; custom scripts: `setup_preset_cli(parser)` + `parse_env_cfg(task, device, num_envs, overrides=[...])` | `hydra_task_config` is gone; `resolve_task_config` in `isaaclab_tasks/utils/hydra.py:442` |
| task ids `Isaac-Cartpole-v0` | `Isaac-Cartpole`, `Isaac-Cartpole-Direct` | no `-v0`; `isaaclab list_envs [--show_presets]` |
| `isaaclab_tasks.{direct,manager_based}.<task>` | `isaaclab_tasks.core.<task>`, `isaaclab_tasks.contrib.*` | e.g. `core/velocity/velocity_env_cfg.py`, `core/cartpole/` (direct and manager files share a package) |
| tasks found by importing `isaaclab_tasks` | downstream packages register via entry-point group `isaaclab.tasks` (module path); `isaaclab` CLI calls `load_external_tasks()` | `cli/__init__.py:39-55`; plain `import isaaclab_tasks` does not load external ones |
| `isaaclab.test.benchmark`, `benchmark_*.py`, `run_*_benchmarks.sh` | `isaaclab benchmark {runtime,startup,training,play}`, `isaaclab.benchmark` | backend via `physics=` token |
| `--viz newton`, `NewtonVisualizerCfg` | `--viz newton_gl` / `newton_rtx`, `NewtonGLVisualizerCfg` / `NewtonRTXVisualizerCfg` | `isaaclab_visualizers.newton`; `tiled_cam_*` fields → `streaming_*` |

### Backends, sim cfg, schemas

| Old (2.x) | New (3.0) | Note |
|---|---|---|
| `SimulationCfg(physx=sim_utils.PhysxCfg(...))`, `.render`, `.rendering_mode` | `SimulationCfg(physics=PhysxCfg(...))` with `from isaaclab_physx.physics import PhysxCfg` | 2.3.2 `simulation_cfg.py:341,412,424`; 3.0 `:114`; `physics=None` means `PhysxCfg()`. `sim_utils.PhysxCfg` no longer exists |
| one backend, PhysX | `NewtonCfg(solver_cfg=MJWarpSolverCfg(...))` from `isaaclab_newton.physics`; `OvPhysxCfg` from `isaaclab_ov.physics` | `Articulation`/`RigidObject`/sensors dispatch to the active backend (factory), imports unchanged |
| hard-coded backend in env cfg | `PresetCfg` in `SimulationCfg.physics`; pick with `physics=newton_mjwarp` | see `common-cfgs.md`; `from isaaclab_tasks.utils import PresetCfg`; `PhysxAutoCfg` in `isaaclab.physics` |
| `from isaaclab.assets import SurfaceGripper, SurfaceGripperCfg` | `from isaaclab_physx.assets import ...` | PhysX only |
| `sim_utils.RigidBodyPropertiesCfg`, `CollisionPropertiesCfg`, `ArticulationRootPropertiesCfg`, `JointDrivePropertiesCfg`, `MassPropertiesCfg`, `Physx*PropertiesCfg` | schema fragments in a list: `sim_utils.UsdPhysicsRigidBodyCfg` + `isaaclab_physx.sim.schemas.PhysxRigidBodyCfg`; `UsdPhysicsCollisionCfg` + `PhysxCollisionCfg`; `PhysxArticulationCfg` (+ `isaaclab_newton.sim.schemas.NewtonArticulationCfg`); `UsdPhysicsDriveCfg` + `PhysxJointCfg`; `MassCfg` | old names work with `DeprecationWarning`, removed in 3.2; full map `migrating.rst:411-470` (rubric at :256); slots `rigid_props`, `articulation_props`, `collision_props`, `mass_props`, `joint_drive_props` take a fragment, list or `{pattern: [..]}` |
| `max_effort`, `max_velocity` on joint-drive cfgs | `max_force`, `max_joint_velocity` | deprecated aliases until 4.0 |
| `sim_utils.RigidBodyMaterialCfg(friction_combine_mode=...)` | `isaaclab_physx.sim.spawners.materials.PhysxRigidBodyMaterialCfg` (combine modes), `isaaclab.sim.spawners.materials.RigidBodyMaterialBaseCfg` (friction, restitution, density) | old name warns, removal 3.2 (`physics_materials_cfg.py:308-328`); combine modes are PhysX-only |
| `modify_*_properties`, `define_*_properties` writers | `sim_utils.apply_rigid_body_properties`, `apply_collision_properties`, `apply_mass_properties`, `apply_articulation_root_properties`, `apply_joint_drive_properties` | take a prim-path regex and fragment list; deformable writers not deprecated |
| `XformPrimView` | `isaaclab.sim.views.FrameView` | alias kept; `FabricXformPrimView` → `isaaclab_physx.sim.views.FabricFrameView` |
| `isaacsim.core.utils.stage/prims`, `isaacsim.core.simulation_manager.SimulationManager` | `isaaclab.sim.utils.*`; `from isaaclab_physx.physics import PhysxManager as SimulationManager` (Newton: `isaaclab_newton.physics.NewtonManager`) | `migrating.rst:809` |
| `env_cfg.viewer` (`ViewerCfg`), `ViewportCameraController` | `sim.default_visualizer_cfg = VisualizerCfg(eye=..., lookat=...)`; tracking: `sim.visualizer_cfgs = [KitVisualizerCfg(origin_type="asset", origin_track_path="robot")]` | `from isaaclab.visualizers import VisualizerCfg`; `isaaclab_visualizers.kit` |
| `DirectRLEnv._setup_scene` creating assets + `scene.clone_environments(...)` | assets on `InteractiveSceneCfg` (`robot = replace(ROBOT_CFG, prim_path="{ENV_REGEX_NS}/Robot")`); `_setup_scene` is an optional no-op hook | `clone_environments` no longer exists; 3.0 `direct_rl_env.py:149,709`; template `core/cartpole/cartpole_direct_env_cfg.py:20-33` |
| `{ENV_REGEX_NS}` vs `/World/envs/env_.*` | `{ENV_REGEX_NS}` in stock 3.0 cfgs | use it in new code |

### Data, writes, math

| Old (2.x) | New (3.0) | Note |
|---|---|---|
| quaternion `(w, x, y, z)`, identity `(1,0,0,0)` | `(x, y, z, w)`, identity `(0,0,0,1)` | new = `old[1:] + old[:1]`; applies to `rot`, goals, `isaaclab.utils.math`, `OffsetCfg.rot`; `scripts/tools/find_quaternions.py` (own code only), `WARN_ON_TORCH_QUATF_ACCESS=1` at runtime |
| `convert_quat(q, "xyzw")` on Lab data | not needed | keep only for external wxyz data |
| `robot.data.joint_pos` is a `torch.Tensor` | `ProxyArray`: `.torch` (zero-copy tensor), `.warp` | applies to assets and sensor data (`isaaclab/utils/warp/proxy_array.py`); `wp.to_torch(p)` shim warns; `torch.*` calls on it warn once |
| `write_root_pose_to_sim(pose, env_ids)` | `write_root_pose_to_sim_index(root_pose=pose, env_ids=env_ids)` or `..._mask(root_pose=, env_mask=)` | keyword-only; pose is `[x y z qx qy qz qw]`; same split for velocity, joint position/velocity/stiffness/damping/limits |
| `write_root_state_to_sim`, `write_joint_state_to_sim` | pose writer + velocity writer (`root_velocity=`), `write_joint_position_to_sim_index(position=)` + `write_joint_velocity_to_sim_index(velocity=)` | no `_index` root-state writer; joint writers take `joint_ids=` |
| `write_joint_position_limit_to_sim(limits)` etc. | `write_joint_position_limit_to_sim_index(limits=, joint_ids=, env_ids=)` | also `..._velocity_limit_...`, `..._effort_limit_...`, `..._armature_...`, `..._friction_coefficient_...` |
| `robot.set_joint_position_target(t, joint_ids=)` (also velocity, effort) | `robot.actuators.target_command.set_position_index(value=t, joint_ids=)` (`set_velocity_index`, `set_effort_index`) | keyword-only; old methods warn; LEAPP-exported terms keep the old `set_joint_*_target_index` |
| `data.joint_pos_target`, `joint_vel_target`, `joint_effort_target`, `computed_torque`, `applied_torque` | `actuators.target_command.position/velocity/effort`, `actuators.computed_effort`, `actuators.applied_effort` | `ArticulationData.gear_ratio` removed |
| `root_physx_view` | `root_view` | backend-specific type; `root_physx_view` warns on PhysX |
| `write_object_*_to_sim`, `data.object_*`, `find_objects` (RigidObjectCollection) | `write_body_*_to_sim` (velocity → `write_body_com_velocity_to_sim`), `data.body_*`, `find_bodies`, `body_ids=` | |
| `data.body_incoming_joint_wrench_b` | `JointWrenchSensorCfg` in the scene, `sensor.data.force.torch` / `.torque.torch`; obs `mdp.body_incoming_wrench` | PhysX, Newton, OvPhysX |
| `TimestampedBufferWarp` | `TimestampedBuffer(wp.zeros(..))` | custom data classes only |

### Actuators

| Old (2.x) | New (3.0) | Note |
|---|---|---|
| `effort_limit_sim`, `velocity_limit_sim` (cfg) | `joint_effort_limit`, `joint_velocity_limit` | solver-side; aliases to 3.1 |
| `effort_limit`, `velocity_limit` (cfg) | `actuator_effort_limit`, `actuator_velocity_limit` | actuator-model rated limits |
| runtime group `.armature/.friction/.effort_limit_sim` | read `data.joint_armature`, `joint_friction_coeff`, `joint_effort_limits`; write `write_joint_*_to_sim_index` | `ActuatorBase._parse_joint_parameter` → `resolve_joint_parameter` |
| explicit actuator groups got solver effort limit 1e9 | solver keeps `joint_effort_limit` | set it ≥ `actuator_effort_limit` if the asset authors a tight limit |
| `write_actuator_stiffness_to_sim`, `_damping_` | `mdp.events.randomize_actuator_gains` | `SimulationCfg.use_newton_actuators=True` lets Newton run `IdealPDActuatorCfg`/`DCMotorCfg` natively |

### Sensors

| Old (2.x) | New (3.0) | Note |
|---|---|---|
| `Imu`, `ImuCfg` (full state, `gravity_bias`) | `Pva`, `PvaCfg` (no gravity); new `Imu` only gives `ang_vel_b`, `lin_acc_b` incl. gravity | `mdp.imu_orientation`/`imu_projected_gravity` → `mdp.pva_orientation`/`pva_projected_gravity` |
| `TiledCamera`, `TiledCameraCfg` | `Camera`, `CameraCfg` (`renderer_cfg=`) | tiled path now in `Camera`; old names deprecated (`tiled_camera.py`) |
| `CameraCfg(depth_clipping_behavior=...)` | on the renderer cfg (`IsaacRtxRendererCfg`) | field deprecated in `camera_cfg.py:75` |
| `RayCasterCfg(attach_yaw_only=True/False)` | `ray_alignment="yaw"` / `"base"` (+ `"world"`) | `RayCasterData.pos_w/quat_w/ray_hits_w` are `ProxyArray`; `RayCaster.meshes` key is `(prim_path, device)` |
| `ContactSensorData.net_forces_w` | still there: total force on Newton/OvPhysX/PhysX 6.2+; prefer `net_normal_forces_w`, `net_friction_forces_w`, `normal_force_matrix_w`, `friction_force_matrix_w` | `pos_w`, `quat_w` on contact data deprecated (use `FrameTransformer`); `track_pose` is not available on Newton |

### Other packages

| Old (2.x) | New (3.0) | Note |
|---|---|---|
| `RslRlPpoActorCriticCfg` (`policy=`) | `RslRlMLPModelCfg` for `actor` and `critic` | old class deprecated for rsl-rl ≥ 4 (`rl_cfg.py:367-375`); `rsl_rl/utils.py:78` bridges versions |
| `UrdfConverterCfg(make_instanceable, usd_file_name, replace_cylinders_with_capsules, root_link_name)` | dropped or ignored; output at `{usd_dir}/{robot}/{robot}.usda`; `NaturalFrequencyGainsCfg` → `PDGainsCfg` | `convert_urdf.py` flags: `--fix-base --joint-stiffness --joint-damping --viz kit`; MJCF: `merge_mesh`, `collision_from_visuals`, `collision_type`, `self_collision` |
| `isaaclab.devices.openxr` (`OpenXRDevice`, `XrCfg`) | `isaaclab_teleop` (`IsaacTeleopDevice`, `IsaacTeleopCfg`, `XrCfg`); env cfg field `isaac_teleop` | needs `--extra teleop` |
| deformable body cfgs/APIs | see `migrating.rst` "Migration of deformables" | |

Isaac Gym → Lab: `migrating.rst` "Migration from Isaac Gym and IsaacGymEnvs", `LAB3/skills/user/migrate-from-isaac-gym/`.
Asset to Newton: `LAB3/skills/user/prepare-assets-for-newton/`.

## Directory rename (Lab repo)

| Old path                                     | New path (3.0)                           |
|----------------------------------------------|------------------------------------------|
| `source/standalone/workflows/<lib>/train.py` (2.x: `scripts/reinforcement_learning/<lib>/train.py`) | `scripts/reinforcement_learning/train.py` (or `isaaclab train --rl_library <lib>`) |
| `source/standalone/workflows/robomimic/`     | `scripts/imitation_learning/robomimic/`  |
| `source/extensions/omni.isaac.lab/`          | `source/isaaclab/`                       |
| `source/extensions/omni.isaac.lab_tasks/`    | `source/isaaclab_tasks/` (tasks under `core/`, `contrib/`, `benchmark/`) |
| `source/extensions/omni.isaac.lab_assets/`   | `source/isaaclab_assets/`                |
| (new)                                        | `source/isaaclab_physx/`, `isaaclab_newton/`, `isaaclab_ov/`, `isaaclab_visualizers/`, `isaaclab_teleop/` |

## Quick translation pattern

Map each old module by its **longest matching prefix** of whole dotted components (first match wins;
`omni.isaac.core_nodes` does not match `omni.isaac.core`):

1. `omni.isaac.lab_tasks.utils.wrappers.<lib>` → `isaaclab_rl.<lib>`
2. `omni.isaac.lab` → `isaaclab`, `omni.isaac.lab_tasks` → `isaaclab_tasks`, `omni.isaac.lab_assets` → `isaaclab_assets` (submodules move under `.robots`/`.sensors`)
3. `omni.isaac.kit` → `isaacsim.simulation_app`; in a Lab script replace the whole launcher with `launch_simulation`
4. `omni.isaac.core.utils.nucleus` → `isaaclab.utils.assets` constants (or `isaacsim.storage.native`)
5. `omni.isaac.core.utils.{stage,prims,...}` → `isaaclab.sim.utils.*`
6. `omni.isaac.core.prims` / `.articulations` / `.robots` → Lab `Articulation`, `RigidObject`, `FrameView`; otherwise `isaacsim.core.experimental.prims` (not the deprecated `isaacsim.core.prims` class table)
7. every other row of the Isaac Sim table, using the 6.2 column
8. `omni.importer.` → `isaacsim.asset.importer.` (Lab: its converters)
9. `source/standalone/workflows/` → `scripts/reinforcement_learning/` (or `scripts/imitation_learning/`)

There is no catch-all: `omni.isaac.` → `isaacsim.` produces modules that do not exist
(`isaacsim.sensor`, `isaacsim.kit`, `isaacsim.franka`, `isaacsim.ros2_bridge`, ...).
Flag any unmapped `omni.isaac.*` for lookup (audit tool, rename table link above) instead of guessing.
Afterwards grep the result for `isaacsim\.core\.(api|prims|utils)` and `isaacsim\.sensors\.(camera|physics|physx|rtx)`:
all are deprecated in 6.2 (step 5/6 were skipped or no Lab equivalent exists).

If the user pastes old code and asks for help, **translate it first**, then explain what you changed.
