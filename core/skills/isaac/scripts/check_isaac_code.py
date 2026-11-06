#!/usr/bin/env python3
"""Static checks for Isaac Lab 3.0.0 (Isaac Sim 6.2.0.0, Python 3.12) code. Read-only, stdlib only (ast + re);
runs on the Mac, imports nothing from Isaac and writes no bytecode.

    check_isaac_code.py PATH [PATH ...] [--exclude NAME ...]

PATH is a .py file or a directory, searched recursively for *.py. Below a directory it skips virtual envs
(any directory holding pyvenv.cfg or conda-meta), .git __pycache__ node_modules site-packages .tox .nox
.mypy_cache .pytest_cache .eggs *.egg-info, and third_party / _isaac_sim (the pinned Lab checkout and its
Isaac Sim link are never ours to fix). build/ and dist/ are scanned: a setuptools copy only repeats
findings, while skipping by name could hide a real package; add --exclude NAME to skip more. Each file is
compiled from its bytes exactly as py_compile does (encoding cookie, BOM), in memory, so no __pycache__.

One line per finding, `path:line: RULE message`. Rules whose message says "removed" or "no longer" fail or
misbehave on 3.0.0; "deprecated" ones still run on 3.0.0 (DeprecationWarning) but have a removal date.
  ISC000  syntax or compile error (Isaac Lab 3.0 is Python 3.12: run this with python3 >= 3.12, 3.11 can
          report 3.12-only syntax as an error)
  ISC001  import of omni.isaac.* (renamed isaacsim.* in Sim 4.5; the shims are gone in Sim 6)
  ISC002  import of omni.isaac.lab* (renamed isaaclab* in Lab 2.0; no shim)
  ISC003  import path removed or moved in Lab 3.0 / Sim 6: omni.physics.tensors.impl, isaaclab.test.benchmark,
          isaaclab.envs.utils.recording_hooks, SurfaceGripper(Cfg) from isaaclab.assets,
          isaaclab_physx.physics.SimulationManager, mdp.imu_orientation / imu_projected_gravity,
          TimestampedBufferWarp
  ISC010  omni / carb / isaacsim import (or one of the few Lab modules that import them at import time, e.g.
          the envs.ui windows, keyboard/gamepad devices, PhysxManager) that runs before AppLauncher(...),
          SimulationApp(...) or launch_simulation(...). Plain `isaaclab.*` and `pxr` imports are fine before
          launch in 3.0 (kit-less configs start no Kit at all). Checked only in files that start a launcher,
          so env and cfg modules (imported before or after launch) are exempt.
  ISC011  AppLauncher: deprecated shim in 3.0 that forces Kit even for kit-less configs; use
          add_launcher_args(parser) and `with launch_simulation(cfg, args_cli):` from isaaclab.app
  ISC012  --headless / --enable_cameras / --cpu in a command string or argv list: the launcher parser rejects
          them in 3.0 (headless is the default; --viz selects a visualizer; --device cpu)
  ISC013  scripts/reinforcement_learning/<library>/train.py or play.py: removed, use
          `isaaclab train|play --rl_library <library>` (or scripts/reinforcement_learning/train.py)
  ISC021  a module that calls gym.register, or any parent package __init__.py of it, imports Kit (omni, carb,
          isaacsim, or a Kit-bound Lab module) at import time, directly or through relative / same-package
          imports, so the task package cannot be imported before launch_simulation (the RL entrypoints
          import isaaclab_tasks first); keep them gymnasium-only with lazy string entry points
  ISC030  attach_yaw_only removed from RayCasterCfg: use ray_alignment="yaw" (or "base"; "world" is new)
  ISC031  deprecated actuator limit fields (removed in 3.1): effort_limit_sim / velocity_limit_sim ->
          joint_effort_limit / joint_velocity_limit; effort_limit / velocity_limit -> actuator_* (explicit
          actuators) or joint_* (ImplicitActuatorCfg)
  ISC032  gravity_bias= on ImuCfg / PvaCfg: removed (Pva has no gravity, the new Imu always includes it)
  ISC040  UrdfFileCfg(...) / UrdfConverterCfg(...) without fix_base= (still MISSING; cfg validation fails).
          Skipped when the call has **kwargs or the file assigns .fix_base. joint_drive is optional now.
  ISC050  Isaac Sim module paths deprecated in Sim 6.0 that Lab 3.0's Kit experiences no longer preload
          (isaacsim.core.utils.stage/prims/..., isaacsim.core.prims, isaacsim.core.simulation_manager,
          isaacsim.core.cloner, isaacsim.core.api, isaacsim.sensors.*, ...): use the Lab replacement
  ISC060  write_<root|joint|body|object>_*_to_sim( without _index / _mask: deprecated, use
          write_*_to_sim_index(..., env_ids=) or write_*_to_sim_mask(..., env_mask=)
  ISC061  deprecated asset API: root_physx_view (root_view), set_joint_{position,velocity,effort}_target
          (actuators.target_command.set_*_index), data.joint_{pos,vel,effort}_target / computed_torque /
          applied_torque (actuators.*), RigidObjectCollection object_* names (body_*), XformPrimView
          (FrameView)
  ISC062  removed asset data: data.gear_ratio, data.body_incoming_joint_wrench_b (use JointWrenchSensorCfg)
  ISC070  rot=(1.0, 0.0, 0.0, 0.0): the wxyz identity, but 3.0 quaternions are xyzw so this is a 180 degree
          rotation about x; the identity is (0.0, 0.0, 0.0, 1.0). Heuristic: only exact literals in `rot`.
  ISC071  deprecated viewport config: ViewerCfg / env_cfg.viewer.eye|lookat|... (use
          sim.default_visualizer_cfg = VisualizerCfg(eye=, lookat=)), ViewportCameraController

Only literal usage is matched: aliases (IA = ImplicitActuatorCfg), values passed through **kwargs, .replace(),
attribute assignment after construction (except the cases noted above) and importlib / __import__ are not seen.
Append `# isaac-check: ignore` to a line to silence the findings reported on it.
Exit 0: no findings. 1: at least one finding. 2: usage error (bad option, missing path, no .py files).
"""
import argparse
import ast
import io
import os
import re
import sys
import tokenize
from collections import deque

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", "site-packages", ".tox", ".nox", ".mypy_cache", ".pytest_cache",
    ".eggs", "third_party", "_isaac_sim",
}
LAUNCHERS = {"AppLauncher", "SimulationApp", "launch_simulation"}
KIT_ROOTS = {"omni", "isaacsim", "carb"}
# pxr is not Kit-bound in Lab 3.0: usd-exchange ships it (pyproject.toml) and isaaclab.sim imports it, which tutorials do
# before launch_simulation. Lab modules that import omni / carb / isaacsim unconditionally at import time (module level,
# outside TYPE_CHECKING); everything else under isaaclab* imports without Kit.
LAB_KIT_MODULES = (
    "isaaclab.envs.ui.base_env_window", "isaaclab.envs.ui.empty_window", "isaaclab.envs.ui.manager_based_rl_env_window",
    "isaaclab.ui.widgets.image_plot", "isaaclab.ui.widgets.line_plot", "isaaclab.ui.widgets.ui_widget_wrapper",
    "isaaclab.ui.xr_widgets.instruction_widget", "isaaclab.sim.converters.mesh_converter",
    "isaaclab.devices.keyboard.se2_keyboard", "isaaclab.devices.keyboard.se3_keyboard",
    "isaaclab.devices.gamepad.se2_gamepad", "isaaclab.devices.gamepad.se3_gamepad",
    "isaaclab_physx.physics.physx_manager", "isaaclab_physx.app.kit_stage", "isaaclab_physx.cloner.replicate",
)
_DEVICES = {"Se2Keyboard", "Se3Keyboard", "Se2Gamepad", "Se3Gamepad"}
LAB_KIT_NAMES = {  # lazily exported names whose defining module is in LAB_KIT_MODULES
    "isaaclab.envs.ui": {"BaseEnvWindow", "EmptyWindow", "ManagerBasedRLEnvWindow"},
    "isaaclab.ui.widgets": {"ImagePlot", "LiveLinePlot"},
    "isaaclab.sim.converters": {"MeshConverter"},
    "isaaclab.devices": _DEVICES, "isaaclab.devices.keyboard": _DEVICES, "isaaclab.devices.gamepad": _DEVICES,
    "isaaclab_physx.physics": {"PhysxManager", "IsaacEvents"},
}
IGNORE_RE = re.compile(r"#\s*isaac-check:\s*ignore\b")
# fallback for files that do not parse
OLD_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+(omni\.isaac\b[\w.]*)", re.M)


# ------------------------------------------------------------------ helpers
def is_kit_module(module):
    """True for a module that needs a running Kit app to import (omni, carb, isaacsim, or a Kit-bound Lab module)."""
    if module.split(".")[0] in KIT_ROOTS:
        return True
    return any(module == m or module.startswith(m + ".") for m in LAB_KIT_MODULES)


def pre_launch_ok(node):
    """Imports allowed above the launcher: the isaacsim launcher class itself (no Kit needed)."""
    if isinstance(node, ast.Import):
        return all(a.name in ("isaacsim", "isaacsim.simulation_app") for a in node.names)
    mod = node.module or ""
    names = {a.name for a in node.names}
    if mod == "isaacsim.simulation_app":
        return True
    if mod == "isaacsim":
        return names <= {"SimulationApp", "AppFramework"}
    return False


def kit_modules(node):
    """Absolute Kit-bound modules an Import/ImportFrom node brings in (empty for relative imports)."""
    if isinstance(node, ast.Import):
        return [a.name for a in node.names if is_kit_module(a.name)]
    if node.level == 0 and node.module:
        if is_kit_module(node.module):
            return [node.module]
        return ["{}.{}".format(node.module, a.name) for a in node.names
                if is_kit_module("{}.{}".format(node.module, a.name)) or a.name in LAB_KIT_NAMES.get(node.module, ())]
    return []


def final_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def import_text(node):
    if isinstance(node, ast.Import):
        return "import " + ", ".join(a.name for a in node.names)
    names = ", ".join(a.name for a in node.names)
    return "from {}{} import {}".format("." * node.level, node.module or "", names)


def is_type_checking(test):
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def is_main_guard(test):
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    sides = [test.left] + list(test.comparators)
    has_name = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return has_name and has_main


def decode(data):
    """Source bytes to text the way the interpreter decodes them (cookie, BOM), for comments and regexes."""
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    except SyntaxError:
        encoding = "utf-8"
    return data.decode(encoding, errors="replace")


class Parsed:
    """A parsed file plus the context of every node: enclosing function, TYPE_CHECKING, main guard."""

    def __init__(self, path, text, tree):
        self.path = path
        self.lines = text.splitlines()
        self.tree = tree
        self.parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
        self._import_time = None

    def _chain(self, node):
        while node in self.parent:
            parent = self.parent[node]
            yield node, parent
            node = parent

    def scope(self, node):
        for _, anc in self._chain(node):
            if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return anc
        return None

    def under_if(self, node, pred):
        for child, anc in self._chain(node):
            if isinstance(anc, ast.If) and pred(anc.test) and any(child is s for s in anc.body):
                return True
        return False

    def imports(self):
        return [n for n in ast.walk(self.tree) if isinstance(n, (ast.Import, ast.ImportFrom))]

    def import_time_imports(self):
        """Imports that run when the module is imported (not in functions, TYPE_CHECKING or a main guard)."""
        if self._import_time is None:
            self._import_time = sorted(
                (n for n in self.imports() if self.scope(n) is None and not self.under_if(n, is_type_checking)
                 and not self.under_if(n, is_main_guard)),
                key=lambda n: n.lineno,
            )
        return self._import_time

    def calls(self):
        return [n for n in ast.walk(self.tree) if isinstance(n, ast.Call)]


_CACHE = {}


def load(path):
    """Compile from bytes like py_compile, in memory. Returns (Parsed or None, (line, message) or None)."""
    path = os.path.abspath(path)
    if path in _CACHE:
        return _CACHE[path]
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        compile(data, path, "exec", dont_inherit=True)  # py_compile's check: decoding, syntax, symtable
        tree = ast.parse(data, filename=path)
        result = (Parsed(path, decode(data), tree), None)
    except SyntaxError as exc:
        msg = exc.msg
        if sys.version_info < (3, 12):
            msg += "; parsed with Python {}.{}, Isaac Lab 3.0 code is 3.12: use python3 >= 3.12".format(*sys.version_info[:2])
        result = (None, (exc.lineno or 1, msg))
    except (OSError, ValueError) as exc:
        result = (None, (1, str(exc)))
    _CACHE[path] = result
    return result


# --------------------------------------------------- resolving project-local imports
def resolve_parts(base, parts, names):
    """Files executed by importing `parts` (then `names` from it) below directory `base`."""
    files, cur = [], base
    for i, part in enumerate(parts):
        pkg = os.path.join(cur, part)
        if os.path.isfile(os.path.join(pkg, "__init__.py")):
            files.append(os.path.join(pkg, "__init__.py"))
            cur = pkg
        elif i == len(parts) - 1 and os.path.isfile(pkg + ".py"):
            files.append(pkg + ".py")
            return files
        else:
            return files
    for name in names:
        sub = os.path.join(cur, name)
        if os.path.isfile(os.path.join(sub, "__init__.py")):
            files.append(os.path.join(sub, "__init__.py"))
        elif os.path.isfile(sub + ".py"):
            files.append(sub + ".py")
    return files


def package_root(path):
    """(name, parent dir) of the top package holding `path`, or (None, None)."""
    top = None
    d = os.path.dirname(os.path.abspath(path))
    while os.path.isfile(os.path.join(d, "__init__.py")):
        top = d
        d = os.path.dirname(d)
    return (os.path.basename(top), os.path.dirname(top)) if top else (None, None)


def parent_inits(path):
    """__init__.py of every package above the module at `path`, nearest first, up to the top package."""
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    if os.path.basename(path) == "__init__.py":
        d = os.path.dirname(d)
    out = []
    while os.path.isfile(os.path.join(d, "__init__.py")):
        out.append(os.path.join(d, "__init__.py"))
        d = os.path.dirname(d)
    return out


def local_targets(path, node):
    """Project files an import node executes: relative imports and same-package absolute imports."""
    if isinstance(node, ast.ImportFrom) and node.level > 0:
        base = os.path.dirname(os.path.abspath(path))
        for _ in range(node.level - 1):
            base = os.path.dirname(base)
        parts = node.module.split(".") if node.module else []
        return resolve_parts(base, parts, [a.name for a in node.names if a.name != "*"])
    top, root = package_root(path)
    if not top:
        return []
    if isinstance(node, ast.Import):
        files = []
        for a in node.names:
            parts = a.name.split(".")
            if parts[0] == top:
                files += resolve_parts(root, parts, [])
        return files
    parts = (node.module or "").split(".")
    if parts[0] == top:
        return resolve_parts(root, parts, [a.name for a in node.names if a.name != "*"])
    return []


_CLEAN = set()   # modules whose whole import-time closure is proven Kit-free
_CHAINS = {}     # module -> first Kit chain found from it


def kit_chain(path):
    """Shortest chain of import-time imports from `path` that reaches Kit, as [(file, line, text)], else None.
    Breadth-first over the project-local import graph, each module visited once, so linear in its size."""
    path = os.path.abspath(path)
    if path in _CLEAN:
        return None
    if path in _CHAINS:
        return _CHAINS[path]
    came_from = {path: None}  # module -> (importer, line, import text)
    queue = deque([path])
    while queue:
        cur = queue.popleft()
        parsed, _ = load(cur)
        if parsed is None:
            continue
        for node in parsed.import_time_imports():
            if kit_modules(node) and not pre_launch_ok(node):
                chain = [(cur, node.lineno, import_text(node))]
                while came_from[cur] is not None:
                    cur, line, text = came_from[cur]
                    chain.insert(0, (cur, line, text))
                _CHAINS[path] = chain
                return chain
            for target in local_targets(cur, node):
                target = os.path.abspath(target)
                if target not in came_from and target not in _CLEAN:
                    came_from[target] = (cur, node.lineno, import_text(node))
                    queue.append(target)
    _CLEAN.update(came_from)  # the search exhausted every module it reached
    return None


def chain_finding(chain, what):
    here = os.path.dirname(chain[0][0])
    hops = " -> ".join("{}:{} `{}`".format(os.path.relpath(f, here), line, text) for f, line, text in chain[1:])
    return (chain[0][1], "ISC021", "{} imports Kit at import time: `{}`{}; keep it gymnasium-only (lazy string "
            "entry points)".format(what, chain[0][2], " -> " + hops if hops else ""))


# ------------------------------------------------------------------ rules
def gym_register_calls(p):
    gym_names, register_names = {"gym", "gymnasium"}, set()
    for node in p.imports():
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name in ("gym", "gymnasium"):
                    gym_names.add(a.asname or a.name)
        elif node.module in ("gymnasium", "gym", "gymnasium.envs.registration", "gym.envs.registration"):
            for a in node.names:
                if a.name == "register":
                    register_names.add(a.asname or a.name)
    out = []
    for call in p.calls():
        f = call.func
        on_gym = isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in gym_names
        if (on_gym and f.attr == "register") or (isinstance(f, ast.Name) and f.id in register_names):
            out.append(call)
    return out


# ------------------------------------------------------------------ rule tables
MOVED_MODULES = (
    ("omni.physics.tensors.impl", "omni.physics.tensors.api (same classes, only the module path moved)"),
    ("isaaclab.test.benchmark", "isaaclab.benchmark"),
    ("isaaclab.envs.utils.recording_hooks", "removed; register physics-backend hooks with "
     "SimulationContext.add_render_callback() and record with env_cfg.video_recorders = [VideoRecorderCfg(...)]"),
    ("isaaclab.assets.surface_gripper", "isaaclab_physx.assets (SurfaceGripper moved to the PhysX package)"),
)
MOVED_NAMES = {
    ("isaaclab.assets", "SurfaceGripper"): "from isaaclab_physx.assets import SurfaceGripper",
    ("isaaclab.assets", "SurfaceGripperCfg"): "from isaaclab_physx.assets import SurfaceGripperCfg",
    ("isaaclab_physx.physics", "SimulationManager"): "isaaclab_physx.physics.PhysxManager (import it `as SimulationManager` "
    "to keep call sites backend-agnostic)",
    ("isaaclab.envs.mdp", "imu_orientation"): "pva_orientation (the old full-state Imu is now Pva)",
    ("isaaclab.envs.mdp", "imu_projected_gravity"): "pva_projected_gravity (the old full-state Imu is now Pva)",
    ("isaaclab.utils.buffers", "TimestampedBufferWarp"): "TimestampedBuffer(wp.zeros(...))",
}
MOVED_ATTRS = {"imu_orientation": "pva_orientation", "imu_projected_gravity": "pva_projected_gravity"}

# Isaac Sim 6.0 deprecations from docs/source/isaaclab/migrating.rst ("Python module renames"), longest prefix first.
SIM_DEPRECATED = (
    ("isaacsim.core.utils.extensions", "isaaclab.sim.utils.enable_extension"),
    ("isaacsim.core.utils.stage", "isaaclab.sim.utils.stage"),
    ("isaacsim.core.utils.prims", "isaaclab.sim.utils.prims"),
    ("isaacsim.core.utils.queries", "isaaclab.sim.utils.queries"),
    ("isaacsim.core.utils.transforms", "isaaclab.sim.utils.transforms"),
    ("isaacsim.core.utils.semantics", "isaaclab.sim.utils.semantics"),
    ("isaacsim.core.utils.viewports", "isaacsim.core.rendering_manager.ViewportManager"),
    ("isaacsim.core.prims", "isaaclab.sim.views.FrameView (or isaacsim.core.experimental.prims)"),
    ("isaacsim.core.simulation_manager",
     "isaaclab_physx.physics.PhysxManager or isaaclab_newton.physics.NewtonManager"),
    ("isaacsim.core.cloner", "isaaclab.cloner"),
    ("isaacsim.core.api", "isaaclab.sim / isaacsim.core.experimental.* (Lab 3.0 no longer depends on isaacsim.core.api)"),
    ("isaacsim.replicator.mobility_gen", "isaacsim.replicator.experimental.mobility_gen"),
)

DEPRECATED_ATTRS = {  # any attribute access or call
    "root_physx_view": "root_view (backend-specific view)",
    "set_joint_position_target": "actuators.target_command.set_position_index(value=, joint_ids=)",
    "set_joint_velocity_target": "actuators.target_command.set_velocity_index(value=, joint_ids=)",
    "set_joint_effort_target": "actuators.target_command.set_effort_index(value=, joint_ids=)",
    "find_objects": "find_bodies",
}
DEPRECATED_DATA = {  # only on a `.data` receiver
    "joint_pos_target": "actuators.target_command.position",
    "joint_vel_target": "actuators.target_command.velocity",
    "joint_effort_target": "actuators.target_command.effort",
    "computed_torque": "actuators.computed_effort",
    "applied_torque": "actuators.applied_effort",
}
REMOVED_DATA = {  # only on a `.data` receiver
    "gear_ratio": "removed; read the gear ratio from your actuator configuration",
    "body_incoming_joint_wrench_b": "removed; add a JointWrenchSensorCfg to the scene and read "
    "sensor.data.force.torch / .torque.torch",
}
OBJECT_DATA_RE = re.compile(r"^(default_object_state|object_names|object_(?:link_|com_)?(?:state|pose|pos|quat|vel|"
                            r"lin_vel|ang_vel|acc|lin_acc|ang_acc)_[wb])$")
WRITE_RE = re.compile(r"^write_(?:root|joint|body|object)_\w+_to_sim$")
VIEWER_FIELDS = {"eye", "lookat", "cam_prim_path", "resolution", "origin_type", "env_index", "asset_name", "body_name"}
ACTUATOR_LIMITS = {
    "effort_limit_sim": "joint_effort_limit", "velocity_limit_sim": "joint_velocity_limit",
}
ACTUATOR_CFGS = {"ActuatorBaseCfg", "DCMotorCfg", "DelayedPDActuatorCfg", "IdealPDActuatorCfg", "ImplicitActuatorCfg",
                 "RemotizedPDActuatorCfg", "ActuatorNetLSTMCfg", "ActuatorNetMLPCfg"}
REMOVED_FLAGS_RE = re.compile(r"(?<!\S)(--headless|--enable_cameras|--cpu)(?![\w-])")
COMMAND_MARKERS = ("isaaclab", ".py", "python", "uv run")
PER_LIB_SCRIPT_RE = re.compile(r"reinforcement_learning/(rsl_rl|rl_games|skrl|sb3|rlinf)/(train|play)\.py")


def write_replacement(name):
    """3.0 replacement text for a deprecated write_*_to_sim name."""
    if name.endswith("_state_to_sim") and name != "write_joint_state_to_sim":
        return ("the pose and velocity writers, e.g. write_root_link_pose_to_sim_index(root_pose=, env_ids=) and "
                "write_root_com_velocity_to_sim_index(root_velocity=, env_ids=)")
    if name == "write_joint_state_to_sim":
        return "write_joint_state_to_sim_index(position=, velocity=, env_ids=)"
    new = {"write_joint_limits_to_sim": "write_joint_position_limit_to_sim",
           "write_joint_friction_to_sim": "write_joint_friction_coefficient_to_sim",
           "write_object_velocity_to_sim": "write_body_com_velocity_to_sim"}.get(name, name)
    new = new.replace("_object_", "_body_")
    return "{0}_index(..., env_ids=) or {0}_mask(..., env_mask=)".format(new)


def sim_replacement(module):
    """Replacement for a deprecated Isaac Sim module path, else None."""
    for prefix, repl in SIM_DEPRECATED:
        if module == prefix or module.startswith(prefix + "."):
            return repl
    parts = module.split(".")
    if len(parts) >= 3 and parts[:2] == ["isaacsim", "sensors"] and parts[2] != "experimental":
        return "isaacsim.sensors.experimental." + parts[2]
    if module.startswith("isaacsim.robot.wheeled_robots") and not module.startswith("isaacsim.robot.wheeled_robots.nodes"):
        return "isaacsim.robot.experimental.wheeled_robots"
    return None


def on_data(node):
    """True for `<x>.data.<attr>` or `data.<attr>` receivers (node is the Attribute)."""
    v = node.value
    return (isinstance(v, ast.Attribute) and v.attr == "data") or (isinstance(v, ast.Name) and v.id == "data")


def is_wxyz_identity(node):
    if not isinstance(node, (ast.Tuple, ast.List)) or len(node.elts) != 4:
        return False
    vals = []
    for e in node.elts:
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd)):
            e = e.operand
        if not (isinstance(e, ast.Constant) and isinstance(e.value, (int, float)) and not isinstance(e.value, bool)):
            return False
        vals.append(abs(e.value))
    return vals == [1, 0, 0, 0]


def is_actuator_cfg(name):
    return name in ACTUATOR_CFGS or bool(name and name.endswith("ActuatorCfg"))


def string_nodes(p):
    """(Constant str node, is_first_add_argument_arg) for every string that is not a docstring or a help= text."""
    skip = set()
    for n in ast.walk(p.tree):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
            skip.add(id(n.value))  # docstrings and bare string statements
        elif isinstance(n, ast.keyword) and n.arg in ("help", "description", "epilog"):
            skip.add(id(n.value))
        elif isinstance(n, ast.Call) and final_name(n.func) == "add_argument":
            skip.update(id(a) for a in n.args)  # the flag names a script defines for itself
    for n in ast.walk(p.tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip:
            yield n


def has_isaac_context(p):
    for n in p.imports():
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
        if any(m.split(".")[0].startswith(("isaaclab", "isaacsim", "omni")) for m in mods):
            return True
    return False


def check_file(path):
    """Findings as {abs path: [(line, rule, message)]}: the file itself, plus parent __init__.py files (ISC021)."""
    apath = os.path.abspath(path)
    findings = []
    out = {apath: findings}
    parsed, err = load(path)
    if parsed is None:
        line, msg = err
        findings.append((line, "ISC000", msg))
        try:
            with open(path, "rb") as fh:
                text = decode(fh.read())
        except OSError:
            text = ""
        for m in OLD_IMPORT_RE.finditer(text):
            lineno = text.count("\n", 0, m.start()) + 1
            rule = "ISC002" if m.group(1).startswith("omni.isaac.lab") else "ISC001"
            findings.append((lineno, rule, "{} (found by regex; the file does not parse)".format(m.group(1))))
        return out
    p = parsed

    # ISC001 / ISC002 / ISC003 / ISC050 / ISC061 / ISC071: import paths
    for node in p.imports():
        if isinstance(node, ast.Import):
            primary = [a.name for a in node.names]
            secondary = []
            names = []
        elif node.level == 0 and node.module:
            names = [(node.module, a.name) for a in node.names]
            if node.module in ("omni", "omni.isaac"):
                primary, secondary = ["{}.{}".format(node.module, a.name) for a in node.names], []  # from omni.isaac import lab
            else:
                primary, secondary = [node.module], ["{}.{}".format(node.module, a.name) for a in node.names]
        else:
            primary, secondary, names = [], [], []
        for mod in primary:
            if mod == "omni.isaac.lab" or mod.startswith(("omni.isaac.lab.", "omni.isaac.lab_")):
                new = "isaaclab" + mod[len("omni.isaac.lab"):]
                findings.append((node.lineno, "ISC002", "{}: Lab 2.x name is {} (no shim)".format(mod, new)))
            elif mod == "omni.isaac" or mod.startswith("omni.isaac."):
                findings.append((node.lineno, "ISC001",
                                 "{}: pre-4.5 name, use isaacsim.* (the omni.isaac shims are gone in Sim 6; many "
                                 "isaacsim.core.* paths are deprecated too, see ISC050)".format(mod)))
        for mod in primary + secondary:
            hit = None
            for prefix, repl in MOVED_MODULES:
                if mod == prefix or mod.startswith(prefix + "."):
                    hit = (prefix, repl)
                    break
            if hit and (mod in primary or not any(m == hit[0] or m.startswith(hit[0] + ".") for m in primary)):
                findings.append((node.lineno, "ISC003", "{}: removed or moved in Lab 3.0, use {}".format(*hit)))
            repl = sim_replacement(mod)
            if repl and (mod in primary or not any(sim_replacement(m) for m in primary)):
                findings.append((node.lineno, "ISC050", "{}: deprecated in Isaac Sim 6.0 and not preloaded by Lab 3.0's "
                                 "Kit experiences; use {} (call isaaclab.sim.utils.enable_extension(...) after launch "
                                 "before importing an isaacsim.* replacement)".format(mod, repl)))
        for key in names:
            if key in MOVED_NAMES:
                findings.append((node.lineno, "ISC003", "{}.{}: removed or moved in Lab 3.0, use {}".format(
                    key[0], key[1], MOVED_NAMES[key])))
            if key[1] == "XformPrimView":
                findings.append((node.lineno, "ISC061", "XformPrimView: deprecated alias, use FrameView"))
            if key[1] in ("ViewerCfg", "ViewportCameraController") and key[0].startswith("isaaclab"):
                findings.append((node.lineno, "ISC071", "{} is deprecated: set sim.default_visualizer_cfg = "
                                 "VisualizerCfg(eye=, lookat=) instead".format(key[1])))

    # ISC010 / ISC011: launcher order and the deprecated AppLauncher
    launches = [c for c in p.calls() if final_name(c.func) in LAUNCHERS]
    if launches:
        module_level = [c for c in launches if p.scope(c) is None]
        first = min(module_level or launches, key=lambda c: c.lineno)
        first_scope = p.scope(first)
        what = final_name(first.func)
        for node in p.imports():
            if not kit_modules(node) or pre_launch_ok(node) or p.under_if(node, is_type_checking):
                continue
            scope = p.scope(node)
            if first_scope is None:
                early = scope is None and node.lineno < first.lineno
            else:
                early = (scope is None and not p.under_if(node, is_main_guard)) or (
                    scope is first_scope and node.lineno < first.lineno
                )
            if early:
                findings.append((node.lineno, "ISC010", "`{}` needs a running Kit app but runs before {}(...) at line {}: "
                                 "move it below the launcher".format(import_text(node), what, first.lineno)))
    for node in ast.walk(p.tree):
        if isinstance(node, ast.Call) and final_name(node.func) == "AppLauncher" and isinstance(
                node.func, (ast.Name, ast.Attribute)):
            findings.append((node.lineno, "ISC011", "AppLauncher is a deprecated shim that always starts Kit; use "
                             "`from isaaclab.app import add_launcher_args, launch_simulation`, add_launcher_args(parser) "
                             "and `with launch_simulation(env_cfg, args_cli):` (starts only the runtime the cfg needs)"))
        elif isinstance(node, ast.Attribute) and node.attr == "add_app_launcher_args":
            findings.append((node.lineno, "ISC011", "AppLauncher.add_app_launcher_args is deprecated: use "
                             "isaaclab.app.add_launcher_args(parser)"))

    # ISC012 / ISC013: command strings
    for node in string_nodes(p):
        text = node.value
        m = REMOVED_FLAGS_RE.search(text)
        if m:
            # an argv element on its own (in a file that uses Isaac), or a flag inside a command line; prose and log
            # messages that merely mention a flag are not commands
            if text.strip() == m.group(1):
                flagged = m.group(1) != "--cpu" and has_isaac_context(p)
            else:
                flagged = any(marker in text for marker in COMMAND_MARKERS)
            if flagged:
                findings.append((node.lineno, "ISC012", "{}: rejected by the 3.0 launcher parser (headless is the default; "
                                 "--viz kit|newton_gl|... selects a visualizer, --device cpu selects the device, cameras "
                                 "are enabled automatically)".format(m.group(1))))
        m = PER_LIB_SCRIPT_RE.search(text)
        if m:
            findings.append((node.lineno, "ISC013", "scripts/reinforcement_learning/{0}/{1}.py was removed: use "
                             "`isaaclab {1} --rl_library {0} --task ...` (or "
                             "scripts/reinforcement_learning/{1}.py --rl_library {0})".format(m.group(1), m.group(2))))

    # ISC021: registration and the packages above it must stay Kit-free
    registers = gym_register_calls(p)
    if registers:
        chain = kit_chain(path)
        if chain:
            findings.append(chain_finding(chain, "registration module"))
        for init in parent_inits(path):
            chain = kit_chain(init)
            if chain:
                out.setdefault(init, []).append(chain_finding(chain, "parent package of a task registration"))

    # cfg fields and calls
    assigned = set()  # attribute names assigned anywhere (cfg.fix_base = ...)
    for n in ast.walk(p.tree):
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            value = n.value
            for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                if isinstance(t, ast.Attribute):
                    assigned.add(t.attr)
                    if t.attr == "attach_yaw_only":
                        findings.append((n.lineno, "ISC030", _yaw_message(value)))
                    if t.attr == "rot" and value is not None and is_wxyz_identity(value):
                        findings.append((value.lineno, "ISC070", _quat_message()))
    for call in p.calls():
        name = final_name(call.func)
        kws = {kw.arg for kw in call.keywords}
        for kw in call.keywords:
            if kw.arg == "attach_yaw_only":
                findings.append((kw.value.lineno, "ISC030", _yaw_message(kw.value)))
            if kw.arg == "rot" and is_wxyz_identity(kw.value):
                findings.append((kw.value.lineno, "ISC070", _quat_message()))
        if is_actuator_cfg(name):
            implicit = name == "ImplicitActuatorCfg"
            for kw in call.keywords:
                if kw.arg in ACTUATOR_LIMITS:
                    new = ACTUATOR_LIMITS[kw.arg]
                elif kw.arg in ("effort_limit", "velocity_limit"):
                    new = ("joint_" if implicit else "actuator_") + kw.arg
                    if not implicit:
                        new += " (rated actuator-model limit; joint_{} requests a solver clamp)".format(kw.arg)
                else:
                    continue
                findings.append((kw.value.lineno, "ISC031", "{}= on {} is deprecated (removed in 3.1): use {}=".format(
                    kw.arg, name, new)))
        if name in ("ImuCfg", "PvaCfg") and "gravity_bias" in kws:
            kw = next(k for k in call.keywords if k.arg == "gravity_bias")
            findings.append((kw.value.lineno, "ISC032", "gravity_bias= was removed from {}: Pva reports kinematic "
                             "acceleration without gravity, the new Imu always includes gravity".format(name)))
        if name in ("UrdfFileCfg", "UrdfConverterCfg") and None not in kws:
            if "fix_base" not in kws and "fix_base" not in assigned:
                findings.append((call.lineno, "ISC040", "{}(...) without fix_base=: fix_base is MISSING, so cfg "
                                 "validation fails".format(name)))
        if isinstance(call.func, ast.Attribute) and WRITE_RE.match(call.func.attr):
            findings.append((call.lineno, "ISC060", "{}() is deprecated (DeprecationWarning, forwards to the _index "
                             "variant): use {}".format(call.func.attr, write_replacement(call.func.attr))))

    # attribute-level rules
    for node in ast.walk(p.tree):
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if attr in DEPRECATED_ATTRS:
                findings.append((node.lineno, "ISC061", "{}: deprecated in 3.0, use {}".format(attr, DEPRECATED_ATTRS[attr])))
            elif attr in DEPRECATED_DATA and on_data(node):
                findings.append((node.lineno, "ISC061", "data.{}: deprecated in 3.0, use robot.{}".format(
                    attr, DEPRECATED_DATA[attr])))
            elif attr in REMOVED_DATA and on_data(node):
                findings.append((node.lineno, "ISC062", "data.{}: {}".format(attr, REMOVED_DATA[attr])))
            elif OBJECT_DATA_RE.match(attr) and on_data(node):
                findings.append((node.lineno, "ISC061", "data.{}: deprecated RigidObjectCollection name, use {}".format(
                    attr, attr.replace("object_", "body_", 1) if attr != "default_object_state" else "default_body_state")))
            elif attr in MOVED_ATTRS:
                findings.append((node.lineno, "ISC003", "{}: removed in Lab 3.0, use {} (the old full-state Imu is "
                                 "now Pva)".format(attr, MOVED_ATTRS[attr])))
            elif attr in VIEWER_FIELDS and isinstance(node.value, ast.Attribute) and node.value.attr == "viewer":
                findings.append((node.lineno, "ISC071", "env_cfg.viewer.{} is deprecated: set "
                                 "sim.default_visualizer_cfg = VisualizerCfg(eye=, lookat=) (asset tracking: "
                                 "KitVisualizerCfg(origin_type=\"asset\", origin_track_path=))".format(attr)))
            elif attr in ("XformPrimView", "ViewerCfg", "ViewportCameraController"):
                if attr == "XformPrimView":
                    findings.append((node.lineno, "ISC061", "XformPrimView: deprecated alias, use FrameView"))
                else:
                    findings.append((node.lineno, "ISC071", "{} is deprecated: set sim.default_visualizer_cfg = "
                                     "VisualizerCfg(eye=, lookat=) instead".format(attr)))
        elif isinstance(node, ast.Name):
            if node.id == "XformPrimView":
                findings.append((node.lineno, "ISC061", "XformPrimView: deprecated alias, use FrameView"))
            elif node.id in ("ViewerCfg", "ViewportCameraController"):
                findings.append((node.lineno, "ISC071", "{} is deprecated: set sim.default_visualizer_cfg = "
                                 "VisualizerCfg(eye=, lookat=) instead".format(node.id)))
    return out


def _yaw_message(value):
    new = 'ray_alignment="base"'
    if isinstance(value, ast.Constant) and value.value is True:
        new = 'ray_alignment="yaw"'
    return "attach_yaw_only was removed from RayCasterCfg: use {} (False -> \"base\", True -> \"yaw\", \"world\" is new)".format(new)


def _quat_message():
    return ("rot=(1.0, 0.0, 0.0, 0.0) is the wxyz identity, but Lab 3.0 quaternions are xyzw, so this is a 180 degree "
            "rotation about x: the identity is (0.0, 0.0, 0.0, 1.0) (ignore if the 180 degree rotation is intended)")


def not_ignored(apath, finding):
    parsed, _ = load(apath)
    lines = parsed.lines if parsed else []
    line = finding[0]
    return not (0 < line <= len(lines) and IGNORE_RE.search(lines[line - 1]))


def is_venv(d):
    return os.path.isfile(os.path.join(d, "pyvenv.cfg")) or os.path.isdir(os.path.join(d, "conda-meta"))


def iter_files(paths, excludes):
    for path in paths:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in excludes and not d.endswith(".egg-info")
                             and not is_venv(os.path.join(root, d)))
            for f in sorted(files):
                if f.endswith(".py"):
                    yield os.path.join(root, f)


def display(apath, given):
    if apath in given:
        return given[apath]
    rel = os.path.relpath(apath)
    return apath if rel.startswith("..") else rel


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="check_isaac_code.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="+", metavar="PATH", help=".py file or directory (searched recursively)")
    ap.add_argument("--exclude", action="append", default=[], metavar="NAME",
                    help="directory name to skip below a PATH (repeatable; adds to the defaults)")
    args = ap.parse_args(argv)

    missing = [p for p in args.paths if not os.path.exists(p)]
    if missing:
        ap.error("no such file or directory: " + ", ".join(missing))
    files = list(dict.fromkeys(iter_files(args.paths, SKIP_DIRS | set(args.exclude))))
    if not files:
        ap.error("no .py files under: " + ", ".join(args.paths))

    given = {os.path.abspath(f): f for f in files}
    results = {}
    for path in files:
        for apath, found in check_file(path).items():
            results.setdefault(apath, set()).update(f for f in found if not_ignored(apath, f))
    total = 0
    order = list(given) + sorted(a for a in results if a not in given)
    for apath in order:
        for line, rule, msg in sorted(results.get(apath, ())):
            print("{}:{}: {} {}".format(display(apath, given), line, rule, msg))
            total += 1
    sys.stdout.flush()
    print("check_isaac_code: {} finding(s) in {} file(s)".format(total, len(files)), file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
