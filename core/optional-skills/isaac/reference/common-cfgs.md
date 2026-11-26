# Common Cfg snippets (Isaac Lab 3.0)

Drop-in fragments for the configs you write over and over, checked against Isaac Lab 3.0.0. Quaternions are
`(x, y, z, w)`, identity `(0.0, 0.0, 0.0, 1.0)`; `.data.*` values are `ProxyArray` (`.torch` for a tensor).
Prefer `{ENV_REGEX_NS}` in asset and sensor prim paths (the stock 3.0 tasks do).

## Backend support

Backends: Isaac Sim PhysX (needs Kit), Newton (Warp, kit-less), OvPhysX (PhysX without Kit; never in the
same process as Kit). Kit-less = no Isaac Sim install; check `LAB3/docs/source/concepts/physics_backends.rst`.

| Snippet | PhysX (Kit) | Newton | OvPhysX | Notes |
|---|---|---|---|---|
| Articulation, actuators, scene | yes | yes | yes | backend-neutral; the `Physx*` schema fragments are also read by Newton's USD importer |
| Contact sensor | yes | yes (no `track_pose`) | yes | shape-level `sensor_shape_prim_expr` / `filter_shape_prim_expr` Newton only |
| RayCaster | yes, static Warp meshes | yes, live BVH, sees dynamic bodies | yes, static Warp meshes | Newton ignores `mesh_prim_paths`; `global_world_only` is Newton-only |
| Camera | `IsaacRtxRendererCfg` (needs Kit) | `NewtonWarpRendererCfg` (kit-less) | `OVRTXRendererCfg` (kit-less) | output support differs per renderer |
| Imu, Pva, FrameTransformer, JointWrenchSensor | yes | yes | yes | |
| Terrain | yes | yes | yes | mesh terrain; combine modes are PhysX-only |
| URDF spawn | needs the importer: Kit, or the standalone importer wheel (`--extra importers`) kit-less | | | prefer converting offline |
| Physics preset | yes | yes | yes | |

Dropped snippets: none; every class below still exists. `TiledCameraCfg` is now a deprecated alias of the
camera and is not shown. No snippet uses 2.x names (`RigidBodyPropertiesCfg`, `effort_limit_sim`, ...); the
mapping is in `import-migration.md`.

## Articulation from a USD file (backend-neutral)

```python
import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab_newton.sim.schemas import NewtonArticulationCfg
from isaaclab_physx.sim.schemas import PhysxArticulationCfg, PhysxRigidBodyCfg

ROBOT_CFG = ArticulationCfg(
    prim_path="{ENV_REGEX_NS}/Robot",
    spawn=sim_utils.UsdFileCfg(
        usd_path="/path/to/robot.usd",
        activate_contact_sensors=True,            # stock assets set it; needed if a ContactSensor reads this robot
        rigid_props=[
            sim_utils.UsdPhysicsRigidBodyCfg(rigid_body_enabled=True),
            PhysxRigidBodyCfg(disable_gravity=False, max_depenetration_velocity=10.0),
        ],
        articulation_props=[
            PhysxArticulationCfg(
                enabled_self_collisions=False,
                solver_position_iteration_count=4,
                solver_velocity_iteration_count=0,
            ),
            NewtonArticulationCfg(self_collision_enabled=False),
        ],
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.5),
        rot=(0.0, 0.0, 0.0, 1.0),                 # x, y, z, w
        joint_pos={".*": 0.0},
    ),
    actuators={
        "all_joints": ImplicitActuatorCfg(
            joint_names_expr=[".*"],
            stiffness=100.0,
            damping=10.0,
            joint_effort_limit=200.0,
            joint_velocity_limit=10.0,
        ),
    },
)
```

- `stiffness`/`damping` have no default (MISSING): set them, or `None` to keep the USD values.
- Position control: `robot.actuators.target_command.set_position_index(value=t, joint_ids=ids)` (keyword-only), with
  stiffness > 0; effort control: stiffness 0 and `set_effort_index`. `robot.set_joint_*_target` is deprecated.
- `joint_effort_limit`/`joint_velocity_limit` go to the solver (velocity enforcement is backend-dependent).
  `actuator_effort_limit`/`actuator_velocity_limit` are the actuator model's rated limits: they clip explicit
  actuators (`IdealPDActuatorCfg`, `DCMotorCfg` + `saturation_effort`, `DelayedPDActuatorCfg`) and are not sent to
  the solver. An explicit group keeps the solver effort limit, so set `joint_effort_limit >= actuator_effort_limit`.
- Property slots take a fragment, a list of fragments or `{"/.*": [..]}`; edit `spawn.articulation_props` as a list,
  not as one object. A PhysX-only asset can use the `Physx*` fragments alone.

## Articulation from a URDF (convert at runtime)

```python
spawn=sim_utils.UrdfFileCfg(
    asset_path="/path/to/robot.urdf",
    fix_base=False,                               # required (MISSING)
    merge_fixed_joints=True,
    # joint_drive defaults to PD gains of None (keep URDF values); the actuator cfg sets the gains.
    # Ignored by importer 3.0: make_instanceable, usd_file_name, replace_cylinders_with_capsules, root_link_name,
    # convert_mimic_joints_to_normal_joints. Output lands at {usd_dir}/{robot}/{robot}.usda.
)
```

For training, prefer offline conversion (`<IsaacLab>/scripts/tools/convert_urdf.py <urdf> <out_dir> --fix-base`,
or the project's own converter) and spawn the USD with `UsdFileCfg`. MJCF: `sim_utils.MjcfFileCfg`
(`merge_mesh`, `collision_from_visuals`, `collision_type`, `self_collision`).

## Camera sensor

Camera and the old TiledCamera are one class (`Camera`; the `renderer_cfg` decides the pipeline). Camera rendering
is switched on by the launcher when the scene has Kit camera sensors (`sim_launcher.py:643-649`) and by `--video`
(`isaaclab_rl/entrypoints/common.py:264`). There is no `--enable_cameras` or `--headless` flag in 3.0.0: the launcher
parser rejects both (`isaaclab_physx/test/app/test_kit_launcher.py:227`). `migrating.rst` ("Visualizer CLI") still
shows them; it is stale, never pass either.

```python
import isaaclab.sim as sim_utils
from isaaclab.sensors import CameraCfg
from isaaclab_newton.renderers import NewtonWarpRendererCfg   # kit-less; Kit: isaaclab_physx.renderers.IsaacRtxRendererCfg

camera_cfg = CameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/head/Camera",
    update_period=0.1,                            # 10 Hz; 0 = every step
    height=120,
    width=160,
    data_types=["rgb", "distance_to_image_plane"],   # "depth" is an alias of the latter
    spawn=sim_utils.PinholeCameraCfg(
        focal_length=24.0,
        focus_distance=400.0,
        horizontal_aperture=20.955,
        clipping_range=(0.1, 20.0),
    ),
    offset=CameraCfg.OffsetCfg(pos=(0.1, 0.0, 0.05), rot=(-0.5, 0.5, -0.5, 0.5), convention="ros"),  # x, y, z, w
    renderer_cfg=NewtonWarpRendererCfg(),         # omit for the runtime default
)
```

- `OVRTXRendererCfg` (`isaaclab_ov.renderers`) is the other kit-less renderer and cannot share a process with Kit.
- Newton Warp has no `motion_vectors` or `simple_shading_*`; `instance_id_segmentation_fast` is RTX only; asking for
  an unsupported output fails at camera init (`concepts/sensors/camera.rst`).
- Task presets pick the renderer with `renderer=newton_renderer|isaacsim_rtx|ovrtx`.

## Contact sensor (for foot contact, collision detection)

PhysX, Newton and OvPhysX; `ContactSensor` is a backend factory.

```python
from isaaclab.sensors import ContactSensorCfg

contact_cfg = ContactSensorCfg(
    prim_path="{ENV_REGEX_NS}/Robot/.*FOOT",
    history_length=3,
    track_air_time=True,
    update_period=0.0,                            # every step
    # filter_prim_paths_expr=["{ENV_REGEX_NS}/Object"],   # per-partner force_matrix_w; one sensor body per env
)
```

`data.net_forces_w` is the total force (normal + friction) on Newton, OvPhysX and Sim PhysX 6.2+; on 6.1 it warns
and returns the normal part. Use `net_normal_forces_w`, `net_friction_forces_w`, `normal_force_matrix_w`,
`friction_force_matrix_w` when the split matters. `track_pose` is not supported on Newton; the sensor's `pos_w`/`quat_w`
are deprecated (use `FrameTransformer`).

## RayCaster sensor (height scanner / lidar-like)

```python
from isaaclab.sensors import RayCasterCfg, patterns

height_scanner_cfg = RayCasterCfg(
    prim_path="{ENV_REGEX_NS}/Robot/base",
    update_period=0.02,
    offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),   # rot is (x, y, z, w), default identity
    ray_alignment="yaw",                           # "base" (default), "yaw", "world"; attach_yaw_only is gone
    pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=(1.6, 1.0)),
    debug_vis=False,
    mesh_prim_paths=["/World/ground"],             # PhysX/OvPhysX: static meshes; Newton ignores it
    global_world_only=True,                        # Newton only: hit only shapes shared by all envs (terrain)
)
```

`data.ray_hits_w` is a `ProxyArray` (`.torch`). On Newton the rays see every collision shape in the env unless
`global_world_only=True`; start rays outside the carrier body (the 20 m offset does that).
`isaaclab_newton.sensors.NewtonRaycastSensorCfg` makes the Newton behaviour explicit.

## IMU / PVA / joint wrench

```python
from isaaclab.sensors import ImuCfg, JointWrenchSensorCfg, PvaCfg

imu = ImuCfg(prim_path="{ENV_REGEX_NS}/Robot/base")             # data.ang_vel_b, data.lin_acc_b (gravity included)
pva = PvaCfg(prim_path="{ENV_REGEX_NS}/Robot/base")             # pose, velocity, acceleration, projected gravity
joint_wrench = JointWrenchSensorCfg(prim_path="{ENV_REGEX_NS}/Robot")   # data.force.torch, data.torque.torch
```

The 2.x `Imu` (full state, `gravity_bias`) is now `Pva`.

## Terrain

```python
from isaaclab.sim.spawners.materials import RigidBodyMaterialBaseCfg
from isaaclab.terrains import HfRandomUniformTerrainCfg, TerrainGeneratorCfg, TerrainImporterCfg
# PhysX-only combine modes: from isaaclab_physx.sim.spawners.materials import PhysxRigidBodyMaterialCfg

# Flat ground
flat = TerrainImporterCfg(
    prim_path="/World/ground",
    terrain_type="plane",
    collision_group=-1,
    physics_material=RigidBodyMaterialBaseCfg(static_friction=1.0, dynamic_friction=1.0),
)

# Procedural rough terrain
rough = TerrainImporterCfg(
    prim_path="/World/ground",
    terrain_type="generator",
    collision_group=-1,
    terrain_generator=TerrainGeneratorCfg(
        size=(8.0, 8.0),
        border_width=2.0,
        num_rows=10, num_cols=10,
        sub_terrains={
            "random_rough": HfRandomUniformTerrainCfg(
                proportion=1.0, noise_range=(0.02, 0.10), noise_step=0.02,
                border_width=0.25,
            ),
        },
    ),
    physics_material=RigidBodyMaterialBaseCfg(static_friction=1.0, dynamic_friction=1.0),
)
```

`sim_utils.RigidBodyMaterialCfg(friction_combine_mode=..., ...)` still works but warns (removed in 3.2); the combine
modes live on `PhysxRigidBodyMaterialCfg` and Newton ignores them. `visual_material` defaults to dark for
`generator` and unchanged for `plane`.

## Scene (DirectRLEnv style)

In 3.0 assets and sensors are declared on the scene cfg and built with it; do not create them in `_setup_scene`
(a no-op hook now) or call `scene.clone_environments` (gone).

```python
import isaaclab.sim as sim_utils
from isaaclab.assets import AssetBaseCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.utils import configclass, replace

@configclass
class MySceneCfg(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path="/World/ground", spawn=sim_utils.GroundPlaneCfg())
    robot = replace(ROBOT_CFG, prim_path="{ENV_REGEX_NS}/Robot")
    light = AssetBaseCfg(prim_path="/World/Light", spawn=sim_utils.DistantLightCfg(intensity=2000.0))

scene_cfg = MySceneCfg(
    num_envs=4096,
    env_spacing=4.0,
    # True = shared USD prototypes (fast). Set False only for USD-level per-env variation
    # (scale/texture/color/multi-asset); mass/friction DR works with True.
    replicate_physics=True,
)
```

## Physics backend preset (SimulationCfg)

`SimulationCfg.physics` replaces 2.x `SimulationCfg.physx`. A `PresetCfg` there makes the backend a launch-time
choice; the field named `default` is used when no selector is given. Keep PhysX as `default` when porting a 2.x
task (adding a variant must not change the established default); stock 3.0 tasks default to `newton_mjwarp`.

```python
from isaaclab.sim import SimulationCfg
from isaaclab.utils import configclass
from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg
from isaaclab_physx.physics import PhysxCfg
from isaaclab_tasks.utils import PresetCfg

@configclass
class PhysicsCfg(PresetCfg):
    isaacsim_physx: PhysxCfg = PhysxCfg(bounce_threshold_velocity=0.2)
    newton_mjwarp: NewtonCfg = NewtonCfg(
        solver_cfg=MJWarpSolverCfg(njmax=20, nconmax=20, cone="pyramidal", integrator="implicitfast", impratio=1),
        num_substeps=1,
    )
    default: PhysxCfg = isaacsim_physx

sim: SimulationCfg = SimulationCfg(dt=1 / 120, physics=PhysicsCfg())
```

Select at launch: `uv run isaaclab train --rl_library rsl_rl --task <Task> physics=newton_mjwarp` (also
`physics=isaacsim_physx`). Optional extras seen in stock tasks: `ovphysx: OvPhysxCfg = OvPhysxCfg()`
(`isaaclab_ov.physics`) and `physx: PhysxAutoCfg = PhysxAutoCfg(isaacsim_physx=isaacsim_physx, ovphysx=ovphysx)`
(`isaaclab.physics`; picks Isaac Sim PhysX when Kit is needed, else OvPhysX), then `physics=physx`.
`newton_kamino` uses `NewtonCfg(solver_cfg=KaminoPADMMSolverCfg(...))` for selected tasks. `isaaclab list_envs
--show_presets` lists what a task accepts. A preset replaces the whole section, no field merging.

## Manager-based action terms (common ones)

```python
import isaaclab.envs.mdp as mdp

# Effort/torque on selected joints
joint_effort = mdp.JointEffortActionCfg(
    asset_name="robot", joint_names=[".*"], scale=1.0
)

# Position target
joint_position = mdp.JointPositionActionCfg(
    asset_name="robot", joint_names=[".*"], scale=0.5, use_default_offset=True
)

# Velocity target
joint_velocity = mdp.JointVelocityActionCfg(
    asset_name="robot", joint_names=[".*"], scale=1.0
)
```

## Manager-based observation terms (common ones)

```python
import isaaclab.envs.mdp as mdp
from isaaclab.managers import ObservationTermCfg as ObsTerm

ObsTerm(func=mdp.base_lin_vel)                      # (3,)
ObsTerm(func=mdp.base_ang_vel)                      # (3,)
ObsTerm(func=mdp.projected_gravity)                 # (3,) — gravity vector in body frame
ObsTerm(func=mdp.joint_pos_rel)                     # joint pos relative to default
ObsTerm(func=mdp.joint_vel_rel)                     # joint vel relative to default
ObsTerm(func=mdp.last_action)                       # previous action
ObsTerm(func=mdp.generated_commands, params={"command_name": "base_velocity"})  # cmd input
```

Sensor terms: `mdp.pva_orientation`, `mdp.pva_projected_gravity` (were `imu_*`), `mdp.imu_ang_vel`,
`mdp.imu_lin_acc`, `mdp.body_incoming_wrench` (joint-wrench sensor).

## Manager-based reward terms (common building blocks)

```python
from isaaclab.managers import RewardTermCfg as RewTerm

# Survival
alive = RewTerm(func=mdp.is_alive, weight=1.0)
terminating = RewTerm(func=mdp.is_terminated, weight=-2.0)

# Tracking a velocity command
track_lin_vel = RewTerm(
    func=mdp.track_lin_vel_xy_exp,
    weight=1.0,
    params={"command_name": "base_velocity", "std": 0.5},
)
track_ang_vel = RewTerm(
    func=mdp.track_ang_vel_z_exp,
    weight=0.5,
    params={"command_name": "base_velocity", "std": 0.5},
)

# Penalties
ang_vel_xy = RewTerm(func=mdp.ang_vel_xy_l2, weight=-0.05)
lin_vel_z = RewTerm(func=mdp.lin_vel_z_l2, weight=-2.0)
dof_torques = RewTerm(func=mdp.joint_torques_l2, weight=-2.5e-5)
action_rate = RewTerm(func=mdp.action_rate_l2, weight=-0.01)
```

## Common termination terms

```python
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm

time_out = DoneTerm(func=mdp.time_out, time_out=True)
base_contact = DoneTerm(
    func=mdp.illegal_contact,
    params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base"), "threshold": 1.0},
)
bad_orientation = DoneTerm(
    func=mdp.bad_orientation,
    params={"limit_angle": 0.7},                    # ~40 degrees
)
```
