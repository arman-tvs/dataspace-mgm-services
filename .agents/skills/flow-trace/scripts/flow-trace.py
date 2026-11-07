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
"""Trace the flows of Process Orchestration (C12-M1 flows.yaml) across the modules, read-only.

Usage: flow-trace.py <command> [args]

  list                  every flow: key, trigger event (with condition), subject, steps, ends on
  show <flow>           one flow step by step: module, step, condition, waits for, completes / fails on, inputs
  module <module>       every flow and step a module takes part in, and the lookups that query it
  event <Event>         which flows an event starts, unblocks (waitFor), completes, fails or ends
  check                 static check of flows.yaml against the specs, like C12-M1 does at start-up
                        (README 6.2): unknown steps, lookups, events; inputs from later steps

The flows file is $FLOWS_FILE or C12-M1-ProcessOrchestration/flows.yaml of the backend spec.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the repository free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portal-spec-sources" / "scripts"))
import specs  # noqa: E402


def _flows() -> dict:
    return specs.flows()


def _get(key: str) -> dict:
    for f in _flows()["flows"]:
        if f["key"] == key:
            return f
    sys.exit(f"No flow {key!r}. Flows: {', '.join(f['key'] for f in _flows()['flows'])}")


def _cond(when: dict | None) -> str:
    return ", ".join(f"{k}={v}" for k, v in (when or {}).items())


def _inputs(inp: dict) -> str:
    def src(v):
        return str(v) if not isinstance(v, dict) else "{" + ", ".join(f"{k}: {src(x)}" for k, x in v.items()) + "}"
    return "; ".join(f"{k} ← {src(v)}" for k, v in (inp or {}).items())


def _evs(entries) -> list[str]:
    """Event names of `completesOn` / `failsOn`: plain names or `{event: X, set: {...}}` (README 6.1)."""
    return [e["event"] if isinstance(e, dict) else e for e in (entries or [])]


def _evs_text(entries) -> str:
    out = []
    for e in entries or []:
        if isinstance(e, dict):
            out.append(e["event"] + (f" (set {_cond(e.get('set'))})" if e.get("set") else ""))
        else:
            out.append(e)
    return ", ".join(out)


def cmd_list(_: list[str]) -> None:
    rows = []
    for f in _flows()["flows"]:
        t = f["trigger"]
        rows.append([f["key"], t["event"] + (f" ({_cond(t.get('when'))})" if t.get("when") else ""),
                     f"{f['subject']['type']}:{f['subject']['key']}", len(f["steps"]),
                     ", ".join(f.get("endOn") or []) or "–"])
    print(specs.table(rows, ["Flow", "Trigger", "Subject", "Steps", "Ends early on"]))


def cmd_show(args: list[str]) -> None:
    if not args:
        sys.exit("usage: flow-trace.py show <flow>")
    f = _get(args[0])
    t = f["trigger"]
    print(f"Flow `{f['key']}`: starts on `{t['event']}`" + (f" when {_cond(t.get('when'))}" if t.get("when") else "")
          + f"; subject {f['subject']['type']} `{f['subject']['key']}`; correlated by `{f.get('correlateBy')}`"
          + (f"; ends early on {', '.join(f['endOn'])}" if f.get("endOn") else "") + ".\n")
    rows = []
    for n, s in enumerate(f["steps"], 1):
        mod, step = s["call"].split(".", 1)
        rows.append([n, s["key"], mod.upper(), step, _cond(s.get("when")) or "–", s.get("waitFor") or "–",
                     s.get("lookup") or "–", _evs_text(s.get("completesOn")) or "DONE",
                     _evs_text(s.get("failsOn")) or "–", _inputs(s.get("input"))])
    print(specs.table(rows, ["#", "Step key", "Module", "Step", "When", "Waits for", "Lookup",
                             "Completes on", "Fails on", "Inputs"]))
    print("\nSources: `name` = process variable, `steps.<key>.<field>` = result of an earlier step, "
          "`lookup.<name>.<field>` = query result, `=VALUE` = fixed (flows.yaml header).")


def cmd_module(args: list[str]) -> None:
    if not args:
        sys.exit("usage: flow-trace.py module <module>")
    mid = specs.module_id(args[0])
    data = _flows()
    rows = [[f["key"], n, s["key"], s["call"].split(".", 1)[1], s.get("waitFor") or "–",
             _evs_text(s.get("completesOn")) or "DONE"]
            for f in data["flows"] for n, s in enumerate(f["steps"], 1) if s["call"].split(".", 1)[0] == mid]
    print(f"Steps of {mid.upper()} in the flows:\n")
    print(specs.table(rows, ["Flow", "#", "Step key", "Step", "Waits for", "Completes on"]) if rows else "(none)")
    looks = [[name, lk["query"], ", ".join(f"{k}←{v}" for k, v in (lk.get("params") or {}).items())]
             for name, lk in (data.get("lookups") or {}).items() if lk["query"].split(".", 1)[0] == mid]
    if looks:
        print(f"\nLookups that query {mid.upper()}:\n")
        print(specs.table(looks, ["Lookup", "Query", "Params"]))
    evs = [e for m, e, _ in specs.event_catalogue() if m == mid]
    starts = [f["key"] for f in data["flows"] if f["trigger"]["event"] in evs]
    if starts:
        print(f"\nFlows started by events of {mid.upper()}: {', '.join(starts)}")


def cmd_event(args: list[str]) -> None:
    if not args:
        sys.exit("usage: flow-trace.py event <EventName>")
    ev, rows = args[0], []
    for f in _flows()["flows"]:
        if f["trigger"]["event"] == ev:
            rows.append([f["key"], "starts the flow", _cond(f["trigger"].get("when")) or "–"])
        if ev in (f.get("endOn") or []):
            rows.append([f["key"], "ends the flow early", "–"])
        for s in f["steps"]:
            if s.get("waitFor") == ev:
                rows.append([f["key"], f"unblocks step `{s['key']}`", "–"])
            if ev in _evs(s.get("completesOn")):
                rows.append([f["key"], f"completes step `{s['key']}`", "–"])
            if ev in _evs(s.get("failsOn")):
                rows.append([f["key"], f"fails step `{s['key']}`", "–"])
    owner = [m.upper() for m, e, _ in specs.event_catalogue() if e == ev]
    print(f"`{ev}` is published by {', '.join(owner) or 'NO MODULE in FRAMEWORK 6 (check the name)'}.\n")
    print(specs.table(rows, ["Flow", "Effect", "Condition"]) if rows else "No flow reacts to it.")


def cmd_check(_: list[str]) -> None:
    mods = specs.load_modules()
    data = _flows()
    events = {e for _, e, _ in specs.event_catalogue()}
    problems: list[list[str]] = []
    for name, lk in (data.get("lookups") or {}).items():
        mid, op_id = lk["query"].split(".", 1)
        ok = mid in mods and any(o.operation_id == op_id and o.is_query and o.method == "GET"
                                 for o in mods[mid].operations)
        if not ok:
            problems.append(["lookups", name, f"query {lk['query']} is not a GET /internal operation of the spec"])
    for f in data["flows"]:
        seen: list[str] = []
        for ev in [f["trigger"]["event"], *(f.get("endOn") or [])]:
            if ev not in events:
                problems.append([f["key"], "trigger/endOn", f"event {ev} is not in FRAMEWORK 6"])
        for s in f["steps"]:
            mid, step = s["call"].split(".", 1)
            if mid not in mods or not any(o.path == f"/steps/{step}" for o in mods[mid].operations):
                problems.append([f["key"], s["key"], f"step {s['call']} is not a /steps/ path of {mid.upper()}"])
            for ev in [s.get("waitFor"), *_evs(s.get("completesOn")), *_evs(s.get("failsOn"))]:
                if ev and ev not in events:
                    problems.append([f["key"], s["key"], f"event {ev} is not in FRAMEWORK 6"])
            if s.get("lookup") and s["lookup"] not in (data.get("lookups") or {}):
                problems.append([f["key"], s["key"], f"lookup {s['lookup']} is not declared"])
            for v in _leaves(s.get("input")):
                if isinstance(v, str) and v.startswith("steps."):
                    ref = v.split(".")[1]
                    if ref not in seen:
                        problems.append([f["key"], s["key"], f"input {v} refers to a step that is not earlier"])
            seen.append(s["key"])
    if problems:
        print(specs.table(problems, ["Flow", "Where", "Problem"]))
        sys.exit(1)
    print(f"OK: {len(data['flows'])} flows, {sum(len(f['steps']) for f in data['flows'])} steps, "
          f"{len(data.get('lookups') or {})} lookups match the specs and the event catalogue.")


def _leaves(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from _leaves(x)
    elif isinstance(v, list):
        for x in v:
            yield from _leaves(x)
    else:
        yield v


COMMANDS = {"list": cmd_list, "show": cmd_show, "module": cmd_module, "event": cmd_event, "check": cmd_check}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help") else 2)
    COMMANDS[sys.argv[1]](sys.argv[2:])
