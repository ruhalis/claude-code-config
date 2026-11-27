#!/usr/bin/env bash
# ERC or DRC through kicad-cli: the JSON report is kept, a grouped summary is printed, and the result is recorded
# in <outdir>/gate.json for fab_export.sh. Never modifies the project (kicad-cli itself rewrites
# <project>.kicad_prl beside it).
#
#   erc_drc.sh erc <root.kicad_sch|project.kicad_pro> [outdir]   -> <outdir>/erc.json, <outdir>/gate.json
#   erc_drc.sh drc <board.kicad_pcb|project.kicad_pro> [outdir]  -> <outdir>/drc.json   (--schematic-parity,
#                                                                   --all-track-errors)
#                                                                 + <outdir>/drc_refilled.json, <outdir>/gate.json
#
# A .kicad_pro maps to its sibling <name>.kicad_sch / <name>.kicad_pcb. outdir defaults to review/ next to the file,
# the only place fab_export.sh reads the gate from.
# DRC runs twice: on the zone fills saved in the board (drc.json), then with zones refilled in memory
# (drc_refilled.json; never --save-board, the file is not written). Counts that differ mean the saved fills are stale.
# DRC counts the three report arrays apart in both runs and prints them on one line per run:
#   saved fills: violations=<n> (errors=<n>) unconnected=<n> parity=<n>
# Both ERC and DRC print `disabled checks: <names or none>` and `exclusions: <n>` (scripts/fabset.py record).
# Exit codes are the first kicad-cli run's, passed through: 0 clean, 5 violations reported (any severity),
# 3 the file failed to load; a 0 becomes 5 when either DRC run has an error-severity violation, an unconnected item
# or a parity issue. 1 = misuse of this script, including a file of the wrong type, or no gate record written.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${KICAD_APP:-/Applications/KiCad/KiCad.app}"
CLI="${APP}/Contents/MacOS/kicad-cli"

mode="${1:-}"
in="${2:-}"
out="${3:-}"

usage() { echo "usage: $(basename "$0") erc <root.kicad_sch|.kicad_pro> [outdir] | drc <board.kicad_pcb|.kicad_pro> [outdir]"; }

case "${mode}" in
  -h|--help) usage; exit 0 ;;
  erc) ext=kicad_sch ;;
  drc) ext=kicad_pcb ;;
  *) usage >&2; exit 1 ;;
esac
case "${in}" in
  *.kicad_pro) in="${in%.kicad_pro}.${ext}"; echo "using ${in}" ;;
  *."${ext}") ;;
  *) echo "${mode} needs a .${ext} or .kicad_pro file, got: ${in:-nothing}" >&2; usage >&2; exit 1 ;;
esac
[[ -f "${in}" ]] || { echo "no such file: ${in}" >&2; exit 1; }
[[ -x "${CLI}" ]] || { echo "kicad-cli not found at ${CLI}; run check_kicad.sh" >&2; exit 1; }
[[ -n "${out}" ]] || out="$(dirname "${in}")/review"
mkdir -p "${out}" || exit 1
json="${out}/${mode}.json"
rm -f "${json}"
DRC_FLAGS="--severity-all --schematic-parity --all-track-errors"

if [[ "${mode}" == erc ]]; then
  "${CLI}" sch erc --format json --severity-all --exit-code-violations -o "${json}" "${in}"
else
  # shellcheck disable=SC2086  # DRC_FLAGS is a fixed list of plain flags
  "${CLI}" pcb drc --format json ${DRC_FLAGS} --exit-code-violations -o "${json}" "${in}"
fi
rc=$?

flags="--severity-all"; [[ "${mode}" == drc ]] && flags="${DRC_FLAGS}"
record() { python3 -B "${SKILL_DIR}/scripts/fabset.py" record "${mode}" "${in}" "${out}" --flags="${flags}"; }

if [[ ! -s "${json}" ]]; then
  echo "kicad-cli exit ${rc}: no report written (load failure? see the lines above)"
  rm -f "${json}"; record
  [[ "${rc}" -ne 0 ]] || rc=1
  exit "${rc}"
fi

refilled=""
if [[ "${mode}" == drc ]]; then
  refilled="${out}/drc_refilled.json"
  rm -f "${refilled}"
  # shellcheck disable=SC2086
  "${CLI}" pcb drc --format json ${DRC_FLAGS} --refill-zones -o "${refilled}" "${in}" >/dev/null
fi

python3 - "${json}" "${mode}" "${refilled}" <<'PY'
import json, sys
from collections import Counter, OrderedDict

path, mode, refilled = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.load(open(path))

# Flatten to (category, violation). ERC: sheets[].violations[]. DRC: violations[], unconnected_items[], schematic_parity[].
def flatten(d):
    rows = []
    if mode == "erc":
        for sheet in d.get("sheets", []):
            for v in sheet.get("violations", []):
                rows.append(("sheet %s" % sheet.get("path", "/"), v))
    else:
        for cat in ("violations", "unconnected_items", "schematic_parity"):
            for v in d.get(cat, []):
                rows.append((cat, v))
    return rows

rows = flatten(d)
sev = Counter(v.get("severity", "?") for _, v in rows)
print("%s of %s (kicad %s)" % (mode.upper(), d.get("source", "?"), d.get("kicad_version", "?")))
print("report: %s" % path)
print("counts: " + (", ".join("%s=%d" % (k, sev[k]) for k in ("error", "warning", "exclusion") if sev[k]) or "clean"))

by_type = OrderedDict()
for cat, v in rows:
    key = (v.get("severity", "?"), v.get("type", "?"))
    if key not in by_type:
        by_type[key] = [0, v.get("description", "")]
    by_type[key][0] += 1
if by_type:
    print("by type:")
    for (s, t), (n, desc) in sorted(by_type.items(), key=lambda kv: ({"error": 0, "warning": 1}.get(kv[0][0], 2), -kv[1][0])):
        print("  %-9s %-32s x%-4d %s" % (s, t, n, desc[:90]))

# Every error and warning with its items, 20 per severity. ERC positions are left out: KiCad 10.0.5 writes them
# at 1/100 of the declared mm (reported fixed for 10.0.7); the item descriptions name the symbol and pin instead.
CAP = 20
for s in ("error", "warning"):
    sel = [(cat, v) for cat, v in rows if v.get("severity") == s]
    if not sel:
        continue
    print("%ss (%d of %d):" % (s, min(CAP, len(sel)), len(sel)))
    for cat, v in sel[:CAP]:
        items = "; ".join(i.get("description", "") for i in v.get("items", [])[:3])
        where = ""
        if mode == "drc":
            pos = (v.get("items") or [{}])[0].get("pos")
            where = " @(%.2f,%.2f)" % (pos["x"], pos["y"]) if pos else ""
        print("  [%s] %s: %s -- %s%s" % (v.get("type", "?"), cat, v.get("description", ""), items, where))
    if len(sel) > CAP:
        print("  ... %d more in the JSON" % (len(sel) - CAP))

# DRC on zones refilled in memory: counts that differ from the saved-fill run mean the saved fills are stale.
if refilled:
    try:
        r = flatten(json.load(open(refilled)))
    except (OSError, ValueError):
        print("refilled DRC: no report at %s" % refilled)
    else:
        a = Counter((v.get("severity", "?"), v.get("type", "?")) for _, v in rows)
        b = Counter((v.get("severity", "?"), v.get("type", "?")) for _, v in r)
        print("refilled DRC (zones refilled in memory, board not saved): %s" % refilled)
        if a == b:
            print("zone fills: current (same counts after refill)")
        else:
            print("zone fills are stale: Edit > Fill All Zones (B) and save in the GUI")
            for key in sorted(set(a) | set(b)):
                if a[key] != b[key]:
                    print("  %-9s %-32s saved x%d, refilled x%d" % (key[0], key[1], a[key], b[key]))
PY

echo "== gate"
record; grc=$?
case "${grc}" in
  0) ;;
  5) [[ "${rc}" -ne 0 ]] || rc=5 ;;
  *) echo "gate record failed (exit ${grc}): fab_export.sh will read this check as not run" >&2; exit 1 ;;
esac
review_default="$(cd "$(dirname "${in}")" && pwd)/review"
[[ "$(cd "${out}" && pwd)" == "${review_default}" ]] || echo "note: outdir is not ${review_default}; fab_export.sh reads the gate only from there"
exit "${rc}"
