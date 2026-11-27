#!/usr/bin/env python3
"""Stock and JLCPCB basic/extended status of LCSC part numbers, before an order. Stdlib only, no credentials.

    parts_check.py [--bom bom.csv] [--json] [--timeout S] [--delay S] [PART ...]

Parts: the LCSC column of --bom (the first header containing `lcsc`, any case: fab_export.sh writes
`LCSC Part #`; empty cells are counted, not looked up) and/or part numbers as arguments (C12345). Duplicates are
looked up once.

Source: the jlcsearch community API (github.com/tscircuit/jlcsearch), one GET per part:
    https://jlcsearch.tscircuit.com/api/search?q=C<n>&limit=10
An exact part number returns that part only, never a substitute. Its `stock` is the quantity JLCPCB reported in
a check of the last few hours, or null (unknown) when no check is that recent; each lookup asks jlcsearch to
check again (its refresh job is scheduled hourly), so a later run may turn unknown into a number. `is_basic` and
`is_preferred` give basic, preferred extended or extended; when the API sends neither, the tier is printed as
unknown, never guessed. `is_standard_only` (when sent) marks parts only Standard PCBA can place. `price` is the
unit price at the smallest quantity break as jlcsearch reports it (USD in its data).

Output: one row per part (part, tier, stock, price, when jlcsearch last checked stock, MPN and description), then a
summary. --json prints the same as one JSON object instead.

Exit 0: every part found and in stock. 2: a part is not in the catalogue, has an invalid number, or has zero stock
(listed). 3: the result is unverified: a lookup failed (network, HTTP error, a response shape this script does not
know) or a part's stock is unknown; a failed lookup wins over 2, unknown stock does not. 1: misuse (no parts, an
unreadable BOM, no LCSC column).
A request times out after --timeout seconds (default 15) and is retried once; --delay (default 0.5 s) separates
requests; after 3 failed lookups in a row the remaining parts are not looked up. User-Agent is a generic client
name. --responses FILE reads saved response bodies ({"C12345": <body>, ...}) instead of the network, for the
self-test; a part missing from the file counts as a failed lookup.
"""
import argparse
import csv
import datetime
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://jlcsearch.tscircuit.com/api/search"
UA = "parts-check/1.0 (python-urllib)"
PART = re.compile(r"^C[1-9][0-9]*$")


class Parser(argparse.ArgumentParser):
    def error(self, message):  # argparse exits 2, which here means a part problem; misuse is 1
        self.print_usage(sys.stderr)
        sys.exit("%s: error: %s" % (self.prog, message))


class LookupFailed(Exception):
    pass


def bom_parts(path):
    """(part numbers in BOM order, column name, number of rows with an empty LCSC cell)."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        sys.exit("cannot read %s: %s" % (path, e))
    if not rows:
        sys.exit("%s is empty" % path)
    col = next((i for i, h in enumerate(rows[0]) if "lcsc" in h.lower()), None)
    if col is None:
        sys.exit("%s has no column whose header contains 'lcsc' (headers: %s)" % (path, ", ".join(rows[0])))
    parts, empty = [], 0
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        cell = r[col].strip() if col < len(r) else ""
        if not cell:
            empty += 1
            continue
        parts += [t.strip() for t in re.split(r"[,;\s]+", cell) if t.strip()]
    return parts, rows[0][col], empty


def fetch(part, timeout, saved):
    if saved is not None:
        if part not in saved:
            raise LookupFailed("no saved response for %s" % part)
        return saved[part]
    url = "%s?%s" % (API, urllib.parse.urlencode({"q": part, "limit": 10}))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    last = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = "HTTP %d" % e.code
            if e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, OSError) as e:
            last = "network: %s" % getattr(e, "reason", e)
        except ValueError as e:
            last = "not JSON: %s" % e
            break
        if attempt == 1:
            time.sleep(2)
    raise LookupFailed(last or "unknown error")


def parse(part, body):
    """The row for `part` from an /api/search body; LookupFailed when the shape is not the known one."""
    if not isinstance(body, dict) or not isinstance(body.get("components"), list):
        raise LookupFailed("unexpected response shape (no components list): %s" % str(body)[:120])
    n = int(part[1:])
    hits = [c for c in body["components"] if isinstance(c, dict) and str(c.get("lcsc", "")).upper().lstrip("C") == str(n)]
    row = {"part": part, "status": "missing", "mfr": "", "description": "", "package": "", "stock": None,
           "tier": "", "standard_only": None, "price": None, "stock_checked_at": None, "note": ""}
    if not hits:
        row["note"] = "not in the jlcsearch catalogue"
        return row
    c = hits[0]
    if "stock" not in c:
        raise LookupFailed("unexpected response shape (no stock field) for %s" % part)
    stock = c.get("stock")
    if stock is not None and not (isinstance(stock, int) and not isinstance(stock, bool) and stock >= 0):
        raise LookupFailed("unexpected stock value %r for %s" % (stock, part))
    if "is_basic" in c or "is_preferred" in c:
        tier = ("basic" if c.get("is_basic") else
                "preferred extended" if c.get("is_preferred") else "extended")
    else:
        tier = "unknown (API gave no basic/extended field)"
    price = c.get("price")
    row.update(mfr=str(c.get("mfr") or ""), description=str(c.get("description") or ""),
               package=str(c.get("package") or ""), stock=stock, tier=tier,
               standard_only=c.get("is_standard_only") if isinstance(c.get("is_standard_only"), bool) else None,
               price=price if isinstance(price, (int, float)) and not isinstance(price, bool) else None,
               stock_checked_at=c.get("stock_checked_at"))
    if len(hits) > 1:
        row["note"] = "%d catalogue rows for this number; first shown" % len(hits)
    if stock is None:
        row["status"] = "unknown stock"
        row["note"] = (row["note"] + "; " if row["note"] else "") + \
            "no stock check in the last 6 h; this lookup asked jlcsearch for one, a later run may have a number"
    elif stock == 0:
        row["status"] = "zero stock"
    else:
        row["status"] = "ok"
    if row["standard_only"]:
        row["note"] = (row["note"] + "; " if row["note"] else "") + "Standard PCBA only (not Economic)"
    return row


def main():
    ap = Parser(prog="parts_check.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parts", nargs="*", metavar="PART", help="LCSC part numbers, e.g. C14663")
    ap.add_argument("--bom", help="BOM CSV with an LCSC column (fab_export.sh's bom.csv)")
    ap.add_argument("--json", action="store_true", help="print one JSON object instead of the table")
    ap.add_argument("--timeout", type=float, default=15.0, help="seconds per request (default 15)")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests (default 0.5)")
    ap.add_argument("--responses", metavar="FILE", help="saved response bodies instead of the network (self-test)")
    a = ap.parse_args()

    raw, col, empty = [], None, 0
    if a.bom:
        raw, col, empty = bom_parts(a.bom)
    raw += [t for arg in a.parts for t in re.split(r"[,;\s]+", arg) if t]
    if not raw:
        sys.exit("no part numbers: pass --bom <csv> or C<number> arguments")
    parts = []
    for p in raw:
        p = p.strip().upper()
        if p not in parts:
            parts.append(p)
    saved = None
    if a.responses:
        try:
            saved = json.load(open(a.responses))
        except (OSError, ValueError) as e:
            sys.exit("cannot read --responses %s: %s" % (a.responses, e))

    rows, failed_in_row, first = [], 0, True
    for p in parts:
        if not PART.match(p):
            rows.append({"part": p, "status": "invalid", "note": "not an LCSC number (C<digits>)"})
            continue
        if failed_in_row >= 3:
            rows.append({"part": p, "status": "lookup failed", "note": "not looked up after 3 failures in a row"})
            continue
        if not first and saved is None:
            time.sleep(a.delay)
        first = False
        try:
            rows.append(parse(p, fetch(p, a.timeout, saved)))
            failed_in_row = 0
        except LookupFailed as e:
            rows.append({"part": p, "status": "lookup failed", "note": str(e)})
            failed_in_row += 1

    def having(*st):
        return [r["part"] for r in rows if r["status"] in st]
    bad, failed, unknown = having("missing", "invalid", "zero stock"), having("lookup failed"), having("unknown stock")
    code = 3 if failed else 2 if bad else 3 if unknown else 0
    verdict = {0: "every part found and in stock", 2: "not orderable as is",
               3: "UNVERIFIED: %s" % ("a lookup failed" if failed else "stock unknown for some parts")}[code]
    summary = {"parts": len(rows), "ok": len(having("ok")), "missing": having("missing"), "invalid": having("invalid"),
               "zero_stock": having("zero stock"), "unknown_stock": unknown, "lookup_failed": failed,
               "bom_rows_without_lcsc": empty if a.bom else None, "exit": code, "verdict": verdict}
    if a.json:
        print(json.dumps({"source": "saved responses %s" % a.responses if saved is not None else API,
                          "checked": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                          "bom": a.bom, "bom_column": col, "parts": rows, "summary": summary}, indent=2))
        return code

    print("source: %s" % ("saved responses %s" % a.responses if saved is not None else API + " (jlcsearch)"))
    if a.bom:
        print("bom: %s, column %r, %d part numbers, %d rows without one" % (a.bom, col, len(parts), empty))
    print("%-10s %-14s %-19s %9s %9s  %-10s  %s" % ("part", "status", "tier", "stock", "price", "checked", "mpn / description"))
    for r in rows:
        stock = r.get("stock")
        checked = (r.get("stock_checked_at") or "")[:10]
        desc = " / ".join(x for x in (r.get("mfr", ""), r.get("description", "")[:60]) if x)
        print("%-10s %-14s %-19s %9s %9s  %-10s  %s%s" % (
            r["part"], r["status"], "unknown" if (r.get("tier") or "").startswith("unknown") else r.get("tier") or "-",
            "unknown" if stock is None and r["status"] not in ("missing", "invalid", "lookup failed") else
            "-" if stock is None else stock,
            "%.4f" % r["price"] if r.get("price") is not None else "-", checked or "-", desc,
            ("  [%s]" % r["note"]) if r.get("note") else ""))
    if any(r.get("tier", "").startswith("unknown") for r in rows):
        print("note: the API did not report basic/extended for some parts; their tier is unknown, not guessed")
    for label, lst in (("not in the catalogue", summary["missing"]), ("invalid numbers", summary["invalid"]),
                       ("zero stock", summary["zero_stock"]), ("stock unknown", unknown), ("lookup failed", failed)):
        if lst:
            print("%s: %s" % (label, ", ".join(lst)))
    print("parts: %d, in stock: %d; %s (exit %d)" % (len(rows), summary["ok"], verdict, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
