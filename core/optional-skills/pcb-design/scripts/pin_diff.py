#!/usr/bin/env python3
"""Diff GPIO assignments between a KiCad netlist and a firmware pin header. Read-only, stdlib only.

    pin_diff.py --netlist review/board.net --header firmware/main/app_config.h --mcu U1
                [--pin-regex REGEX] [--io-regex REGEX] [--alias NAME=GPIO ...]
                [--reserved LIST] [--caution LIST] [--pinmap pad_to_gpio.csv] [--psram octal|quad|none]
                [--record <board_dir|project.kicad_pro>]

--record writes the result into <board_dir>/review/gate.json for fab_export.sh's pin-diff gate: the counts and the
sha256 of every schematic sheet, the header and the netlist, which must be <board_dir>/review/board.net. The gate
also needs the netlist record export_review.sh sch writes; when it is missing or names another netlist, or the
sheets changed since, the record line says so instead of `pass` (the exit code still follows the rows). The table still goes to stdout (redirect it to
review/pin_diff.txt); the record line goes to stderr.

Netlist: `kicad-cli sch export netlist --format kicadsexpr`. Only nodes whose (ref) equals --mcu are read.
KiCad 10 writes each node's pinfunction as NAME_<pad> (USB_D-_13, IO4_4); a trailing `_<pad>` equal to the node's
pad is stripped before matching, and the raw name is kept in the note column. The GPIO number of a node comes from,
in order: an --alias for its raw or stripped pin name, the first --io-regex match on the stripped name (KiCad's
RF_Module:ESP32-S3-WROOM-1 names pins IO4, IO12, ...), or --pinmap (CSV `pad,gpio`) by pad number. Built-in
aliases cover the WROOM-1 pins that carry no number: USB_D-=19 USB_D+=20 RXD0=44 TXD0=43.

Header: flat `#define PIN_<name> <value>` lines. The value is a decimal or 0x hex number or GPIO_NUM_<n>, bare or
inside parentheses or a cast (`((gpio_num_t)21)`); GPIO_NUM_NC or -1 is an NC info row. Any other #define PIN_
line is unparsable input (exit 1, lines named). A --pin-regex (two groups: name, decimal gpio) replaces this parser.
Comments are stripped; #if branches are not evaluated. Names are compared to net names by their `_`-separated
tokens, case-insensitive, either side a subset of the other (PIN_I2C_SDA matches /SDA; PIN_MOTOR_FR does not match
/M1).

Module variant: the MCU symbol's value in the netlist (ESP32-S3-WROOM-1-N16R8, ESP32-S3R8). R8, R16, R16V and the
like are octal PSRAM: GPIO35-37 are RESERVED. R2 (quad) and no R suffix (no PSRAM) leave them free. A value without
an ordering code: they stay CAUTION, with the variant named unknown. --psram octal|quad|none gives the variant when
the value does not carry it; it may not contradict a value that does.

Verdicts, one row per GPIO:
  OK              header GPIO wired to a net whose name matches the header name
  NAME-MISMATCH   wired, but the net name does not match (warning)
  HEADER-ONLY     header GPIO has no net, or an `unconnected-` net, on the MCU (error)
  SCHEMATIC-ONLY  MCU GPIO on a named net that the header does not mention (info; `Net-(...)` auto names too)
  RESERVED        GPIO in --reserved (default 26-34: flash lines, never on a WROOM-1 pin), or GPIO35-37 on an
                  octal-PSRAM variant, on either side (error)
  CAUTION         GPIO in --caution (default 0,3,19,20,43,44,45,46: strapping, USB, UART0), or GPIO35-37 when the
                  variant is unknown, on either side (warning; the module variant and the design note decide)
  NC              a header name defined as GPIO_NUM_NC or -1 (info)
  DUPLICATE       two header names on one GPIO (warning)
  PINMAP-CLASH    two MCU pins map to one GPIO through --alias/--pinmap (error)

Exit 0: no error rows. 2: at least one error row. 1: misuse (bad arguments included), a file that could not be
parsed, or --record with another netlist than <board_dir>/review/board.net (nothing is recorded then).
"""
import argparse
import os
import re
import sys

DEFAULT_ALIASES = {"USB_D-": 19, "USB_D+": 20, "RXD0": 44, "TXD0": 43}
OCTAL_PSRAM = (35, 36, 37)
DEFINE = re.compile(r"^[ \t]*#[ \t]*define[ \t]+(PIN_\w+)(.*)$", re.M)
CAST = re.compile(r"^\(\s*[A-Za-z_]\w*\s*\)\s*(\S.*)$")


# ---------------------------------------------------------------- s-expressions
def tokenize(text):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "()":
            yield c
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            yield "".join(buf)
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            yield text[i:j]
            i = j


def parse(text):
    stack = [[]]
    for tok in tokenize(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced parentheses in netlist")
    return stack[0]


def child(node, key):
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def value(node, key, default=""):
    c = child(node, key)
    return c[1] if c and len(c) > 1 and not isinstance(c[1], list) else default


# ---------------------------------------------------------------- helpers
def parse_list(spec):
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def tokens(name):
    name = re.sub(r"^.*/", "", name)  # hierarchical path
    name = re.sub(r"^PIN_", "", name, flags=re.I)
    return set(t.lower() for t in re.split(r"[_\-. ]+", name) if t)


def names_match(header_name, net_name):
    h, n = tokens(header_name), tokens(net_name)
    if not h or not n:
        return False
    return h <= n or n <= h or "".join(sorted(h)) == "".join(sorted(n))


def strip_comments(src):
    """Comments removed; a block comment keeps its newlines, so line numbers stay those of the file."""
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def closing(s):
    """Index of the parenthesis that closes s[0], or -1."""
    depth = 0
    for i, c in enumerate(s):
        depth += {"(": 1, ")": -1}.get(c, 0)
        if depth == 0:
            return i
    return -1


def pin_value(expr):
    """The GPIO number of a #define PIN_ value, -1 for GPIO_NUM_NC or -1, None when it cannot be resolved:
    decimal, 0x hex or GPIO_NUM_<n>, inside any number of parentheses and casts."""
    s = expr.strip()
    while True:
        if s.startswith("(") and closing(s) == len(s) - 1:
            s = s[1:-1].strip()
            continue
        m = CAST.match(s)
        if m:
            s = m.group(1).strip()
            continue
        break
    if re.match(r"^(0|[1-9][0-9]*)$", s):
        return int(s)
    if re.match(r"^0[xX][0-9a-fA-F]+$", s):
        return int(s, 16)
    m = re.match(r"^GPIO_NUM_([0-9]+)$", s)
    if m:
        return int(m.group(1))
    if s == "GPIO_NUM_NC" or re.match(r"^-\s*1$", s):
        return -1
    return None


def psram_of(value):
    """'octal', 'quad' or 'none' from an ESP32-S3 module's or chip's ordering code in a symbol value, else None."""
    v = value.upper()
    m = re.search(r"ESP32-S3-(?:WROOM|WROVER|MINI)[-A-Z0-9]*?-[NH][0-9]+(R[0-9]+)?V?A?(?![A-Z0-9])", v) or \
        re.search(r"ESP32-S3(?=[FR])(?:F[NH][0-9]+)?(R[0-9]+)?V?(?![-A-Z0-9])", v)
    if not m:
        return None
    if not m.group(1):
        return "none"
    size = int(m.group(1)[1:])
    return "octal" if size >= 8 else "quad" if size == 2 else None


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse exits 2, which here means error rows; misuse is 1
        self.print_usage(sys.stderr)
        sys.exit("%s: error: %s" % (self.prog, message))


# ---------------------------------------------------------------- main
def main():
    ap = Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--netlist", required=True)
    ap.add_argument("--header", required=True)
    ap.add_argument("--mcu", required=True, help="reference designator of the MCU/module symbol, e.g. U1")
    ap.add_argument("--pin-regex", help="two groups: name, gpio (replaces the built-in #define PIN_ parser)")
    ap.add_argument("--io-regex", default=r"IO(\d+)", help="one group: gpio number inside the pin name")
    ap.add_argument("--alias", action="append", default=[], help="PINNAME=GPIO, repeatable")
    ap.add_argument("--reserved", default="26-34")
    ap.add_argument("--caution", default="0,3,19,20,43,44,45,46")
    ap.add_argument("--pinmap", help="CSV pad,gpio for symbols whose pin names carry no GPIO number")
    ap.add_argument("--psram", choices=["octal", "quad", "none"], help="the module's PSRAM, when the MCU symbol's "
                    "value does not carry the ordering code (octal: GPIO35-37 reserved)")
    ap.add_argument("--record", metavar="BOARD", help="board directory or .kicad_pro: record the result in "
                    "<board_dir>/review/gate.json")
    a = ap.parse_args()

    record = None
    if a.record:
        if a.record.endswith(".kicad_pro"):
            if not os.path.isfile(a.record):
                sys.exit("no such file: %s" % a.record)
            bdir, stem = os.path.dirname(os.path.abspath(a.record)), os.path.basename(a.record)[:-len(".kicad_pro")]
        else:
            if not os.path.isdir(a.record):
                sys.exit("no such directory: %s" % a.record)
            bdir = os.path.abspath(a.record)
            pros = sorted(f for f in os.listdir(bdir) if f.endswith(".kicad_pro"))
            if len(pros) != 1:
                sys.exit("%s holds %d .kicad_pro files; pass the one to use" % (bdir, len(pros)))
            stem = pros[0][:-len(".kicad_pro")]
        want = os.path.join(bdir, "review", "board.net")
        if os.path.realpath(a.netlist) != os.path.realpath(want):
            sys.exit("--record needs --netlist %s (the netlist export_review.sh writes), got %s" % (want, a.netlist))
        record = (bdir, stem)

    aliases = dict(DEFAULT_ALIASES)
    for s in a.alias:
        k, _, v = s.rpartition("=")
        if not k or not v.strip().isdigit():
            sys.exit("bad --alias %r (want NAME=GPIO with an integer GPIO)" % s)
        aliases[k] = int(v)
    pinmap = {}
    if a.pinmap:
        try:
            for ln, line in enumerate(open(a.pinmap), 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [x.strip() for x in line.split(",")]
                if len(parts) < 2 or not parts[1].isdigit():
                    sys.exit("bad --pinmap line %d: %r (want pad,gpio)" % (ln, line))
                pinmap[parts[0]] = int(parts[1])
        except OSError as e:
            sys.exit("cannot read pinmap: %s" % e)
    try:
        reserved, caution = parse_list(a.reserved), parse_list(a.caution)
    except ValueError:
        sys.exit("bad --reserved/--caution list (want e.g. 0,3,26-34)")
    try:
        io_re = re.compile(a.io_regex)
        pin_re = re.compile(a.pin_regex, re.M) if a.pin_regex is not None else None
    except re.error as e:
        sys.exit("bad regex: %s" % e)
    if io_re.groups < 1:
        sys.exit("--io-regex needs one capturing group for the GPIO number")
    if pin_re is not None and pin_re.groups < 2:
        sys.exit("--pin-regex needs two capturing groups: name, gpio")

    # --- header
    try:
        src = strip_comments(open(a.header, encoding="utf-8", errors="replace").read())
    except OSError as e:
        sys.exit("cannot read header: %s" % e)
    header = {}  # gpio -> [names]
    nc = []  # names defined as GPIO_NUM_NC or -1
    if pin_re is not None:
        for m in pin_re.finditer(src):
            if not m.group(2).isdigit():
                sys.exit("--pin-regex group 2 must capture an integer GPIO; got %r for %s" % (m.group(2), m.group(1)))
            header.setdefault(int(m.group(2)), []).append(m.group(1))
        if not header:
            sys.exit("no pins matched --pin-regex in %s" % a.header)
    else:
        bad = []
        for m in DEFINE.finditer(src):
            gpio = pin_value(m.group(2))
            if gpio is None:
                bad.append("line %d: %s" % (src.count("\n", 0, m.start()) + 1, m.group(0).strip()))
            elif gpio < 0:
                nc.append(m.group(1))
            else:
                header.setdefault(gpio, []).append(m.group(1))
        if bad:
            sys.exit("unparsable #define PIN_ lines in %s (want a decimal or 0x number, GPIO_NUM_<n> or GPIO_NUM_NC, "
                     "bare, parenthesised or cast; or pass --pin-regex): %s" % (a.header, "; ".join(bad)))
        if not header and not nc:
            sys.exit("no #define PIN_ lines in %s" % a.header)

    # --- netlist
    try:
        tree = parse(open(a.netlist, encoding="utf-8", errors="replace").read())
    except (OSError, ValueError) as e:
        sys.exit("cannot parse netlist: %s" % e)
    root = tree[0] if tree and isinstance(tree[0], list) else None
    nets = child(root, "nets") if root else None
    if nets is None:
        sys.exit("no (nets ...) section: is this a kicadsexpr netlist?")

    refs_seen = set()
    mcu_nodes = []  # (pinname, pad, netname)
    for net in nets[1:]:
        if not isinstance(net, list) or net[0] != "net":
            continue
        netname = value(net, "name")
        for nd in net[1:]:
            if not isinstance(nd, list) or nd[0] != "node":
                continue
            ref = value(nd, "ref")
            refs_seen.add(ref)
            if ref == a.mcu:
                mcu_nodes.append((value(nd, "pinfunction"), value(nd, "pin"), netname))
    if not mcu_nodes:
        sys.exit("ref %s not in netlist; refs present: %s" % (a.mcu, ", ".join(sorted(refs_seen))[:300]))

    # Module variant from the MCU symbol's value: octal PSRAM takes GPIO35-37.
    comps = child(root, "components") or []
    mcu_value = next((value(c, "value") for c in comps[1:]
                      if isinstance(c, list) and c and c[0] == "comp" and value(c, "ref") == a.mcu), "")
    psram = psram_of(mcu_value)
    if a.psram:
        if psram is not None and psram != a.psram:
            sys.exit("--psram %s contradicts the value of %s, %s (%s PSRAM)" % (a.psram, a.mcu, mcu_value, psram))
        variant = "%s PSRAM (--psram)" % a.psram
        psram = a.psram
    elif psram:
        variant = "%s PSRAM (value %s)" % (psram, mcu_value)
    else:
        variant = "unknown variant (value %r names no ESP32-S3 ordering code; --psram gives it)" % mcu_value

    sch = {}  # gpio -> (pinname, netname)
    clashes = []  # (gpio, first pinname, second pinname)
    unmapped = []
    for pinname, pad, netname in mcu_nodes:
        # KiCad 10: pinfunction is NAME_<pad> (USB_D-_13). Aliases match the raw name first (a hand-passed
        # --alias USB_D-_13=19 keeps working), then the stripped one; the regex runs on the stripped name.
        base = pinname[:-(len(pad) + 1)] if pinname and pad and pinname.endswith("_" + pad) else pinname
        gpio = None
        if pinname in aliases:
            gpio = aliases[pinname]
        elif base in aliases:
            gpio = aliases[base]
        else:
            m = io_re.search(base)
            if m:
                gpio = int(m.group(1))
            elif pad in pinmap:
                gpio = pinmap[pad]
        if gpio is None:
            unmapped.append("%s(pad %s)" % (pinname, pad))
            continue
        if gpio in sch:
            clashes.append((gpio, sch[gpio][0], pinname))
            continue
        sch[gpio] = (pinname, netname)
    if not sch:
        sys.exit("no pin of %s could be mapped to a GPIO number (pin names: %s). Pass --pinmap or --io-regex."
                 % (a.mcu, ", ".join(unmapped[:15])))

    def is_unconnected(netname):
        return netname == "" or netname.startswith("unconnected-")

    def is_auto(netname):
        return netname.startswith("Net-(")

    # --- verdicts
    rows = []  # (gpio, header_names, net, verdict, sev, note)
    for gpio in sorted(set(header) | set(sch)):
        hn = header.get(gpio, [])
        pinname, net = sch.get(gpio, ("", None))
        if hn and net is not None and not is_unconnected(net):
            if any(names_match(n, net) for n in hn) and not is_auto(net):
                rows.append((gpio, hn, net, "OK", "ok", pinname))
            elif is_auto(net):
                rows.append((gpio, hn, net, "NAME-MISMATCH", "warning", "connected but unlabeled; add a net label"))
            else:
                rows.append((gpio, hn, net, "NAME-MISMATCH", "warning", "rename the label or the define"))
        elif hn:
            rows.append((gpio, hn, net or "-", "HEADER-ONLY", "error",
                         "firmware uses it; MCU pin %s" % ("is unconnected" if net else "not in netlist")))
        elif net is not None and not is_unconnected(net):
            rows.append((gpio, [], net, "SCHEMATIC-ONLY", "info",
                         "unlabeled" if is_auto(net) else "not in header"))
        else:
            continue
        if len(hn) > 1:
            rows.append((gpio, hn, net or "-", "DUPLICATE", "warning", "two defines on one GPIO"))
        if gpio in reserved:
            rows.append((gpio, hn, net or "-", "RESERVED", "error", "flash/PSRAM line, not a usable GPIO"))
        elif gpio in OCTAL_PSRAM and psram == "octal":
            rows.append((gpio, hn, net or "-", "RESERVED", "error",
                         "octal PSRAM line on this module (%s), not a usable GPIO" % variant))
        elif gpio in caution:
            rows.append((gpio, hn, net or "-", "CAUTION", "warning",
                         "strapping/USB/UART0 pin: check esp32-s3-rules.md and the module variant"))
        elif gpio in OCTAL_PSRAM and psram is None:
            rows.append((gpio, hn, net or "-", "CAUTION", "warning",
                         "octal-PSRAM pin on an %s" % variant))

    for gpio, first, second in clashes:
        rows.append((gpio, header.get(gpio, []), sch[gpio][1], "PINMAP-CLASH", "error",
                     "pins %s and %s both map to GPIO %d: fix --alias/--pinmap" % (first, second, gpio)))
    for name in nc:
        rows.append((None, [name], "-", "NC", "info", "defined as GPIO_NUM_NC or -1: no GPIO"))
    rows.sort(key=lambda r: (r[0] is None, r[0] or 0))

    # --- print
    w = max([len(",".join(h)) for _, h, _, _, _, _ in rows] + [6])
    print("%-4s  %-*s  %-28s  %-14s  %s" % ("GPIO", w, "header", "net", "verdict", "note"))
    for gpio, hn, net, verdict, _, note in rows:
        print("%-4s  %-*s  %-28s  %-14s  %s" % ("NC" if gpio is None else gpio, w, ",".join(hn) or "-",
                                                (net or "-")[:28], verdict, note))
    if unmapped:
        print("unmapped %s pins (no GPIO number): %s" % (a.mcu, ", ".join(unmapped[:20])))
    print("module %s: %s" % (a.mcu, variant))
    counts = {"error": 0, "warning": 0, "info": 0}
    for r in rows:
        if r[4] in counts:
            counts[r[4]] += 1
    print("errors=%d warnings=%d info=%d  (header pins: %d, %s GPIO pins in netlist: %d)"
          % (counts["error"], counts["warning"], counts["info"], len(header), a.mcu, len(sch)))
    if record:
        sys.stdout.flush()
        sys.dont_write_bytecode = True  # no __pycache__ inside the skill
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import fabset
        try:
            p = fabset.record_pin(record[0], record[1], os.path.abspath(a.header), os.path.abspath(a.netlist),
                                  dict(counts, mcu=a.mcu))
        except (OSError, ValueError) as e:
            sys.exit("gate: pin_diff not recorded: %s" % e)
        bad_net = fabset.pin_netlist_problem(record[0], record[1])
        if bad_net:
            print("gate: pin_diff recorded in %s, but the gate blocks: stale netlist: %s; re-run export_review.sh sch, "
                  "then pin_diff.py --record" % (p, bad_net), file=sys.stderr)
        else:
            print("gate: pin_diff %s, recorded in %s" % ("BLOCKS (%d errors)" % counts["error"] if counts["error"]
                                                        else "pass", p), file=sys.stderr)
    sys.exit(2 if counts["error"] else 0)


if __name__ == "__main__":
    main()
