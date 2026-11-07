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
"""Check the seam between the UI and the service: what the frontend expects against what the backend
spec defines. Read-only; works from either repository.

Usage: seam-check.py <command> [--ui <path>]

  summary        all checks below that can run here, with a verdict per seam
  casing         JSON field names of the backend schemas (camelCase / snake_case) against the frontend rule
  errors         error format: Problem Details and 400 of the backend against what the frontend expects
  assumptions    every API call the frontend spec sketches (METHOD /path, client.GET('/path')), checked
                 against the backend spec: exists, or the closest operation
  vendored       the UI's specs/<module>/openapi.yaml copies against the backend spec: missing, extra
                 or changed operations, permissions and schema fields (needs the UI repository)
  ui-calls       the paths the UI code calls (client.GET/POST/... and '/api/...' literals) against the
                 backend spec (needs the UI repository)

--ui <path>: the dataspace-mgm-ui checkout; default: this repository when it is the UI, else ../dataspace-mgm-ui.
Exit code 1 when `vendored` or `ui-calls` find a call or operation that the backend spec does not have.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True  # keep the repository free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portal-spec-sources" / "scripts"))
import specs  # noqa: E402

CALL_MD = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_{}<>/.:\-]+)")
CALL_TS = re.compile(r"\.(GET|POST|PUT|PATCH|DELETE)\(\s*['\"`](/[^'\"`]+)['\"`]")
API_LITERAL = re.compile(r"['\"`](/api/[A-Za-z0-9_{}$/.\-]+)['\"`]")
CAMEL = re.compile(r"^[a-z][a-z0-9]*(?:[A-Z][a-z0-9]*)+$")
SNAKE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
NO_SEAM = ("/me", "/config", "/auth/", "/repos/")  # BFF endpoints of the UI's server part, GitHub API
# Names the frontend spec uses for backend modules (`/api/registration/...`) -> module id of the backend spec
ALIASES = {"registration": "c1-m2", "review": "c1-m3", "users": "c2-m2", "technical-users": "c2-m3",
           "companies": "c3-m1", "company": "c3-m1", "credentials": "c4-m1", "wallet": "c4-m2", "ebw": "c5-m1",
           "connectors": "c6-m1", "apps": "c8-m1", "marketplace": "c8-m1", "offers": "c8-m1",
           "services": "c8-m1", "subscriptions": "c10-m1", "notifications": "c11-m1", "processes": "c12-m1",
           "process": "c12-m1"}
GENERIC = {"api", "id", "the"}


def ui_root(argv: list[str]) -> Path | None:
    if "--ui" in argv:
        p = Path(argv[argv.index("--ui") + 1]).expanduser().resolve()
        return p if p.is_dir() else None
    root = specs.repo_root()
    if (root / ".tractusx").is_file() and "dataspace-mgm-ui" in (root / ".tractusx").read_text(encoding="utf-8") \
            and not (root / "portal_common").is_dir() and (root / "package.json").is_file():
        return root
    for cand in (root.parent / "dataspace-mgm-ui", root.parent.parent / "dataspace-mgm-ui" / "main"):
        if (cand / "package.json").is_file():
            return cand
    return None


def _props(schema, out: list[str]) -> None:
    if isinstance(schema, dict):
        for k, v in (schema.get("properties") or {}).items():
            out.append(k)
            _props(v, out)
        for key in ("items", "additionalProperties"):
            _props(schema.get(key), out)
        for key in ("allOf", "oneOf", "anyOf"):
            for s in schema.get(key) or []:
                _props(s, out)


def field_names(doc: dict) -> list[str]:
    out: list[str] = []
    for s in ((doc.get("components") or {}).get("schemas") or {}).values():
        _props(s, out)
    return out


def cmd_casing(_: list[str]) -> list[str]:
    rows, total = [], Counter()
    for m in specs.load_modules().values():
        if not m.document:
            continue
        c = Counter("camel" if CAMEL.match(n) else "snake" if SNAKE.match(n) else "single" for n in field_names(m.document))
        total += c
        snake = sorted({n for n in field_names(m.document) if SNAKE.match(n)})
        rows.append([m.id.upper(), c["camel"], c["snake"], c["single"], ", ".join(snake[:6]) or "–"])
    print("JSON field names in components.schemas of the backend spec:\n")
    print(specs.table(rows, ["Module", "camelCase", "snake_case", "one word", "snake_case examples"]))
    fe = specs.find_spec("frontend", required=False)
    fe_rule = ""
    if fe and (fe / "architecture" / "01-principles.md").is_file():
        for ln in (fe / "architecture" / "01-principles.md").read_text(encoding="utf-8").splitlines():
            if "API JSON" in ln:
                fe_rule = ln.strip()
    print("\nBackend rule: FRAMEWORK 4.1 \"JSON fields in camelCase\".")
    if fe_rule:
        print(f"Frontend rule: architecture/01-principles.md {fe_rule}")
    verdict = []
    if total["camel"] > total["snake"] and "snake_case" in fe_rule:
        verdict.append("CASING: the backend spec is camelCase, the frontend spec expects snake_case DTOs. The "
                       "generated DTO types follow the vendored openapi.yaml (camelCase); the mappers in the core "
                       "packages must map camelCase, and the MSW mocks must answer camelCase.")
    for v in verdict:
        print("\n" + v)
    return verdict


def cmd_errors(_: list[str]) -> list[str]:
    be = specs.find_spec("backend")
    fw = specs.readme_section((be / "FRAMEWORK.md").read_text(encoding="utf-8"), "4.5").strip()
    print("Backend (FRAMEWORK 4.5):\n" + "\n".join("> " + ln for ln in fw.splitlines() if ln) + "\n")
    print("Scaffold rule (AGENTS.md rule 4, portal_common.problems): validation errors are 400, never 422.\n")
    fe = specs.find_spec("frontend", required=False)
    hits = []
    if fe:
        for f in sorted(fe.rglob("*.md")):
            for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\b422\b|error \*\*keys\*\*|error keys", ln):
                    hits.append([f"{f.relative_to(fe)}:{n}", ln.strip()[:150]])
    if hits:
        print("Frontend spec:\n")
        print(specs.table(hits, ["Where", "Text"]))
        print("\nERRORS: the frontend expects 422 with translatable error keys; the backend answers 400 Problem "
              "Details (`type` urn:<module>:problem:<name>, `errors`/`fields` per module section 12). Map the "
              "`type` suffix to the i18n key in the core package adapter (ensureOk).")
        return ["ERRORS: 422 + keys expected by the UI, 400 Problem Details defined by the backend"]
    return []


def _base(m) -> str:
    return (m.base_path or "").rstrip("/")


def _check_path(method: str, path: str, mods) -> tuple[str, str]:
    if path.startswith(NO_SEAM):
        return "BFF", "endpoint of the server part of the UI (BFF), not of a backend module"
    hits = specs.find_operation(method or None, path, mods)
    if hits:
        op = hits[0]
        return "ok", f"{op.module.upper()} {op.operation_id} ({op.permission}, {op.scope})"
    segs = [s for s in path.strip("/").split("/") if s]
    candidates = list(mods)  # modules to search
    rels = ["/" + "/".join(segs)]
    if segs and segs[0] == "api" and len(segs) > 1:
        alias = ALIASES.get(segs[1].lower())
        if alias:
            candidates = [alias]
            rels = ["/" + "/".join(segs[2:]), "/" + "/".join(segs[1:])]
    same, other = [], []  # same path under the right base, or the right path with another method
    for mid in candidates:
        m = mods.get(mid)
        for rel in rels:
            for op in (m.operations if m else []):
                if op.matches(None, rel):
                    full = f"{op.method} {_base(m)}{op.path} ({op.operation_id})"
                    (same if not method or op.method == method.upper() else other).append(full)
    if same:
        return "MISSING", f"path differs: backend has {same[0]}"
    if other:
        return "MISSING", f"method differs: backend has {other[0]}"
    words = {w.lower() for s in segs for w in re.split(r"[-_{}]", s) if len(w) > 2} - GENERIC
    best = []
    for mid in candidates:
        m = mods.get(mid)
        for op in (m.operations if m else []):
            if op.is_step or op.is_query:
                continue  # the UI never calls steps or queries
            op_words = {w.lower() for w in re.split(r"[-_/{}]", op.path) if len(w) > 2} - GENERIC
            score = len(words & op_words) - 0.25 * len(op_words - words) + (0.5 if op.method == method.upper() else 0)
            if words & op_words:
                best.append((score, f"{op.method} {_base(m)}{op.path}"))
    best.sort(reverse=True)
    where = f" in {candidates[0].upper()}" if len(candidates) == 1 else ""
    return "MISSING", (f"closest{where}: " + "; ".join(b for _, b in best[:2])) if best else "no similar operation"


def cmd_assumptions(_: list[str]) -> list[str]:
    fe = specs.find_spec("frontend", required=False)
    if not fe:
        print("Frontend spec not found; run: portal-spec-sources/scripts/spec-src.py sync")
        return []
    mods = specs.load_modules()
    seen, rows = set(), []
    for f in sorted(fe.rglob("*.md")):
        for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for rx in (CALL_MD, CALL_TS):
                for method, path in rx.findall(ln):
                    path = path.split("?")[0].rstrip(".,")
                    if (method, path) in seen or not path.startswith(("/api", "/me", "/config", "/auth", "/applications")):
                        continue
                    seen.add((method, path))
                    status, note = _check_path(method, path, mods)
                    rows.append([status, f"{method} {path}", f"{f.relative_to(fe)}:{n}", note])
    rows.sort(key=lambda r: ["MISSING", "BFF", "ok"].index(r[0]))
    print("API calls sketched in the frontend spec, checked against the backend spec:\n")
    print(specs.table(rows, ["Status", "Call", "Where", "Backend"]))
    missing = [r for r in rows if r[0] == "MISSING"]
    out = []
    if missing:
        out.append(f"PATHS: {len(missing)} call(s) of the frontend spec are not in the backend spec; the backend "
                   "base path is /api/<module id> (FRAMEWORK 4.1), e.g. /api/c1-m2, /api/c12-m1.")
    if any(r[0] == "BFF" for r in rows):
        out.append("BFF: /me, /config and /auth/* belong to the server part of the UI; no backend module defines "
                   "them. The BFF holds the session, calls the modules with the person's token and opens the SSE "
                   "streams (FRAMEWORK 5.2 step 2, C12-M1 7.6).")
    for v in out:
        print("\n" + v)
    return out


def _vendored(ui: Path) -> list[tuple[str, Path, dict]]:
    out = []
    for f in sorted((ui / "specs").glob("*/openapi.yaml")):
        doc = specs.yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        url = ((doc.get("servers") or [{}])[0]).get("url", "")
        m = re.search(r"c\d+-m\d+", url) or re.search(r"[Cc]\d+-[Mm]\d+", (doc.get("info") or {}).get("title", ""))
        out.append((specs.module_id(m.group(0)) if m else "", f, doc))
    return out


def cmd_vendored(argv: list[str]) -> list[str]:
    ui = ui_root(argv)
    if not ui:
        print("UI repository not found (use --ui <path>); skipped.")
        return []
    mods = specs.load_modules()
    copies = _vendored(ui)
    if not copies:
        print(f"{ui}/specs has no <module>/openapi.yaml yet; nothing to compare.")
        return []
    rows, bad = [], 0
    for mid, f, doc in copies:
        rel = f.relative_to(ui)
        if mid not in mods:
            rows.append(["?", str(rel), "cannot tell the module (servers url /api/<module> or C<n>-M<n> in the title)"])
            bad += 1
            continue
        be = mods[mid]
        ops_ui = {(m.upper(), p): op for p, item in (doc.get("paths") or {}).items() for m, op in (item or {}).items()
                  if m in specs.METHODS and isinstance(op, dict)}
        ops_be = {(o.method, o.path): o for o in be.operations}
        for key in sorted(set(ops_be) - set(ops_ui)):
            rows.append([mid.upper(), str(rel), f"missing in the copy: {key[0]} {key[1]}"])
        for key in sorted(set(ops_ui) - set(ops_be)):
            rows.append([mid.upper(), str(rel), f"NOT IN THE BACKEND SPEC: {key[0]} {key[1]}"])
            bad += 1
        for key in sorted(set(ops_ui) & set(ops_be)):
            a, b = ops_ui[key], ops_be[key]
            if a.get("x-permission") != b.permission:
                rows.append([mid.upper(), str(rel), f"{key[0]} {key[1]}: permission {a.get('x-permission')} → {b.permission}"])
        f_ui, f_be = set(field_names(doc)), set(field_names(be.document))
        if f_be - f_ui:
            rows.append([mid.upper(), str(rel), "fields only in the backend spec: " + ", ".join(sorted(f_be - f_ui)[:12])])
        if f_ui - f_be:
            rows.append([mid.upper(), str(rel), "FIELDS NOT IN THE BACKEND SPEC: " + ", ".join(sorted(f_ui - f_be)[:12])])
            bad += 1
    be_dir = specs.find_spec("backend")
    print(f"Vendored specs in {ui}/specs against the backend spec @ {specs.git_rev(be_dir)}:\n")
    print(specs.table(rows, ["Module", "Copy", "Difference"]) if rows else "All copies match the backend spec.")
    if rows:
        print("\nRefresh a copy from the backend spec, then `npx nx run <module>-core:generate-api` and "
              "`check-api` (frontend architecture 04, 13 #19).")
    return [f"VENDORED: {bad} difference(s) the backend does not have"] if bad else []


def cmd_ui_calls(argv: list[str]) -> list[str]:
    ui = ui_root(argv)
    if not ui:
        print("UI repository not found (use --ui <path>); skipped.")
        return []
    mods = specs.load_modules()
    base_of = {}
    for mid, f, _ in _vendored(ui):
        if mid in mods:
            base_of[f.parent.name] = mods[mid].base_path
    rows, bad = [], 0
    for f in sorted(ui.rglob("*.ts*")):
        if any(p in f.parts for p in ("node_modules", "dist", "generated", ".nx")) or f.suffix not in (".ts", ".tsx"):
            continue
        pkg = next((p[:-5] for p in f.parts if p.endswith("-core")), None)
        text = f.read_text(encoding="utf-8", errors="replace")
        for n, ln in enumerate(text.splitlines(), 1):
            calls = [(m, p) for m, p in CALL_TS.findall(ln)] + [(None, p) for p in API_LITERAL.findall(ln)]
            for method, path in calls:
                path = re.sub(r"\$\{[^}]+\}", "{x}", path.split("?")[0])
                full = path if path.startswith("/api/") or not pkg or pkg not in base_of else base_of[pkg] + path
                status, note = _check_path(method or "", full, mods) if full.startswith(("/api/",) + NO_SEAM) \
                    else ("?", f"relative path in {pkg or 'no core package'}; no vendored spec tells the module")
                if status == "MISSING":
                    bad += 1
                rows.append([status, f"{method or '*'} {full}", f"{f.relative_to(ui)}:{n}", note])
    rows.sort(key=lambda r: ["MISSING", "?", "BFF", "ok"].index(r[0]))
    print(f"Calls in the UI code ({ui}) against the backend spec:\n")
    print(specs.table(rows, ["Status", "Call", "Where", "Backend"]) if rows else "No API calls found in the UI code.")
    return [f"UI-CALLS: {bad} call(s) of the UI code are not in the backend spec"] if bad else []


def cmd_summary(argv: list[str]) -> list[str]:
    verdicts = []
    for name, fn in (("casing", cmd_casing), ("errors", cmd_errors), ("assumptions", cmd_assumptions),
                     ("vendored", cmd_vendored), ("ui-calls", cmd_ui_calls)):
        print(f"\n## {name}\n")
        verdicts += fn(argv)
    print("\n## Verdict\n")
    print("\n".join(f"- {v}" for v in verdicts) if verdicts else "- No seam found between the UI and the backend spec.")
    return verdicts


COMMANDS = {"summary": cmd_summary, "casing": cmd_casing, "errors": cmd_errors, "assumptions": cmd_assumptions,
            "vendored": cmd_vendored, "ui-calls": cmd_ui_calls}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help") else 2)
    result = COMMANDS[sys.argv[1]](sys.argv[2:])
    sys.exit(1 if sys.argv[1] in ("vendored", "ui-calls") and result else 0)
