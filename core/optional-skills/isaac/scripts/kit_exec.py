#!/usr/bin/env python3
"""Send Python source to a running Isaac Sim 6.2 code-execution server and print its reply.

The server is the Kit extension isaacsim.code_editor.python_server, listening on 127.0.0.1:8226. It runs
the source it receives only after EOF, so this client half-closes the socket after sending, then reads one
JSON reply {status, output[, ename, evalue, traceback]}. Globals persist per server context (shared by
default). print() what you want back.

From the Mac, reach the box through an SSH tunnel first: ssh -N -L 8226:127.0.0.1:8226 <linux-box>.
This client connects to 127.0.0.1 only; the server runs any code it gets, so it never listens elsewhere.

    kit_exec.py 'import omni.usd; print(omni.usd.get_context().get_stage().GetRootLayer().identifier)'
    kit_exec.py --file probe.py          # a file on this machine
    echo 'print(1)' | kit_exec.py -      # stdin

A synchronous payload can't be interrupted by the server, so keep long work in a file on the box and send
exec(open("/path/on/box.py").read()). Exit 0 ok, 1 the code raised, 2 no connection or no reply.
Stdlib only; inferred from the 6.2 extension source, not yet run against a live server.
"""
import argparse
import json
import socket
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("code", nargs="?", help="Python source, or - for stdin")
    ap.add_argument("--file", help="read the source from this file instead")
    ap.add_argument("--port", type=int, default=8226, help="local port (default 8226)")
    ap.add_argument("--timeout", type=float, default=10.0, help="seconds to wait for the reply (default 10)")
    ap.add_argument("--token", help="auth token, when the server runs with require_auth (printed at its startup)")
    args = ap.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            code = f.read()
    elif args.code == "-":
        code = sys.stdin.read()
    elif args.code:
        code = args.code
    else:
        ap.error("give the code, - for stdin, or --file")
    if args.token:
        code = f"# isaacsim-python-server-token: {args.token}\n{code}"

    try:
        s = socket.create_connection(("127.0.0.1", args.port), timeout=args.timeout)
    except OSError as e:
        print(f"cannot connect ({e}): is Isaac Sim up with isaacsim.code_editor.python_server "
              "(from the Mac: is the SSH tunnel open)?", file=sys.stderr)
        return 2
    with s:
        s.sendall(code.encode("utf-8"))
        s.shutdown(socket.SHUT_WR)  # the server runs the code on EOF; without this it waits forever
        buf = b""
        try:
            while chunk := s.recv(4096):
                buf += chunk
        except socket.timeout:
            print(f"no reply within {args.timeout:g} s: the code is still running or the sim is busy",
                  file=sys.stderr)
            return 2
    if not buf:
        print("no reply: the server closed the connection", file=sys.stderr)
        return 2

    r = json.loads(buf)
    if r.get("output"):
        print(r["output"], end="" if r["output"].endswith("\n") else "\n")
    if r.get("status") == "error":
        print(f"{r.get('ename')}: {r.get('evalue')}", file=sys.stderr)
        print("".join(r.get("traceback") or []), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
