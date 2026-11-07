#!/usr/bin/env python3
#################################################################################
#  Copyright (c) 2026 Catena-X Automotive Network e.V.
#  Copyright (c) 2026 Contributors to the Eclipse Foundation
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  This program and the accompanying materials are made available under the
#  terms of the Apache License, Version 2.0 which is available at
#  https://www.apache.org/licenses/LICENSE-2.0.
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#
#  AI Disclosure: This file was entirely AI-generated.
#  The AI-generated portions are made available under CC0-1.0 and not subject
#  to the project's license. The human contributor has reviewed and verified
#  that the code is correct.
#
#  SPDX-License-Identifier: Apache-2.0 AND CC0-1.0
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""Look things up in the specs of the Dataspace Management product, read-only.

Usage: spec-src.py <command> [args]

  where                      paths and commits of the backend and frontend spec in use
  sync                       clone or fast-forward both specs into the cache (~/.cache/dataspace-mgm/specs)
  modules                    every module: id, base path, version, kind, operations, steps, queries
  ops <module> [--tag T]     operations of a module: method, path, operationId, permission, scope
  steps [module]             steps (/steps/...) with the Python function name of the call convention
  queries [module]           queries (/internal/...) with the Python function name
  events [module]            event catalogue of FRAMEWORK 6
  perm <permission>          operations that require a permission (e.g. register_company)
  route <METHOD> <path>      which operation a call hits, e.g.  route POST /api/c1-m2/applications
  sse                        Server-Sent Events streams (paths ending in /events)
  section <module|FRAMEWORK> <n>   print section n of a module README (4 = configuration, 12 = errors)
  open-points [module]       open points of a module, or the cross-module list
  grep <regex> [--fe|--be]   search both specs (default), or only the frontend / backend spec

<module> accepts c3-m1, c3_m1, C3-M1 or the folder name. Output is Markdown, ready to paste.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the repository free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
import specs  # noqa: E402

IFACE = "interface.py"


def cmd_where(_: list[str]) -> None:
    for kind in ("backend", "frontend"):
        p = specs.find_spec(kind, required=False)
        print(f"{kind:9} {p or 'NOT FOUND (run: spec-src.py sync)'}" + (f"  @ {specs.git_rev(p)}" if p else ""))
    print(f"cache     {specs.cache_dir()}")


def cmd_sync(_: list[str]) -> None:
    specs.cache_dir().mkdir(parents=True, exist_ok=True)
    for kind, url in specs.REPOS.items():
        target = specs.cache_dir() / url.rsplit("/", 1)[-1].removesuffix(".git")
        if (target / ".git").is_dir():
            subprocess.run(["git", "-C", str(target), "pull", "-q", "--ff-only"], check=True)
        else:
            subprocess.run(["git", "clone", "-q", "--depth", "50", url, str(target)], check=True)
        print(f"{kind:9} {target} @ {specs.git_rev(target)}")
    local = specs.repo_root() / "spec"
    if (local / ".git").exists():
        print(f"note: this repository also has its own clone at {local}; update it with: git -C spec pull --ff-only")


def cmd_modules(_: list[str]) -> None:
    rows = []
    for m in specs.load_modules().values():
        steps = sum(op.is_step for op in m.operations)
        queries = sum(op.is_query for op in m.operations)
        rows.append([m.id.upper(), m.title.split(" ", 1)[-1], m.base_path or "–", m.version or "–",
                     m.kind or "–", len(m.operations), steps, queries])
    print(specs.table(rows, ["Module", "Name", "Base path", "Version", "Kind", "Ops", "Steps", "Queries"]))


def cmd_ops(args: list[str]) -> None:
    if not args:
        sys.exit("usage: spec-src.py ops <module> [--tag T]")
    m = specs.get_module(args[0])
    tag = args[args.index("--tag") + 1] if "--tag" in args else None
    rows = [[op.method, (m.base_path or "") + op.path, op.operation_id, op.permission, op.scope,
             ",".join(op.tags), "SSE" if op.sse else ""]
            for op in m.operations if not tag or tag in op.tags]
    print(f"{m.title}  ({m.folder.name}/openapi.yaml)\n")
    print(specs.table(rows, ["Method", "Path", "operationId", "x-permission", "scope", "tags", ""]))


def _ops_of(args: list[str], pred) -> list:
    mods = specs.load_modules()
    selected = [specs.get_module(args[0], mods)] if args else mods.values()
    return [op for m in selected for op in m.operations if pred(op)]


def cmd_steps(args: list[str]) -> None:
    rows = [[op.module.upper(), op.path.removeprefix("/steps/"), f"{op.function_name}(input: dict) -> dict",
             op.permission] for op in _ops_of(args, lambda o: o.is_step)]
    print(specs.table(rows, ["Module", "Step", IFACE, "x-permission (over HTTP)"]))


def cmd_queries(args: list[str]) -> None:
    rows = [[op.module.upper(), f"{op.method} {op.path}", op.operation_id, f"{op.function_name}(**params)",
             op.permission] for op in _ops_of(args, lambda o: o.is_query)]
    print(specs.table(rows, ["Module", "Operation", "operationId", IFACE, "x-permission (over HTTP)"]))


def cmd_events(args: list[str]) -> None:
    want = specs.module_id(args[0]) if args else None
    rows = [[m.upper(), e, c] for m, e, c in specs.event_catalogue() if not want or m == want]
    print(specs.table(rows, ["Module", "Event", "Content (at least)"]))


def cmd_perm(args: list[str]) -> None:
    if not args:
        sys.exit("usage: spec-src.py perm <permission>")
    mods = specs.load_modules()
    rows = [[op.module.upper(), op.method, (mods[op.module].base_path or "") + op.path, op.operation_id, op.scope]
            for op in specs.all_operations(mods) if op.permission == args[0]]
    if not rows:
        known = sorted({op.permission for op in specs.all_operations(mods) if op.permission})
        close = [p for p in known if args[0].split("_")[-1] in p][:10]
        sys.exit(f"No operation requires {args[0]!r}." + (f" Similar: {', '.join(close)}" if close else ""))
    print(specs.table(rows, ["Module", "Method", "Path", "operationId", "scope"]))


def cmd_route(args: list[str]) -> None:
    if len(args) < 2:
        sys.exit("usage: spec-src.py route <METHOD> <path>   e.g. route GET /api/c3-m1/companies/123")
    hits = specs.find_operation(args[0], args[1])
    if not hits:
        sys.exit(f"No operation of the spec matches {args[0].upper()} {args[1]}. "
                 "Check the base path (/api/<module>) and the method; `spec-src.py ops <module>` lists them.")
    op = hits[0]
    print(specs.table([[op.module.upper(), op.method, op.path, op.operation_id, op.permission, op.scope,
                        op.function_name or "–"]],
                      ["Module", "Method", "Path", "operationId", "x-permission", "scope", IFACE]))


def cmd_sse(_: list[str]) -> None:
    mods = specs.load_modules()
    rows = [[op.module.upper(), (mods[op.module].base_path or "") + op.path, op.operation_id, op.permission, op.scope]
            for op in specs.all_operations(mods) if op.sse]
    print(specs.table(rows, ["Module", "Stream", "operationId", "x-permission", "scope"]))
    print("\nToken only in `Authorization: Bearer` (never in the query string); the server part of the UI "
          "opens the stream (FRAMEWORK 4.1, C11-M1 7.6, C12-M1 7.6).")


def cmd_section(args: list[str]) -> None:
    if len(args) < 2:
        sys.exit("usage: spec-src.py section <module|FRAMEWORK> <n>")
    if args[0].upper() == "FRAMEWORK":
        text = (specs.find_spec("backend") / "FRAMEWORK.md").read_text(encoding="utf-8")
    else:
        text = specs.get_module(args[0]).readme()
    out = specs.readme_section(text, args[1])
    print(out or f"Section {args[1]} not found.")


def cmd_open_points(args: list[str]) -> None:
    spec = specs.find_spec("backend")
    f = specs.get_module(args[0]).folder / "open-points.md" if args else spec / "open-points.md"
    print(f.read_text(encoding="utf-8") if f.is_file() else f"{f} does not exist.")


def cmd_grep(args: list[str]) -> None:
    if not args:
        sys.exit("usage: spec-src.py grep <regex> [--fe|--be]")
    kinds = ["backend", "frontend"]
    if "--fe" in args:
        kinds = ["frontend"]
    elif "--be" in args:
        kinds = ["backend"]
    rx = re.compile(args[0], re.IGNORECASE)
    for kind in kinds:
        root = specs.find_spec(kind, required=kind == "backend" or "--fe" in args)
        if not root:
            print(f"({kind} spec not found, skipped; run: spec-src.py sync)")
            continue
        for f in sorted(root.rglob("*")):
            if f.suffix not in (".md", ".yaml", ".yml") or ".git" in f.parts:
                continue
            for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if rx.search(ln):
                    print(f"{kind}:{f.relative_to(root)}:{n}: {ln.strip()[:200]}")


COMMANDS = {"where": cmd_where, "sync": cmd_sync, "modules": cmd_modules, "ops": cmd_ops, "steps": cmd_steps,
            "queries": cmd_queries, "events": cmd_events, "perm": cmd_perm, "route": cmd_route, "sse": cmd_sse,
            "section": cmd_section, "open-points": cmd_open_points, "grep": cmd_grep}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help") or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help", "help") else 2)
    COMMANDS[sys.argv[1]](sys.argv[2:])
