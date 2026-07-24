from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import DEMO, analyze, parse_ply
from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="splatgrade")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_cmd = sub.add_parser("analyze")
    analyze_cmd.add_argument("input")
    scan_cmd = sub.add_parser("scan")
    scan_cmd.add_argument("ply")
    sub.add_parser("demo")
    server = sub.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    if args.command == "serve":
        serve(args.host, args.port)
        return
    if args.command == "scan":
        result = analyze({"gaussians": parse_ply(args.ply)})
    else:
        payload = DEMO if args.command == "demo" else json.loads(Path(args.input).read_text())
        result = analyze(payload)
    print(json.dumps(result, indent=2))
