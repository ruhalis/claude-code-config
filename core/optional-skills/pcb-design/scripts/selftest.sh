#!/usr/bin/env bash
# Offline self-test of the pcb-design scripts on assets/fixtures/. No kicad-cli, no project, no network; writes
# only a temp dir. Run it whenever check_kicad.sh reports a kicad-cli other than the pin, and after editing a script.
#
#   selftest.sh
#
# Fixtures, trimmed from aquila-fc exported by kicad-cli 10.0.5:
#   board.net   netlist with U1 = ESP32-S3-WROOM-1-N16R8 and KiCad 10 pin functions NAME_<pad>: IO4_4, IO8_12,
#               IO17_10, USB_D-_13, USB_D+_14, RXD0_36, TXD0_37, EN_3, 3V3_2, GND_1; IO3 and IO35 unconnected
#   pins.h      a flat #define PIN_* header wired to it
#   fab/        bom.csv, cpl.csv and gerber/aquila-fc-job.gbrjob from a fab_export.sh run; the layer, drill and map
#               files are generated here with a timestamp, so fab_diff sees two exports of one board
# Hand-made, in the kicad-cli 10.0.5 shapes:
#   gate/drc_one_each.json  one item in each DRC array (an error violation, an unconnected item, a parity issue);
#               gate/drc_clean.json, gate/erc_warning.json, gate/erc_error.json; gate/aquila-fc.kicad_pro with ERC
#               and DRC rules at severity ignore and exclusions; gate/noerc.kicad_pro without an erc section (as
#               Diode's pcb writes it); gate/aquila-fc.kicad_dru with a (severity ignore) rule
#   jlcsearch_responses.json  saved /api/search bodies, real and edited (its _note says which)
# Asserts: pin_diff.py exit codes (0 clean, 2 error rows, 1 misuse) and its OK/CAUTION/HEADER-ONLY/RESERVED/
# NAME-MISMATCH/DUPLICATE rows, on KiCad 10 and pre-10 (no _<pad>) pin names; GPIO35-37 by module variant (octal
# RESERVED, quad free, unknown CAUTION, --psram); header values (GPIO_NUM_<n>, hex, casts, NC, unparsable lines
# exit 1); fabset.py check, the file-set and
# BOM/CPL designator-set check fab_export.sh runs, on a good set and broken ones; fabset.py manifest on stand-in
# files (sheets referenced from the root, a missing one, a G85 slot, a pin diff older than board.net, the git line
# clean and then DIRTY with sheets modified in a sub- and a sibling directory); fab_diff.sh
# on a re-stamped set and a changed one; erc_drc.sh through a stand-in kicad-cli (the three DRC counts in both
# runs, exit 5 raised from 0, --schematic-parity and --all-track-errors on both runs, disabled checks and
# exclusions, the gate record); downgraded critical rules (record exit 5, gate block, --accept waives it);
# malformed reports (not recorded, an earlier pass removed); the netlist record of export_review.sh sch (a
# schematic edit after the export, a hand-replaced board.net, sheets changed during the export, a failed export);
# pin_diff.py --record; fab_export.sh through the stand-in: exit 4 with nothing written when a gate is not run,
# stale (board or header changed) or failing, a full set when every gate passes, --accept waiving only failing
# counts and downgraded rules (refused for not run, stale, no parity, no refilled run, unreadable gate.json),
# --no-pin-header refused while a pin diff is recorded and named in MANIFEST.txt when honoured, an outdir that
# holds an earlier set refused, nothing left behind by a failed export or by an input changed during it; parts_check.py on the saved responses; no
# __pycache__ left in the skill.
# Runs python with PYTHONDONTWRITEBYTECODE=1.
# Exit 0: every assertion passed. 1: at least one failed (each printed as FAIL with its output).
set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
usage() { echo "usage: $(basename "$0")   (no arguments; offline self-test on assets/fixtures)"; }
case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) usage >&2; exit 1 ;;
esac

FIX="${SKILL_DIR}/assets/fixtures"
PIN="${SKILL_DIR}/scripts/pin_diff.py"
FAB="${SKILL_DIR}/scripts/fabset.py"
DIFF="${SKILL_DIR}/scripts/fab_diff.sh"
for f in "${FIX}/board.net" "${FIX}/pins.h" "${FIX}/fab/bom.csv" "${FIX}/fab/cpl.csv" \
         "${FIX}/fab/gerber/aquila-fc-job.gbrjob" "${PIN}" "${FAB}" "${DIFF}" "${FIX}/jlcsearch_responses.json" \
         "${FIX}/gate/drc_one_each.json" "${FIX}/gate/drc_clean.json" "${FIX}/gate/erc_warning.json" \
         "${FIX}/gate/erc_error.json" "${FIX}/gate/aquila-fc.kicad_pro" "${FIX}/gate/noerc.kicad_pro" \
         "${FIX}/gate/aquila-fc.kicad_dru" "${SKILL_DIR}/scripts/erc_drc.sh" "${SKILL_DIR}/scripts/fab_export.sh" \
         "${SKILL_DIR}/scripts/parts_check.py"; do
  [[ -f "${f}" ]] || { echo "missing ${f}" >&2; exit 1; }
done
T="$(mktemp -d "${TMPDIR:-/tmp}/pcb-design-selftest.XXXXXX")" || exit 1
trap 'rm -rf "${T}"' EXIT

passed=0; failed=0; out=""; rc=0
ok()  { passed=$((passed + 1)); echo "ok    $*"; }
bad() { failed=$((failed + 1)); echo "FAIL  $*"; printf '%s\n' "${out}" | tail -n 25 | sed 's/^/      | /'; }
# expect <exit code> <label> <command...>: runs it, keeps its output in ${out} for the has/lacks checks after it
expect() {
  local want="$1" label="$2"; shift 2
  out="$("$@" 2>&1)"; rc=$?
  if [[ "${rc}" -eq "${want}" ]]; then ok "${label}: exit ${rc}"; else bad "${label}: exit ${rc}, want ${want}"; fi
}
has()   { if printf '%s\n' "${out}" | grep -Eq -- "$2"; then ok "$1"; else bad "$1: no line matching /$2/"; fi; }
lacks() { if printf '%s\n' "${out}" | grep -Eq -- "$2"; then bad "$1: a line matches /$2/"; else ok "$1"; fi; }

echo "== pin_diff.py on the KiCad 10 fixture"
pd() { python3 "${PIN}" --netlist "${1}" --header "${2}" --mcu U1 "${@:3}"; }
expect 0 "--help" python3 "${PIN}" --help
expect 0 "clean header" pd "${FIX}/board.net" "${FIX}/pins.h"
has   "IO4_4 -> GPIO4 OK"                  '^4 +PIN_MOTOR_FR +/MOTOR_FR +OK +IO4_4$'
has   "IO8_12: pad suffix stripped, GPIO8"  '^8 +PIN_I2C_SDA +/I2C_SDA +OK +IO8_12$'
has   "USB_D-_13 -> GPIO19 OK"             '^19 +PIN_USB_DN +/USB_DN +OK +USB_D-_13$'
has   "USB_D+_14 -> GPIO20 OK"             '^20 +PIN_USB_DP +/USB_DP +OK +USB_D\+_14$'
has   "TXD0_37 -> GPIO43 OK"               '^43 +PIN_UART0_TX +/UART0_TX +OK +TXD0_37$'
has   "RXD0_36 -> GPIO44 OK"               '^44 +PIN_UART0_RX +/UART0_RX +OK +RXD0_36$'
has   "GPIO19 CAUTION (USB)"               '^19 +PIN_USB_DN +/USB_DN +CAUTION '
has   "GPIO43 CAUTION (UART0)"             '^43 +PIN_UART0_TX +/UART0_TX +CAUTION '
has   "GPIO0 /BOOT CAUTION (strapping)"    '^0 +- +/BOOT +CAUTION '
lacks "USB/UART0 pins all mapped"          '^unmapped .*(USB_D|RXD0|TXD0)'
has   "only power pins unmapped"           '^unmapped U1 pins \(no GPIO number\): 3V3_2\(pad 2\), EN_3\(pad 3\), GND_1\(pad 1\), GND_40\(pad 40\), GND_41\(pad 41\)$'
has   "summary"                            '^errors=0 warnings=5 info=1 +\(header pins: 7, U1 GPIO pins in netlist: 10\)$'

sed -E 's/\(pinfunction "(.+)_[0-9]+"\)/(pinfunction "\1")/' "${FIX}/board.net" > "${T}/pre10.net"
expect 0 "pre-10 pin names (no _<pad>)" pd "${T}/pre10.net" "${FIX}/pins.h"
has   "USB_D- alias without suffix"        '^19 +PIN_USB_DN +/USB_DN +OK +USB_D-$'
has   "same summary"                       '^errors=0 warnings=5 info=1 '

{ cat "${FIX}/pins.h"; echo '#define PIN_FLOW_MOT 35'; } > "${T}/io35.h"
expect 2 "define on an unconnected pin (IO35, octal PSRAM on N16R8)" pd "${FIX}/board.net" "${T}/io35.h"
has   "HEADER-ONLY row"                    '^35 +PIN_FLOW_MOT +unconnected-\(U1-IO35-Pad28\) +HEADER-ONLY '
has   "RESERVED row for 35 (N16R8)"        '^35 +PIN_FLOW_MOT .* RESERVED +octal PSRAM line'

{ cat "${FIX}/pins.h"; echo '#define PIN_SPARE 30'; } > "${T}/io30.h"
expect 2 "define on a flash line (GPIO30)" pd "${FIX}/board.net" "${T}/io30.h"
has   "RESERVED row"                       '^30 +PIN_SPARE +- +RESERVED '

sed 's/PIN_BUZZER /PIN_BEEPER /' "${FIX}/pins.h" > "${T}/beeper.h"
expect 0 "renamed define" pd "${FIX}/board.net" "${T}/beeper.h"
has   "NAME-MISMATCH row"                  '^17 +PIN_BEEPER +/BUZZER +NAME-MISMATCH '

{ cat "${FIX}/pins.h"; echo '#define PIN_MOTOR_ALT 4'; } > "${T}/dup.h"
expect 0 "two defines on GPIO4" pd "${FIX}/board.net" "${T}/dup.h"
has   "DUPLICATE row"                      '^4 +PIN_MOTOR_FR,PIN_MOTOR_ALT .* DUPLICATE '

echo "== pin_diff.py: GPIO35-37 by module variant"
sed 's/unconnected-(U1-IO35-Pad28)/\/FLOW_MOT/' "${FIX}/board.net" > "${T}/io35_n16r8.net"
expect 2 "GPIO35 wired on an N16R8 (octal PSRAM)" pd "${T}/io35_n16r8.net" "${T}/io35.h"
has   "RESERVED error row"                 '^35 +PIN_FLOW_MOT +/FLOW_MOT +RESERVED +octal PSRAM line'
lacks "no CAUTION row for 35"              '^35 .* CAUTION '
has   "variant named"                      '^module U1: octal PSRAM \(value ESP32-S3-WROOM-1-N16R8\)$'
sed 's/"ESP32-S3-WROOM-1-N16R8"/"ESP32-S3-WROOM-1-N8R2"/' "${T}/io35_n16r8.net" > "${T}/io35_n8r2.net"
expect 0 "GPIO35 on an N8R2 (quad PSRAM): free" pd "${T}/io35_n8r2.net" "${T}/io35.h"
has   "OK row"                             '^35 +PIN_FLOW_MOT +/FLOW_MOT +OK '
lacks "no RESERVED or CAUTION row for 35"  '^35 .* (RESERVED|CAUTION) '
sed 's/"ESP32-S3-WROOM-1-N16R8"/"ESP32-S3-WROOM-1-N8"/' "${T}/io35_n16r8.net" > "${T}/io35_n8.net"
expect 0 "GPIO35 on an N8 (no PSRAM): free" pd "${T}/io35_n8.net" "${T}/io35.h"
lacks "no RESERVED or CAUTION row for 35"  '^35 .* (RESERVED|CAUTION) '
sed 's/"ESP32-S3-WROOM-1-N16R8"/"ESP32-S3-WROOM-1"/' "${T}/io35_n16r8.net" > "${T}/io35_any.net"
expect 0 "GPIO35, value without an ordering code" pd "${T}/io35_any.net" "${T}/io35.h"
has   "CAUTION, variant unknown"           '^35 +PIN_FLOW_MOT .* CAUTION +octal-PSRAM pin on an unknown variant'
expect 0 "--psram quad for that value" pd "${T}/io35_any.net" "${T}/io35.h" --psram quad
lacks "no CAUTION row for 35"              '^35 .* CAUTION '
expect 2 "--psram octal for that value" pd "${T}/io35_any.net" "${T}/io35.h" --psram octal
has   "RESERVED row"                       '^35 +PIN_FLOW_MOT .* RESERVED '
expect 1 "misuse: --psram contradicting the value" pd "${T}/io35_n16r8.net" "${T}/io35.h" --psram none
has   "says so"                            'contradicts the value of U1'

echo "== pin_diff.py: header values"
cat > "${T}/values.h" <<'H'
#define PIN_MOTOR_FR    GPIO_NUM_4
#define PIN_I2C_SDA     0x08
#define PIN_BUZZER      ((gpio_num_t)17)
#define PIN_USB_DN      (gpio_num_t)GPIO_NUM_19
#define PIN_USB_DP      (20)
#define PIN_UART0_TX    ( (gpio_num_t) (0x2B) )
#define PIN_UART0_RX    44
#define PIN_SPARE       GPIO_NUM_NC
#define PIN_OFF         (-1)
H
expect 0 "GPIO_NUM_<n>, hex, casts, parentheses, NC" pd "${FIX}/board.net" "${T}/values.h"
has   "GPIO_NUM_4"                         '^4 +PIN_MOTOR_FR +/MOTOR_FR +OK '
has   "0x08 is GPIO8"                      '^8 +PIN_I2C_SDA +/I2C_SDA +OK '
lacks "nothing read as GPIO0"              '^0 +PIN_'
has   "((gpio_num_t)17)"                   '^17 +PIN_BUZZER +/BUZZER +OK '
has   "a cast of GPIO_NUM_19"              '^19 +PIN_USB_DN +/USB_DN +OK '
has   "a cast of hex, parenthesised"       '^43 +PIN_UART0_TX +/UART0_TX +OK '
has   "GPIO_NUM_NC: NC info row"           '^NC +PIN_SPARE +- +NC '
has   "-1: NC info row"                    '^NC +PIN_OFF +- +NC '
has   "summary: two more info rows"        '^errors=0 warnings=5 info=3 +\(header pins: 7, '
printf '#define PIN_MOTOR_FR 4\n/* a\n   comment */\n#define PIN_LED (PIN_BASE + 1)\n#define PIN_FAST 5U\n' > "${T}/unparsable.h"
expect 1 "unparsable #define PIN_ lines" pd "${FIX}/board.net" "${T}/unparsable.h"
has   "named with their line numbers"      'line 4: #define PIN_LED \(PIN_BASE \+ 1\); line 5: #define PIN_FAST 5U$'
expect 0 "--pin-regex as before" pd "${FIX}/board.net" "${FIX}/pins.h" --pin-regex '^\s*#define\s+(PIN_\w+)\s+\(?(\d+)\)?'
has   "same summary"                       '^errors=0 warnings=5 info=1 '

echo '/* no pins */' > "${T}/empty.h"
expect 1 "misuse: --mcu not in netlist" pd "${FIX}/board.net" "${FIX}/pins.h" --mcu U99
has   "names the refs present"             'ref U99 not in netlist'
expect 1 "misuse: unknown option" pd "${FIX}/board.net" "${FIX}/pins.h" --bogus
expect 1 "misuse: header without PIN_ defines" pd "${FIX}/board.net" "${T}/empty.h"
expect 1 "misuse: not a netlist" pd "${FIX}/pins.h" "${FIX}/pins.h"

echo "== fabset.py check (fab_export.sh's file-set and BOM/CPL checks)"
# gen.py <job> <gerber_dir> <timestamp> all|gerbers|drill, or gen.py pos <cpl.csv> <out.csv>: the fixture set's
# layer, drill and map files carrying the timestamp (mkset), and the stand-in kicad-cli's exports further down
cat > "${T}/gen.py" <<'PY'
import csv, json, os, sys
if sys.argv[1] == "pos":  # the fixture cpl.csv back in kicad-cli's pos columns
    with open(sys.argv[2], newline="") as f, open(sys.argv[3], "w", newline="") as g:
        r = csv.reader(f); w = csv.writer(g); next(r)
        w.writerow(["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
        for row in r:
            if row:
                w.writerow(row[:6] + [row[6].lower()])
    sys.exit(0)
job, gdir, ts, what = sys.argv[1:5]
d = json.load(open(job))
d["Header"]["CreationDate"] = ts
if what in ("all", "gerbers"):
    open(os.path.join(gdir, os.path.basename(job)), "w").write(json.dumps(d, indent=2) + "\n")
    for a in d["FilesAttributes"]:
        open(os.path.join(gdir, a["Path"]), "w").write(
            "G04 #@! TF.CreationDate,%s*\nG04 #@! TF.FileFunction,%s*\n%%FSLAX46Y46*%%\n"
            "G04 Created by KiCad (PCBNEW 10.0.5) date %s*\n%%MOMM*%%\n%%ADD10C,0.200000*%%\nD10*\n"
            "X10000000Y-10000000D03*\nM02*\n" % (ts, a["FileFunction"], ts))
if what in ("all", "drill"):
    open(os.path.join(gdir, "aquila-fc.drl"), "w").write(
        "M48\n; DRILL file KiCad 10.0.5 date %s\n; #@! TF.CreationDate,%s\nFMAT,2\nMETRIC\n"
        "; #@! TA.AperFunction,Plated,PTH,ViaDrill\nT1C0.300\n"
        "; #@! TA.AperFunction,NonPlated,NPTH,ComponentDrill\nT2C3.200\n%%\nG90\nG05\n"
        "T1\nX10.0Y-10.0\nX12.0Y-10.0\nT2\nX3.0Y-3.0\nM30\n" % (ts, ts))
    open(os.path.join(gdir, "aquila-fc-drl_map.gbr"), "w").write(
        "%%TF.CreationDate,%s*%%\n%%FSLAX45Y45*%%\nG04 Created by KiCad (PCBNEW 10.0.5) date %s*\n%%MOMM*%%\nM02*\n"
        % (ts, ts))
PY
# mkset <dir> <timestamp>: the fixture set plus generated layer, drill and map files carrying the timestamp
mkset() {
  mkdir -p "$1/gerber" && cp "${FIX}/fab/bom.csv" "${FIX}/fab/cpl.csv" "$1/" && \
  python3 "${T}/gen.py" "${FIX}/fab/gerber/aquila-fc-job.gbrjob" "$1/gerber" "$2" all
}
chk() { python3 "${FAB}" check "$1" aquila-fc "${2:-4}"; }
mkset "${T}/good" 2026-09-22T16:17:03+05:00 || { echo "cannot build the fixture set" >&2; exit 1; }
expect 0 "--help" python3 "${FAB}" --help
expect 0 "good set" chk "${T}/good"
has   "gerber set"                         '^gerber files: 14, expected 14  \(copper: 4, drill: 1, edge: aquila-fc-Edge_Cuts\.gm1\)$'
has   "bom counts"                         '^bom lines: 5, parts: 8  \(without LCSC part #: 1: J7\)$'
has   "designator sets agree"              '^bom vs cpl designators: in BOM not CPL: none; in CPL not BOM .*: none$'
has   "assembled count"                    '^  with LCSC in BOM \(assembled\): 7$'
has   "hand-soldered listed"               '^  in BOM without LCSC \(hand-soldered or unassigned\): 1: J7$'

cp -R "${T}/good" "${T}/range" && sed -i.bak 's/"C3,C4,C7,C19"/"C3-C4,C7,C19"/' "${T}/range/bom.csv"
expect 1 "designator range" chk "${T}/range"
has   "range named"                        '^FAIL bom designator ranges \(JLC does not expand them\): C3-C4$'

cp -R "${T}/good" "${T}/nocpl" && grep -v '^U1,' "${T}/good/cpl.csv" > "${T}/nocpl/cpl.csv"
expect 1 "LCSC part with no CPL row" chk "${T}/nocpl"
has   "U1 named"                           '^FAIL bom designators with an LCSC number but no CPL row .*: U1$'

cp -R "${T}/good" "${T}/fid" && echo 'FID1,Fiducial,Fiducial_1mm_Mask2mm,2.000000,-2.000000,0.000000,Top' >> "${T}/fid/cpl.csv"
expect 0 "CPL-only fiducial is listed, not failed" chk "${T}/fid"
has   "FID1 listed"                        'in CPL not BOM .*: FID1$'
has   "board-only count"                   '^  not in BOM \(board-only\): 1$'

cp -R "${T}/good" "${T}/extra" && echo x > "${T}/extra/gerber/stray.gbr"
expect 1 "unexpected gerber file" chk "${T}/extra"
has   "stray named"                        '^FAIL gerber set: .*unexpected: stray\.gbr$'

cp -R "${T}/good" "${T}/missing" && rm "${T}/missing/gerber/aquila-fc-In2_Cu.g2"
expect 1 "missing inner layer file" chk "${T}/missing"
has   "missing named"                      '^FAIL gerber set: .*files missing: aquila-fc-In2_Cu\.g2;'

expect 1 "copper count differs from the job file (fab: says 2 layers)" chk "${T}/good" 2
expect 1 "misuse: no such outdir" chk "${T}/nothing"

echo "== fab_diff.sh"
mkset "${T}/again" 2026-09-23T09:00:00+05:00
expect 0 "--help" bash "${DIFF}" --help
expect 0 "same board exported twice" bash "${DIFF}" "${T}/good" "${T}/again"
has   "timestamps ignored"                 '^identical except timestamps and G04 comments$'

cp -R "${T}/again" "${T}/moved"
# cpl.csv has CRLF line ends, as fab_export.sh writes it
sed -i.bak 's/^U1,\(.*\),22\.000000,-6\.750000,0\.000000,Top/U1,\1,23.500000,-6.750000,90.000000,Top/' "${T}/moved/cpl.csv"
sed -i.bak 's/^T1C0\.300$/T1C0.200/' "${T}/moved/gerber/aquila-fc.drl"
sed -i.bak 's/^X10000000Y-10000000D03\*$/X11000000Y-10000000D03*/' "${T}/moved/gerber/aquila-fc-F_Cu.gtl"
rm -f "${T}"/moved/*.bak "${T}"/moved/gerber/*.bak
expect 2 "moved U1, changed via drill, changed F.Cu" bash "${DIFF}" "${T}/good" "${T}/moved"
has   "U1 move named"                      '^cpl\.csv +1 difference\(s\): U1: Mid X 22\.000000 -> 23\.500000; Rotation 0\.000000 -> 90\.000000$'
has   "drill change by size"               '^  drill 0\.200 mm Plated,PTH,ViaDrill: none -> x2$'
has   "summary names the files"            '^identical except: cpl\.csv, aquila-fc-F_Cu\.gtl, aquila-fc\.drl$'
expect 1 "misuse: one argument" bash "${DIFF}" "${T}/good"

echo "== fabset.py manifest (sheet tree, slots, STALE review counts)"
# Stand-in text files, not KiCad designs: only the Sheetfile properties, the drill file and the mtimes matter here.
R="${T}/repo"; P="${R}/hardware/b"; mkdir -p "${P}/sub" "${P}/review" "${R}/hardware/common" "${T}/mf/gerber"
printf '(kicad_sch\n  (sheet (property "Sheetfile" "sub/child.kicad_sch"))\n  (sheet (property "Sheet file" "gone.kicad_sch"))\n  (sheet (property "Sheetfile" "../common/pwr.kicad_sch"))\n)\n' > "${P}/b.kicad_sch"
printf '(kicad_sch)\n' > "${R}/hardware/common/pwr.kicad_sch"
printf '(kicad_sch\n  (sheet (property "Sheetfile" "grandchild.kicad_sch"))\n)\n' > "${P}/sub/child.kicad_sch"
printf '(kicad_sch)\n' > "${P}/sub/grandchild.kicad_sch"
printf '(kicad_sch)\n' > "${P}/unrelated.kicad_sch"
printf '(kicad_pcb)\n' > "${P}/b.kicad_pcb"
printf 'M48\n; DRILL file KiCad 10.0.5 date 2026-09-23T12:00:00\nMETRIC\n; #@! TA.AperFunction,Plated,PTH,ViaDrill\nT1C0.300\n; #@! TA.AperFunction,Plated,PTH,ComponentDrill\nT2C0.600\n%%\nG90\nG05\nT1\nX1.0Y-1.0\nX2.0Y-1.0\nT2\nX5.0Y-5.0\nX1.91Y-19.28G85X1.31Y-19.28\nG05\nM30\n' > "${T}/mf/gerber/b.drl"
printf '{"sheets":[{"path":"/","violations":[{"severity":"warning","type":"pin_to_pin"}]}]}\n' > "${P}/review/erc.json"
printf 'errors=0 warnings=1 info=2  (header pins: 1, U1 GPIO pins in netlist: 3)\n' > "${P}/review/pin_diff.txt"
printf '(export)\n' > "${P}/review/board.net"
touch -t 202609220900 "${P}/b.kicad_sch" "${P}/sub/child.kicad_sch" "${P}/sub/grandchild.kicad_sch" "${P}/b.kicad_pcb" \
  "${R}/hardware/common/pwr.kicad_sch"
# A git repo around it, so the manifest's git line is exercised: no hooks, no signing, no user config needed.
g() { git -c user.name=selftest -c user.email=selftest@example.invalid -c commit.gpgsign=false -c core.hooksPath="${T}/nohooks" -C "${R}" "$@"; }
have_git=0
if command -v git >/dev/null 2>&1 && g init -q && g add -A && g commit -q -m "board" 2>/dev/null; then have_git=1; else echo "skip  git repo (git missing or cannot commit): git-line checks skipped"; fi
touch -t 202609221000 "${P}/review/erc.json" "${P}/review/pin_diff.txt"
touch -t 202609221100 "${P}/review/board.net"
expect 0 "manifest" python3 "${FAB}" manifest "${T}/mf" --pcb "${P}/b.kicad_pcb" --sch "${P}/b.kicad_sch" \
  --kicad 10.0.5 --copper F.Cu,B.Cu --checks pass
has   "sub-sheet in a subdirectory hashed" '^  [0-9a-f]{64}  sub/child\.kicad_sch$'
has   "its own sub-sheet, relative to it"  '^  [0-9a-f]{64}  sub/grandchild\.kicad_sch$'
has   "missing sheet listed as none"       '^  none +gone\.kicad_sch$'
lacks "unreferenced sheet not hashed"      'unrelated\.kicad_sch'
has   "slot counted apart"                 '^  T2 +0\.600 mm  x1 \+ 1 slots +Plated,PTH,ComponentDrill$'
has   "hole and slot totals"               '^  holes: 3, slots: 1$'
has   "ERC current"                        '^  erc: +warning=1  \(erc\.json, [0-9T:-]+\)$'
has   "pin diff STALE against board.net"   '^  pin_diff: +errors=0 warnings=1 info=2  \(pin_diff\.txt, [0-9T:-]+, STALE: older than review/board\.net\)$'
has   "DRC not run"                        '^  drc: +not run '
if [[ -f "${T}/mf/MANIFEST.txt" ]]; then ok "MANIFEST.txt written"; else bad "MANIFEST.txt not written"; fi
if [[ "${have_git}" -eq 1 ]]; then
  has "git line clean"                     '^git: +[0-9a-f]{12,} clean$'
  echo "; edited" >> "${P}/sub/child.kicad_sch"; echo "; edited" >> "${R}/hardware/common/pwr.kicad_sch"
  touch -t 202609220900 "${P}/sub/child.kicad_sch" "${R}/hardware/common/pwr.kicad_sch"   # keep the review counts current
  expect 0 "manifest on a dirty tree" python3 "${FAB}" manifest "${T}/mf" --pcb "${P}/b.kicad_pcb" --sch "${P}/b.kicad_sch" \
    --kicad 10.0.5 --copper F.Cu,B.Cu --checks pass
  has "sub-sheet in a subdirectory seen"   '^git: +[0-9a-f]{12,} DIRTY: .*sub/child\.kicad_sch \(modified\)'
  has "sheet in a sibling directory seen"  '^git: +[0-9a-f]{12,} DIRTY: .*\.\./common/pwr\.kicad_sch \(modified\)'
  lacks "root sheet not reported"          'DIRTY: .*[ ,]b\.kicad_sch'
fi

echo "== erc_drc.sh and fabset.py record (stand-in kicad-cli)"
ERCDRC="${SKILL_DIR}/scripts/erc_drc.sh"; FABX="${SKILL_DIR}/scripts/fab_export.sh"; G="${FIX}/gate"
# A stand-in kicad-cli: answers the calls erc_drc.sh and fab_export.sh make from the fixtures and logs its arguments.
mkdir -p "${T}/app/Contents/MacOS"
cat > "${T}/app/Contents/MacOS/kicad-cli" <<'STUB'
#!/usr/bin/env bash
o=""; prev=""; refill=0
for a in "$@"; do [[ "${prev}" == "-o" ]] && o="${a}"; [[ "${a}" == --refill-zones ]] && refill=1; prev="${a}"; done
echo "$*" >> "${STUB_LOG}"
[[ "$1" == version ]] && { echo 10.0.5; exit 0; }
case "$1 $2" in
  "sch erc") cp "${STUB_ERC}" "${o}" 2>/dev/null; exit "${STUB_ERC_RC:-0}" ;;
  "pcb drc") if [[ ${refill} -eq 1 ]]; then cp "${STUB_DRC_REFILLED}" "${o}" 2>/dev/null; exit "${STUB_REFILL_RC:-0}"; fi
             [[ -n "${STUB_DRC_TOUCH:-}" ]] && echo '# saved during the run' >> "${STUB_DRC_TOUCH}"
             cp "${STUB_DRC}" "${o}" 2>/dev/null; exit "${STUB_DRC_RC:-0}" ;;
  "sch export")
    case "$3" in
      netlist) [[ -n "${STUB_NET_TOUCH:-}" ]] && echo '; edited during the export' >> "${STUB_NET_TOUCH}"
               [[ -n "${STUB_NET_FAIL:-}" ]] && exit 1
               cp "${STUB_FIX}/board.net" "${o}" ;;
      pdf) printf '%%PDF-1.4\n' > "${o}" ;;
      *) cp "${STUB_FIX}/fab/bom.csv" "${o}" ;;
    esac ;;
  "pcb export")
    case "$3" in
      gerbers|drill) python3 "${STUB_GEN}" "${STUB_FIX}/fab/gerber/aquila-fc-job.gbrjob" "${o}" 2026-11-27T10:00:00+05:00 "$3" ;;
      pos) [[ -n "${STUB_POS_FAIL:-}" ]] && exit 1
           [[ -n "${STUB_POS_TOUCH:-}" ]] && echo '; edited during the export' >> "${STUB_POS_TOUCH}"
           python3 "${STUB_GEN}" pos "${STUB_FIX}/fab/cpl.csv" "${o}" ;;
      *) exit 1 ;;
    esac ;;
  *) exit 1 ;;
esac
STUB
chmod +x "${T}/app/Contents/MacOS/kicad-cli"
printf '#!/bin/sh\nexit 0\n' > "${T}/pdftoppm"; chmod +x "${T}/pdftoppm"   # export_review.sh rasterises nothing
export STUB_LOG="${T}/stub.log" STUB_FIX="${FIX}" STUB_GEN="${T}/gen.py" PDFTOPPM="${T}/pdftoppm"
stub() { KICAD_APP="${T}/app" "$@"; }
EXPORT="${SKILL_DIR}/scripts/export_review.sh"
# mkboard <dir>: a stand-in board aquila-fc (4 copper layers in its (layers ...) header) with the gate fixtures'
# .kicad_pro and .kicad_dru, and the fixture netlist as review/board.net through export_review.sh sch
mkboard() {
  mkdir -p "$1/review" && printf '(kicad_sch)\n' > "$1/aquila-fc.kicad_sch" && \
  printf '(kicad_pcb\n  (layers\n    (0 "F.Cu" signal)\n    (4 "In1.Cu" power)\n    (6 "In2.Cu" power)\n    (2 "B.Cu" signal)\n  )\n)\n' > "$1/aquila-fc.kicad_pcb" && \
  cp "${G}/aquila-fc.kicad_pro" "${G}/aquila-fc.kicad_dru" "$1/" && stub bash "${EXPORT}" sch "$1" >/dev/null 2>&1
}
fstart() { python3 "${FAB}" start "$@" >/dev/null; }   # fstart erc|drc <file> <review>: what erc_drc.sh does first
# has_entry <board dir> <name>: exit 0 when review/gate.json holds that entry
has_entry() { python3 -c 'import json, sys; sys.exit(0 if sys.argv[2] in json.load(open(sys.argv[1])) else 1)' "$1/review/gate.json" "$2"; }
B2="${T}/gp/aquila-fc"; mkboard "${B2}" || { echo "cannot build the stand-in board" >&2; exit 1; }
cp "${FIX}/pins.h" "${T}/gp/pins.h"
pcb2="${B2}/aquila-fc.kicad_pcb"; sch2="${B2}/aquila-fc.kicad_sch"

expect 0 "erc_drc.sh --help" bash "${ERCDRC}" --help
has   "usage line"                         '^usage: erc_drc\.sh erc '
export STUB_DRC="${G}/drc_one_each.json" STUB_DRC_REFILLED="${G}/drc_one_each.json" STUB_DRC_RC=0
: > "${STUB_LOG}"
expect 5 "drc, one item in each array: kicad-cli exit 0 raised to 5" stub bash "${ERCDRC}" drc "${pcb2}"
has   "three counts, saved fills"          '^saved fills: violations=1 \(errors=1\) unconnected=1 parity=1$'
has   "three counts, refilled"             '^refilled: +violations=1 \(errors=1\) unconnected=1 parity=1$'
has   "disabled: report, .kicad_pro, .kicad_dru" '^disabled checks: missing_courtyard, track_not_centered_on_via, silk_overlap, dru:"Silenced rule"$'
has   "drc exclusions from the .kicad_pro" '^exclusions: 1$'
has   ".kicad_pro-only ignore named"       'note: set to ignore in aquila-fc\.kicad_pro but not in the report.s ignored_checks: silk_overlap$'
has   "gate record blocks"                 '^gate: drc BLOCKS \(1 error \(saved fills\), 1 unconnected \(saved fills\), 1 parity \(saved fills\), 1 error \(refilled\)'
if grep -q -- '--schematic-parity' "${STUB_LOG}" && grep -q -- '--refill-zones' "${STUB_LOG}" && \
   [[ "$(grep -c -- '--all-track-errors' "${STUB_LOG}")" -eq 2 ]]; then
  ok "both DRC runs get --schematic-parity and --all-track-errors"; else out="$(cat "${STUB_LOG}")"; bad "DRC flags"; fi
if grep -q -- '--save-board' "${STUB_LOG}"; then out="$(cat "${STUB_LOG}")"; bad "DRC run with --save-board"; else ok "no --save-board"; fi
export STUB_DRC="${G}/drc_clean.json" STUB_DRC_REFILLED="${G}/drc_clean.json"
expect 0 "drc clean, given the .kicad_pro" stub bash "${ERCDRC}" drc "${B2}/aquila-fc.kicad_pro"
has   "clean counts"                       '^saved fills: violations=0 \(errors=0\) unconnected=0 parity=0$'
has   "gate record passes"                 '^gate: drc pass, recorded in '
export STUB_ERC="${G}/erc_warning.json" STUB_ERC_RC=5
expect 5 "erc with a warning (kicad-cli exit 5 kept)" stub bash "${ERCDRC}" erc "${sch2}"
has   "erc counts"                         '^erc: errors=0 warnings=1 excluded=0$'
has   "erc disabled checks"                '^disabled checks: four_way_junction, single_global_label$'
has   "erc exclusions"                     '^exclusions: 2$'
has   "warnings do not block"              '^gate: erc pass, recorded in '
expect 1 "misuse: erc on a .kicad_pcb" stub bash "${ERCDRC}" erc "${pcb2}"
B3="${T}/np"; mkdir -p "${B3}/review"; printf '(kicad_sch)\n' > "${B3}/np.kicad_sch"; cp "${G}/noerc.kicad_pro" "${B3}/np.kicad_pro"
fstart erc "${B3}/np.kicad_sch" "${B3}/review"
sed 's/"aquila-fc\.kicad_sch"/"np.kicad_sch"/' "${G}/erc_warning.json" > "${B3}/review/erc.json"
expect 0 "record erc, .kicad_pro without an erc section" python3 "${FAB}" record erc "${B3}/np.kicad_sch" "${B3}/review" --rc 0
has   "names from the report"              '^disabled checks: four_way_junction, single_global_label$'
has   "no erc section said"                'note: np\.kicad_pro has no erc section: KiCad.s built-in severities apply$'
has   "no exclusions"                      '^exclusions: 0$'

echo "== downgraded rules (.kicad_pro severities below KiCad's defaults)"
B7="${T}/soft/aquila-fc"; mkboard "${B7}"
python3 - "${B7}/aquila-fc.kicad_pro" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["board"]["design_settings"]["rule_severities"].update({"clearance": "warning", "missing_footprint": "warning"})
d["erc"]["rule_severities"].update({"pin_not_connected": "warning", "pin_to_pin": "warning"})
json.dump(d, open(p, "w"), indent=2)
PY
printf '(rule "Soft clearance"\n  (constraint clearance (min 0.5mm))\n  (severity warning))\n' >> "${B7}/aquila-fc.kicad_dru"
export STUB_DRC="${G}/drc_clean.json" STUB_DRC_REFILLED="${G}/drc_clean.json" STUB_DRC_RC=0
expect 5 "drc clean, clearance at warning: raised to 5" stub bash "${ERCDRC}" drc "${B7}/aquila-fc.kicad_pcb"
has   "downgraded checks line"             '^downgraded checks: clearance=warning \(default error, critical: blocks\), silk_overlap=ignore \(default warning\), dru:"Soft clearance"=warning \(custom rule, not blocking\)$'
has   "disabled checks line kept"          '^disabled checks: missing_courtyard, track_not_centered_on_via, silk_overlap, dru:"Silenced rule"$'
lacks "parity rule at its default not listed" 'missing_footprint'
has   "gate record blocks"                 '^gate: drc BLOCKS \(critical rule below its floor: clearance=warning\)'
export STUB_ERC="${G}/erc_warning.json" STUB_ERC_RC=0
expect 5 "erc, pin_not_connected at warning: raised to 5" stub bash "${ERCDRC}" erc "${B7}/aquila-fc.kicad_sch"
has   "erc downgraded line"                '^downgraded checks: pin_not_connected=warning \(default error, critical: blocks\)$'
has   "gate record blocks"                 '^gate: erc BLOCKS \(critical rule below its floor: pin_not_connected=warning\)'
expect 0 "fixture .kicad_pro: no critical rule downgraded" stub bash "${ERCDRC}" erc "${sch2}"
has   "erc downgraded: none"               '^downgraded checks: none$'

echo "== malformed reports are not recorded"
B8="${T}/bad/aquila-fc"; mkboard "${B8}"; pcb8="${B8}/aquila-fc.kicad_pcb"
rec_drc() { python3 "${FAB}" record drc "${pcb8}" "${B8}/review" --flags="--severity-all --schematic-parity --all-track-errors" --rc 0; }
# put8: a started DRC run with a clean refilled report; the saved-fill report is written after it
put8() { fstart drc "${pcb8}" "${B8}/review" && cp "${G}/drc_clean.json" "${B8}/review/drc_refilled.json"; }
put8; cp "${G}/drc_clean.json" "${B8}/review/drc.json"
expect 0 "a clean report records a pass" rec_drc
put8; printf '{}\n' > "${B8}/review/drc.json"
expect 1 "{} as drc.json" rec_drc
has   "not a report"                       '^gate: drc not recorded \(.*drc\.json is not a kicad-cli DRC report: its source is None, not aquila-fc\.kicad_pcb\)'
if has_entry "${B8}" drc; then out="$(cat "${B8}/review/gate.json")"; bad "the earlier drc pass is still in gate.json"; else ok "the earlier drc pass is removed"; fi
put8; cp "${G}/drc_clean.json" "${B8}/review/drc.json"; rec_drc >/dev/null 2>&1
put8; printf '[]\n' > "${B8}/review/drc.json"
expect 1 "[] as drc.json" rec_drc
has   "not an object"                      'drc\.json is not a kicad-cli DRC report: not a JSON object'
if has_entry "${B8}" drc; then out="$(cat "${B8}/review/gate.json")"; bad "the earlier drc pass survived a non-object report"; else ok "the earlier drc pass is removed"; fi
put8; sed 's/"aquila-fc\.kicad_pcb"/"other.kicad_pcb"/' "${G}/drc_clean.json" > "${B8}/review/drc.json"
expect 1 "a report on another file" rec_drc
has   "source named"                       "its source is 'other\.kicad_pcb', not aquila-fc\.kicad_pcb"
put8; grep -v '"unconnected_items"' "${G}/drc_clean.json" > "${B8}/review/drc.json"
expect 1 "a report without unconnected_items" rec_drc
has   "missing array named"                'no unconnected_items list'
put8; cp "${G}/drc_clean.json" "${B8}/review/drc.json"; printf '{"source": "aquila-fc.kicad_pcb"}\n' > "${B8}/review/drc_refilled.json"
expect 1 "a malformed refilled report" rec_drc
has   "refilled report named"              'drc_refilled\.json is not a kicad-cli DRC report: no violations list'
fstart erc "${B8}/aquila-fc.kicad_sch" "${B8}/review"
printf '{"source": "aquila-fc.kicad_sch", "sheets": [{"path": "/", "violations": [{"type": "x"}]}]}\n' > "${B8}/review/erc.json"
expect 1 "an ERC item without a severity" python3 "${FAB}" record erc "${B8}/aquila-fc.kicad_sch" "${B8}/review" --rc 0
has   "says so"                            'an item in sheets\[0\]\.violations has no severity'
printf '{}\n' > "${T}/empty.json"
export STUB_DRC="${T}/empty.json"
expect 1 "erc_drc.sh drc with {} from kicad-cli" stub bash "${ERCDRC}" drc "${pcb8}"
has   "record failed"                      'gate record failed \(exit 1\): its entry was removed'

echo "== a record needs its own start and a completed kicad-cli run"
B9="${T}/rerec/aquila-fc"; mkboard "${B9}"; pcb9="${B9}/aquila-fc.kicad_pcb"; sch9="${B9}/aquila-fc.kicad_sch"
export STUB_DRC="${G}/drc_clean.json" STUB_DRC_REFILLED="${G}/drc_clean.json" STUB_DRC_RC=0
stub bash "${ERCDRC}" drc "${pcb9}" >/dev/null 2>&1
echo '# edited after the DRC' >> "${pcb9}"
expect 1 "bare record of the old reports after a board edit" python3 "${FAB}" record drc "${pcb9}" "${B9}/review" --flags="--severity-all --schematic-parity --all-track-errors" --rc 0
has   "no start state"                     '^gate: drc not recorded \(no start state for this run'
if has_entry "${B9}" drc; then out="$(cat "${B9}/review/gate.json")"; bad "drc entry left"; else ok "no drc entry"; fi
fstart drc "${pcb9}" "${B9}/review"
if [[ ! -e "${B9}/review/drc.json" && ! -e "${B9}/review/drc_refilled.json" ]]; then ok "start removed the old reports"; else bad "old reports kept by start"; fi
expect 1 "start, then record without a kicad-cli run" python3 "${FAB}" record drc "${pcb9}" "${B9}/review" --flags="--severity-all --schematic-parity --all-track-errors" --rc 0
has   "no report"                          '^gate: drc not recorded \(no .*/drc\.json\)'
expect 1 "the board saved during the DRC run" stub env STUB_DRC_TOUCH="${pcb9}" bash "${ERCDRC}" drc "${pcb9}"
has   "named"                              'gate: drc not recorded \(changed during the run: aquila-fc\.kicad_pcb changed\)'
if has_entry "${B9}" drc; then out="$(cat "${B9}/review/gate.json")"; bad "drc entry recorded after a save during the run"; else ok "no drc entry"; fi
expect 0 "a run on an unchanged board records" stub bash "${ERCDRC}" drc "${pcb9}"
export STUB_ERC="${G}/erc_warning.json" STUB_ERC_RC=3
expect 3 "kicad-cli exit 3 with a report written: exit 3 kept" stub bash "${ERCDRC}" erc "${sch9}"
has   "not recorded"                       'gate: erc not recorded \(kicad-cli exit 3: the check did not complete\)'
if has_entry "${B9}" erc; then out="$(cat "${B9}/review/gate.json")"; bad "erc entry recorded after kicad-cli exit 3"; else ok "no erc entry"; fi
export STUB_ERC_RC=0 STUB_REFILL_RC=3
expect 1 "refilled DRC run exits 3" stub bash "${ERCDRC}" drc "${pcb9}"
has   "not recorded"                       'gate: drc not recorded \(kicad-cli exit 3: the check did not complete\)'
if has_entry "${B9}" drc; then out="$(cat "${B9}/review/gate.json")"; bad "drc entry recorded after a refilled run exit 3"; else ok "no drc entry"; fi
export STUB_REFILL_RC=0

echo "== pin_diff.py --record"
expect 1 "misuse: --record with another netlist" pd "${FIX}/board.net" "${T}/gp/pins.h" --record "${B2}"
expect 0 "--record" pd "${B2}/review/board.net" "${T}/gp/pins.h" --record "${B2}"
has   "recorded"                           '^gate: pin_diff pass, recorded in .*/review/gate\.json$'
has   "table unchanged"                    '^errors=0 warnings=5 info=1 '

echo "== netlist record (export_review.sh sch)"
B6="${T}/net/aquila-fc"; mkboard "${B6}"; pcb6="${B6}/aquila-fc.kicad_pcb"; sch6="${B6}/aquila-fc.kicad_sch"
cp "${FIX}/pins.h" "${T}/net/pins.h"
expect 0 "export_review.sh sch" stub bash "${EXPORT}" sch "${B6}"
has   "netlist recorded"                   '^gate: netlist recorded in .*/review/gate\.json \(tied to 1 sheet\)$'
export STUB_DRC="${G}/drc_clean.json" STUB_DRC_REFILLED="${G}/drc_clean.json" STUB_DRC_RC=0 STUB_ERC="${G}/erc_warning.json" STUB_ERC_RC=5
checks6() { stub bash "${ERCDRC}" erc "${sch6}" >/dev/null 2>&1; stub bash "${ERCDRC}" drc "${pcb6}" >/dev/null 2>&1
            pd "${B6}/review/board.net" "${T}/net/pins.h" --record "${B6}" >/dev/null 2>&1; }
gate6() { python3 "${FAB}" gate --pcb "${pcb6}" --sch "${sch6}" "$@"; }
checks6
expect 0 "gate passes on the recorded netlist" gate6
echo '; edited after the export' >> "${sch6}"; checks6
expect 4 "refused: schematic edited after the export, every check but the export re-run" gate6
has   "stale netlist named"                '^  pin_diff: +BLOCKED: stale netlist: netlist exported from older sheets \(aquila-fc\.kicad_sch changed\); re-run export_review\.sh sch, then pin_diff\.py --record \[cannot be accepted\]'
lacks "erc and drc current"                '^  (erc|drc): +BLOCKED'
expect 4 "--accept cannot waive a stale netlist" gate6 --accept "user accepted: selftest"
has   "says which block"                   '^--accept cannot waive: pin_diff: stale netlist: '
stub bash "${EXPORT}" sch "${B6}" >/dev/null 2>&1; checks6
expect 0 "re-exported, pin diff re-run: pass" gate6
{ cat "${FIX}/board.net"; echo; } > "${B6}/review/board.net"; checks6
expect 0 "--record on a board.net that is not the export: rows decide the exit" pd "${B6}/review/board.net" "${T}/net/pins.h" --record "${B6}"
has   "record line says the gate blocks"   '^gate: pin_diff recorded in .*, but the gate blocks: stale netlist: review/board\.net is not the netlist export_review\.sh recorded; re-run export_review\.sh sch'
lacks "no plain pass"                      '^gate: pin_diff pass'
expect 4 "refused: board.net replaced after the export" gate6
has   "not the recorded netlist"           'stale netlist: review/board\.net is not the netlist export_review\.sh recorded'
expect 1 "a sheet changed during the export" stub env STUB_NET_TOUCH="${sch6}" bash "${EXPORT}" sch "${B6}"
has   "says so"                            'netlist not recorded: the sheets changed during the export \(aquila-fc\.kicad_sch changed\)'
if [[ ! -e "${B6}/review/board.net" ]]; then ok "no board.net left"; else bad "board.net left after a refused record"; fi
if has_entry "${B6}" netlist; then out="$(cat "${B6}/review/gate.json")"; bad "netlist record left"; else ok "no netlist record left"; fi
stub bash "${EXPORT}" sch "${B6}" >/dev/null 2>&1
expect 1 "failed netlist export" stub env STUB_NET_FAIL=1 bash "${EXPORT}" sch "${B6}"
if [[ ! -e "${B6}/review/board.net" ]]; then ok "no board.net left"; else bad "an earlier board.net survived a failed export"; fi
if has_entry "${B6}" netlist; then out="$(cat "${B6}/review/gate.json")"; bad "netlist record left"; else ok "no netlist record left"; fi

echo "== fab_export.sh gates (stand-in kicad-cli)"
fx() { stub bash "${FABX}" "$@"; }
partials() { find "${T}" -maxdepth 3 -name '*.partial.*' | grep -q .; }
expect 0 "fab_export.sh --help" bash "${FABX}" --help
has   "usage line"                         '^usage: fab_export\.sh \[--no-pin-header\] \[--accept'
B4="${T}/fresh/aquila-fc"; mkboard "${B4}"; mkdir -p "${T}/out/empty"; : > "${STUB_LOG}"
expect 4 "refused: no check run" fx "${B4}/aquila-fc.kicad_pcb" "${B4}/aquila-fc.kicad_sch" "${T}/out/empty"
has   "erc not run"                        '^  erc: +BLOCKED: not run'
has   "drc not run"                        '^  drc: +BLOCKED: not run'
has   "pin_diff not run"                   '^  pin_diff: +BLOCKED: not run'
has   "says nothing was written"           '^NOT EXPORTED: '
if [[ -z "$(ls -A "${T}/out/empty")" ]]; then ok "output directory left empty"; else out="$(ls -A "${T}/out/empty")"; bad "output directory written"; fi
expect 4 "refused into a new directory" fx "${B4}/aquila-fc.kicad_pcb" "${B4}/aquila-fc.kicad_sch" "${T}/out/new"
if [[ ! -e "${T}/out/new" ]]; then ok "output directory not created"; else bad "output directory created"; fi
if grep -q '^pcb export' "${STUB_LOG}"; then out="$(cat "${STUB_LOG}")"; bad "kicad-cli plotted while refused"; else ok "nothing plotted while refused"; fi
expect 4 "--accept cannot waive gates not run" fx --accept "user accepted: selftest" "${B4}/aquila-fc.kicad_pcb" "${B4}/aquila-fc.kicad_sch" "${T}/out/new"
has   "marked on the gate line"            '^  erc: +BLOCKED: not run \[cannot be accepted\]'
has   "named on the refusal line"          '^--accept cannot waive: erc: not run; drc: not run; pin_diff: not run$'
if [[ ! -e "${T}/out/new" ]]; then ok "nothing written"; else bad "an --accept of gates not run wrote ${T}/out/new"; fi

expect 0 "every gate current and passing" fx "${pcb2}" "${sch2}" "${T}/out/pass"
has   "set moved into place"               "^set: ${T}/out/pass\$"
if partials; then out="$(find "${T}" -maxdepth 3 -name '*.partial.*')"; bad "temporary directory left"; else ok "no temporary directory left"; fi
out="$(cat "${T}/out/pass/MANIFEST.txt" 2>&1)"
has   "manifest: gates pass"               '^gates: +pass$'
has   "manifest: no gate flags"            '^gate flags: +none$'
has   "manifest: erc gate"                 '^  erc: +pass: errors=0 warnings=1 excluded=0 '
has   "manifest: drc gate, both runs"      '^  drc: +pass: saved fills violations=0 \(errors=0\) unconnected=0 parity=0; refilled violations=0 '
has   "manifest: pin_diff gate"            '^  pin_diff: +pass: errors=0 warnings=5 info=1 '
has   "manifest: erc disabled checks"      '^erc disabled checks: four_way_junction, single_global_label$'
has   "manifest: erc exclusions"           '^erc exclusions: 2$'
has   "manifest: drc disabled checks"      '^drc disabled checks: missing_courtyard, track_not_centered_on_via, silk_overlap, dru:"Silenced rule"$'
has   "manifest: drc downgraded checks"    '^drc downgraded checks: silk_overlap=ignore \(default warning\)$'
has   "manifest: drc exclusions"           '^drc exclusions: 1$'
has   "manifest: fab checks kept"          '^fab checks: +pass$'
has   "manifest: uploads hashed"           '^  [0-9a-f]{64}  gerbers\.zip$'
ln -s "${B2}" "${T}/out/boardlink"
expect 1 "refused: outdir is a symlink to the board's own directory" fx "${pcb2}" "${sch2}" "${T}/out/boardlink"
has   "says so"                            "outdir is the board's own directory"
if [[ ! -e "${B2}/gerbers.zip" && ! -e "${B2}/gerber" ]]; then ok "nothing written into the board directory"; else bad "a set was written into the board directory"; fi

expect 4 "--no-pin-header refused while a pin diff is recorded" fx --no-pin-header "${pcb2}" "${sch2}" "${T}/out/np_refused"
has   "says why"                           '^  pin_diff: +BLOCKED: --no-pin-header given, but a pin diff is recorded for this board'
expect 4 "--accept cannot waive that" fx --no-pin-header --accept "user accepted: selftest" "${pcb2}" "${sch2}" "${T}/out/np_refused"
has   "named on the refusal line"          '^--accept cannot waive: pin_diff: --no-pin-header given'
if [[ ! -e "${T}/out/np_refused" ]]; then ok "nothing written"; else bad "--no-pin-header over a recorded pin diff wrote ${T}/out/np_refused"; fi

before="$(cksum < "${T}/out/pass/MANIFEST.txt")"
expect 1 "refused: outdir holds an earlier set" fx "${pcb2}" "${sch2}" "${T}/out/pass"
has   "says to use a new dated folder"     'already holds gerber from an earlier export; never export over a set: use a new dated folder'
if [[ "$(cksum < "${T}/out/pass/MANIFEST.txt")" == "${before}" ]]; then ok "earlier set untouched"; else bad "earlier MANIFEST.txt rewritten"; fi
mkdir -p "${T}/out/onlybom"; echo keep > "${T}/out/onlybom/bom.csv"
expect 1 "refused: outdir holds a bom.csv" fx "${pcb2}" "${sch2}" "${T}/out/onlybom"
has   "names the file"                     'already holds bom\.csv'
if [[ "$(cat "${T}/out/onlybom/bom.csv")" == keep && "$(ls -A "${T}/out/onlybom")" == bom.csv ]]; then ok "bom.csv untouched, nothing added"; else out="$(ls -A "${T}/out/onlybom")"; bad "outdir changed"; fi
expect 1 "pos export fails part-way" stub env STUB_POS_FAIL=1 bash "${FABX}" "${pcb2}" "${sch2}" "${T}/out2/day/new"
has   "failure named"                      '^FAILED: pos export'
if [[ ! -e "${T}/out2" ]]; then ok "nothing left behind, not even the parent directories"; else out="$(find "${T}/out2")"; bad "left behind"; fi
mkdir -p "${T}/out/emptyfail"
expect 1 "pos export fails into an empty outdir" stub env STUB_POS_FAIL=1 bash "${FABX}" "${pcb2}" "${sch2}" "${T}/out/emptyfail"
if [[ -z "$(ls -A "${T}/out/emptyfail")" ]]; then ok "outdir still empty"; else out="$(ls -A "${T}/out/emptyfail")"; bad "outdir written"; fi
if partials; then out="$(find "${T}" -maxdepth 3 -name '*.partial.*')"; bad "temporary directory left"; else ok "no temporary directory left"; fi

expect 4 "the board changes during the export" stub env STUB_POS_TOUCH="${pcb2}" bash "${FABX}" "${pcb2}" "${sch2}" "${T}/out/during"
has   "says an input changed"              '^NOT EXPORTED: an input changed during the export'
has   "the recomputed gate names it"       '^  drc: +BLOCKED: stale: aquila-fc\.kicad_pcb changed'
if [[ ! -e "${T}/out/during" ]] && ! partials; then ok "set discarded, no temporary directory"; else out="$(ls -A "${T}/out")"; bad "a set with BLOCKED gates landed"; fi

echo '# edited' >> "${pcb2}"; echo '/* edited */' >> "${T}/gp/pins.h"
expect 4 "refused: board and header changed since the checks" fx "${pcb2}" "${sch2}" "${T}/out/stale"
has   "drc stale names the board"          '^  drc: +BLOCKED: stale: aquila-fc\.kicad_pcb changed'
has   "pin_diff stale names the header"    '^  pin_diff: +BLOCKED: stale: pins\.h changed'
has   "erc still current"                  '^  erc: +pass: '
if [[ ! -e "${T}/out/stale" ]]; then ok "nothing written"; else bad "stale export wrote ${T}/out/stale"; fi
expect 4 "--accept cannot waive stale gates" fx --accept "user accepted: selftest" "${pcb2}" "${sch2}" "${T}/out/accept"
has   "named on the refusal line"          '^--accept cannot waive: drc: stale: aquila-fc\.kicad_pcb changed; pin_diff: stale: pins\.h changed$'
if [[ ! -e "${T}/out/accept" ]]; then ok "nothing written"; else bad "an --accept of stale gates wrote ${T}/out/accept"; fi

export STUB_DRC="${G}/drc_one_each.json" STUB_DRC_REFILLED="${G}/drc_clean.json" STUB_DRC_RC=5 STUB_ERC="${G}/erc_error.json"
stub bash "${ERCDRC}" drc "${pcb2}" >/dev/null 2>&1; stub bash "${ERCDRC}" erc "${sch2}" >/dev/null 2>&1
pd "${B2}/review/board.net" "${T}/gp/pins.h" --record "${B2}" >/dev/null 2>&1
expect 4 "refused: failing counts" fx "${pcb2}" "${sch2}" "${T}/out/fail"
has   "drc counts named"                   '^  drc: +BLOCKED: 1 error \(saved fills\); 1 unconnected \(saved fills\); 1 parity \(saved fills\): '
has   "erc error named"                    '^  erc: +BLOCKED: 1 error: '
has   "pin diff current again"             '^  pin_diff: +pass: '
if [[ ! -e "${T}/out/fail" ]]; then ok "nothing written"; else bad "failing export wrote ${T}/out/fail"; fi
expect 0 "--accept waives failing counts on current inputs" fx --accept "user accepted: selftest" "${pcb2}" "${sch2}" "${T}/out/accept"
out="$(cat "${T}/out/accept/MANIFEST.txt" 2>&1)"
has   "manifest: ACCEPTED with the reason" '^gates: +ACCEPTED - user accepted: selftest$'
has   "manifest: --accept verbatim"        '^gate flags: +--accept "user accepted: selftest"$'
has   "manifest: waived drc gate, counts"  '^  drc: +WAIVED \(accepted: "user accepted: selftest"\): 1 error \(saved fills\); 1 unconnected \(saved fills\); 1 parity \(saved fills\): saved fills violations=1 \(errors=1\) unconnected=1 parity=1'
has   "manifest: waived erc gate, counts"  '^  erc: +WAIVED \(accepted: "user accepted: selftest"\): 1 error: errors=1 '
has   "manifest: pin diff passes"          '^  pin_diff: +pass: '
cp "${B2}/review/drc.json" "${B2}/review/drc_refilled.json" "${T}/"   # re-record the same reports, started
fstart drc "${pcb2}" "${B2}/review"; cp "${T}/drc.json" "${T}/drc_refilled.json" "${B2}/review/"
python3 "${FAB}" record drc "${pcb2}" "${B2}/review" --flags=--severity-all --rc 5,0 >/dev/null 2>&1
expect 4 "--accept cannot waive DRC without parity" fx --accept "user accepted: selftest" "${pcb2}" "${sch2}" "${T}/out/noparity"
has   "named"                              '^--accept cannot waive: drc: run without --schematic-parity$'
fstart drc "${pcb2}" "${B2}/review"; cp "${T}/drc.json" "${B2}/review/"   # no drc_refilled.json
python3 "${FAB}" record drc "${pcb2}" "${B2}/review" --flags="--severity-all --schematic-parity --all-track-errors" --rc 5 >/dev/null 2>&1
expect 4 "--accept cannot waive a missing refilled run" fx --accept "user accepted: selftest" "${pcb2}" "${sch2}" "${T}/out/norefill"
has   "named"                              '^--accept cannot waive: drc: refilled run missing$'
cp "${B2}/review/gate.json" "${T}/gate.json.bak"; printf '[1]\n' > "${B2}/review/gate.json"
expect 4 "--accept cannot waive an unreadable gate.json" fx --accept "user accepted: selftest" "${pcb2}" "${sch2}" "${T}/out/badgate"
has   "named"                              '^--accept cannot waive: erc: gate.json unreadable: '
cp "${T}/gate.json.bak" "${B2}/review/gate.json"
if [[ ! -e "${T}/out/noparity" && ! -e "${T}/out/norefill" && ! -e "${T}/out/badgate" ]]; then ok "nothing written"; else bad "a refused --accept wrote a set"; fi

pd "${B7}/review/board.net" "${T}/net/pins.h" --record "${B7}" >/dev/null 2>&1
expect 4 "refused: critical rules downgraded" fx "${B7}/aquila-fc.kicad_pcb" "${B7}/aquila-fc.kicad_sch" "${T}/out/soft"
has   "drc block named"                    '^  drc: +BLOCKED: critical rule below its floor: clearance=warning: '
has   "erc block named"                    '^  erc: +BLOCKED: critical rule below its floor: pin_not_connected=warning: '
expect 0 "--accept waives a downgraded critical rule" fx --accept "user accepted: soft clearance" "${B7}/aquila-fc.kicad_pcb" "${B7}/aquila-fc.kicad_sch" "${T}/out/soft"
out="$(cat "${T}/out/soft/MANIFEST.txt" 2>&1)"
has   "manifest: downgraded checks"        '^drc downgraded checks: clearance=warning \(default error, critical: blocks\), '
has   "manifest: waived drc gate"          '^  drc: +WAIVED \(accepted: "user accepted: soft clearance"\): critical rule below its floor: clearance=warning: '

B5="${T}/nopin/aquila-fc"; mkboard "${B5}"
export STUB_DRC="${G}/drc_clean.json" STUB_DRC_REFILLED="${G}/drc_clean.json" STUB_DRC_RC=0 STUB_ERC="${G}/erc_warning.json"
stub bash "${ERCDRC}" drc "${B5}/aquila-fc.kicad_pcb" >/dev/null 2>&1; stub bash "${ERCDRC}" erc "${B5}/aquila-fc.kicad_sch" >/dev/null 2>&1
expect 4 "refused: pin diff not run" fx "${B5}/aquila-fc.kicad_pcb" "${B5}/aquila-fc.kicad_sch" "${T}/out/nopin"
has   "only the pin diff blocks"           '^  pin_diff: +BLOCKED: not run'
lacks "erc and drc pass"                   '^  (erc|drc): +BLOCKED'
expect 0 "--no-pin-header" fx --no-pin-header "${B5}/aquila-fc.kicad_pcb" "${B5}/aquila-fc.kicad_sch" "${T}/out/nopin"
has   "gate output: not applicable by flag" '^gates: +pass \(pin diff not applicable: --no-pin-header\)$'
out="$(cat "${T}/out/nopin/MANIFEST.txt" 2>&1)"
has   "manifest: not a plain pass"         '^gates: +pass \(pin diff not applicable: --no-pin-header\)$'
has   "manifest: --no-pin-header verbatim" '^gate flags: +--no-pin-header$'
has   "manifest: pin diff not applicable"  '^  pin_diff: +not applicable: --no-pin-header'
has   "manifest review block agrees"       '^  pin_diff: +not applicable \(--no-pin-header\)$'
export STUB_DRC=/nonexistent/drc.json
expect 1 "drc wrote no report: gate entry removed" stub bash "${ERCDRC}" drc "${B5}/aquila-fc.kicad_pcb"
has   "says not recorded"                  '^gate: drc not recorded '
expect 4 "refused after a failed DRC run" fx --no-pin-header "${B5}/aquila-fc.kicad_pcb" "${B5}/aquila-fc.kicad_sch" "${T}/out/nopin2"
has   "drc not run"                        '^  drc: +BLOCKED: not run'
expect 1 "misuse: --accept without a reason" fx --accept "" "${pcb2}" "${sch2}" "${T}/out/x"
expect 1 "misuse: unknown option" fx --bogus "${pcb2}" "${sch2}" "${T}/out/x"

echo "== parts_check.py (saved jlcsearch responses, no network)"
pc() { python3 "${SKILL_DIR}/scripts/parts_check.py" --responses "${FIX}/jlcsearch_responses.json" "$@"; }
expect 0 "--help" python3 "${SKILL_DIR}/scripts/parts_check.py" --help
expect 0 "in stock" pc C15849
has   "row: tier, stock, price"            '^C15849 +ok +basic +1834410 +0\.0083 +2026-11-27 +CL10A105KB8NNNC'
expect 2 "zero stock and not in the catalogue" pc C15849 C2913203 C1
has   "zero stock listed"                  '^zero stock: C2913203$'
has   "missing listed"                     '^not in the catalogue: C1$'
has   "Standard-only noted"                'Standard PCBA only'
expect 3 "unknown stock is unverified" pc C14663
has   "real response: basic, stock unknown" '^C14663 +unknown stock +basic +unknown +0\.0083 +2026-11-03 '
has   "verdict"                            'UNVERIFIED: stock unknown for some parts \(exit 3\)$'
expect 3 "changed response shape" pc C2 C1
has   "lookup failure listed"              '^lookup failed: C2$'
has   "unverified"                         'UNVERIFIED: a lookup failed'
expect 0 "no tier fields: unknown, not guessed" pc C3
has   "says so"                            'their tier is unknown, not guessed$'
expect 3 "--bom finds the LCSC column" pc --bom "${FIX}/fab/bom.csv"
has   "column and counts"                  "column 'LCSC Part #', 4 part numbers, 1 rows without one$"
expect 2 "invalid number" pc X123
expect 0 "--json" pc --json C15849 c15849
has   "json status"                        '"status": "ok"'
has   "json exit"                          '"exit": 0'
expect 1 "misuse: no parts" pc

echo "== bytecode"
out="$(find "${SKILL_DIR}" -name __pycache__ -o -name '*.pyc')"
if [[ -z "${out}" ]]; then ok "no __pycache__ or .pyc in the skill"; else bad "bytecode in the skill"; fi

echo "selftest: ${passed} passed, ${failed} failed"
[[ "${failed}" -eq 0 ]]
