#!/usr/bin/env bash
# JLCPCB-ready file set from a finished board, through kicad-cli only. Never touches the project files.
#
#   fab_export.sh [--no-pin-header] [--accept "<reason>"] <board.kicad_pcb> <root.kicad_sch> <outdir>
#
# First the gates (scripts/fabset.py gate), before anything is plotted or <outdir> is created: from
# <board>/review/gate.json, which erc_drc.sh and pin_diff.py --record write, ERC run, current and 0 errors (warnings
# allowed); DRC run with --schematic-parity, current, 0 error-severity violations, 0 unconnected, 0 parity in both
# the saved-fill and the refilled run; pin diff run, current, 0 errors. Current = every input still hashes as
# recorded. A blocking gate: exit 4, each gate named with its reason (not run, stale: <file> changed,
# 2 unconnected), nothing written.
#   --no-pin-header      the project has no firmware pin header: the pin-diff gate does not apply
#   --accept "<reason>"  export despite failing or stale gates (the user accepted the remaining items)
# Both are written verbatim into MANIFEST.txt (`gates: ACCEPTED - <reason>`, `gate flags: ...`).
#
# Writes  <outdir>/gerber/*   gerbers (Protel extensions, zones refilled in memory) + Excellon drill + drill map;
#                             the directory is emptied first, so no stale file reaches the zip
#         <outdir>/gerbers.zip
#         <outdir>/bom.csv    JLC columns: Comment, Designator, Footprint, LCSC Part #, plus Quantity and MPN;
#                             designators comma-listed, never ranges
#         <outdir>/cpl.csv    JLC columns: Designator, Val, Package, Mid X, Mid Y, Rotation, Layer
#         <outdir>/MANIFEST.txt  sha256 of the board, every sheet of the hierarchy, .kicad_pro, .kicad_dru and the
#                             uploads; kicad-cli version; git revision and dirty flag; the gate lines and flags; the
#                             ERC and DRC disabled checks and exclusions; copper layers; drill tools with holes and
#                             slots; ERC/DRC/pin_diff counts from <board>/review/ ("not run" when absent, "STALE"
#                             when older than a file they depend on)
# then checks the set (scripts/fabset.py check) and prints counts for the pre-order checklist in
# references/jlcpcb-order.md.
#
# Env: LCSC_FIELD (default LCSC) — the symbol field that holds the LCSC part number.
#      MPN_FIELD  (default MPN)
# Exit 4: a gate blocks (no --accept); nothing written. Exit 1 on any kicad-cli failure, on misuse, or on a failed
# check: gerber/ is not exactly the files the job file lists plus drill, map and job file, one per requested layer;
# a BOM cell holds a designator range; a BOM designator with an LCSC number has no CPL row. CPL-only designators
# (fiducials, logos) are listed, not failed. MANIFEST.txt is written either way; after a failed check it says so.
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
  echo "NOT EXPORTED: a gate blocks (lines above); nothing was written to ${out}. Re-run the blocking check, or pass --accept \"<reason>\" once the user has accepted the remaining items." >&2
  exit 4
fi
[[ ${grc} -eq 0 ]] || { echo "FAILED: gate check (exit ${grc})" >&2; exit 1; }
# <outdir>/gerber is emptied before plotting, so refuse an outdir that could hold anything else: the board's own
# directory, or a gerber/ with files that are not fab outputs.
mkdir -p "${out}" || exit 1
[[ "$(cd "$(dirname "${pcb}")" && pwd)" != "$(cd "${out}" && pwd)" ]] || { echo "outdir is the board's own directory; use <board>/fab/<date>" >&2; exit 1; }
if [[ -d "${out}/gerber" ]] && find "${out}/gerber" -type f ! -name '*.g[a-z0-9]*' ! -name '*.drl' ! -name '*.pdf' | grep -q .; then
  echo "${out}/gerber holds files that are not fab outputs; move them or use a fresh outdir" >&2; exit 1
fi
rm -rf "${out}/gerber" "${out}/MANIFEST.txt" && mkdir -p "${out}/gerber" || exit 1

fail() { echo "FAILED: $*" >&2; exit 1; }

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

# MANIFEST.txt ties this set to the files it came from; written after a failed check too, marked FAIL.
echo "== manifest"
python3 -B "${SKILL_DIR}/scripts/fabset.py" manifest "${out}" --pcb "${pcb}" --sch "${sch}" \
  --kicad "$("${CLI}" version 2>/dev/null | head -n 1 | tr -d '[:space:]')" --copper "${copper}" \
  --checks "$([[ ${checks} -eq 0 ]] && echo pass || echo FAIL)" ${gate_args[@]+"${gate_args[@]}"} || fail "manifest"
[[ ${checks} -eq 0 ]] || fail "file-set checks (FAIL lines above)"
