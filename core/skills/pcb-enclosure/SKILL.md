---
name: pcb-enclosure
description: Design enclosures, cases, lids, mounts, brackets and standoffs for the user's own PCBs (ESP32 boards for Athena and Aquila) and prepare them for FDM printing. Exports the real board geometry from KiCad with kicad-cli on one shared datum (board outline and holes STEP, connector STEP, placement CSV, outline DXF), supplies the user's FDM fit tolerances and a numeric fit-check script. All modeling is deferred to the text-to-cad plugin's cad skill (build123d through the `cad` command). Use whenever the user mentions an enclosure, case, housing, box, lid, mount, bracket, standoff, 3D print, STL, 3MF, STEP, build123d, cadgen, `cad run`, fitting a board or printing a part. Not for schematic or PCB review (kicad-review), changing a board (pcb-author) or firmware (esp-idf).
compatibility: macOS, KiCad 10 app bundle (kicad-cli 10.0.5), the text-to-cad Claude Code plugin 0.11.x (`text-to-cad@text-to-cad`, from the local catalog in `~/Library/Application Support/cad/plugin`; the CAD server installs patch releases by itself). Network only for the first install and the integrations `cad` fetches on first use.
---

# PCB enclosure

Personal skill for printed parts around the user's own boards. It does not model anything itself.

## Who owns what

- This skill: board geometry out of KiCad with one datum (`scripts/board_export.sh`), the FDM fit values (`references/fdm-fits.md`) and the fit check (`scripts/fit_check.py`).
- text-to-cad `cad` skill: all modeling, runs, snapshots, STEP/STL/3MF export, and the printing check `cad model dfm` (walls, overhangs, support; no fits, no hole diameters). `fea` skill: optional strength check. `print3d` skill: slicing only, it never starts a print.
- pcb-author: any change to the board; kicad-review: reviewing it. Never use text-to-cad's `pcb` skill or `kicad_pcb.edit`/`kicad_sch.edit` to change a board: they save in the KiCad nightly format, which `pcb import` rejects and KiCad 10.0.5 may refuse to open, and they bypass pcb-author.

## Scripts and references

| File | Use |
|---|---|
| `scripts/board_export.sh [--filter 'J*,SW*,U*'] <file.kicad_pcb\|file.kicad_pro> [outdir]` | Writes `board.step`, `connectors.step`, `positions.csv`, `outline.dxf`, `README.txt` into `cad/board/` next to the pcb (default). `--filter`, only as the first argument, sets which components go into connectors.step (default `J*,SW*`). |
| `scripts/fit_check.py` | Template. Copy to `cad/checks/fit_<part>.py`, set its CONFIG, run every round. |
| `references/fdm-fits.md` | Hole, insert, clearance, wall, check-threshold and mesh-tolerance values to start from. Calibrate on one coupon per printer. |

text-to-cad 0.11 has its own `cad kicad_pcb export --to step|dxf`, but it runs kicode's KiCad nightly (10.99). `board_export.sh` on the user's KiCad 10.0.5 stays the datum source.

## What it reads from the project

- `CLAUDE.md` `## Hardware` -> `kicad:` (the path kicad-review also uses to find the board).
- Optional: a `## Print` section with `printer:`, `nozzle:`, `material:`. If absent, assume 0.4 mm nozzle, PLA or PETG, and say so.

## Workflow

0. Setup is the `cad` skill's: the `cad` command (`~/.local/bin/cad`), `cad doctor --check` on any install or kernel error (it changes nothing; `cad doctor` repairs). Environment names are `CAD_*` (`CAD_TELEMETRY=0`); 0.11 reads no `CADGEN_*`. Models import `from cad import model, step`. A script from 0.8 to 0.10 runs unchanged (`from cadgen import model` still imports; old names such as `read_step` only warn); a 0.7-era script (`from cadgen import build123d as bd`, `read_scene`, `@stl(mesh_tolerance=...)`, as in the existing athena and aquila CAD scripts) is ported once with upstream's `docs/migrations/migrating-0.7-to-0.8.md`. The CAD project root is `cad/` next to the pcb file, where `board_export.sh` writes `board/`; run every command from there. Layout: `src/<part>.py`, `checks/`, outputs in `STEP/`, `STL/`, `3MF/`, snapshots in `tmp/`.
1. Read the repo `CLAUDE.md` `## Hardware` section for the `kicad:` path.
2. Run `scripts/board_export.sh <that path>`. Set the drill/aux origin on a mounting hole or board corner in pcbnew first; it is the datum for every file. Confirm the Y axis / origin convention of the STEP once per project by comparing one known hole position between `positions.csv` and the STEP. Checked on aquila-fc with kicad-cli 10.0.5: X and Y in `positions.csv` match the STEP `CARTESIAN_POINT` values exactly, Y is negative below the origin (pcbnew's Y-down), Z=0 is the board bottom.
3. Invoke the `text-to-cad:cad` skill and model in `src/<part>.py`, in the board datum (no offset, so the check needs no transform):
   - `step.read("board/board.step")` gives a build123d tree; mounting holes are its full circular edges (`arc_center`, `radius`).
   - Apply the values in `references/fdm-fits.md`.
   - `cad run src/<part>.py`; read its line and the bounds under it before anything else.
4. Fit check, every round: `cad run checks/fit_<part>.py`. It asserts mounting-hole centres (and the part's hole diameter) against `board.step` and any mounting-hole rows in `positions.csv`, clearance from the part to each body in `connectors.step`, no overlap with the board, the board seated, and the pocket gap at board height, and prints every number. A failing or undecided check has shown nothing: fix the model and run both again.
5. Snapshots judge arrangement and look only; a number is never read off a picture. Make `src/fit_view.py`, an assembly that calls the part and adds `step.read` of `board.step` and `connectors.step`, then draw what the change needs: `cad model snapshot "$FIT" tmp/iso.png`, `--camera top --display hidden-line`, a cut through each connector opening (`--camera front --display '{"clip": {"enabled": true, "axis": "y", "at": <y>}}'`), and `--display '{"hidden": ["lid"]}'` for the inside. Read every PNG. Show the user the part once (`cad_show` or the run's `view:` link); never screenshot the viewer.
6. Export from the part's own id, never the fit view: `cad model export "$ID" STEP/<part>.step`, then `cad model export "$ID" STL/<part>.stl 3MF/<part>.3mf --tolerance 0.02` (fdm-fits: about a tenth of the smallest clearance; the default mesh can sit 0.2 mm inside a curved surface).
7. `cad model dfm "$ID" --process printing --angle-limit 45 --candidates`. It reports facts, not a verdict: compare its wall figures with fdm-fits' minimum wall, and list hole diameter and bridges as not measured by it (the fit check covers the holes).
8. Optional, for load-bearing parts (drone mounts, brackets, anything a screw clamp or a crash loads): the `text-to-cad:fea` skill on the model (`cad model solve "$ID"`), linear static only. Printed layers are not isotropic: give the modulus along the load, call the result rough and keep a larger margin than for metal; a crash only as a steady g-load.
9. Report overall dimensions, the fits used, the fit-check numbers, the dfm figures, and what to verify after printing (hole fit, board seating, connector access, lid closure). Slicing, when asked, is the `print3d` skill.

## Not yet verified on this machine

Written on 2026-11-10 from text-to-cad 0.11.6's docs, before 0.11 was installed here. `scripts/fit_check.py` ran only on synthetic boards with build123d 0.13.0 and `cad` stubbed. Confirm on the first round, then edit this section: `cad step snapshot`, the leaf labels in KiCad's `connectors.step`, the `positions.csv` headers (`Ref`, `PosX`, `PosY`), and the port of the 0.7-era athena hex and aquila airframe_v2 scripts.

## Orchestration

CAD rounds (model runs, fit checks, snapshots) are design iteration on Fable: they run in a Fable main session, a fork of it, or `general-purpose` with `model: "fable"` and `effort: "high"` (pass the effort; a Fable subagent may otherwise default to medium). Never the verifier agent, which cannot load skills.
