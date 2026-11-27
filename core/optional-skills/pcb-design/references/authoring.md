# Authoring a board as code

Design mode. The rules in `SKILL.md` apply to every step. Where the project's design note records toolchain facts (aquila: `hardware/DESIGN.md`, "Toolchain facts"), that note wins over this file: it was checked on the real board.

## 0. Preconditions

- The session is on Claude Fable 5.2 or later at `high` effort.
- `pcb --version`, recorded in the round's notes. A version newer than the one the design note names: read Diode's changelog for the releases in between before any write. Missing `pcb`: stop and give the user the install command; do not install it.
- `bash .claude/skills/pcb-design/scripts/check_kicad.sh` exits 0.
- `export KICAD_CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` in the same Bash call as every `pcb` command that needs KiCad; `kicad-cli` is not on `PATH`.
- Read the repo's `## Hardware` section, the firmware pin header and the design note.
- Checkpoint the board directory (the rule in `SKILL.md`).

## 1. Start the board

New board: `pcb new board <Name> <repo-url>` gives `<Name>.zen` and `pcb.toml` (the sources) and an `eda/` KiCad project (generated, and persistent). An existing KiCad project: read `diode/importing-kicad-projects.md`, then `pcb import <project>.kicad_pro .` in a new empty directory. Import rejects layout-only projects, files from a KiCad nightly and projects with more than one top-level sheet. Its success is not manufacturing readiness: the imported text is a starting point that the gates still check.

## 2. Parts (gate 2)

Write the requirements and each part choice into the design note first, each with its datasheet on disk and the page that carries the pinout and the package drawing.

- The standard library has generics for passives, LEDs, crystals, headers, test points, TVS diodes and mounting holes. A module, a regulator or a connector comes from a registry package or from your own `Component()` on a `.kicad_sym` and `.kicad_mod` (`diode/librarian.md`). If the registry asks you to sign in, take the other route.
- Every component in the BOM needs `Part(mpn=..., manufacturer=...)` or the symbol's properties; the build fails without them. Unused pins take `NotConnected()`.
- Check each footprint's pad numbering and pin 1 against the datasheet's package drawing. A wrong footprint passes ERC and DRC and is the most common way these boards die.
- An LCSC number is not a Zener field. The project keeps it where its apply wrapper reads it (aquila: `lcsc.json` per board). Check stock and basic or extended status:

  ```bash
  python3 .claude/skills/pcb-design/scripts/parts_check.py --bom <board dir>/review/bom.csv
  ```

## 3. Write the Zener (gate 3)

Follow `diode/zener-language.md`. Then `pcb sync` after a dependency change, `pcb fmt`, and `pcb build <board>.zen` until the diagnostics are clean. `pcb build` needs no KiCad.

Regenerate the KiCad project with the project's apply wrapper when it has one (aquila: `sh tools/apply_board.sh <b>`, never plain `pcb apply`), otherwise `pcb apply --no-open <board>.zen`. The schematic is redrawn; the board file keeps its placement and tracks. What the apply step does to the project, found on aquila's boards with `pcb` 0.4.101:

- It renumbers reference designators when a part is added. Layout tools name a part by its Zener path (`MCU.R_EN`), never by `R12`.
- It rewrites the constraint values and the Default net class in `.kicad_pro`. Board rules belong in the `.zen` and in `eda/<b>.kicad_dru`, where they survive.
- After one part is swapped for another, move `eda/<b>.kicad_sch` away first so the schematic is drawn afresh; the incremental update left wire stubs that ERC flags.
- The generated schematic embeds its symbols without a library name, so ERC gives one `lib_symbol_issues` warning per symbol. Leave them: they are not errors and are not excluded.
- ERC's `power_pin_not_driven` on a supply net with no power-output pin is handled in the source (a flagged test pad), not excluded.

Then run review steps 1 to 4 (`review.md`) on the generated project, and hand the datasheet review to the reviewer (`delegate.md`).

## 4. Place and route (gates 4 and 5)

`routing.md`. Whatever is not placed or routed is reported as open, with the count from `erc_drc.sh drc`, not as done.

## 5. Check, every round

- `pcb dfm --pdk jlc <board>.zen` for a JLCPCB board (`jlc` is the profile name on aquila's version; confirm with `pcb help dfm`).
- `pcb test` or `pcb sim` where a testbench exists (`diode/spice-sim.md`). `pcb sim` reports success whenever ngspice exits normally, even when a measurement failed: read the measurements.
- Review steps 5 and 6 (`review.md`). Schematic parity comes from `erc_drc.sh drc` and nowhere else: `pcb layout --check` runs DRC without the parity check (Diode issue 1657), so a pass from it says nothing about whether the board matches the schematic.
- Sort each finding into fix or accepted-by-the-user, with the reason written down, and append it to the defect ledger.

## 6. Report

What changed in Zener and in the layout, each gate with its counts, the findings left open, what is unverified, and what the user should look at in KiCad. The order set is gate 7, on the user's request (`review.md` step 7).
