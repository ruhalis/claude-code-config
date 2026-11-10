# Fit check for one printed part against the real board (pcb-enclosure skill).
#
#   Copy to cad/checks/fit_<part>.py, set CONFIG, run from cad/:  cad run checks/fit_<part>.py
#
# The part is modeled in the board datum of board_export.sh (board bottom at Z=0, X/Y as in
# board.step), so nothing is transformed here. Every number it measures is printed; it exits 1
# when any assert fails or when it finds nothing to check (no holes, no connectors).
# Values come from references/fdm-fits.md, "Check thresholds".
import csv
import math
import re
import sys
from pathlib import Path

import build123d as bd
from cad import step
from cad.build123d import closest_points, overlap_volume

ROOT = Path(__file__).resolve().parents[1]  # cad/
sys.path.insert(0, str(ROOT / "src"))

# ---- CONFIG ---------------------------------------------------------------------------------
PART = "enclosure"              # src/<PART>.py holds @model def <PART>()
HOLE_D_RANGE = (2.0, 4.5)       # board.step holes treated as mounting holes, by diameter (mm)
SKIP_HOLES = []                 # [(x, y), ...] mounting holes the part leaves alone on purpose
EXPECTED_HOLE_D = None          # the part's hole at each mount from fdm-fits, e.g. 3.6 (M2.5 insert); required
MOUNT_REFS = r"^(H|MH)\d+$"     # positions.csv refs of mounting-hole footprints, if they are listed
HOLE_CENTRE_TOL = 0.05          # mm
HOLE_D_TOL = 0.01               # mm, B-rep against the fdm-fits value
SEARCH_R = 1.0                  # mm, a part circle this close to a board hole is that hole's feature
CONNECTOR_CLEARANCE = 0.5       # mm, part to each connector body
POCKET_GAP = 0.5                # mm, board edge to the part's walls, per side
EXPECT_SEATED = True            # the board rests on the part (distance 0); False for a lid alone
# ---------------------------------------------------------------------------------------------

failures = []


def report(check, value, limit, ok):
    print(f"{'PASS' if ok else 'FAIL'}  {check:<48} {value:>12}  {limit}")
    if not ok:
        failures.append(check)


def world_parts(node, parent=None):  # from text-to-cad's inspection-and-validation.md
    here = (bd.Location() if parent is None else parent) * node.location
    if node.children:
        for child in node.children:
            yield from world_parts(child, here)
    else:
        yield node.located(here)


def solids_of(tree):
    return [s for leaf in world_parts(tree) for s in leaf.solids()]


def min_distance(a_shapes, b_shapes):
    return min(closest_points(a, b).distance for a in a_shapes for b in b_shapes)


def full_circles(shape):
    """(x, y, diameter) of every full circle lying in an XY plane, deduplicated by x, y, d."""
    seen = {}
    for e in shape.edges().filter_by(bd.GeomType.CIRCLE):
        if abs(e.length - 2 * math.pi * e.radius) < 1e-3 and e.bounding_box().size.Z < 1e-6:
            c = e.arc_center
            seen.setdefault((round(c.X, 3), round(c.Y, 3), round(2 * e.radius, 3)), (c.X, c.Y, 2 * e.radius))
    return list(seen.values())


module = __import__(PART)
part = solids_of(getattr(module, PART)().shape)
board = solids_of(step.read(str(ROOT / "board" / "board.step")))
connectors = [(leaf.label, leaf.solids() or [leaf])
              for leaf in world_parts(step.read(str(ROOT / "board" / "connectors.step")))]
report("part solids", len(part), ">= 1", len(part) > 0)

# 1. Mounting holes: board.step is the truth, positions.csv a cross-check where it lists them.
holes = {h for s in board for h in full_circles(s) if HOLE_D_RANGE[0] <= h[2] <= HOLE_D_RANGE[1]}
holes = [h for h in holes if not any(math.dist(h[:2], p) < SEARCH_R for p in SKIP_HOLES)]
report("mounting holes in board.step", len(holes), ">= 1", len(holes) > 0)
part_circles = [c for s in part for c in full_circles(s)]
for x, y, d in sorted(holes):
    name = f"hole ({x:.3f}, {y:.3f}) d{d:.2f}"
    near = [(math.dist((x, y), c[:2]), c[2]) for c in part_circles if math.dist((x, y), c[:2]) <= SEARCH_R]
    if not near:
        report(f"{name}: part feature", "none", f"within {SEARCH_R}", False)
        continue
    off = min(n[0] for n in near)
    report(f"{name}: centre offset", f"{off:.3f}", f"<= {HOLE_CENTRE_TOL}", off <= HOLE_CENTRE_TOL)
    diameters = sorted({round(n[1], 3) for n in near})
    print(f"      part diameters there: {diameters}")
    if EXPECTED_HOLE_D is None:
        report(f"{name}: part hole d", "unset", "set EXPECTED_HOLE_D", False)
    else:
        best = min(diameters, key=lambda v: abs(v - EXPECTED_HOLE_D))
        report(f"{name}: part hole d", f"{best:.3f}", f"{EXPECTED_HOLE_D} +/- {HOLE_D_TOL}",
               abs(best - EXPECTED_HOLE_D) <= HOLE_D_TOL)

with open(ROOT / "board" / "positions.csv", newline="") as f:
    reader = csv.DictReader(f)
    columns_ok = {"Ref", "PosX", "PosY"} <= set(reader.fieldnames or [])
    rows = [r for r in reader if re.match(MOUNT_REFS, r["Ref"])] if columns_ok else []
report("positions.csv has Ref, PosX, PosY", str(columns_ok), "True", columns_ok)
if not rows:
    print(f"note  positions.csv lists no {MOUNT_REFS} footprints (excluded from pos files?): board.step alone")
for r in rows:
    px, py = float(r["PosX"]), float(r["PosY"])
    off = min((math.dist((px, py), h[:2]) for h in holes), default=math.inf)
    report(f"{r['Ref']} positions.csv vs board.step", f"{off:.3f}", f"<= {HOLE_CENTRE_TOL}", off <= HOLE_CENTRE_TOL)

# 2. Connectors: clearance per connector body; 0 means touching or overlapping.
report("connector bodies in connectors.step", len(connectors), ">= 1", len(connectors) > 0)
for i, (label, shapes) in enumerate(connectors):
    dist = min_distance(shapes, part)
    report(f"{label or f'connector {i}'}: clearance to part", f"{dist:.3f}", f">= {CONNECTOR_CLEARANCE}",
           dist >= CONNECTOR_CLEARANCE)
    if dist == 0:
        overlap = sum(overlap_volume(a, b) for a in shapes if a.solids() for b in part)
        print(f"      overlap volume {overlap:.3f} mm3 (0: touching only)")

# 3. Board pocket: no part material in the board, seated on it, walls clear of its edge.
board_body = max(board, key=lambda s: s.volume)
bb = board_body.bounding_box()
overlap = sum(overlap_volume(board_body, p) for p in part)
report("part overlap with board body", f"{overlap:.4f}", "== 0 mm3", overlap <= 1e-6)
if EXPECT_SEATED:
    seat = min_distance([board_body], part)
    report("board seated on part", f"{seat:.3f}", "== 0", seat <= 1e-3)
bottom = board_body.faces().filter_by(bd.GeomType.PLANE).sort_by(bd.Axis.Z)[0]
prism = bd.extrude(bd.Face(bottom.outer_wire()), amount=bb.size.Z, dir=(0, 0, 1))  # outline, no holes
slab = bd.Pos(bb.center().X, bb.center().Y, bb.center().Z) * bd.Box(bb.size.X + 60, bb.size.Y + 60, bb.size.Z - 0.02)


def solids_in(shape):  # an empty boolean result can be None, a list or an empty compound
    if shape is None:
        return []
    if isinstance(shape, (list, tuple)):
        return [s for x in shape for s in solids_in(x)]
    return [s for s in shape.solids() if s.volume > 1e-9]


walls = []  # part at board height, outside the board outline
for p in part:
    for piece in solids_in(p & slab):
        walls += solids_in(piece - prism)
if walls:
    gap = min_distance(walls, prism.solids())
    report("PCB pocket gap (walls at board height)", f"{gap:.3f}", f">= {POCKET_GAP}", gap >= POCKET_GAP)
else:
    print("note  no part material at board height: pocket gap not applicable")

print(f"\n{len(failures)} failed" + (": " + "; ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
