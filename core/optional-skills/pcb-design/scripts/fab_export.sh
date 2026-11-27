#!/usr/bin/env bash
# JLCPCB-ready file set from a finished board, through kicad-cli only. Never touches the project files.
#
#   fab_export.sh [--no-pin-header] [--accept "<reason>"] <board.kicad_pcb> <root.kicad_sch> <outdir>
#
# First the gates (scripts/fabset.py gate), before anything is plotted or <outdir> is created: from
# <board>/review/gate.json, which erc_drc.sh and pin_diff.py --record write, ERC run, current and 0 errors (warnings
# allowed); DRC run with --schematic-parity, current, 0 error-severity violations, 0 unconnected, 0 parity in both
# the saved-fill and the refilled run; pin diff run, current, 0 errors, on the netlist export_review.sh recorded
# from the current sheets; no critical rule downgraded. The full definition is in SKILL.md (Gates).
# Current = every input still hashes as recorded. A blocking gate: exit 4, each gate named with its reason
# (not run, stale: <file> changed, 2 unconnected), nothing written.
#   --no-pin-header      the project has no firmware pin header: the pin-diff gate does not apply. Refused
#                        (exit 4) when review/gate.json holds a pin diff for this board.
#   --accept "<reason>"  export despite failing counts or downgraded critical rules recorded on the current
#                        inputs (the user accepted them). It cannot waive a gate that is not run, stale, run
#                        without parity or without the refilled run, a stale netlist, an unreadable gate.json or
#                        a refused --no-pin-header: those still exit 4.
# Both are written verbatim into MANIFEST.txt (`gates: ACCEPTED - <reason>`, `gate flags: ...`, each waived gate
# as `WAIVED` with its counts).
#
# <outdir> must be new or hold no order file (gerber/, gerbers.zip, bom.csv, cpl.csv, MANIFEST.txt): exit 1
# otherwise, use a new dated folder. The set is built in a temporary sibling directory and moved into <outdir> only
# when every step and check passed; on any failure nothing is left behind.
# Writes  <outdir>/gerber/*   gerbers (Protel extensions, zones refilled in memory) + Excellon drill + drill map
#         <outdir>/gerbers.zip
#         <outdir>/bom.csv    JLC columns: Comment, Designator, Footprint, LCSC Part #, plus Quantity and MPN;
#                             designators comma-listed, never ranges
#         <outdir>/cpl.csv    JLC columns: Designator, Val, Package, Mid X, Mid Y, Rotation, Layer
#         <outdir>/MANIFEST.txt  sha256 of the board, every sheet of the hierarchy, .kicad_pro, .kicad_dru and the
#                             uploads; kicad-cli version; git revision and dirty flag; the gate lines and flags; the
#                             ERC and DRC disabled and downgraded checks and exclusions; copper layers; drill tools
#                             with holes and slots; ERC/DRC/pin_diff counts from <board>/review/ ("not run" when
#                             absent, "STALE" when older than a file they depend on)
# then checks the set (scripts/fabset.py check) and prints counts for the pre-order checklist in
# references/jlcpcb-order.md.
#
# Env: LCSC_FIELD (default LCSC) — the symbol field that holds the LCSC part number.
#      MPN_FIELD  (default MPN)
# Exit 4: a gate blocks (and --accept was not given or cannot waive it), before the export or when the manifest
# recomputes the gates after it (an input changed during the export); nothing written. Exit 1 on any kicad-cli
# failure, on misuse, on an <outdir> that holds order files, or on a failed check: gerber/ is not exactly the files
# the job file lists plus drill, map and job file, one per requested layer; a BOM cell holds a designator range; a
# BOM designator with an LCSC number has no CPL row. CPL-only designators (fiducials, logos) are listed, not failed.
# Exit 1 leaves nothing in <outdir>; the check and manifest lines are printed.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${KICAD_APP:-/Applications/KiCad/KiCad.app}"
CLI="${APP}/Contents/MacOS/kicad-cli"
LCSC_FIELD="${LCSC_FIELD:-LCSC}"
MPN_FIELD="${MPN_FIELD:-MPN}"

usage() { echo "usage: $(basename "$0") [--no-pin-header] [--accept \"<reason>\"] <board.kicad_pcb> <root.kicad_sch> <outdir>"; }
gate_args=(); nopin=0; accept=""; have_accept=0; pos=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --no-pin-header) nopin=1; shift ;;
    --accept) [[ $# -ge 2 && -n "${2// /}" ]] || { echo "--accept needs a reason" >&2; usage >&2; exit 1; }
              accept="$2"; have_accept=1; shift 2 ;;
    --accept=*) accept="${1#--accept=}"; have_accept=1; [[ -n "${accept// /}" ]] || { echo "--accept needs a reason" >&2; exit 1; }; shift ;;
    -*) echo "unknown option: $1" >&2; usage >&2; exit 1 ;;
    *) pos+=("$1"); shift ;;
  esac
done
[[ ${#pos[@]} -eq 3 ]] || { usage >&2; exit 1; }
pcb="${pos[0]}"; sch="${pos[1]}"; out="${pos[2]}"
[[ -f "${pcb}" && -f "${sch}" && -n "${out}" ]] || { usage >&2; exit 1; }
[[ "${nopin}" -eq 1 ]] && gate_args+=(--no-pin-header)
[[ "${have_accept}" -eq 1 ]] && gate_args+=(--accept "${accept}")
[[ -x "${CLI}" ]] || { echo "kicad-cli not found at ${CLI}; run check_kicad.sh" >&2; exit 1; }

# The gates decide before anything is plotted or written.
echo "== gates ($(dirname "${pcb}")/review/gate.json)"
python3 -B "${SKILL_DIR}/scripts/fabset.py" gate --pcb "${pcb}" --sch "${sch}" ${gate_args[@]+"${gate_args[@]}"}
grc=$?
if [[ ${grc} -eq 4 ]]; then
  echo "NOT EXPORTED: a gate blocks (lines above); nothing was written to ${out}. Re-run the blocking check; --accept \"<reason>\" waives only failing counts and downgraded critical rules the user has accepted, never a block marked [cannot be accepted]." >&2
  exit 4
fi
[[ ${grc} -eq 0 ]] || { echo "FAILED: gate check (exit ${grc})" >&2; exit 1; }
# Never over an earlier set: an outdir holding any order file is refused, and the board's own directory too
# (physical paths, so a symlink to it counts).
out="${out%/}"
if [[ -d "${out}" ]]; then
  [[ "$(cd "$(dirname "${pcb}")" && pwd -P)" != "$(cd "${out}" && pwd -P)" ]] || { echo "outdir is the board's own directory; use <board>/fab/<date>" >&2; exit 1; }
  for f in gerber gerbers.zip bom.csv cpl.csv MANIFEST.txt; do
    if [[ -e "${out}/${f}" ]]; then
      echo "${out} already holds ${f} from an earlier export; never export over a set: use a new dated folder (fab/<date>b)" >&2; exit 1
    fi
  done
elif [[ -e "${out}" ]]; then
  echo "${out} exists and is not a directory" >&2; exit 1
fi
# Built in a temporary sibling directory, moved into place only when every step passed; removed on any failure.
parent="$(dirname "${out}")"; top=""; d="${parent}"
while [[ ! -d "${d}" ]]; do top="${d}"; d="$(dirname "${d}")"; done   # the highest directory this run creates
mkdir -p "${parent}" || exit 1
final="${out}"
out="$(mktemp -d "${final}.partial.XXXXXX")" || exit 1
cleanup() {
  rm -rf "${out}"
  d="${parent}"
  while [[ -n "${top}" ]] && rmdir "${d}" 2>/dev/null && [[ "${d}" != "${top}" ]]; do d="$(dirname "${d}")"; done
  return 0
}
trap cleanup EXIT
mkdir -p "${out}/gerber" || exit 1

fail() { echo "FAILED: $*; nothing was written to ${final}" >&2; exit 1; }

# Copper layer set from the board's (layers ...) header only, lines like `(4 "In1.Cu" power ["GND"])`: F.Cu, In1.Cu..,
# B.Cu. Pad and zone layer lists elsewhere in the file can name In1..In30 on a 2-layer board, so they are not read.
inner="$(grep -oE '^[[:space:]]*\([0-9]+ "In[0-9]+\.Cu"' "${pcb}" | grep -oE 'In[0-9]+\.Cu' | sort -t n -k2 -n | uniq | tr '\n' ',')"
copper="F.Cu,${inner}B.Cu"
copper_count=$(( $(printf '%s' "${copper}" | tr ',' '\n' | grep -c .) ))
layers="${copper},F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# --check-zones refills zones in memory before plotting (the saved fills may be stale); the board is not saved.
echo "== gerbers (${copper_count} copper layers)"
"${CLI}" pcb export gerbers -o "${out}/gerber/" -l "${layers}" \
  --subtract-soldermask --no-x2 --check-zones "${pcb}" || fail "gerber export"

echo "== drill"
"${CLI}" pcb export drill -o "${out}/gerber/" --format excellon --drill-origin absolute \
  --excellon-zeros-format decimal --excellon-units mm --generate-map --map-format gerberx2 "${pcb}" || fail "drill export"

echo "== position (CPL)"
raw="${out}/pos_kicad.csv"
"${CLI}" pcb export pos -o "${raw}" --format csv --units mm --side both --exclude-dnp "${pcb}" || fail "pos export"
# kicad-cli columns: Ref,Val,Package,PosX,PosY,Rot,Side  ->  JLC: Designator,Val,Package,Mid X,Mid Y,Rotation,Layer
python3 - "${raw}" "${out}/cpl.csv" <<'PY' || fail "cpl rewrite"
import csv, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, newline="") as f, open(dst, "w", newline="") as g:
    r = csv.reader(f); w = csv.writer(g)
    header = next(r)
    want = ["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"]
    if header[:7] != want:
        sys.exit("unexpected pos columns: %r" % header)
    w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
    n = 0
    for row in r:
        if not row: continue
        row[6] = {"top": "Top", "bottom": "Bottom"}.get(row[6].lower(), row[6])
        w.writerow(row[:7]); n += 1
print("cpl rows: %d" % n)
PY
rm -f "${raw}"

# --ref-range-delimiter '' lists every designator (C10,C11,...): JLC's uploader does not expand C10-C15.
echo "== BOM"
"${CLI}" sch export bom -o "${out}/bom.csv" \
  --fields "Value,Reference,Footprint,${LCSC_FIELD},\${QUANTITY},${MPN_FIELD}" \
  --labels "Comment,Designator,Footprint,LCSC Part #,Quantity,MPN" \
  --group-by "Value,Footprint,${LCSC_FIELD}" --ref-range-delimiter '' --exclude-dnp "${sch}" || fail "bom export"

echo "== zip"
( cd "${out}" && rm -f gerbers.zip && zip -q -r gerbers.zip gerber ) || fail "zip"

echo "== checks and counts"
python3 -B "${SKILL_DIR}/scripts/fabset.py" check "${out}" "$(basename "${pcb}" .kicad_pcb)" "${copper_count}"
checks=$?

# MANIFEST.txt ties this set to the files it came from; printed after a failed check too, marked FAIL.
echo "== manifest"
python3 -B "${SKILL_DIR}/scripts/fabset.py" manifest "${out}" --pcb "${pcb}" --sch "${sch}" \
  --kicad "$("${CLI}" version 2>/dev/null | head -n 1 | tr -d '[:space:]')" --copper "${copper}" \
  --checks "$([[ ${checks} -eq 0 ]] && echo pass || echo FAIL)" --fail-if-blocked ${gate_args[@]+"${gate_args[@]}"}
mrc=$?
if [[ ${mrc} -eq 4 ]]; then
  echo "NOT EXPORTED: an input changed during the export, so a gate recomputed for the manifest blocks (lines above); the set was discarded and nothing was written to ${final}. Re-run the check it names, then export again." >&2
  exit 4
fi
[[ ${mrc} -eq 0 ]] || fail "manifest"
[[ ${checks} -eq 0 ]] || fail "file-set checks (FAIL lines above)"

# Every step passed: the set moves into place.
if [[ -d "${final}" ]]; then
  for f in gerber gerbers.zip bom.csv cpl.csv MANIFEST.txt; do mv "${out}/${f}" "${final}/" || fail "move into ${final}"; done
  rmdir "${out}" || fail "move into ${final}"
else
  mv "${out}" "${final}" || fail "move into ${final}"
fi
trap - EXIT
echo "set: ${final}"
