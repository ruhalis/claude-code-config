#!/usr/bin/env python3
"""Regression tests for check_isaac_code.py (Isaac Lab 3.0.0). Stdlib only; fixtures live in a temp dir, no
bytecode is written. One positive and one negative case per rule.

    python3 test_check_isaac_code.py        (exit 0 when every test passes)
"""
import contextlib
import io
import os
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_isaac_code as chk  # noqa: E402


class CheckerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        chk._CACHE.clear()
        chk._CLEAN.clear()
        chk._CHAINS.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text, raw=None):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(raw if raw is not None else text.encode())
        return path

    def run_checker(self, *rels):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = chk.main([os.path.join(self.root, r) for r in rels] or [self.root])
        return code, out.getvalue()

    def rules(self, text):
        return sorted(line.split(": ", 1)[1].split()[0] for line in text.splitlines())

    def rule_set(self, text, name="m.py"):
        """Sorted distinct rule IDs reported for one source text (empty list when clean)."""
        chk._CACHE.clear()
        self.write(name, text)
        code, out = self.run_checker(name)
        found = sorted(set(self.rules(out)))
        self.assertEqual(code, 1 if found else 0)
        return found

    def clean(self, text):
        self.assertEqual(self.rule_set(text), [])

    # ---------------------------------------------------------------- structure
    def test_diamond_import_graph_is_linear(self):
        n = 40  # each module imports the next two: exponential without memoisation
        self.write("tp/__init__.py", 'import gymnasium as gym\nfrom . import m0\ngym.register(id="Isaac-X", '
                   'entry_point="a:b")\n')
        for i in range(n):
            self.write("tp/m%d.py" % i, "from . import m%d, m%d\n" % (i + 1, i + 2))
        self.write("tp/m%d.py" % n, "import os\n")
        self.write("tp/m%d.py" % (n + 1), "import omni.usd\n")
        start = time.time()
        code, out = self.run_checker()
        self.assertLess(time.time() - start, 5.0)
        self.assertEqual(code, 1)
        self.assertEqual(self.rules(out), ["ISC021"])

    def test_env_dir_is_scanned_but_venv_is_not(self):
        self.write("mytask/__init__.py", "")
        self.write("mytask/env/my_env.py", "from omni.isaac.core import World\n")
        self.write("venv/pyvenv.cfg", "home = /usr/bin\n")
        self.write("venv/lib/bad.py", "from omni.isaac.core import World\n")
        code, out = self.run_checker()
        self.assertEqual(self.rules(out), ["ISC001"])
        self.assertIn("my_env.py", out)

    def test_decoding_matches_py_compile(self):
        self.write("bom.py", "", raw=b"\xef\xbb\xbfimport os\n")
        self.write("latin1_nocookie.py", "", raw=b'x = "caf\xe9"\n')
        self.write("latin1_cookie.py", "", raw=b'# -*- coding: latin-1 -*-\nx = "caf\xe9"\n')
        code, out = self.run_checker()
        self.assertEqual(self.rules(out), ["ISC000"])
        self.assertIn("latin1_nocookie.py", out)

    def test_ignore_comment_and_usage_error(self):
        self.assertEqual(self.rule_set("from omni.isaac.core import World  # isaac-check: ignore\n"), [])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                chk.main([os.path.join(self.root, "missing.py")])
        self.assertEqual(ctx.exception.code, 2)

    def test_templates_are_clean(self):
        templates = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(chk.main([templates]), 0)

    # ---------------------------------------------------------------- ISC000
    def test_isc000_syntax_error(self):
        self.assertEqual(self.rule_set("def f(:\n    pass\n"), ["ISC000"])
        self.clean("def f():\n    pass\n")

    # ---------------------------------------------------------------- ISC001 / ISC002 / ISC003
    def test_isc001_isc002_old_namespaces(self):
        self.assertEqual(self.rule_set("import omni.isaac.core\n"), ["ISC001"])
        self.assertEqual(self.rule_set("from omni.isaac import core\n"), ["ISC001"])
        self.assertEqual(self.rule_set("from omni.isaac.lab.envs import ManagerBasedRLEnv\n"), ["ISC002"])
        self.assertEqual(self.rule_set("from omni.isaac import lab\n"), ["ISC002"])
        self.clean("import omni.usd\nfrom isaacsim.core.experimental.prims import XformPrim\n")

    def test_isc003_moved_and_removed_imports(self):
        self.assertEqual(self.rule_set("import omni.physics.tensors.impl.api as physx\n"), ["ISC003"])
        self.assertEqual(self.rule_set("from omni.physics.tensors.impl import api\n"), ["ISC003"])
        self.assertEqual(self.rule_set("from isaaclab.test.benchmark import BaseIsaacLabBenchmark\n"), ["ISC003"])
        self.assertEqual(self.rule_set("from isaaclab.envs.utils.recording_hooks import x\n"), ["ISC003"])
        self.assertEqual(self.rule_set("from isaaclab.assets import SurfaceGripper, SurfaceGripperCfg\n"), ["ISC003"])
        self.assertEqual(self.rule_set("from isaaclab_physx.physics import SimulationManager\n"), ["ISC003"])
        self.assertEqual(self.rule_set("from isaaclab.envs.mdp import imu_orientation\n"), ["ISC003"])
        self.assertEqual(self.rule_set("import isaaclab.envs.mdp as mdp\nx = mdp.imu_projected_gravity\n"), ["ISC003"])
        self.assertEqual(self.rule_set("from isaaclab.utils.buffers import TimestampedBufferWarp\n"), ["ISC003"])
        self.clean("import omni.physics.tensors.api as physx\nfrom isaaclab.benchmark import x\n"
                   "from isaaclab_physx.assets import SurfaceGripper\nfrom isaaclab.assets import Articulation\n"
                   "from isaaclab_physx.physics import PhysxManager as SimulationManager\n"
                   "from isaaclab.envs.mdp import pva_orientation\n")

    # ---------------------------------------------------------------- ISC010 / ISC011
    def test_isc010_kit_import_before_launch(self):
        self.assertEqual(self.rule_set("import omni.usd\nfrom isaaclab.app import launch_simulation\n"
                                       "with launch_simulation(cfg, args):\n    pass\n"), ["ISC010"])
        self.assertEqual(self.rule_set("from isaacsim import SimulationApp\nimport carb\n"
                                       "app = SimulationApp({})\n"), ["ISC010"])
        self.assertEqual(self.rule_set("from isaaclab.envs.ui import ManagerBasedRLEnvWindow\n"
                                       "from isaaclab.app import launch_simulation\n"
                                       "def main():\n    with launch_simulation(cfg, args):\n        pass\n"), ["ISC010"])
        self.assertEqual(self.rule_set("from isaaclab.app import launch_simulation\n"
                                       "from isaaclab_physx.physics import PhysxManager\n"
                                       "with launch_simulation(cfg, args):\n    pass\n"), ["ISC010"])
        self.assertEqual(self.rule_set("import omni.usd\nfrom isaaclab.app import AppLauncher\n"
                                       "app = AppLauncher().app\n"), ["ISC010", "ISC011"])

    def test_isc010_kitless_and_lab_imports_are_fine(self):
        # the 3.0 tutorial pattern: isaaclab.* and pxr before the with block, Kit imports after it
        self.clean("import argparse\nfrom isaaclab.app import add_launcher_args, launch_simulation\n"
                   "from isaaclab.sim import SimulationCfg, SimulationContext\nfrom isaaclab.envs import ManagerBasedRLEnvCfg\n"
                   "import isaaclab.envs.mdp as mdp\nfrom isaaclab.assets import Articulation\n"
                   "from isaaclab_physx.physics import PhysxCfg\nfrom isaaclab_newton.physics import NewtonCfg\n"
                   "from pxr import Usd\nimport isaaclab_tasks\n"
                   "def main():\n    with launch_simulation(cfg, args):\n        import omni.usd\n        import carb\n")
        # no launcher in the file: env and cfg modules may import anything
        self.clean("import omni.usd\nfrom isaaclab.envs.ui import BaseEnvWindow\n")
        # launcher classes themselves, and TYPE_CHECKING imports, may come first
        self.clean("from typing import TYPE_CHECKING\nimport isaacsim\nfrom isaacsim import SimulationApp\n"
                   "if TYPE_CHECKING:\n    import omni.usd\napp = SimulationApp({})\nimport omni.usd\n")

    def test_isc011_app_launcher_shim(self):
        self.assertEqual(self.rule_set("from isaaclab.app import AppLauncher\nimport argparse\n"
                                       "p = argparse.ArgumentParser()\nAppLauncher.add_app_launcher_args(p)\n"),
                         ["ISC011"])
        self.assertEqual(self.rule_set("from isaaclab.app import AppLauncher\napp = AppLauncher(args).app\n"),
                         ["ISC011"])
        self.clean("from isaaclab.app import add_launcher_args, launch_simulation\n")

    # ---------------------------------------------------------------- ISC012 / ISC013
    def test_isc012_removed_launcher_flags(self):
        self.assertEqual(self.rule_set("import subprocess\nimport isaaclab\n"
                                       "subprocess.run(['uv', 'run', 'isaaclab', 'train', '--headless'])\n"), ["ISC012"])
        self.assertEqual(self.rule_set("import isaaclab\nCMD = './isaaclab.sh -p x.py --enable_cameras --cpu'\n"),
                         ["ISC012"])
        # a script's own flag, help text, a docstring and a different flag are not findings
        self.clean("import argparse\nimport isaaclab\n\"\"\"Run with --headless.\"\"\"\np = argparse.ArgumentParser()\n"
                   "p.add_argument('--headless', help='use --headless in the old days')\nCMD = '--cpus 4'\n"
                   "ARGV = ['--viz', 'none', '--device', 'cpu']\n"
                   "MSG = 'Launch with enable_cameras=True (--enable_cameras) to see frames'\n")
        self.clean("import subprocess\nsubprocess.run(['chrome', '--headless'])\n")  # no Isaac in the file

    def test_isc013_per_library_scripts(self):
        self.assertEqual(self.rule_set("CMD = './isaaclab.sh -p scripts/reinforcement_learning/rsl_rl/train.py --task X'\n"),
                         ["ISC013"])
        self.assertEqual(self.rule_set("P = 'scripts/reinforcement_learning/skrl/play.py'\n"), ["ISC013"])
        self.clean("CMD = 'uv run isaaclab train --rl_library rsl_rl --task Isaac-Cartpole'\n"
                   "P = 'scripts/reinforcement_learning/train.py'\n")

    # ---------------------------------------------------------------- ISC021
    def test_isc021_parent_init_eager_import(self):
        self.write("proj/__init__.py", "")
        self.write("proj/tasks/__init__.py", "from .mytask.env import MyEnv\n")
        self.write("proj/tasks/mytask/__init__.py", 'import gymnasium as gym\ngym.register(id="Isaac-X", '
                   'entry_point=f"{__name__}.env:MyEnv")\n')
        self.write("proj/tasks/mytask/env.py", "import omni.usd\n")
        code, out = self.run_checker("proj/tasks/mytask")
        self.assertEqual(self.rules(out), ["ISC021"])
        self.assertIn("parent package", out)

    def test_isc021_lab_imports_in_task_packages_are_fine(self):
        self.write("proj/__init__.py", "")
        self.write("proj/tasks/__init__.py", "from .mytask import env\n")
        self.write("proj/tasks/mytask/__init__.py", 'import gymnasium as gym\nfrom . import env\n'
                   'gym.register(id="Isaac-X", entry_point=f"{__name__}.env:MyEnv")\n')
        self.write("proj/tasks/mytask/env.py", "from isaaclab.envs import DirectRLEnv\nimport isaaclab.sim as sim_utils\n"
                   "from pxr import Usd\n")
        code, out = self.run_checker("proj/tasks/mytask")
        self.assertEqual((code, out), (0, ""))

    # ---------------------------------------------------------------- ISC030 / ISC031 / ISC032 / ISC040
    def test_isc030_attach_yaw_only(self):
        self.assertEqual(self.rule_set("RayCasterCfg(attach_yaw_only=True)\n"), ["ISC030"])
        self.assertEqual(self.rule_set("cfg.attach_yaw_only = False\n"), ["ISC030"])
        self.clean('RayCasterCfg(ray_alignment="yaw")\n')

    def test_isc031_deprecated_actuator_limits(self):
        self.assertEqual(self.rule_set("ImplicitActuatorCfg(effort_limit_sim=1.0, velocity_limit_sim=2.0)\n"), ["ISC031"])
        self.assertEqual(self.rule_set("ImplicitActuatorCfg(effort_limit=1.0)\n"), ["ISC031"])
        self.assertEqual(self.rule_set("DCMotorCfg(effort_limit=1.0, velocity_limit=2.0)\n"), ["ISC031"])
        self.assertEqual(self.rule_set("IdealPDActuatorCfg(velocity_limit_sim=2.0)\n"), ["ISC031"])
        self.clean("ImplicitActuatorCfg(joint_effort_limit=1.0, joint_velocity_limit=2.0)\n"
                   "DCMotorCfg(actuator_effort_limit=1.0, joint_effort_limit=2.0)\n"
                   "Other(effort_limit=1.0)\n")

    def test_isc032_gravity_bias(self):
        self.assertEqual(self.rule_set("ImuCfg(prim_path='x', gravity_bias=(0.0, 0.0, 9.81))\n"), ["ISC032"])
        self.assertEqual(self.rule_set("PvaCfg(prim_path='x', gravity_bias=(0.0, 0.0, 9.81))\n"), ["ISC032"])
        self.clean("ImuCfg(prim_path='x')\nPvaCfg(prim_path='x')\n")

    def test_isc040_urdf_fix_base(self):
        self.assertEqual(self.rule_set("UrdfFileCfg(asset_path='a.urdf')\n"), ["ISC040"])
        self.assertEqual(self.rule_set("UrdfConverterCfg(asset_path='a.urdf', joint_drive=None)\n"), ["ISC040"])
        self.clean("UrdfFileCfg(asset_path='a.urdf', fix_base=False)\n")  # joint_drive is optional in 3.0
        self.clean("c = UrdfConverterCfg(asset_path='a.urdf')\nc.fix_base = True\n")
        self.clean("UrdfFileCfg(asset_path='a.urdf', **kw)\n")

    # ---------------------------------------------------------------- ISC050
    def test_isc050_deprecated_sim_paths(self):
        for src in ("from isaacsim.core.utils.stage import get_current_stage\n",
                    "import isaacsim.core.utils.prims as prim_utils\n",
                    "from isaacsim.core.utils import stage\n",
                    "from isaacsim.core.simulation_manager import SimulationManager\n",
                    "from isaacsim.core.utils.extensions import enable_extension\n",
                    "from isaacsim.core.api import World\n",
                    "from isaacsim.core.prims import Articulation\n",
                    "from isaacsim.core.cloner import GridCloner\n",
                    "from isaacsim.sensors.camera import Camera\n",
                    "from isaacsim.robot.wheeled_robots.controllers import DifferentialController\n"):
            self.assertEqual(self.rule_set(src), ["ISC050"], src)
        self.clean("from isaacsim.core.experimental.prims import XformPrim\n"
                   "from isaacsim.sensors.experimental.camera import Camera\n"
                   "from isaacsim.robot.wheeled_robots.nodes import x\nfrom isaaclab.sim.utils import stage\n"
                   "from isaacsim.core.utils.numpy.rotations import x\n")

    # ---------------------------------------------------------------- ISC060 / ISC061 / ISC062
    def test_isc060_write_to_sim_without_index_or_mask(self):
        self.assertEqual(self.rule_set("robot.write_root_pose_to_sim(pose, env_ids)\n"), ["ISC060"])
        self.assertEqual(self.rule_set("robot.write_joint_position_to_sim(q, None, env_ids)\n"), ["ISC060"])
        self.assertEqual(self.rule_set("robot.write_root_state_to_sim(s)\nrobot.write_joint_limits_to_sim(l)\n"),
                         ["ISC060"])
        self.assertEqual(self.rule_set("coll.write_object_pose_to_sim(p)\n"), ["ISC060"])
        self.clean("robot.write_root_pose_to_sim_index(root_pose=p, env_ids=e)\n"
                   "robot.write_joint_position_to_sim_mask(position=q, env_mask=m)\n"
                   "scene.write_data_to_sim()\nrobot.write_joint_state_to_sim_index(position=q, velocity=v)\n")

    def test_isc061_deprecated_asset_api(self):
        self.assertEqual(self.rule_set("v = robot.root_physx_view\n"), ["ISC061"])
        self.assertEqual(self.rule_set("robot.set_joint_effort_target(t)\n"), ["ISC061"])
        self.assertEqual(self.rule_set("x = robot.data.applied_torque.torch\n"), ["ISC061"])
        self.assertEqual(self.rule_set("x = robot.data.joint_pos_target\n"), ["ISC061"])
        self.assertEqual(self.rule_set("p = coll.data.object_pose_w\ni = coll.find_objects('a')\n"), ["ISC061"])
        self.assertEqual(self.rule_set("from isaaclab.sim.views import XformPrimView\nv = XformPrimView('/x')\n"),
                         ["ISC061"])
        self.clean("v = robot.root_view\nrobot.actuators.target_command.set_effort_index(value=t)\n"
                   "x = robot.actuators.applied_effort.torch\nself.object_names = []\n"
                   "p = coll.data.body_pose_w\nfrom isaaclab.sim.views import FrameView\n"
                   "robot.set_joint_effort_target_index(target=t)\nself.applied_torque = 1\n")

    def test_isc062_removed_asset_data(self):
        self.assertEqual(self.rule_set("g = robot.data.gear_ratio\n"), ["ISC062"])
        self.assertEqual(self.rule_set("w = robot.data.body_incoming_joint_wrench_b.torch\n"), ["ISC062"])
        self.clean("w = sensor.data.force.torch\ng = cfg.gear_ratio\n")

    # ---------------------------------------------------------------- ISC070
    def test_isc070_wxyz_identity_literal(self):
        self.assertEqual(self.rule_set("InitialStateCfg(pos=(0.0, 0.0, 0.5), rot=(1.0, 0.0, 0.0, 0.0))\n"), ["ISC070"])
        self.assertEqual(self.rule_set("cfg.init_state.rot = [1, 0, 0, 0]\n"), ["ISC070"])
        self.clean("InitialStateCfg(rot=(0.0, 0.0, 0.0, 1.0))\nInitialStateCfg(rot=(0.7071, 0.0, 0.0, 0.7071))\n"
                   "x = (1.0, 0.0, 0.0, 0.0)\nColorCfg(color=(1.0, 0.0, 0.0, 0.0))\n")

    # ---------------------------------------------------------------- ISC071
    def test_isc071_viewer_cfg(self):
        self.assertEqual(self.rule_set("env_cfg.viewer.eye = (1.0, 1.0, 1.0)\n"), ["ISC071"])
        self.assertEqual(self.rule_set("from isaaclab.envs import ViewerCfg\nv = ViewerCfg(eye=(1, 1, 1))\n"), ["ISC071"])
        self.clean("env_cfg.sim.default_visualizer_cfg = VisualizerCfg(eye=(1.0, 1.0, 1.0), lookat=(0.0, 0.0, 0.0))\n"
                   "self.viewer.show()\n")


if __name__ == "__main__":
    unittest.main()
