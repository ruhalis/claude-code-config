"""
Minimal raw Isaac Sim 6.2 standalone script template (SimulationApp, no Isaac Lab).

# Based on source/standalone_examples/api/isaacsim.core.experimental.api/add_cubes.py @ Isaac Sim v6.2.0

Use this only when no Isaac Lab task, env or sensor is involved. For anything that trains or evaluates
a policy, use the Isaac Lab templates instead (direct_rl_env.py, manager_based_env.py, lab_app_script.py).

Run with the Python that has the `isaacsim` pip package (Python 3.12), never the system python:
    uv run --extra isaacsim python standalone_isaac.py --num_steps 300      # inside an Isaac Lab checkout
    <venv>/bin/python standalone_isaac.py                                    # pip install isaacsim[all,extscache]==6.2.0.0
    $ISAACSIM_PATH/python.sh standalone_isaac.py                             # binary (zip) install
Prefix headless/SSH runs with OMNI_KIT_ACCEPT_EULA=YES (no interactive EULA prompt).

Isaac Sim 6.x conventions used here:
  * isaacsim.core.api (World, DynamicCuboid, ...) is deprecated since 6.0.0. Use isaacsim.core.experimental.*:
    objects (Cube, GroundPlane, lights), prims (RigidPrim, GeomPrim), utils (app, stage).
  * There is no World.step(): start the timeline with app_utils.play(), then advance with simulation_app.update().
  * Batched getters/setters take plural keywords (paths=, positions=) and return warp arrays: call .numpy().
  * Quaternions are WXYZ here (identity [1, 0, 0, 0]). Isaac Lab 3.0 is XYZW (identity [0, 0, 0, 1]).
"""

import argparse

# --- 1. Parse CLI args BEFORE creating SimulationApp ---
parser = argparse.ArgumentParser(description="Isaac Sim 6.2 standalone template")
parser.add_argument("--gui", action="store_true", help="Open the GUI window (default: headless)")
parser.add_argument("--num_steps", type=int, default=300)
args, _ = parser.parse_known_args()

# --- 2. Boot the Kit runtime. NOTHING omni / pxr / isaacsim.* (except this import) may be imported above this line. ---
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": not args.gui})

# --- 3. NOW it's safe to import Kit-backed modules. ---
import isaacsim.core.experimental.utils.app as app_utils
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.objects import Cube, DistantLight, GroundPlane
from isaacsim.core.experimental.prims import GeomPrim, RigidPrim

# --- 4. Build the scene ---
stage_utils.create_new_stage()
GroundPlane("/World/GroundPlane", positions=[0, 0, 0])
light = DistantLight("/World/DistantLight")
light.set_intensities(3000)

# A cube falling onto the ground: Cube = shape, GeomPrim adds collision, RigidPrim adds the rigid body
cube_shape = Cube("/World/falling_cube", positions=[0.0, 0.0, 1.0], sizes=1.0, scales=[0.2, 0.2, 0.2])
GeomPrim(paths=cube_shape.paths, apply_collision_apis=True)
cube = RigidPrim(paths=cube_shape.paths)

# --- 5. Start the timeline and step ---
app_utils.play()
simulation_app.update()  # lets physics initialize before the first read/write

for i in range(args.num_steps):
    simulation_app.update()  # one frame = physics step(s) + render
    if i % 60 == 0:
        positions, _orientations = cube.get_world_poses()  # warp arrays, orientations are WXYZ
        print(f"step={i}  cube_z={positions.numpy()[0, 2]:.3f}")

# --- 6. Shutdown ---
# close() flushes stdio and, with the default fast_shutdown=True, terminates the process itself, so
# nothing after it runs: write and close your own files first. A shutdown watchdog
# (SimulationApp config "shutdown_watchdog_timeout", default 120 s) force-exits a deadlocked teardown.
simulation_app.close()
