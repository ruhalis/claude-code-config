#!/usr/bin/env python3
"""Gate, check, record and compare JLCPCB fab sets for the pcb-design skill. Stdlib only; never writes a project
file (only review/gate.json and the fab output directory).

    fabset.py start erc|drc <file> <review_dir>
    fabset.py record erc|drc <file> <review_dir> --rc <codes> [--flags "<kicad-cli flags>"]
    fabset.py netlist start|finish <root.kicad_sch> <state_file>
    fabset.py gate --pcb <board.kicad_pcb> --sch <root.kicad_sch> [--no-pin-header] [--accept REASON]
    fabset.py check <outdir> <stem> <copper_count>
    fabset.py manifest <outdir> --pcb <board.kicad_pcb> --sch <root.kicad_sch> --kicad <version>
                       --copper <F.Cu,...,B.Cu> --checks pass|FAIL [--no-pin-header] [--accept REASON]
                       [--fail-if-blocked]
    fabset.py diff <old_outdir> <new_outdir>

start     Run by erc_drc.sh before the first kicad-cli call: removes the check's entry from <review_dir>/gate.json
          and its report files, and keeps the input hashes in <review_dir>/<erc|drc>.start.json.
record    Run by erc_drc.sh after the last kicad-cli call: removes the check's old entry from gate.json first, then
          refuses (no entry) without the start state of this run (it is used once), when a kicad-cli exit code in
          --rc is not 0 or 5 (the check did not complete), or when an input changed since start; then reads <review_dir>/erc.json, or drc.json and drc_refilled.json, and writes the counts, the kicad-cli flags
          and the sha256 of every input into gate.json (ERC: every sheet of the hierarchy and the .kicad_pro; DRC:
          the .kicad_pcb, every sheet, .kicad_pro, .kicad_dru). A report must be a JSON object whose `source` names
          the checked file and whose arrays (ERC: sheets[].violations; DRC: violations, unconnected_items,
          schematic_parity) are lists of objects with a severity; anything else is not recorded.
          DRC counts the three arrays apart, in both runs: violations (and those at error severity),
          unconnected_items, schematic_parity; excluded items are not counted. Prints the count lines and
          `disabled checks: <names or none>` (the report's ignored_checks, the .kicad_pro rules at severity ignore,
          and for DRC the .kicad_dru rules with (severity ignore)), `downgraded checks: <rule=severity ... or none>`
          (.kicad_pro rules below KiCad 10's default severity, and .kicad_dru rules with another severity than
          error) and `exclusions: <n>` (erc.erc_exclusions or board.design_settings.drc_exclusions in the
          .kicad_pro). A rule of the critical set below its floor blocks (CRITICAL below). No report: the gate entry
          stays removed. pin_diff.py --record writes the pin_diff entry the same way.
netlist   Run by export_review.sh sch around the netlist export: `start` drops the netlist entry from gate.json and
          writes the sheet hashes to <state_file>; `finish` hashes the sheets again and records review/board.net's
          sha256 with them, or refuses when a sheet changed during the export or no board.net was written.
gate      The pre-export gate fab_export.sh runs before it plots anything: ERC run, current, 0 errors; DRC run with
          --schematic-parity, current, 0 errors, 0 unconnected, 0 parity in the saved-fill and the refilled run;
          pin diff run, current, 0 errors, on the review/board.net export_review.sh recorded from the current
          sheets (not applicable with --no-pin-header, which is refused when a pin diff is recorded); no critical
          rule downgraded. Current means every input hashes as recorded. Names each gate that blocks and why.
          --accept waives only failing counts and downgraded critical rules recorded on the current inputs; any
          other block (not run, stale, unreadable gate.json, DRC without parity, no refilled run, stale netlist,
          --no-pin-header refused) is marked `cannot be accepted` and still exits 4.
check     The file-set checks fab_export.sh runs after plotting, here so scripts/selftest.sh can run them without
          kicad-cli: gerber/ holds exactly the layer files the job file lists (one per requested layer function)
          plus drill, drill map and job file; no BOM designator range; every BOM designator with an LCSC number
          has a CPL row. CPL-only designators (fiducials, logos) are listed, not failed. Prints the counts for the
          pre-order table in references/jlcpcb-order.md.
manifest  Writes <outdir>/MANIFEST.txt: sha256 of the board, schematic sheets, .kicad_pro and .kicad_dru and of the
          uploaded files, the kicad-cli version, the git revision and dirty flag when the board is tracked, the
          copper layers, the drill tool table (slots apart from round holes), the gate lines and flags, the
          disabled and downgraded checks and exclusions, and the ERC/DRC/pin_diff counts found in <board>/review/
          ("not run" when absent, "STALE" when older than a file they depend on, board.net included for the pin
          diff). Sheets are the root sheet and every sheet it references. Nothing is re-run.
diff      Compares two fab sets: bom.csv by designator (ranges expanded, a range-format change reported on its
          own), cpl.csv by designator and field, every gerber/ file line by line with timestamp lines stripped (G04
          comments, %TF.CreationDate, the drill header's date, the job file's CreationDate), drill holes by
          diameter and function (tool numbers shift). When both sets hold a MANIFEST.txt its source sha256 lines
          are compared for information; they do not change the exit code. Ends with `identical except ...`.

Exit: record 0 recorded and passing, 5 recorded with a blocking count or a downgraded critical rule, 1 no report,
a malformed report, no start state, a kicad-cli exit other than 0 or 5, an input changed during the run,
or misuse. start 0. netlist 0 recorded, 1 not recorded. gate 0 every gate passes (or every block is one
--accept waives and it was given), 4 a gate blocks. check 0 every check passed, 1 a check failed. manifest 0 written; with --fail-if-blocked,
4 when the gates recomputed for it block (fab_export.sh then discards the set).
diff 0 identical except timestamp lines, 2 the sets differ. Any subcommand: 1 on misuse or input it could not read.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse exits 2, which diff uses for "the sets differ"; misuse is 1
        self.print_usage(sys.stderr)
        sys.exit("%s: error: %s" % (self.prog, message))


def natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def show(refs):
    refs = sorted(refs, key=natural)
    return ", ".join(refs) if refs else "none"


# ---------------------------------------------------------------- check
def cmd_check(out, stem, ncu):
    bad = False
    try:
        # Gerber set. Layer files are named after the layer's user name (a renamed In1.Cu plots as <stem>-GND.g1),
        # so the expected names come from the job file kicad-cli wrote: one file per requested layer by function,
        # and the directory holds exactly those plus drill, drill map and job file.
        g = sorted(os.listdir(os.path.join(out, "gerber")))
        exact = ["%s.drl" % stem, "%s-drl_map.gbr" % stem, "%s-job.gbrjob" % stem]
        try:
            attrs = json.load(open(os.path.join(out, "gerber", exact[2])))["FilesAttributes"]
            plotted = [a["Path"] for a in attrs]
            funcs = [a.get("FileFunction", "") for a in attrs]
        except (OSError, ValueError, KeyError, TypeError) as e:
            print("FAIL gerber job file %s unreadable: %s" % (exact[2], e))
            plotted, funcs, bad = [], [], True
        want = ["Copper,L%d," % i for i in range(1, ncu + 1)] + [
            "SolderPaste,Top", "SolderPaste,Bot", "Legend,Top", "Legend,Bot", "SolderMask,Top", "SolderMask,Bot",
            "Profile"]
        fn_bad = [w.rstrip(",") for w in want if sum(f.startswith(w) for f in funcs) != 1]
        if len(funcs) != len(want):
            fn_bad.append("%d layer files for %d requested layers" % (len(funcs), len(want)))
        missing = [x for x in plotted + exact if x not in g]
        extra = [f for f in g if f not in plotted + exact]
        edge = [p for p, f in zip(plotted, funcs) if f.startswith("Profile")]
        print("gerber files: %d, expected %d  (copper: %d, drill: %d, edge: %s)"
              % (len(g), len(want) + len(exact), sum(f.startswith("Copper,") for f in funcs),
                 sum(x.lower().endswith(".drl") for x in g), ", ".join(edge) or "NONE"))
        if fn_bad or missing or extra:
            print("FAIL gerber set: layer functions missing or duplicated: %s; files missing: %s; unexpected: %s"
                  % (show(fn_bad), show(missing), show(extra)))
            bad = True

        # BOM: comma-listed designators only; a range token (C10-C15) is a failure.
        rows = list(csv.DictReader(open(os.path.join(out, "bom.csv"), newline="")))
        rng = re.compile(r"^([A-Z]+)([0-9]+)-([A-Z]*)([0-9]+)$")

        def members(t):  # a range token counts as its members in the BOM/CPL comparison, so it only fails once
            m = rng.match(t)
            if not m or (m.group(3) and m.group(3) != m.group(1)):
                return [t]
            return ["%s%d" % (m.group(1), i) for i in range(int(m.group(2)), int(m.group(4)) + 1)]
        bom_refs, lcsc_refs, ranges = set(), set(), []
        for r in rows:
            toks = [t.strip() for t in (r.get("Designator") or "").split(",") if t.strip()]
            ranges += [t for t in toks if rng.match(t)]
            toks = [m for t in toks for m in members(t)]
            bom_refs.update(toks)
            if (r.get("LCSC Part #") or "").strip():
                lcsc_refs.update(toks)
        missing_lcsc = [r["Designator"] for r in rows if not (r.get("LCSC Part #") or "").strip()]
        print("bom lines: %d, parts: %d  (without LCSC part #: %d%s)"
              % (len(rows), len(bom_refs), len(missing_lcsc),
                 (": " + "; ".join(missing_lcsc)[:200]) if missing_lcsc else ""))
        if ranges:
            print("FAIL bom designator ranges (JLC does not expand them): %s" % ", ".join(ranges))
            bad = True

        # BOM designator set against CPL designator set, both directions. A BOM designator with an LCSC number and
        # no CPL row is a part JLC will not place: failure. CPL-only designators are footprints excluded from the
        # BOM (KiCad's stock fiducials carry exclude_from_bom): listed for the user to explain.
        cpl = list(csv.DictReader(open(os.path.join(out, "cpl.csv"), newline="")))
        cpl_refs = set(r["Designator"] for r in cpl)
        print("bom vs cpl designators: in BOM not CPL: %s; in CPL not BOM (board-only, excluded from BOM: fiducials, "
              "logos): %s" % (show(bom_refs - cpl_refs), show(cpl_refs - bom_refs)))
        if lcsc_refs - cpl_refs:
            print("FAIL bom designators with an LCSC number but no CPL row (JLC will not place them): %s"
                  % show(lcsc_refs - cpl_refs))
            bad = True

        # CPL rows whose designator has an LCSC number in the BOM are the assembled parts; the other BOM parts are
        # hand-soldered or unassigned; CPL-only rows are listed above.
        hand = (cpl_refs & bom_refs) - lcsc_refs
        print("cpl rows: %d  (top: %d, bottom: %d)"
              % (len(cpl), sum(r["Layer"] == "Top" for r in cpl), sum(r["Layer"] == "Bottom" for r in cpl)))
        print("  with LCSC in BOM (assembled): %d" % len(cpl_refs & lcsc_refs))
        print("  in BOM without LCSC (hand-soldered or unassigned): %d: %s" % (len(hand), show(hand)))
        print("  not in BOM (board-only): %d" % len(cpl_refs - bom_refs))
        print("zip: %s" % os.path.join(out, "gerbers.zip"))
    except (OSError, KeyError, csv.Error) as e:
        print("FAIL fab set unreadable: %s" % e)
        return 1
    return 1 if bad else 0


# ---------------------------------------------------------------- shared readers
def drill_tools(path):
    """OrderedDict tool -> [diameter, holes, slots, function] from a KiCad Excellon file; units from the header.
    A slot (an oval hole) is one G85 line, or one M15 of a routed slot, and is counted apart from round holes."""
    tools, func, cur, header, units = OrderedDict(), "", None, True, "mm"
    for line in open(path, errors="replace"):
        s = line.strip()
        if header:
            if s.startswith("; #@! TA.AperFunction,"):
                func = s.split(",", 1)[1]
            elif s.startswith("INCH"):
                units = "in"
            m = re.match(r"^T(\d+)C([0-9.]+)", s)
            if m:
                tools["T" + m.group(1)] = [float(m.group(2)), 0, 0, func]
                func = ""
            if s in ("%", "M95"):
                header = False
            continue
        m = re.match(r"^T(\d+)$", s)
        if m:
            cur = "T" + m.group(1)
        elif cur in tools and (s == "M15" or "G85" in s):
            tools[cur][2] += 1
        elif cur in tools and re.match(r"^X-?[0-9.]+Y-?[0-9.]+", s):
            tools[cur][1] += 1
    return tools, units


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------- manifest
def git_state(board_dir, files):
    """The board's git revision, and DIRTY with the files when any of `files` (the board and every sheet it
    references, wherever they sit) is modified or untracked. Paths go to git relative to the work-tree root, so a
    sheet in a subdirectory or a sibling directory of the board counts too; they print as the board directory
    sees them (`sub/child.kicad_sch`, `../common/pwr.kicad_sch`). A sheet outside the work tree is named, not
    judged."""
    def git(cwd, *args):
        try:
            r = subprocess.run(["git", "-C", cwd, "--no-optional-locks"] + list(args),
                               capture_output=True, text=True)
        except OSError:
            return None, ""
        return r.returncode, r.stdout.rstrip("\n")  # porcelain lines start with a meaningful space
    rc, top = git(board_dir, "rev-parse", "--show-toplevel")
    if rc is None:
        return "git not found"
    if rc != 0:
        return "not a git work tree"
    # git resolves symlinks in --show-toplevel (/tmp is /private/tmp on macOS); resolve the files the same way.
    inside, outside = {}, []
    for f in files:
        p = os.path.relpath(os.path.realpath(f), top)
        name = os.path.relpath(f, board_dir)
        if p == os.pardir or p.startswith(os.pardir + os.sep):
            outside.append(name)
        else:
            inside[p] = name
    note = "; outside this work tree: %s" % ", ".join(outside) if outside else ""
    tracked = [p for p in inside if git(top, "ls-files", "--error-unmatch", "--", p)[0] == 0]
    if not tracked:
        first = next(iter(inside.values()), outside[0] if outside else "the board")
        return "not tracked (repo %s does not track %s)%s" % (top, first, note)
    _, rev = git(top, "rev-parse", "--short=12", "HEAD")
    _, st = git(top, "status", "--porcelain", "--untracked-files=all", "--", *inside)
    dirty = []
    for ln in st.splitlines():
        if len(ln) <= 3:
            continue
        p = ln[3:].split(" -> ")[-1].strip('"')  # work-tree relative; a rename prints old -> new
        dirty.append(inside.get(p, p) + (" (untracked)" if ln.startswith("??") else " (modified)"))
    if dirty:
        return "%s DIRTY: %s; this set is from the working copy, not %s%s" % (rev, ", ".join(dirty), rev, note)
    return "%s clean%s" % (rev, note)


def review_counts(review, sheets, pcb, settings, no_pin_header=False):
    """Counts from review/, each stamped STALE when a file it depends on is newer: ERC on the sheets and project
    settings, DRC on the board, the sheets (parity) and settings, the pin diff on the sheets and review/board.net
    (the pin header is not known here)."""
    netlist = os.path.join(review, "board.net")
    deps = {"erc": sheets + settings, "drc": [pcb] + sheets + settings, "pin": sheets + [netlist]}

    def stamp(path, sources):
        t = os.path.getmtime(path)
        when = datetime.datetime.fromtimestamp(t).isoformat(timespec="seconds")
        newer = [os.path.relpath(s, os.path.dirname(review)) for s in sources
                 if os.path.exists(s) and os.path.getmtime(s) > t]
        return "%s, %s%s" % (os.path.basename(path), when,
                             ", STALE: older than %s" % ", ".join(newer) if newer else "")

    def sev(rows):
        c = Counter(v.get("severity", "?") if isinstance(v, dict) else "?" for v in rows)
        order = ["error", "warning", "exclusion"] + sorted(k for k in c if k not in ("error", "warning", "exclusion"))
        return " ".join("%s=%d" % (k, c[k]) for k in order if c[k]) or "clean"

    lines = []
    p = os.path.join(review, "erc.json")
    try:
        d = json.load(open(p))
        rows = [v for s in d.get("sheets", []) for v in s.get("violations", [])]
        lines.append("  erc:          %s  (%s)" % (sev(rows), stamp(p, deps["erc"])))
    except FileNotFoundError:
        lines.append("  erc:          not run (no %s)" % p)
    except (OSError, ValueError, AttributeError, TypeError) as e:
        lines.append("  erc:          unreadable %s: %s" % (p, e))
    for name in ("drc.json", "drc_refilled.json"):
        p = os.path.join(review, name)
        label = "drc:" if name == "drc.json" else "drc refilled:"
        try:
            d = json.load(open(p))
            rows = [v for k in ("violations", "unconnected_items", "schematic_parity") for v in d.get(k, [])]
            lines.append("  %-13s %s, unconnected=%d, parity=%d  (%s)"
                         % (label, sev(rows), len(d.get("unconnected_items", [])),
                            len(d.get("schematic_parity", [])), stamp(p, deps["drc"])))
        except FileNotFoundError:
            lines.append("  %-13s not run (no %s)" % (label, p))
        except (OSError, ValueError, AttributeError, TypeError) as e:
            lines.append("  %-13s unreadable %s: %s" % (label, p, e))
    p = os.path.join(review, "pin_diff.txt")
    if no_pin_header and not os.path.exists(p):
        lines.append("  pin_diff:     not applicable (--no-pin-header)")
        return lines
    try:
        m = None
        for line in open(p, errors="replace"):
            m = re.match(r"errors=\d+ warnings=\d+ info=\d+", line) or m
        lines.append("  pin_diff:     %s  (%s)" % (m.group(0) if m else "no summary line", stamp(p, deps["pin"])))
    except FileNotFoundError:
        lines.append("  pin_diff:     not run (no %s)" % p)
    except OSError as e:
        lines.append("  pin_diff:     unreadable %s: %s" % (p, e))
    return lines


def sheet_tree(root, project_dir):
    """(sheets found, sheets referenced but missing): the root sheet and every sheet it references, recursively.
    A (property "Sheetfile" ...) path ("Sheet file" in older files) is taken relative to the sheet that holds it,
    else relative to the project directory."""
    found, missing, todo = [], [], [os.path.abspath(root)]
    prop = re.compile(r'\(property\s+"Sheet ?file"\s+"((?:[^"\\]|\\.)*)"')
    while todo:
        s = todo.pop(0)
        if s in found:
            continue
        found.append(s)
        try:
            text = open(s, errors="replace").read()
        except OSError:
            continue
        for ref in prop.findall(text):
            ref = ref.replace("\\\\", "\\").replace('\\"', '"')
            cands = [os.path.normpath(os.path.join(os.path.dirname(s), ref)),
                     os.path.normpath(os.path.join(project_dir, ref))]
            hit = next((c for c in cands if os.path.isfile(c)), None)
            if hit:
                todo.append(hit)
            elif cands[0] not in missing:
                missing.append(cands[0])
    return found, missing


# ---------------------------------------------------------------- gate
# review/gate.json holds one entry per check (erc, drc, pin_diff): when it ran, the kicad-cli flags, its counts and
# the sha256 of every input it depends on, keyed by path relative to the board directory (absolute when outside it).
GATE = "gate.json"
GATES = ("erc", "drc", "pin_diff")


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def file_hash(p):
    return sha256(p) if os.path.isfile(p) else None


def key_of(path, board_dir):
    a = os.path.abspath(path)
    r = os.path.relpath(a, os.path.abspath(board_dir))
    return a if r == os.pardir or r.startswith(os.pardir + os.sep) else r


def path_of(key, board_dir):
    return key if os.path.isabs(key) else os.path.join(board_dir, key)


def gate_inputs(kind, board_dir, stem, sch=None, header=None, netlist=None):
    """OrderedDict key -> sha256 (None for a missing file) of the inputs a check depends on. kind "sheets" is the
    sheet tree alone (what the netlist export is tied to)."""
    sch = sch or os.path.join(board_dir, stem + ".kicad_sch")
    sheets, lost = sheet_tree(sch, board_dir)
    pro, pcb, dru = (os.path.join(board_dir, stem + e) for e in (".kicad_pro", ".kicad_pcb", ".kicad_dru"))
    if kind == "erc":
        files = sheets + lost + [pro]
    elif kind == "drc":
        files = [pcb] + sheets + lost + [pro, dru]
    elif kind == "sheets":
        files = sheets + lost
    else:
        files = sheets + lost + [header, netlist]
    out = OrderedDict()
    for f in files:
        out[key_of(f, board_dir)] = file_hash(f)
    return out


def load_gate(review):
    p = os.path.join(review, GATE)
    try:
        g = json.load(open(p))
    except FileNotFoundError:
        return {}
    if not isinstance(g, dict):
        raise ValueError("%s is not a JSON object" % p)
    return g


def save_gate(review, g):
    os.makedirs(review, exist_ok=True)
    p = os.path.join(review, GATE)
    with open(p + ".tmp", "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")
    os.replace(p + ".tmp", p)
    return p


def report_problem(mode, d, checked):
    """None when d has the shape of a kicad-cli 10 report on the file `checked`, else what is wrong. Real reports
    always carry `source` (the checked file's name) and their arrays, empty ones included."""
    if not isinstance(d, dict):
        return "not a JSON object"
    src = d.get("source")
    if not isinstance(src, str) or os.path.basename(src) != os.path.basename(checked):
        return "its source is %r, not %s" % (src, os.path.basename(checked))
    if mode == "erc":
        if not isinstance(d.get("sheets"), list):
            return "no sheets list"
        arrays = []
        for i, s in enumerate(d["sheets"]):
            if not isinstance(s, dict) or not isinstance(s.get("violations"), list):
                return "sheets[%d] has no violations list" % i
            arrays.append(("sheets[%d].violations" % i, s["violations"]))
    else:
        arrays = []
        for k in ("violations", "unconnected_items", "schematic_parity"):
            v = d.get(k)
            if not isinstance(v, list):
                return "no %s list" % k
            arrays.append((k, v))
    for k, rows in arrays:
        for v in rows:
            if not isinstance(v, dict) or not isinstance(v.get("severity"), str):
                return "an item in %s has no severity" % k
    return None


def read_report(mode, path, checked):
    """(report, None) or (None, why it cannot be recorded)."""
    try:
        d = json.load(open(path))
    except FileNotFoundError:
        return None, "no %s" % path
    except (OSError, ValueError) as e:
        return None, "%s unreadable: %s" % (path, e)
    why = report_problem(mode, d, checked)
    return (None, "%s is not a kicad-cli %s report: %s" % (path, mode.upper(), why)) if why else (d, None)


# KiCad 10 default rule severities, for the `downgraded checks:` line. DRC: the 62 rules of aquila's core.kicad_pro
# (written by KiCad 10.0.5 at its defaults; its ignore set equals the ignored_checks kicad-cli 10.0.5 reports for a
# project with no rule_severities). ERC: the 44 rules of the project templates KiCad 10.0.5 ships (all 19 agree),
# with simulation_model_issue at ignore as kicad-cli 10.0.5 reports it. A rule not listed has no known default.
def _sev_table(**groups):
    return dict((rule, sev) for sev, rules in groups.items() for rule in rules.split())


DEFAULTS = {
    "drc": _sev_table(
        error="annular_width clearance copper_edge_clearance courtyards_overlap creepage diff_pair_gap_out_of_range "
              "diff_pair_uncoupled_length_too_long drill_out_of_range footprint hole_clearance hole_to_hole "
              "invalid_outline item_on_disabled_layer items_not_allowed length_out_of_range malformed_courtyard "
              "microvia_drill_out_of_range npth_inside_courtyard pth_inside_courtyard shorting_items "
              "skew_out_of_range solder_mask_bridge starved_thermal text_on_edge_cuts through_hole_pad_without_hole "
              "too_many_vias track_angle track_on_post_machined_layer track_segment_length track_width "
              "tracks_crossing unconnected_items unresolved_variable zones_intersect",
        warning="connection_width copper_sliver duplicate_footprints extra_footprint footprint_symbol_field_mismatch "
                "footprint_symbol_mismatch holes_co_located isolated_copper lib_footprint_issues "
                "lib_footprint_mismatch mirrored_text_on_front_layer missing_footprint missing_tuning_profile "
                "net_conflict nonmirrored_text_on_back_layer padstack silk_edge_clearance silk_over_copper "
                "silk_overlap text_height text_thickness track_dangling via_dangling",
        ignore="footprint_filters_mismatch footprint_type_mismatch missing_courtyard track_not_centered_on_via "
               "tuning_profile_track_geometries"),
    "erc": _sev_table(
        error="bus_definition_conflict bus_entry_needed bus_label_syntax bus_to_bus_conflict bus_to_net_conflict "
              "conflicting_netclasses different_unit_footprint different_unit_net duplicate_reference "
              "duplicate_sheet_names extra_units hier_label_mismatch label_dangling missing_power_pin "
              "pin_not_connected pin_not_driven power_pin_not_driven unannotated unit_value_mismatch "
              "unresolved_variable wire_dangling",
        warning="endpoint_off_grid footprint_link_issues global_label_dangling label_multiple_wires lib_symbol_issues "
                "lib_symbol_mismatch missing_bidi_pin missing_input_pin missing_unit multiple_net_names "
                "net_not_bus_member no_connect_connected no_connect_dangling pin_to_pin same_local_global_label "
                "similar_label_and_power similar_labels similar_power unconnected_wire_endpoint",
        ignore="footprint_filter four_way_junction simulation_model_issue single_global_label"),
}
# The critical rules and the lowest severity each may have before the gate blocks: error for the electrical rules;
# warning for the schematic-parity family (KiCad's default, and every parity item blocks at any severity) and for
# pin_to_pin (KiCad uses it only to switch pin conflicts on or off; the pin map decides warning or error).
CRITICAL = {
    "drc": dict([(r, "error") for r in ("unconnected_items", "clearance", "shorting_items", "tracks_crossing",
                                        "copper_edge_clearance", "hole_clearance")] +
                [(r, "warning") for r in ("duplicate_footprints", "extra_footprint", "missing_footprint",
                                          "net_conflict", "footprint_symbol_mismatch",
                                          "footprint_symbol_field_mismatch")]),
    "erc": {"pin_not_connected": "error", "power_pin_not_driven": "error", "pin_to_pin": "warning"},
}
RANK = {"ignore": 0, "info": 1, "warning": 2, "error": 3}


def erc_counts(d):
    c = Counter(v.get("severity", "?") for s in d.get("sheets", []) for v in s.get("violations", []))
    return {"errors": c["error"], "warnings": c["warning"], "excluded": c["exclusion"]}


def drc_counts(d):
    """The three DRC arrays counted apart; items KiCad reports as excluded are not counted."""
    def live(cat):
        return [v for v in d.get(cat, []) if isinstance(v, dict) and v.get("severity") != "exclusion"]
    v = live("violations")
    excluded = sum(1 for cat in ("violations", "unconnected_items", "schematic_parity")
                   for x in d.get(cat, []) if isinstance(x, dict) and x.get("severity") == "exclusion")
    return {"violations": len(v), "errors": sum(1 for x in v if x.get("severity") == "error"),
            "unconnected": len(live("unconnected_items")), "parity": len(live("schematic_parity")),
            "excluded": excluded}


def erc_text(c):
    return "errors=%d warnings=%d excluded=%d" % (c["errors"], c["warnings"], c["excluded"])


def drc_text(c):
    return "violations=%d (errors=%d) unconnected=%d parity=%d" % (
        c["violations"], c["errors"], c["unconnected"], c["parity"])


def drc_blocks(c):
    out = []
    for k, word in (("errors", "error"), ("unconnected", "unconnected"), ("parity", "parity")):
        if c[k]:
            out.append("%d %s" % (c[k], word if k != "errors" else "error" + ("s" if c[k] != 1 else "")))
    return out


def disabled_checks(mode, board_dir, stem, report=None):
    """(names, exclusions, notes) for erc or drc: rules that do not run, and the exclusions recorded in the
    .kicad_pro. Names come from the report's ignored_checks (what kicad-cli skipped, KiCad's defaults included),
    the .kicad_pro rule_severities set to ignore, and for DRC the custom .kicad_dru rules with (severity ignore)."""
    pro = os.path.join(board_dir, stem + ".kicad_pro")
    names = []
    sec, notes = pro_section(mode, board_dir, stem)
    rs = (sec or {}).get("rule_severities") or {}
    pro_ignored = [k for k, v in rs.items() if v == "ignore"] if isinstance(rs, dict) else []
    excl = (sec or {}).get("erc_exclusions" if mode == "erc" else "drc_exclusions")
    exclusions = len(excl) if isinstance(excl, list) else 0
    rep = None
    if isinstance(report, dict) and isinstance(report.get("ignored_checks"), list):
        rep = [c.get("key", "?") for c in report["ignored_checks"] if isinstance(c, dict)]
    for n in (rep or []) + pro_ignored:
        if n not in names:
            names.append(n)
    if rep is not None:
        only_rep = [n for n in rep if n not in pro_ignored]
        only_pro = [n for n in pro_ignored if n not in rep]
        if only_rep:
            notes.append("ignored in the report but not set to ignore in %s (KiCad defaults): %s"
                         % (os.path.basename(pro), ", ".join(only_rep)))
        if only_pro:
            notes.append("set to ignore in %s but not in the report's ignored_checks: %s"
                         % (os.path.basename(pro), ", ".join(only_pro)))
    else:
        notes.append("no report read: names from %s only" % os.path.basename(pro))
    if mode == "drc":
        rules, err = dru_severities(board_dir, stem)
        names += ['dru:"%s"' % r for r, s in rules if s == "ignore"]
        if err:
            notes.append(err)
    return names, exclusions, notes


def pro_section(mode, board_dir, stem):
    """(the .kicad_pro's erc or board.design_settings section or None, notes)."""
    pro = os.path.join(board_dir, stem + ".kicad_pro")
    where = "erc" if mode == "erc" else "board.design_settings"
    try:
        d = json.load(open(pro))
        sec = d.get("erc") if mode == "erc" else (d.get("board") or {}).get("design_settings")
        if isinstance(sec, dict):
            return sec, []
        return None, ["%s has no %s section: KiCad's built-in severities apply" % (os.path.basename(pro), where)]
    except FileNotFoundError:
        return None, ["no %s" % os.path.basename(pro)]
    except (OSError, ValueError, AttributeError) as e:
        return None, ["%s unreadable: %s" % (os.path.basename(pro), e)]


def dru_severities(board_dir, stem):
    """([(rule name, severity)] for every (severity ...) in the .kicad_dru, a note when it cannot be read)."""
    dru = os.path.join(board_dir, stem + ".kicad_dru")
    out, rule = [], None
    try:
        for tok in re.finditer(r'\(rule\s+"((?:[^"\\]|\\.)*)"|\(rule\s+([^\s()"]+)|\(severity\s+([^\s()]+)\s*\)',
                               open(dru, errors="replace").read()):
            if tok.group(3) is None:
                rule = tok.group(1) if tok.group(1) is not None else tok.group(2)
            else:
                out.append((rule or "?", tok.group(3)))
    except FileNotFoundError:
        pass
    except OSError as e:
        return out, "%s unreadable: %s" % (os.path.basename(dru), e)
    return out, None


def severity_changes(mode, board_dir, stem):
    """(downgraded, critical): the .kicad_pro rules below KiCad 10's default severity and, for DRC, the .kicad_dru
    rules at a severity other than error or ignore (printed, never blocking); and the critical rules below their
    floor, which block the gate. A rule missing from rule_severities runs at its default."""
    sec, _ = pro_section(mode, board_dir, stem)
    rs = (sec or {}).get("rule_severities")
    rs = rs if isinstance(rs, dict) else {}
    defaults, floors = DEFAULTS[mode], CRITICAL[mode]
    down, crit = [], []
    for rule in sorted(rs):
        sev = rs[rule] if isinstance(rs[rule], str) else repr(rs[rule])
        rank = RANK.get(sev, -1)
        if rule in floors and rank < RANK[floors[rule]]:
            crit.append("%s=%s" % (rule, sev))
            down.append("%s=%s (default %s, critical: blocks)" % (rule, sev, defaults.get(rule, floors[rule])))
        elif rule in defaults and rank < RANK[defaults[rule]]:
            down.append("%s=%s (default %s)" % (rule, sev, defaults[rule]))
    if mode == "drc":
        down += ['dru:"%s"=%s (custom rule, not blocking)' % (r, s) for r, s in dru_severities(board_dir, stem)[0]
                 if s not in ("error", "ignore")]
    return down, crit


def disabled_lines(mode, board_dir, stem, report=None, prefix=""):
    names, excl, notes = disabled_checks(mode, board_dir, stem, report)
    down, _ = severity_changes(mode, board_dir, stem)
    lines = ["%sdisabled checks: %s" % (prefix, ", ".join(names) or "none"),
             "%sdowngraded checks: %s" % (prefix, ", ".join(down) or "none"), "%sexclusions: %d" % (prefix, excl)]
    return lines + ["%s  note: %s" % (prefix, n) for n in notes]


COMPLETED = (0, 5)  # kicad-cli exit codes of a check that ran to the end: clean, violations reported
START = ".start.json"  # <review>/<mode>.start.json: the input hashes fabset.py start kept for this run


def check_inputs(mode, file):
    board_dir = os.path.dirname(os.path.abspath(file))
    stem = os.path.splitext(os.path.basename(file))[0]
    return gate_inputs(mode, board_dir, stem, sch=file if mode == "erc" else None)


def drop_entry(mode, review):
    """Remove the check's gate.json entry; a gate.json that cannot be read is started anew."""
    try:
        g = load_gate(review)
    except (OSError, ValueError) as e:
        print("gate: %s; starting a new one" % e)
        g = {}
    g.pop(mode, None)
    save_gate(review, g)
    return g


def report_files(mode, review):
    return [os.path.join(review, n) for n in (["erc.json"] if mode == "erc" else ["drc.json", "drc_refilled.json"])]


def cmd_start(mode, file, review):
    """erc_drc.sh, before the first kicad-cli call: drop the entry and the report files, keep the input hashes."""
    drop_entry(mode, review)
    for f in report_files(mode, review):
        if os.path.exists(f):
            os.remove(f)
    with open(os.path.join(review, mode + START), "w") as f:
        json.dump({"file": os.path.abspath(file), "inputs": check_inputs(mode, file)}, f)
    return 0


def cmd_record(mode, file, review, flags, rcs):
    board_dir = os.path.dirname(os.path.abspath(file))
    stem = os.path.splitext(os.path.basename(file))[0]
    # The old entry goes before anything is parsed, so no failure below can leave an earlier pass in place.
    g = drop_entry(mode, review)
    state = os.path.join(review, mode + START)
    try:
        start = json.load(open(state))
        os.remove(state)  # one start, one record
        if not isinstance(start, dict) or start.get("file") != os.path.abspath(file):
            raise ValueError("it is for another file")
    except (OSError, ValueError) as e:
        print("gate: %s not recorded (no start state for this run, %s: %s): run erc_drc.sh %s; it reads `not run`"
              % (mode, state, e, mode))
        return 1
    bad_rc = [c for c in rcs if c not in COMPLETED]
    if bad_rc or not rcs:
        print("gate: %s not recorded (kicad-cli exit %s: the check did not complete); it reads `not run`"
              % (mode, ",".join(str(c) for c in bad_rc) or "unknown"))
        return 1
    ch = stale(start.get("inputs") or {}, check_inputs(mode, file))
    if ch:
        print("gate: %s not recorded (changed during the run: %s); save, then run erc_drc.sh %s again; it reads "
              "`not run`" % (mode, ", ".join(ch), mode))
        return 1
    report = os.path.join(review, mode + ".json")
    d, why = read_report(mode, report, file)
    refilled, rpath = None, os.path.join(review, "drc_refilled.json")
    if d is not None and mode == "drc" and os.path.exists(rpath):
        r, why = read_report("drc", rpath, file)
        refilled = drc_counts(r) if r is not None else None
    if why or d is None:
        print("gate: %s not recorded (%s); it reads `not run`" % (mode, why))
        return 1
    rec: "OrderedDict[str, object]" = OrderedDict([("board", stem), ("recorded", now()), ("kicad", d.get("kicad_version", "?")),
                       ("flags", flags), ("report", key_of(report, board_dir))])
    if mode == "erc":
        c = erc_counts(d)
        rec["counts"] = c
        print("erc: %s" % erc_text(c))
        blocks = ["%d error%s" % (c["errors"], "s" if c["errors"] != 1 else "")] if c["errors"] else []
        rec["inputs"] = start["inputs"]
    else:
        saved = drc_counts(d)
        rec["counts"] = OrderedDict([("saved", saved), ("refilled", refilled)])
        print("saved fills: %s" % drc_text(saved))
        print("refilled:    %s" % (drc_text(refilled) if refilled else "no report at %s" % rpath))
        blocks = ["%s (saved fills)" % b for b in drc_blocks(saved)] + (
            ["%s (refilled)" % b for b in drc_blocks(refilled)] if refilled else ["no refilled run"])
        rec["inputs"] = start["inputs"]
    names, excl, _ = disabled_checks(mode, board_dir, stem, d)
    rec["disabled"], rec["exclusions"] = names, excl
    rec["downgraded"], rec["critical"] = severity_changes(mode, board_dir, stem)
    if rec["critical"]:
        blocks.append("critical rule below its floor: %s" % ", ".join(rec["critical"]))
    for line in disabled_lines(mode, board_dir, stem, d):
        print(line)
    g[mode] = rec
    p = save_gate(review, g)
    print("gate: %s %s, recorded in %s" % (mode, "BLOCKS (%s)" % ", ".join(blocks) if blocks else "pass", p))
    return 5 if blocks else 0


def record_pin(board_dir, stem, header, netlist, counts):
    """pin_diff.py --record: the pin_diff entry of <board_dir>/review/gate.json."""
    review = os.path.join(board_dir, "review")
    try:
        g = load_gate(review)
    except ValueError:
        g = {}
    g["pin_diff"] = OrderedDict([
        ("board", stem), ("recorded", now()), ("header", key_of(header, board_dir)),
        ("netlist", key_of(netlist, board_dir)), ("counts", counts),
        ("inputs", gate_inputs("pin", board_dir, stem, header=header, netlist=netlist))])
    return save_gate(review, g)


def pin_netlist_problem(board_dir, stem):
    """pin_diff.py --record, after recording: None when the pin-diff gate will accept the netlist the pin diff read,
    else what is wrong with it (netlist_problem)."""
    try:
        g = load_gate(os.path.join(board_dir, "review"))
        return netlist_problem(g, g["pin_diff"], board_dir, stem, os.path.join(board_dir, stem + ".kicad_sch"))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        return "gate.json unreadable after the record (%s)" % e


def cmd_netlist(phase, sch, state):
    """export_review.sh sch, around the netlist export. start: drop gate.json's netlist entry, write the sheet
    hashes to `state`. finish: record review/board.net's sha256 with the sheet hashes, if they did not change."""
    board_dir = os.path.dirname(os.path.abspath(sch))
    stem = os.path.splitext(os.path.basename(sch))[0]
    review = os.path.join(board_dir, "review")
    try:
        g = load_gate(review)
    except (OSError, ValueError) as e:
        print("gate: %s; starting a new one" % e)
        g = {}
    sheets = gate_inputs("sheets", board_dir, stem, sch=sch)
    if phase == "start":
        g.pop("netlist", None)
        save_gate(review, g)
        with open(state, "w") as f:
            json.dump(sheets, f)
        return 0
    netlist = os.path.join(review, "board.net")
    try:
        before = json.load(open(state))
    except (OSError, ValueError) as e:
        print("gate: netlist not recorded (no sheet hashes from before the export: %s)" % e)
        return 1
    ch = stale(before, sheets)
    if ch:
        print("gate: netlist not recorded: the sheets changed during the export (%s); save them and re-run "
              "export_review.sh sch" % ", ".join(ch))
        return 1
    if not os.path.isfile(netlist):
        print("gate: netlist not recorded: no %s" % netlist)
        return 1
    g["netlist"] = OrderedDict([("board", stem), ("recorded", now()), ("netlist", key_of(netlist, board_dir)),
                                ("sha256", sha256(netlist)), ("sheets", sheets)])
    print("gate: netlist recorded in %s (tied to %d sheet%s)"
          % (save_gate(review, g), len(sheets), "s" if len(sheets) != 1 else ""))
    return 0


def netlist_problem(g, rec, board_dir, stem, sch):
    """None when review/board.net is the netlist export_review.sh recorded from the current sheets and the one the
    pin diff read, else what differs."""
    nl = g.get("netlist")
    if not isinstance(nl, dict):
        return "no netlist export recorded"
    path = path_of(rec["netlist"], board_dir)
    cur = file_hash(path)
    if nl.get("sha256") != cur:
        return "%s is not the netlist export_review.sh recorded" % rec["netlist"]
    if rec["inputs"].get(key_of(path, board_dir)) != nl.get("sha256"):
        return "the pin diff read another netlist than the recorded export"
    ch = stale(nl.get("sheets") or {}, gate_inputs("sheets", board_dir, stem, sch=sch))
    if ch:
        return "netlist exported from older sheets (%s)" % ", ".join(ch)
    return None


def stale(recorded, current):
    """'<file> changed' for every input whose hash differs from the recorded one, or that came or went."""
    out = []
    show_key = lambda k: os.path.basename(k) if os.path.isabs(k) else k
    for k in list(recorded) + [k for k in current if k not in recorded]:
        if k not in current:
            out.append("%s no longer an input" % show_key(k))
        elif k not in recorded:
            out.append("%s added" % show_key(k))
        elif recorded[k] != current[k]:
            out.append("%s %s" % (show_key(k), "missing" if current[k] is None else
                                  "added" if recorded[k] is None else "changed"))
    return out


RERUN_NETLIST = "re-run export_review.sh sch, then pin_diff.py --record"


def gate_status(pcb, sch, no_pin_header):
    """[(name, state, reasons, detail)] for erc, drc, pin_diff against <board>/review/gate.json. state is "pass",
    "not applicable" or "blocked"; reasons is [(text, acceptable)], acceptable meaning --accept may waive it (a
    failing count or a downgraded critical rule recorded on the current inputs)."""
    board_dir = os.path.dirname(os.path.abspath(pcb))
    stem = os.path.splitext(os.path.basename(pcb))[0]
    review = os.path.join(board_dir, "review")
    try:
        g = load_gate(review)
    except (OSError, ValueError) as e:
        return [(n, "blocked", [("gate.json unreadable: %s" % e, False)], "") for n in GATES]
    res = []
    for name in GATES:
        rec = g.get(name)
        if name == "pin_diff" and no_pin_header:
            if name in g:
                res.append((name, "blocked", [("--no-pin-header given, but a pin diff is recorded for this board in "
                                               "review/gate.json, so the flag does not apply: drop it", False)], ""))
            else:
                res.append((name, "not applicable", [], "--no-pin-header: the project has no firmware pin header"))
            continue
        if not isinstance(rec, dict):
            res.append((name, "blocked", [("not run", False)], "no entry in %s" % os.path.join(review, GATE)))
            continue
        why = []  # (text, acceptable)
        try:
            if name == "erc":
                cur = gate_inputs("erc", board_dir, stem, sch=sch)
            elif name == "drc":
                cur = gate_inputs("drc", board_dir, stem, sch=sch)
            else:
                cur = gate_inputs("pin", board_dir, stem, sch=sch, header=path_of(rec["header"], board_dir),
                                  netlist=path_of(rec["netlist"], board_dir))
            ch = stale(rec["inputs"], cur)
            if ch:
                why.append(("stale: " + ", ".join(ch), False))
            c = rec["counts"]
            if name == "erc":
                detail = erc_text(c)
                if c["errors"]:
                    why.append(("%d error%s" % (c["errors"], "s" if c["errors"] != 1 else ""), True))
            elif name == "drc":
                if "--schematic-parity" not in (rec.get("flags") or "").split():
                    why.append(("run without --schematic-parity", False))
                detail = "saved fills %s; refilled %s" % (drc_text(c["saved"]),
                                                          drc_text(c["refilled"]) if c["refilled"] else "not run")
                why += [("%s (saved fills)" % b, True) for b in drc_blocks(c["saved"])]
                if c["refilled"]:
                    why += [("%s (refilled)" % b, True) for b in drc_blocks(c["refilled"])]
                else:
                    why.append(("refilled run missing", False))
            else:
                detail = "errors=%d warnings=%d info=%d" % (c["error"], c["warning"], c["info"])
                bad_net = netlist_problem(g, rec, board_dir, stem, sch)
                if bad_net:
                    why.append(("stale netlist: %s; %s" % (bad_net, RERUN_NETLIST), False))
                if c["error"]:
                    why.append(("%d error%s" % (c["error"], "s" if c["error"] != 1 else ""), True))
            if name != "pin_diff" and rec["critical"]:
                why.append(("critical rule below its floor: %s" % ", ".join(rec["critical"]), True))
        except (KeyError, TypeError, AttributeError) as e:
            res.append((name, "blocked", [("unreadable entry in gate.json (%s): re-run the check" % e, False)], ""))
            continue
        detail += " (recorded %s, kicad %s)" % (rec.get("recorded", "?"), rec.get("kicad", "-")) \
            if name != "pin_diff" else " (recorded %s, header %s)" % (rec.get("recorded", "?"), rec["header"])
        res.append((name, "blocked" if why else "pass", why, detail))
    return res


def gate_lines(res, accept, no_pin_header):
    """(lines, verdict): verdict "pass", "accepted" (every block is one --accept waives, and it was given) or
    "blocked"."""
    blocked = [r for r in res if r[1] == "blocked"]
    hard = ["%s: %s" % (r[0], t) for r in blocked for t, ok in r[2] if not ok]
    na = " (pin diff not applicable: --no-pin-header)" if any(r[1] == "not applicable" for r in res) else ""
    if not blocked:
        verdict, head = "pass", "pass" + na
    elif accept is not None and not hard:
        verdict, head = "accepted", "ACCEPTED - %s%s" % (accept, na)
    else:
        verdict, head = "blocked", "BLOCKED" + (" (--accept given, but it cannot waive every block)"
                                                if accept is not None else "")
    lines = ["gates:        %s" % head]
    flags = (["--no-pin-header"] if no_pin_header else []) + (['--accept "%s"' % accept] if accept is not None else [])
    lines.append("gate flags:   %s" % (" ".join(flags) or "none"))
    if accept is not None and not blocked:
        lines.append("  (--accept given but not needed: every gate passed)")
    for name, state, reasons, detail in res:
        text = "; ".join(t if ok else t + " [cannot be accepted]" for t, ok in reasons)
        if state == "blocked":
            text = ('WAIVED (accepted: "%s"): ' % accept if verdict == "accepted" else "BLOCKED: ") + text
        else:
            text = state
        lines.append("  %-13s %s%s" % (name + ":", text, ": " + detail if detail else ""))
    if accept is not None and hard:
        lines.append("--accept cannot waive: %s" % "; ".join(hard))
    return lines, verdict


def cmd_gate(pcb, sch, no_pin_header, accept):
    lines, verdict = gate_lines(gate_status(pcb, sch, no_pin_header), accept, no_pin_header)
    print("\n".join(lines))
    return 4 if verdict == "blocked" else 0


def cmd_manifest(out, pcb, sch, kicad, copper, checks, no_pin_header=False, accept=None, fail_blocked=False):
    board_dir = os.path.dirname(os.path.abspath(pcb))
    stem = os.path.splitext(os.path.basename(pcb))[0]
    sheets, lost = sheet_tree(sch, board_dir)
    extra = [os.path.join(board_dir, stem + ext) for ext in (".kicad_pro", ".kicad_dru")]
    sources = [os.path.abspath(pcb)] + sheets + lost + extra
    uploads = [os.path.join(out, f) for f in ("gerbers.zip", "bom.csv", "cpl.csv")]

    lines = ["%s fab set" % stem,
             "written:      %s by fab_export.sh" % datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
             "board:        %s" % os.path.abspath(pcb),
             "kicad-cli:    %s" % kicad,
             "git:          %s" % git_state(board_dir, [s for s in sources if os.path.exists(s)]),
             "fab checks:   %s" % ("pass" if checks == "pass" else "FAIL: do not upload this set")]
    glines, verdict = gate_lines(gate_status(pcb, sch, no_pin_header), accept, no_pin_header)
    lines += glines
    review = os.path.join(board_dir, "review")
    for mode in ("erc", "drc"):
        try:
            rep = json.load(open(os.path.join(review, mode + ".json")))
        except (OSError, ValueError):
            rep = None
        lines += disabled_lines(mode, board_dir, stem, rep, prefix="%s " % mode)
    lines.append("sha256, sources:")
    for s in sources:
        rel = os.path.relpath(s, board_dir)
        lines.append("  %s  %s" % (sha256(s) if os.path.exists(s) else "%-64s" % "none", rel))
    lines.append("sha256, uploads:")
    for u in uploads:
        lines.append("  %s  %s" % (sha256(u) if os.path.exists(u) else "%-64s" % "none", os.path.basename(u)))
    cu = [c for c in copper.split(",") if c]
    lines.append("copper layers: %d (%s)" % (len(cu), ", ".join(cu)))
    drl = os.path.join(out, "gerber", stem + ".drl")
    try:
        tools, units = drill_tools(drl)
        lines.append("drill tools (gerber/%s):" % os.path.basename(drl))
        for t, (dia, holes, slots, func) in tools.items():
            n = " + ".join(x for x in ("%d" % holes if holes else "", "%d slots" % slots if slots else "") if x)
            lines.append("  %-4s %6.3f %s  x%-9s %s" % (t, dia, units, n or "0", func))
        lines.append("  holes: %d, slots: %d" % (sum(v[1] for v in tools.values()), sum(v[2] for v in tools.values())))
    except OSError as e:
        lines.append("drill tools: unreadable %s" % e)
    lines.append("review (%s, as last written there; STALE here is by file time, the gate lines above decide):" % review)
    lines += review_counts(review, sheets, os.path.abspath(pcb), extra, no_pin_header)
    dst = os.path.join(out, "MANIFEST.txt")
    with open(dst, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("manifest: %s" % dst)
    if verdict == "blocked" and fail_blocked:
        print("manifest: the gates no longer pass (an input changed since the gate check); this set is not orderable")
        return 4
    return 0


# ---------------------------------------------------------------- diff
def strip_stamps(name, text):
    """(kept lines, stripped count): lines that only carry a timestamp or a G04 comment are dropped."""
    kept, n = [], 0
    for line in text.splitlines():
        s = line.strip()
        if name.endswith(".drl"):
            drop = s.startswith("; DRILL file") or "TF.CreationDate" in s
        elif name.endswith(".gbrjob"):
            drop = '"CreationDate"' in s
        else:
            drop = s.startswith("G04") or s.startswith("%TF.CreationDate")
        if drop:
            n += 1
        else:
            kept.append(line)
    return kept, n


RANGE = re.compile(r"^([A-Z]+)([0-9]+)-([A-Z]*)([0-9]+)$")


def by_designator(path, bom):
    """(designator -> row dict, range tokens). A BOM row is split into its designators, a range (C10-C15, as an
    older export wrote them) into its members, so a set that only changed its designator format compares equal
    by content and the format change is reported on its own."""
    out, ranges = OrderedDict(), []
    for r in csv.DictReader(open(path, newline="")):
        refs = [t.strip() for t in (r.get("Designator") or "").split(",") if t.strip()] if bom else [r.get("Designator", "")]
        for ref in refs:
            m = RANGE.match(ref) if bom else None
            if m and (not m.group(3) or m.group(3) == m.group(1)):
                ranges.append(ref)
                members = ["%s%d" % (m.group(1), i) for i in range(int(m.group(2)), int(m.group(4)) + 1)]
            else:
                members = [ref]
            for x in members:
                out[x] = {k: v for k, v in r.items() if k not in ("Designator", "Quantity")}
    return out, ranges


def diff_rows(a, b):
    notes = []
    gone, new = [k for k in a if k not in b], [k for k in b if k not in a]
    if gone:
        notes.append("removed %s" % show(gone))
    if new:
        notes.append("added %s" % show(new))
    for k in sorted(set(a) & set(b), key=natural):
        ch = ["%s %s -> %s" % (f, a[k].get(f, ""), b[k].get(f, "")) for f in sorted(set(a[k]) | set(b[k]))
              if a[k].get(f, "") != b[k].get(f, "")]
        if ch:
            notes.append("%s: %s" % (k, "; ".join(ch)))
    return notes


def cmd_diff(old, new):
    for d in (old, new):
        if not os.path.isdir(os.path.join(d, "gerber")) and not os.path.isfile(os.path.join(d, "bom.csv")):
            sys.exit("%s is not a fab set (no gerber/ and no bom.csv)" % d)
    print("fab_diff: %s -> %s" % (old, new))
    differ, same, stripped = [], 0, 0
    for name in ("bom.csv", "cpl.csv"):
        pa, pb = os.path.join(old, name), os.path.join(new, name)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            if os.path.exists(pa) or os.path.exists(pb):
                differ.append(name)
                print("%-34s only in %s" % (name, old if os.path.exists(pa) else new))
            continue
        try:
            (ra, xa), (rb, xb) = by_designator(pa, name == "bom.csv"), by_designator(pb, name == "bom.csv")
        except (OSError, csv.Error) as e:
            sys.exit("cannot read %s: %s" % (name, e))
        notes = diff_rows(ra, rb)
        if xa != xb:
            notes.append("designator ranges (JLC does not expand them) %s -> %s" % (show(xa), show(xb)))
        if notes:
            differ.append(name)
            print("%-34s %d difference(s): %s" % (name, len(notes), " | ".join(notes)[:1500]))
        else:
            same += 1

    ga, gb = os.path.join(old, "gerber"), os.path.join(new, "gerber")
    fa = set(os.listdir(ga)) if os.path.isdir(ga) else set()
    fb = set(os.listdir(gb)) if os.path.isdir(gb) else set()
    for name in sorted(fa | fb, key=natural):
        if name not in fa or name not in fb:
            differ.append(name)
            print("%-34s only in %s" % (name, old if name in fa else new))
            continue
        try:
            ka, na = strip_stamps(name, open(os.path.join(ga, name), errors="replace").read())
            kb, nb = strip_stamps(name, open(os.path.join(gb, name), errors="replace").read())
        except OSError as e:
            sys.exit("cannot read %s: %s" % (name, e))
        stripped += na + nb
        if ka == kb:
            same += 1
            continue
        differ.append(name)
        ca, cb = Counter(ka), Counter(kb)
        print("%-34s %d line(s) only in old, %d only in new (%d vs %d lines)"
              % (name, sum((ca - cb).values()), sum((cb - ca).values()), len(ka), len(kb)))
        if name.endswith(".drl"):
            # by diameter and hole function, not tool number: KiCad renumbers tools when a diameter comes or goes
            def by_size(path):
                tools, units = drill_tools(path)
                c = Counter()
                for dia, holes, slots, func in tools.values():
                    c["%.3f %s %s" % (dia, units, func)] += holes
                    c["%.3f %s %s, slots" % (dia, units, func)] += slots
                return +c
            sa, sb = by_size(os.path.join(ga, name)), by_size(os.path.join(gb, name))
            for k in sorted(set(sa) | set(sb)):
                if sa.get(k) != sb.get(k):
                    print("  drill %s: %s -> %s" % (k, "x%d" % sa[k] if k in sa else "none",
                                                  "x%d" % sb[k] if k in sb else "none"))

    ma, mb = os.path.join(old, "MANIFEST.txt"), os.path.join(new, "MANIFEST.txt")
    if os.path.exists(ma) and os.path.exists(mb):
        def src(p):
            rows, on = {}, False
            for line in open(p, errors="replace"):
                if line.startswith("sha256, "):
                    on = line.startswith("sha256, sources")
                elif on and line.startswith("  "):
                    h, _, f = line.strip().partition("  ")
                    rows[f.strip()] = h
            return rows
        sa, sb = src(ma), src(mb)
        ch = [f for f in sorted(set(sa) | set(sb)) if sa.get(f) != sb.get(f)]
        # information only: an edit no fab file shows (a note on an unplotted layer) still changes the hash
        print("%-34s %s" % ("sources (MANIFEST.txt sha256)",
                            "differ: %s (information; the outputs above decide)" % ", ".join(ch) if ch else "same"))

    print("same: %d file(s); ignored %d G04-comment and timestamp line(s) (%%TF.CreationDate, drill header date, "
          "job CreationDate)" % (same, stripped))
    if differ:
        print("identical except: %s" % ", ".join(differ))
        return 2
    print("identical except timestamps and G04 comments")
    return 0


# ---------------------------------------------------------------- main
def main():
    ap = Parser(prog="fabset.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=Parser)
    c = sub.add_parser("check", help="file-set checks after fab_export.sh plots")
    c.add_argument("outdir")
    c.add_argument("stem", help="board file name stem, as in <stem>.drl")
    c.add_argument("copper_count", type=int)
    m = sub.add_parser("manifest", help="write <outdir>/MANIFEST.txt")
    m.add_argument("outdir")
    m.add_argument("--pcb", required=True)
    m.add_argument("--sch", required=True)
    m.add_argument("--kicad", required=True, help="kicad-cli version string")
    m.add_argument("--copper", required=True, help="comma-separated copper layers, F.Cu first")
    m.add_argument("--checks", required=True, choices=["pass", "FAIL"])
    m.add_argument("--no-pin-header", action="store_true", help="the project has no firmware pin header")
    m.add_argument("--fail-if-blocked", action="store_true", help="exit 4 when the recomputed gates block "
                   "(fab_export.sh: an input changed during the export)")
    m.add_argument("--accept", metavar="REASON", help="the user accepted the failing counts or "
                   "downgraded critical rules, for this reason")
    d = sub.add_parser("diff", help="compare two fab sets")
    d.add_argument("old")
    d.add_argument("new")
    s0 = sub.add_parser("start", help="before an ERC or DRC run (erc_drc.sh): drop its entry and reports, hash inputs")
    s0.add_argument("mode", choices=["erc", "drc"])
    s0.add_argument("file", help="the .kicad_sch (erc) or .kicad_pcb (drc) to be checked")
    s0.add_argument("review", help="the directory the reports go to")
    r = sub.add_parser("record", help="record an ERC or DRC result in <review_dir>/gate.json (erc_drc.sh)")
    r.add_argument("mode", choices=["erc", "drc"])
    r.add_argument("file", help="the .kicad_sch (erc) or .kicad_pcb (drc) that was checked")
    r.add_argument("review", help="the directory holding erc.json or drc.json and drc_refilled.json")
    r.add_argument("--flags", default="", help="the kicad-cli flags of the run, as one string")
    r.add_argument("--rc", required=True, help="the kicad-cli exit codes of the run, comma-separated (0 and 5 mean "
                   "the check completed)")
    n = sub.add_parser("netlist", help="tie review/board.net to the sheets it was exported from (export_review.sh)")
    n.add_argument("phase", choices=["start", "finish"])
    n.add_argument("sch", help="the root .kicad_sch the netlist is exported from")
    n.add_argument("state", help="a temporary file holding the sheet hashes from before the export")
    t = sub.add_parser("gate", help="the pre-export gate (fab_export.sh): exit 4 when a gate blocks")
    t.add_argument("--pcb", required=True)
    t.add_argument("--sch", required=True)
    t.add_argument("--no-pin-header", action="store_true", help="the project has no firmware pin header")
    t.add_argument("--accept", metavar="REASON", help="the user accepted the failing counts or "
                   "downgraded critical rules, for this reason")
    a = ap.parse_args()
    if getattr(a, "accept", None) is not None and not a.accept.strip():
        sys.exit("--accept needs a reason")
    if a.cmd in ("start", "record"):
        if not os.path.isfile(a.file):
            sys.exit("no such file: %s" % a.file)
        if a.cmd == "start":
            os.makedirs(a.review, exist_ok=True)
            sys.exit(cmd_start(a.mode, a.file, a.review))
        try:
            rcs = [int(c) for c in a.rc.split(",") if c.strip()]
        except ValueError:
            sys.exit("--rc wants comma-separated integers, got %r" % a.rc)
        sys.exit(cmd_record(a.mode, a.file, a.review, a.flags, rcs))
    if a.cmd == "netlist":
        if not os.path.isfile(a.sch):
            sys.exit("no such file: %s" % a.sch)
        sys.exit(cmd_netlist(a.phase, a.sch, a.state))
    if a.cmd == "gate":
        for p in (a.pcb, a.sch):
            if not os.path.isfile(p):
                sys.exit("no such file: %s" % p)
        sys.exit(cmd_gate(a.pcb, a.sch, a.no_pin_header, a.accept))
    if a.cmd == "check":
        if not os.path.isdir(a.outdir):
            sys.exit("no such directory: %s" % a.outdir)
        sys.exit(cmd_check(a.outdir, a.stem, a.copper_count))
    if a.cmd == "manifest":
        for p in (a.outdir, a.pcb, a.sch):
            if not os.path.exists(p):
                sys.exit("no such file or directory: %s" % p)
        sys.exit(cmd_manifest(a.outdir, a.pcb, a.sch, a.kicad, a.copper, a.checks, a.no_pin_header, a.accept,
                              a.fail_if_blocked))
    sys.exit(cmd_diff(a.old, a.new))


if __name__ == "__main__":
    main()
