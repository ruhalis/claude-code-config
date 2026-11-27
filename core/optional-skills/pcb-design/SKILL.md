---
name: pcb-design
description: Designs and checks the user's own circuit boards. Design mode writes a board as code in Zener with Diode's pcb CLI, generates the KiCad 10 project, then places and routes it. Review mode checks any KiCad 10 project read-only through kicad-cli - ERC, DRC with schematic parity, firmware pin diff, ESP32-S3 rules, datasheet-cited findings. Both end at the same gates, and the JLCPCB order set (gerbers, BOM, CPL) is exported only when they pass. Use whenever the user asks to design, change, place, route, review or order a board or schematic, or mentions KiCad, .kicad_sch, .kicad_pcb, Zener, a .zen file, pcb.toml, the pcb CLI, ERC, DRC, a netlist, a footprint, a pin map, strapping pins, decoupling, a BOM, LCSC, JLCPCB, gerbers or a CPL. Not for enclosures (text-to-cad's cad skill) or firmware (esp-idf).
compatibility: Claude Code on macOS. KiCad 10 as /Applications/KiCad/KiCad.app (kicad-cli by absolute path), python3 3.10 or later, Homebrew pdftoppm optional. Design mode also needs Diode's pcb CLI in ~/.local/bin and runs on Claude Fable 5.2 or later at high effort. ngspice only for pcb sim. Network for datasheets, part lookups and the pcb toolchain.
---

# PCB design

Project skill for boards the user designs. Two modes share one set of gates:

- **Design.** The board is code: Zener (`.zen`) is the source, Diode's `pcb` CLI generates the KiCad 10 project, and the project's own tools place and route. Read `references/authoring.md`.
- **Review.** Any KiCad 10 project, hand-drawn or generated, checked read-only through `kicad-cli`. Read `references/review.md`.

The model drafts and the scripts decide. Models report a board clean while nets are still open, and a "DRC 0" can hide switched-off rules, so nothing here counts as done until a script's numbers from this round say so. Nothing made with this skill has been fabricated yet: treat every result as unproven until a board has been powered.

## Rules

- **Counts come from the scripts.** "Clean", "routed" and "ready" are statements about what `erc_drc.sh`, `pin_diff.py` and `fab_export.sh` printed this round, never about what you believe you did. Never change a rule, a severity or an exclusion to make a report clean: `erc_drc.sh` prints the disabled and downgraded checks and the exclusions, and the manifest records them.
- **Review writes nothing.** In review mode no `.kicad_*` file is written by any route: not by hand, not with `sed`, not through KiCad's Python or its IPC API. A finding is a sentence someone acts on. Asked to "just fix the file" during a review: finish the finding, then switch to design mode if the board is authored as code, or hand the change to the user's KiCad GUI if it is hand-drawn.
- **Design writes through the source.** A schematic change is an edit to a `.zen` file and a regenerate through the project's apply wrapper, never a hand edit of the generated `.kicad_sch`. Placement, tracks and zones live in the `.kicad_pcb` and change only through the project's layout tools, so every board write goes through one place. A board the user drew by hand is imported into a new directory; the original changes only when the user names that file in this conversation.
- **Design runs on Claude Fable 5.2 or later at `high` effort:** the main session, a fork of it, or `general-purpose` launched with `model: "fable"` and `effort: "high"`. On any other model, finish as review findings and say the change needs a Fable session. No hook enforces this; the gates below are what protect an order.
- **Checkpoint before every step that writes.** `git check-ignore -q <board dir>` succeeding means git does not track the board (aquila's `hardware/`): copy the board directory aside first (`rsync -a --exclude .history`). Tracked: start from a clean `git status` for that directory.
- **Every electrical number has a source.** Pin numbers, absolute maximums, strapping levels, regulator equations, capacitor values: download the datasheet with `curl -L -o` into the project's datasheet folder, read it from disk, and cite the page next to the Zener or in the finding. The project's design note is the other valid source. Nothing from memory, the tables in `references/` included: they are starting points to re-verify. No datasheet: the item is `unverified`.
- **Nothing leaves the machine through Diode.** Never `pcb auth`, `pcb publish`, `pcb quote` or `pcb scan`, never build.diode.computer; `pcb bom` only with `--offline`.
- **Tool facts come from the tool.** `pcb help <command>`, not memory and not this skill: the CLI ships several releases a week. Record `pcb --version` each round; its launcher updates itself inside the lane `pcb.toml` pins, so a new version means reading the changelog before the next write. One KiCad per machine, pinned in `kicad-version`: another major is a stop. Never install or update KiCad or `pcb`, and never use text-to-cad's `pcb` skill, which saves boards in a nightly format KiCad 10 and `pcb import` reject.
- **Ordering and paying are human-only.** Never upload, log in, fill a cart or drive the fab's site.
- **Project facts come from the repo:** the `## Hardware` section of its `CLAUDE.md` (format in `references/review.md`), the firmware pin header, the design note. A missing fact is asked, never defaulted. Where the project's design note records toolchain facts (aquila: `hardware/DESIGN.md`), it wins over this skill.
- **Say what was not verified.** A board that passes every gate has had no electrical validation, RF tuning, thermal check or bring-up. The report says so.

## Gates

A board moves forward one gate at a time. The user approves each gate; when they have said to run through, record the evidence at every gate and still stop at 1, 2 and 7.

| Gate | Passes when | Evidence |
|---|---|---|
| 1 Requirements | Interfaces, supplies, currents, mechanical limits, fab and layer count are written in the design note | The note, approved by the user |
| 2 Parts | Every part has a datasheet on disk, a footprint checked against its package drawing, and a known tier and stock at the fab | Part table with datasheet pages; `parts_check.py` for the tier, and for stock when it can read it (exit 3 means the user reads stock on the fab's page) |
| 3 Schematic | The source builds; ERC has 0 errors; the firmware pin diff has 0 errors; the datasheet review has no open mismatch | `erc_drc.sh erc`, `pin_diff.py`, the reviewer's table (`delegate.md`) |
| 4 Placement | Connectors, holes and outline sit where the user fixed them; decoupling is at its pins; keep-outs are clear | Renders from `export_review.sh pcb`, read by you and shown to the user |
| 5 Routing | DRC has 0 violations, 0 unconnected and 0 parity errors on saved and on refilled zones; the post-route checks pass | `erc_drc.sh drc`; `references/routing.md` |
| 6 Verification | Every finding is fixed or accepted by the user by name; the unverified list is written | The report |
| 7 Order package | `fab_export.sh` produced the set, which it refuses to do (exit 4, nothing written) until the pre-export gate below passes | `MANIFEST.txt` with `gates: pass`, the table in `references/jlcpcb-order.md`, the user reading the fab's placement preview |

Review mode enters at gate 3 with the board as it is and runs 3, 5, 6 and, on request, 7.

**The pre-export gate passes** (`fab_export.sh` reads it from `review/gate.json`; this is the one definition, the other files follow it) when ERC has 0 errors (warnings are counted, not failed); DRC, run with `--schematic-parity`, has 0 error-severity violations, 0 unconnected items and 0 parity issues on both the saved and the refilled zones; the pin diff has 0 errors and read the `review/board.net` that `export_review.sh sch` recorded from the current sheets; no rule of the critical set is set below its floor in the `.kicad_pro` (the `downgraded checks:` line marks it `critical: blocks`); and each result is current, meaning every file it depends on hashes as it did when the check ran. `--no-pin-header` drops the pin diff only for a project with no firmware pin header; it is refused once a pin diff is recorded, and the manifest then reads `gates: pass (pin diff not applicable: --no-pin-header)`. `--accept "<reason>"` waives only failing counts and downgraded critical rules recorded on current inputs. It never waives a check not run or stale, DRC without parity or without the refilled run, a stale netlist, an unreadable `gate.json` or a refused `--no-pin-header`: those exit 4 with `--accept cannot waive:`.

## Files

Scripts locate their own directory. Run them from the project root by the installed path, `.claude/skills/pcb-design/scripts/<name>`.

| File | Use |
|---|---|
| `references/review.md` | Review mode, and every check in design mode: the steps, the exit codes, how to read the exports. |
| `references/authoring.md` | Design mode: preconditions, Zener, regenerate, what the `pcb` CLI does to the KiCad project. |
| `references/routing.md` | Gates 4 and 5: placement order, which nets are routed by hand, routers, post-route checks. |
| `references/esp32-s3-rules.md` | When the MCU is an ESP32-S3. |
| `references/schematic-review.md` | Gate 3 checklist. |
| `references/layout-review.md` | Gates 4 and 5 checklist. |
| `references/jlcpcb-order.md` | Gate 7 pre-upload table. |
| `references/diode/zener-language.md` | Before writing or changing any `.zen`. |
| `references/diode/importing-kicad-projects.md` | Starting from an existing KiCad project. |
| `references/diode/librarian.md` | A part with no package needs its own `Component()`, symbol and footprint. Its registry-publishing parts do not apply. |
| `references/diode/registry-search.md` | Looking for a reusable module or component package. |
| `references/diode/spice-sim.md` | A testbench would settle a question. |
| `references/diode/PIN` | The Diode release the five files above were copied from. |
| `delegate.md` | Handed to agents that cannot load this skill: gate runs for `verifier`, the datasheet review for the reviewer. |
| `kicad-version` | The pinned KiCad, the only authoritative copy. |
| `scripts/check_kicad.sh` | Once per session: KiCad at the pinned major, python3, pdftoppm, `pcb` and ngspice present. |
| `scripts/export_review.sh` | Netlist, BOM, PDFs, renders and PNG crops into `review/`. |
| `scripts/erc_drc.sh` | ERC, and DRC with schematic parity on saved and refilled zones. |
| `scripts/pin_diff.py` | Netlist GPIO assignments against the firmware pin header. |
| `scripts/parts_check.py` | Stock and basic or extended status of each LCSC number. |
| `scripts/fab_export.sh` | Gate 7: gerbers, drill, BOM, CPL, checks and `MANIFEST.txt`. |
| `scripts/fab_diff.sh` | Two fab sets compared after a change. |
| `scripts/fabset.py` | Not run directly: behind the three scripts above and the self-test. |
| `scripts/selftest.sh` | Offline check of the scripts against `assets/fixtures/`; run after editing a script or when KiCad differs from the pin. |

The Diode files are Diode's own agent skills, copied verbatim (MIT, `references/diode/LICENSE`). Where one conflicts with the rules above, the rules win. They mention tools and skills that exist only inside Diode's environment (`agent-schema`, `librarian-dispatch`, `module-layout`, `kicad-symbol`, `kicad-footprint`): skip those lines.

## Who runs what

- **Authoring rounds** (writing Zener, regenerating, placing, routing, looking at renders) are design iteration: the Fable agent doing the design runs them and looks at the result.
- **Gate runs** whose result is pass or fail (`erc_drc.sh`, `pin_diff.py`, `parts_check.py`, `fab_export.sh`, `selftest.sh`) go to `verifier` from the main session, with `delegate.md` named in the brief.
- **The datasheet review** at gate 3 goes to a reviewer in a fresh context that has not seen the author's reasoning: `deep-reasoner`, briefed with `delegate.md`. It is a different model from the same maker, which is weaker independence than a reviewer from another maker; if the user has one, its findings go into the same table.
- **Defect ledger.** Append every defect to the project's ledger (aquila: `hardware/DEFECTS.md`) as `date | board | gate that caught it | defect | fix`, including what the fab's checks and the bench find later. It is the only record of which gates earn their cost.

## Not yet verified

Written 2026-11-27 from two skills that took aquila's `core` and `top` boards to a clean export on 2026-11-12, and from research of the same date. Confirm on first use and then edit this section: that `pcb` still launches and which version it resolves to; whether registry packages on `code.diode.computer` clone without signing in; KiCadRoutingTools on a real board (`references/routing.md`); the numbers in `references/esp32-s3-rules.md` and `references/jlcpcb-order.md` against the live Espressif and JLCPCB pages; anything about a fabricated board.
