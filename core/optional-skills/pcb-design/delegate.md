# PCB rules for agents working without the pcb-design skill

Read this before you run a board check or review a board in this project. The project's `CLAUDE.md` and its hardware design note win where they are more specific. Two jobs are handed out with this file; your brief says which one is yours.

## For every agent

- Write no `.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, `.kicad_sym`, `.kicad_mod`, `.kicad_dru` or `.zen` file, by any route. You check and report; the designing agent fixes.
- Never run `pcb` in any form (its launcher updates itself on every call), never open the KiCad GUI, never install anything, never upload a design or log in anywhere.
- KiCad's command line is `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`; it is not on `PATH`. The scripts call it themselves.
- Run from the project root. The scripts are at `.claude/skills/pcb-design/scripts/`. `B` is the board directory that holds the `.kicad_pro` (aquila: `hardware/boards/<b>/eda`), and it must be given to you; do not guess it. The other placeholders also come from your brief or the project's `## Hardware` section: `<b>` the board's file name stem, `<header>` the firmware pin header, `<ref>` the MCU's reference designator, and `<date>` today as `YYYY-MM-DD` (add `b`, `c` for a second set on the same day; never export over an earlier set).
- A board checked on a scratch copy keeps its folder layout: copy from the project root down, or link the sibling library folders, because the project's library table uses paths relative to the board directory. A copy of the `eda` folder alone adds false `footprint_link_issues` and `lib_footprint_issues` warnings (156 each on aquila's `core`).
- Report numbers as the scripts printed them. Do not summarise a non-zero count as "minor".

## Job 1: gate run (verifier)

Run the commands your brief names, in this order when it asks for the full gate, and report each exit code with the summary lines.

| Step | Command | Exit codes |
|---|---|---|
| Environment | `bash .claude/skills/pcb-design/scripts/check_kicad.sh` | 0 go; 1 KiCad missing, wrong major, or no python3: stop |
| Exports | `bash .claude/skills/pcb-design/scripts/export_review.sh sch "$B"` | 0; 1 misuse, a failed export, or a sheet changed during the export: stop, no netlist is left and the pin diff cannot pass without it |
| ERC | `bash .claude/skills/pcb-design/scripts/erc_drc.sh erc "$B/<b>.kicad_sch"` | 0 clean; 5 violations of any severity, or a critical rule downgraded; 3 did not load, and nothing is recorded even when a report was written; 1 misuse, or no gate record (a file saved during the run, no report, one that is not a kicad-cli report on this file, or only the refilled DRC run did not load) |
| Pin diff | `python3 .claude/skills/pcb-design/scripts/pin_diff.py --netlist "$B/review/board.net" --header <header> --mcu <ref> --record "$B" > "$B/review/pin_diff.txt"` | 0; 2 at least one error row; 1 misuse or unparsable input (a `#define PIN_` line it cannot resolve is named). A record on a stale or missing netlist still exits 0 or 2: the stderr line `gate: pin_diff recorded ..., but the gate blocks: stale netlist: ...` shows the block; quote it and re-run Exports first |
| DRC | `bash .claude/skills/pcb-design/scripts/erc_drc.sh drc "$B/<b>.kicad_pcb"` | as ERC |
| Parts | `python3 .claude/skills/pcb-design/scripts/parts_check.py --bom "$B/review/bom.csv"` | 0 all found and in stock; 2 a part missing or out of stock; 3 a lookup failed or a stock figure is unknown: report the tiers it did print and say stock is unverified |
| Order set | `bash .claude/skills/pcb-design/scripts/fab_export.sh "$B/<b>.kicad_pcb" "$B/<b>.kicad_sch" "$B/fab/<date>"` | 0 the set is in `$B/fab/<date>`; 4 a gate blocks, or `--accept` cannot waive it, or an input changed during the export, and nothing was exported; 1 misuse, an outdir that already holds an order file (use the next dated folder), a failed export, or the file set or the BOM against the CPL failed, and nothing was left in the outdir |

The gate passes only when ERC has 0 errors (warnings are listed, not failed); DRC, run with schematic parity, has 0 error-severity violations, 0 unconnected items and 0 parity errors on both the saved and the refilled zones; the pin diff has 0 errors on the netlist the Exports step recorded from the current sheets; no critical rule is downgraded; and every result is current (its files unchanged since it ran). This is the definition in `SKILL.md`, section Gates. So run Exports again after any schematic change, before the pin diff. Quote both DRC count lines (`saved fills:` and `refilled:`) and always quote the `disabled checks:`, `downgraded checks:` and `exclusions:` lines: a clean count with checks switched off is not clean. Run the order-set step only when the brief asks for it. Pass `--no-pin-header` only when the brief says the project has no firmware pin header; the script refuses it once a pin diff is recorded. Never pass `--accept` unless the brief gives the user's reason word for word. It waives only failing counts and downgraded critical rules; it cannot waive a check not run or stale, DRC without parity or without the refilled run, a stale netlist, an unreadable `gate.json` or a refused `--no-pin-header`, which exit 4 with a `--accept cannot waive:` line: report that line.

`bash .claude/skills/pcb-design/scripts/selftest.sh` checks the scripts themselves, offline: 0 passed; 1, quote every FAIL line.

## Job 2: datasheet review (reviewer)

You are the independent check on a schematic someone else wrote. You have not seen their reasoning and must not ask for it. Your inputs are `$B/review/board.net` (the netlist), `$B/review/bom.csv`, the project's datasheet folder, the firmware pin header and the design note's requirements. Work from the netlist and the datasheets as text. Do not judge connectivity from a picture of the schematic: images are for finding a part on the sheet, nothing more.

For every IC, module, regulator, connector, transistor, diode and polarised part, check each pin against the datasheet page that defines it. For each claim give one verdict:

- `OK`: the netlist matches the datasheet, and you cite the datasheet file and page.
- `MISMATCH`: it does not, and you cite the page and quote the line or table cell.
- `UNVERIFIED`: you could not find the page, the datasheet is missing, or the part number is ambiguous. Abstain; never fill the gap from memory.

What to check, in this order of how often it kills a board:

1. Pin number to pin function for every pin, and the footprint's pad numbering and pin 1 against the package drawing for the exact package in the BOM.
2. Enable, reset, boot and strapping pins: the level each one is tied to and what that level selects.
3. Regulators: feedback divider arithmetic against the datasheet's equation, the resulting output voltage, input and output capacitor values and types against the datasheet's requirements, inductor value and saturation current.
4. Every pin's voltage against its absolute maximum and its supply domain; level mismatches between parts on different rails.
5. USB: D+ and D− not swapped, CC resistors, ESD part pinout. UART: TX to RX. I2C: pull-ups present once, addresses distinct. SPI: MOSI, MISO and chip selects.
6. Connectors: pin order against the mating cable or module's datasheet, pin 1, and whether the footprint is the mirrored variant.
7. Decoupling at every supply pin by the datasheet's recommendation; bulk capacitance at each connector that feeds a load.
8. Unused pins: tied or left open as the datasheet requires.
9. The firmware pin header against the netlist, for any signal the pin diff does not cover.

Report one table, mismatches first: `verdict | ref and pin | net | what the datasheet says | datasheet file and page`. Then the count of each verdict, and the list of parts whose datasheet was missing. Do not propose a redesign; state what is wrong and where it is written.
