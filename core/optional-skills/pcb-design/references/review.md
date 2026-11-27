# Review procedure

Review mode runs these steps on a board as it is and writes no KiCad file. Design mode runs the same steps as its checks after each regenerate (`authoring.md`). Run every command from the project root.

## What a hardware project looks like

```
hardware/<board>/<board>.kicad_pro|.kicad_sch|.kicad_pcb    drawn in the GUI, committed
hardware/<board>/lib/                                       project symbol and footprint libraries, committed
hardware/<board>/review/                                    kicad-cli exports and reports, generated
hardware/<board>/fab/<date>/                                gerbers, BOM, CPL, zip, MANIFEST.txt, generated
```

A board authored as code (design mode) keeps its generated KiCad project one level down, in `hardware/boards/<board>/eda/` (aquila's `core` and `top`). That `eda/` directory is the board directory `B` in every step below. Its `fp-lib-table` points at `${KIPRJMOD}/../../../components` and `../../../.pcb/stdlib`, so a scratch copy must keep that depth (step 0 shows one), or ERC reports every footprint library as missing.

Before the first commit, `git check-ignore -v hardware/<board>/lib/<x>.kicad_sym hardware/<board>/.history` must print a rule for `.history` and none for `lib/`: a Python `.gitignore` template ignores `lib/`.

The `## Hardware` section sits next to `## Boards` in the project's `CLAUDE.md` (or `CLAUDE.local.md`), one `key: value` per line so it can be grepped:

```
## Hardware
kicad: hardware/boards/core/eda/core.kicad_pro
pins: hardware/boards/core/core_pins.h
mcu: U11                         # reference designator of the MCU or module symbol
fab: jlcpcb, 4 layers, economic assembly
note: hardware/DESIGN.md
```

Resolve the project the way esp-idf resolves ports: the section, else a path named in this message, else exactly one `*.kicad_pro` in the repo (use it and offer to record the section), else zero: say so and stop, else several: ask.

## Steps

Shell variables do not persist between Bash calls, so every block below first sets `B` (the board directory; `<b>` is the board's file name stem). The working directory does persist: run from the repo root.

### 0. Environment, once per session

```bash
bash .claude/skills/pcb-design/scripts/check_kicad.sh
```

Exit 0: go. Exit 1: KiCad missing, wrong major, or no python3: stop, quote the output, say KiCad comes from kicad.org as an app bundle. Never `brew install` it. The `pdftoppm`, `ipc api`, `pcb` and `ngspice` lines are informational; the script reports where `pcb` is and never runs it.

A `WARNING: differs from pin` line (another patch or minor) runs the self-test before anything else:

```bash
bash .claude/skills/pcb-design/scripts/selftest.sh
```

Exit 0: every assertion passed; carry on and say the pin differs. Exit 1: quote the FAIL lines and stop. It checks the scripts against a 10.0.5 fixture and cannot see a changed kicad-cli output. Before `kicad-version` is bumped, run the known project, aquila's `core` board at `~/projects/aquila/hardware/boards/core/eda` (mcu `U11`), through the new kicad-cli. Copy it with its library depth kept (no `review/` comes along, so nothing from the old kicad-cli is read back), run steps 1, 2, 4 and 5 on the copy with `--header ~/projects/aquila/hardware/boards/core/core_pins.h` read in place, and compare with what 10.0.5 gave on 2026-11-17:

```bash
A=~/projects/aquila/hardware; S="$(mktemp -d)"; mkdir -p "$S/hw/boards/core" "$S/hw/.pcb"
rsync -a --exclude .history --exclude review --exclude fab "$A/boards/core/eda" "$S/hw/boards/core/"
rsync -a "$A/components" "$S/hw/"; ln -s "$(readlink "$A/.pcb/stdlib")" "$S/hw/.pcb/stdlib"; echo "$S/hw/boards/core/eda"
```

Each result depends on the files in its last column, recorded by their sha256 prefix:

| Step | 10.0.5 result | Depends on (sha256 prefix) |
|---|---|---|
| 2 ERC | exit 5: 308 warnings, all `lib_symbol_issues` (symbol library `''`), 0 errors; 464 with 156 `footprint_link_issues` means the copy lost its library depth | `.kicad_sch` `9e895069`, `.kicad_pro` `f57efdda` |
| 4 pin diff | exit 0: `errors=0 warnings=7 info=0`, header pins 32, GPIO pins in netlist 36, only power pins and `EN` unmapped | `.kicad_sch` `9e895069`, `core_pins.h` `aade4921` |
| 5 DRC | exit 0: clean, 0 unconnected, 0 parity; zone fills current (same counts after refill) | `.kicad_pcb` `6ea53cfb`, `.kicad_sch` `9e895069`, `.kicad_pro` `f57efdda`, `.kicad_dru` `91765201` |

```bash
A=~/projects/aquila/hardware/boards/core; shasum -a 256 "$A"/eda/core.kicad_{sch,pro,pcb,dru} "$A/core_pins.h" | cut -c1-8,65-
```

A row whose files all hash as recorded but whose result differs: the new KiCad changed a check or a report shape; find which before bumping. A row with a changed file: the project changed since, not KiCad; compare that row by hand.

### 1. Read the project

The `## Hardware` section, the pin header, the design note, `BOM.md`, the MCU family and exact module variant (the symbol's Value field). If the MCU is an ESP32-S3, read `references/esp32-s3-rules.md` now. Then export once. Every export in this procedure lands in `review/` inside the board directory, the same place `erc_drc.sh` defaults to, never beside the sources:

```bash
B=hardware/<b>
bash .claude/skills/pcb-design/scripts/export_review.sh sch "$B"
```

It writes `review/board.net` (kicadsexpr), `review/bom.csv` (grouped by value, footprint and LCSC, no ranges) and `review/schematic.pdf`. The old `board.net` is deleted first, and the new one's sha256 is recorded in `review/gate.json` with the hashes the sheets had before the export; the pin-diff gate in step 7 passes only on that netlist, so re-run this step after every schematic change. It then rasterises each page with `pdftoppm -r 200 -png` into `review/png/`: `schematic-p<N>.png` for the whole sheet and, over its drawn area, overlapping crops of about a megapixel, `schematic-p<N>-r<row>c<col>.png`. A dense sheet read as one image loses pin numbers and values; the crops keep them. Read the page PNG for the layout, then the crops; never describe a schematic you have not looked at. Each finding cites the crop it was read from (`review/png/schematic-p1-r2c3.png`). Exit 1: misuse, not exactly one `.kicad_pro` in the directory (pass the `.kicad_pro` instead), an export failed, or a sheet changed during the export (no netlist is kept; save the sheets and run it again). No pdftoppm (the script says so): read the PDF. For a closer look at one spot, crop at 400 dpi; `-x -y -W -H` are pixels at that resolution, so twice the position in the 200-dpi page PNG:

```bash
B=hardware/<b>
/opt/homebrew/bin/pdftoppm -r 400 -png -singlefile -f 1 -l 1 -x 2000 -y 1200 -W 1200 -H 1000 "$B/review/schematic.pdf" "$B/review/png/schematic-p1-zoom1"
```

### 2. ERC

```bash
B=hardware/<b>
bash .claude/skills/pcb-design/scripts/erc_drc.sh erc "$B/<b>.kicad_sch"
```

Exit 0 clean; 5 violations (any severity); 3 the schematic did not load, and nothing is recorded (quote the reason; a missing library table or a moved sheet is fixed in the project, never by editing the file until it loads); 1 misuse, including a file of the wrong type (`erc` takes a `.kicad_sch`, `drc` a `.kicad_pcb`, both a `.kicad_pro`). Each error becomes a fix in the source (the `.zen` for a board authored as code, the user's KiCad GUI for a hand-drawn one) or an exclusion the user sets by name. The script also prints `disabled checks:`, `downgraded checks:` and `exclusions:`; report all three lines with the counts. `downgraded checks:` lists the `.kicad_pro` rules below KiCad 10's default severity (and, for DRC, `.kicad_dru` rules at `warning`, printed only). A rule of the critical set below its floor is marked `critical: blocks`, makes the script exit 5 and blocks step 7: for ERC `pin_not_connected` and `power_pin_not_driven` below `error`, `pin_to_pin` at `ignore`; for DRC `unconnected_items`, `clearance`, `shorting_items`, `tracks_crossing`, `copper_edge_clearance` and `hole_clearance` below `error`, and the parity rules (`duplicate_footprints`, `extra_footprint`, `missing_footprint`, `net_conflict`, `footprint_symbol_mismatch`, `footprint_symbol_field_mismatch`) at `ignore`. A report that is not a kicad-cli report on the file checked (no `source` naming it, an array missing) is not recorded: exit 1, and step 7 reads the check as not run. KiCad ships with a few checks ignored, so the list is rarely empty: what matters is a check that is off beyond the project's baseline, or any exclusion. Aquila's `core` board on 2026-11-27, all KiCad defaults with 0 exclusions: ERC `single_global_label`, `four_way_junction`, `simulation_model_issue`, `footprint_filter`; DRC `missing_courtyard`, `track_not_centered_on_via`, `tuning_profile_track_geometries`, `footprint_filters_mismatch`, `footprint_type_mismatch`. Warnings are triaged one by one, not dismissed as a class: the script lists each one with the symbols and pins involved, up to 20 per severity; the rest are in the JSON. The step-3 checklist reads this result.

### 3. Schematic-stage review

Walk `references/schematic-review.md` against the netlist, the PDF, the header, the ERC result and the fetched datasheets. Report as a table `sev | ref/net | finding | source`, errors first: one row for each finding someone acts on, repeated or info-level findings summarised by type. Every row names its evidence or says `unverified`. The pin-by-pin datasheet check is the reviewer's job (`delegate.md`, job 2); merge its table into this one.

### 4. Pin diff against firmware

```bash
B=hardware/<b>
python3 .claude/skills/pcb-design/scripts/pin_diff.py --netlist "$B/review/board.net" --header <pins:> --mcu <mcu:> --record "$B" > "$B/review/pin_diff.txt"; echo "exit $?"; cat "$B/review/pin_diff.txt"
```

The table is kept in `review/pin_diff.txt`, and `--record` writes the counts and the hashes of the sheets, the header and the netlist into `review/gate.json`, which step 7 reads. Exit 2 means at least one error row; paste the table. Exit 1 is misuse or a file it could not parse, including a `#define PIN_` line whose value it cannot resolve (it names each line). The header contract is flat `#define PIN_* <value>` lines (aquila's `core_pins.h`), the value a decimal or `0x` number or `GPIO_NUM_<n>`, bare, parenthesised or cast (`((gpio_num_t)21)`); `GPIO_NUM_NC` or `-1` is an `NC` info row. A header with `#if` branches or struct initialisers (athena's `board_pins.h`) is out of scope: say so and ask for a flat header or a `--pinmap`. GPIO35 to 37 follow the module variant in the MCU symbol's value: an octal-PSRAM code (R8, R16V) makes them `RESERVED` errors, a quad-PSRAM (R2) or no-PSRAM code frees them, a value without an ordering code keeps them `CAUTION` with the variant named unknown. When the value does not carry the code, pass `--psram octal|quad|none` from the BOM or the design note, never from a guess. KiCad 10 netlists write pin functions as `NAME_<pad>` (`USB_D-_13`); `pin_diff.py` strips the suffix, maps `IOn` by regex and `USB_D-`/`USB_D+`/`RXD0`/`TXD0` by built-in alias. If the unmapped line lists any of those four, stop and report. A symbol whose pin names carry no GPIO number needs `--pinmap pad,gpio`. Skip the step and say so when the project has no pin header yet.

### 5. DRC

```bash
B=hardware/<b>
bash .claude/skills/pcb-design/scripts/erc_drc.sh drc "$B/<b>.kicad_pcb"
```

Runs with `--schematic-parity` on the zone fills saved in the board, then again with zones refilled in memory into `review/drc_refilled.json`. Any `unconnected_items` or parity issue blocks step 7. If the script prints `zone fills are stale`, that is a finding: the zones are refilled and the board saved (the project's layout tool for a board authored as code; Edit > Fill All Zones, B, in the GUI for a hand-drawn one), and step 7 waits until the saved board passes without refill. `--refill-zones` here and `--check-zones` in steps 6 and 7 refill in memory only; the board file is never saved. Each run prints one line, `violations=N (errors=N) unconnected=N parity=N`: quote both. Exit codes as in step 2, and 5 also when either run has an error-severity violation, an unconnected item or a parity issue. ERC and DRC each record their counts and the hashes their inputs had when the run started in `review/gate.json`, and only for a completed run: a kicad-cli exit other than 0 or 5, or a file saved during the run, records nothing (exit 1, or 3 kept), and step 7 reads the check as not run.

### 6. Layout-stage review

```bash
B=hardware/<b>
bash .claude/skills/pcb-design/scripts/export_review.sh pcb "$B"
```

It writes `review/stats.json`; `front.pdf` (F.Cu, F.Silkscreen, Edge.Cuts) and `back.pdf` (the B side, mirrored as seen from below), each one page with the board autoscaled (`--mode-single --scale 0`: the board's longer side fits the page, so aquila's 44 × 60 mm board fills the height and about a third of the A4-landscape width; at scale 1 it is a thumbnail in a corner, and the crops carry the detail either way); one `inner_In<n>.Cu.pdf` per inner copper layer in the board's `(layers ...)` header; `render_top.png` and `render_bottom.png`. Every PDF plots zones refilled in memory (`--check-zones`). Then the same 200-dpi page PNGs and crops as in step 1 go to `review/png/` (`front-p1-r1c1.png`, `inner_In1.Cu-p1-r1c1.png`, ...). Read the renders for placement and the crops for copper, planes and silkscreen, then walk `references/layout-review.md`. Same report format as step 3, each finding citing its crop or render. Placement and routing quality are the user's judgement; report what the exports show.

### 7. Pre-order

The script checks the gates before it plots anything, from `review/gate.json`, as `SKILL.md` defines them (section Gates): ERC, DRC and the pin diff run, current and passing, the pin diff on the netlist step 1 recorded, no critical rule downgraded. A gate that fails, is stale or was not run makes the script exit 4, name each blocked gate with its reason, and write nothing. The fix is to re-run the step it names, never to work around the script. Two flags, both copied into the manifest:

- `--no-pin-header` when the project has no firmware pin header, so the pin-diff gate does not apply. Refused (exit 4) once a pin diff is recorded for the board; the manifest then reads `gates: pass (pin diff not applicable: --no-pin-header)`.
- `--accept "<reason>"` exports despite failing counts or downgraded critical rules. Use it only with the user's own reason, given in this conversation for the items that remain, quoted word for word. A block marked `[cannot be accepted]` (not run, stale, no parity, no refilled run, stale netlist, unreadable `gate.json`) still exits 4.

The output directory must be new, or hold none of `gerber/`, `gerbers.zip`, `bom.csv`, `cpl.csv`, `MANIFEST.txt`: the script refuses one that does (exit 1). It builds the set in a temporary directory beside it and moves it in only when every step and check passed, so a failure leaves nothing. If an input changes during the export, the gates recomputed for the manifest block and the script discards the set and exits 4.

If the project has an `ORDER.md` (earlier order fields, delivery country, fab route), read it first. Run `parts_check.py` on the BOM before the export: it gives each LCSC number's basic or extended tier and price, and exits 3 when it cannot read a stock figure (the lookup service has reported none since early November 2026), in which case stock is read by the user on the fab's parts page at order time.

```bash
B=hardware/<b>
bash .claude/skills/pcb-design/scripts/fab_export.sh "$B/<b>.kicad_pcb" "$B/<b>.kicad_sch" "$B/fab/<date>"
```

The script plots with zones refilled in memory. It exits 1 when the gerber set is not exactly one file per requested layer (named as the job file lists them, so a renamed inner layer is fine) plus drill, map and job file, when a BOM cell holds a designator range, or when a BOM designator with an LCSC number has no CPL row. It prints both designator differences; CPL-only rows (fiducials, logos: footprints excluded from the BOM) are listed, not failed. Then fill the pre-upload table in `references/jlcpcb-order.md`: copper layer count equals the `fab:` line, Edge.Cuts and drill present, every BOM designator with an LCSC number in the CPL and no ranges, BOM-only and CPL-only rows listed and explained, every BOM row without an LCSC number explained, CPL rows with an LCSC number equal the assembled parts and the other BOM parts are listed as hand-soldered, the delivery country offers PCBA, rotation caveat stated.

Last, the script writes `<outdir>/MANIFEST.txt`, which ties the set to what it came from: sha256 of the `.kicad_pcb`, the root sheet and every sheet it references, the `.kicad_pro` and `.kicad_dru`, and of `gerbers.zip`, `bom.csv` and `cpl.csv`; the kicad-cli version; the git revision, `DIRTY` with the files when the board has uncommitted changes, or `not tracked`; the copper layers; the drill tool table with hole and slot counts; `gates: pass` or `gates: ACCEPTED - <reason>`, the flags as given, one line per gate with its counts (a waived gate reads `WAIVED`), and the `disabled checks`, `downgraded checks` and `exclusions` lines for ERC and DRC. An `ACCEPTED` line the user did not ask for is not an orderable set. Hand the user the zip path, `MANIFEST.txt` and the table. They upload.

### 8. Report

One short paragraph per stage run: counts by severity, the findings that matter most, what changes next and where, and what stays unverified. Full JSON stays in `review/`.

### 9. Re-check after a change

After the board changes, or the user asks a what-if (another drill size, another part, a moved connector), the set is re-checked before anything is uploaded.

A what-if happens on a scratch copy, never the original; the change is made there the way that board is normally changed (in review mode, by the user in the GUI). The copy leaves out `.history`, and `review/` and `fab/` so no earlier output is read back as the copy's own: step 1 on the copy writes its own `review/`, and older fab sets are compared from the original's `fab/`. A fab set exported from the copy is for comparison only; the order comes from the original once the user has made the change there.

```bash
B=hardware/<b>; S="$(mktemp -d)"
rsync -a --exclude .history --exclude review --exclude fab "$B" "$S/"; echo "$S/$(basename "$B")"
```

- Re-run what the change touches: steps 1 to 5 for a schematic change (DRC checks parity), 5 and 6 for a layout change; steps 2, 4 and 5 gate step 7 as before.
- Export into a new directory, never over an earlier set (the script refuses one that holds an order file): `fab/<date>`, then `fab/<date>b`, `fab/<date>c` on the same day.
- Compare it with the set it replaces:

```bash
B=hardware/<b>
bash .claude/skills/pcb-design/scripts/fab_diff.sh "$B/fab/<old>" "$B/fab/<new>"
```

Exit 0 ends `identical except timestamps and G04 comments`: nothing a fab reads changed. Exit 2 names each file that differs, CPL moves and BOM part changes by designator, drill changes by diameter and hole type; the last line lists them (`identical except: cpl.csv, <b>-F_Cu.gtl`). The two manifests' source sha256 lines are printed for information and do not change the exit code. Every difference must be one the user intended; report the others. Exit 1: misuse. Tell the user which directory to upload, with its `MANIFEST.txt`.

## macOS notes

- App bundle path only; `kicad-cli` needs no display and no running KiCad.
- Scripts are bash 3.2-safe (no `mapfile`, no associative arrays) and python3 stdlib-only; `python3` is Homebrew's, the KiCad-bundled Python 3.9 is not used.
- No `timeout` on macOS; every `kicad-cli` call here returns on its own within seconds.
- `pdftoppm` is Homebrew's poppler at `/opt/homebrew/bin/pdftoppm` (`PDFTOPPM` overrides); optional, never installed by this skill.

## Degradation

- KiCad missing or wrong major: quote `check_kicad.sh`, stop.
- No `.kicad_pro` yet: say so; offer `references/schematic-review.md` as a pre-draw checklist against the design note.
- ERC or DRC exit 3: quote the load error; never edit a file to make it load.
- Datasheet unreachable: mark the finding `unverified`, continue.
- No pdftoppm: `export_review.sh` stops after the PDFs; read those and say the crops were skipped.
- `selftest.sh` fails: quote its FAIL lines and stop; a script no longer matches the fixture it was written against.
- No pin header: skip step 4, say so, and pass `--no-pin-header` in step 7 (refused if a pin diff was recorded for the board). Symbol without numbered pin names: `pin_diff.py` says which pins it could not map; ask for a `--pinmap`, never guess one.
- In review mode, asked to place, route or edit a KiCad file: finish the finding, then switch to design mode (`authoring.md`) for a board authored as code, or name the GUI edit for a hand-drawn one.
