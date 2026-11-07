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
"""Map the module folders of this installation against the spec, statically (nothing is imported or run).

Usage: module-map.py [module] [--strict]

  (no module)   one row per module of the spec: kind (team, stand-in, provided, no folder), steps and
                queries the folder implements itself, routes outside the spec, tests, OPEN-QUESTIONS.md,
                imports that break the call convention
  <module>      the details for one module: every step and query of the spec and where it is answered,
                every route of router.py checked against openapi.yaml, configuration variables read in
                code that section 4 of the README does not name, imports of other modules' internals
  --strict      exit 1 when a team module has a finding (for a pre-push hook or CI)

The rules come from AGENTS.md (call convention, rules 1, 4, 6) and the module structure of README.md.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the repository free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portal-spec-sources" / "scripts"))
import specs  # noqa: E402

ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}
ENV_RX = re.compile(r"""os\.(?:environ\.get\(|getenv\(|environ\[)\s*["']([A-Z][A-Z0-9_]+)["']""")
IFACE = "interface.py"
SCAFFOLD_ENV = {"SETTINGS_FILE", "BASE_URL", "IAM_URL", "IAM_REALM", "MODULE_URLS", "MODULE_URLS_DEFAULT",
                "TEST_TOOLS", "SPEC_DIR", "FLOWS_FILE", "SSE_REPLAY_SIZE", "SSE_HEARTBEAT_SECONDS"}


def _parse(f: Path) -> ast.Module | None:
    try:
        return ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
    except (OSError, SyntaxError):
        return None


def _flag(tree: ast.Module | None, name: str) -> bool:
    for node in tree.body if tree else []:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return isinstance(node.value, ast.Constant) and node.value.value is True
    return False


def _functions(tree: ast.Module | None) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in (tree.body if tree else []) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _routes(tree: ast.Module | None) -> list[tuple[str, str, int]]:
    out = []
    for node in ast.walk(tree) if tree else []:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ROUTE_METHODS
                    and isinstance(d.func.value, ast.Name) and d.func.value.id == "router"
                    and d.args and isinstance(d.args[0], ast.Constant)):
                out.append((d.func.attr.upper(), d.args[0].value, d.lineno))
    return out


def _bad_imports(folder: Path, pkg: str) -> list[tuple[str, int, str]]:
    """Imports of another module's internals (anything but modules.<other>.interface)."""
    out = []
    for f in sorted(folder.rglob("*.py")):
        tree = _parse(f)
        for node in ast.walk(tree) if tree else []:
            names = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names if node.module == "modules"]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            for name in names:
                parts = name.split(".")
                if parts[0] != "modules" or len(parts) < 2 or parts[1] == pkg:
                    continue
                if len(parts) == 2 or parts[2] != "interface":
                    out.append((str(f), node.lineno, name))
    return out


def _env_names(folder: Path) -> dict[str, tuple[str, int]]:
    found = {}
    for f in sorted(folder.rglob("*.py")):
        for n, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in ENV_RX.finditer(ln):
                found.setdefault(m.group(1), (str(f), n))
    return found


def _section4_vars(mod: specs.Module) -> set[str]:
    sec = specs.readme_section(mod.readme(), "4")
    return set(re.findall(r"`([A-Z][A-Z0-9_]{2,})`", sec))


def analyse(root: Path, mod: specs.Module) -> dict:
    pkg = mod.id.replace("-", "_")
    folder = root / "modules" / pkg
    res = {"id": mod.id, "folder": folder, "exists": folder.is_dir(), "kind": "no folder", "findings": [],
           "steps": [], "queries": [], "routes": [], "tests": sorted((root / "tests").glob(f"test_{pkg}_*.py"))}
    if not folder.is_dir():
        return res
    rtree, itree = _parse(folder / "router.py"), _parse(folder / IFACE)
    res["kind"] = "team"
    if _flag(rtree, "STANDIN"):
        res["kind"] = "stand-in"
    elif _flag(rtree, "PROVIDED"):
        res["kind"] = "provided"
    funcs = _functions(itree)
    fallback = itree is not None and "missing_interface" in (folder / IFACE).read_text(encoding="utf-8")
    if itree is None:
        res["findings"].append(("blocker", "interface.py is missing or does not parse", "AGENTS.md call convention 1"))
    for op in mod.operations:
        if not (op.is_step or op.is_query):
            continue
        fn = funcs.get(op.function_name)
        where = "own code" if fn else "stand-in fallback"
        if not fn and not fallback:
            where = "MISSING"
        (res["steps"] if op.is_step else res["queries"]).append((op, where))
        if fn and op.is_step:
            a = fn.args
            if len(a.args) + len(a.posonlyargs) != 1:
                res["findings"].append(("high", f"step function {op.function_name}() must take exactly one argument "
                                                f"(input: dict)", "AGENTS.md call convention 3"))
        if not fn and not fallback:
            res["findings"].append(("blocker", f"{op.function_name}() missing in interface.py and no "
                                               "`__getattr__ = standin.missing_interface(MODULE)` fallback",
                                    "README module structure 8"))
    for method, path, line in _routes(rtree):
        ok = any(o.matches(method, path) for o in mod.operations)
        res["routes"].append((method, path, line, ok))
        if not ok:
            res["findings"].append(("high", f"route {method} {path} (router.py:{line}) is not in openapi.yaml",
                                    "AGENTS.md rule 3"))
    if res["kind"] == "team" and "reset" not in _functions(rtree):
        res["findings"].append(("high", "router.py has no reset()", "README: how a team replaces its module 2"))
    for f, line, name in _bad_imports(folder, pkg):
        res["findings"].append(("blocker", f"{Path(f).relative_to(root)}:{line} imports {name}; import only "
                                           "modules.<id>.interface", "AGENTS.md call convention 1"))
    allowed = _section4_vars(mod) | SCAFFOLD_ENV
    for name, (f, line) in _env_names(folder).items():
        if name not in allowed and not name.endswith("_URL"):
            res["findings"].append(("medium", f"{Path(f).relative_to(root)}:{line} reads {name}, which section 4 "
                                              f"of the {mod.id.upper()} README does not name", "AGENTS.md rule 6"))
        if name.endswith("_URL") and re.fullmatch(r"C\d+_M\d+_URL", name):
            res["findings"].append(("medium", f"{Path(f).relative_to(root)}:{line} reads the neighbour address "
                                              f"{name} itself; portal_common.neighbours resolves it", "AGENTS.md rule 6"))
    if res["kind"] == "team" and not (folder / "OPEN-QUESTIONS.md").is_file():
        res["findings"].append(("low", "modules/%s/OPEN-QUESTIONS.md is missing" % pkg, "AGENTS.md rule 10, DoD 4"))
    if res["kind"] == "team" and not res["tests"]:
        res["findings"].append(("high", f"no tests/test_{pkg}_*.py", "AGENTS.md definition of done 1"))
    return res


def overview(root: Path, mods: dict[str, specs.Module]) -> list[dict]:
    rows, results = [], []
    for mod in mods.values():
        if not mod.base_path or not mod.base_path.startswith("/api/"):
            continue  # C2-M5 (Keycloak) and C5-M1 (standards) are not module folders
        r = analyse(root, mod)
        results.append(r)
        own = lambda lst: f"{sum(w == 'own code' for _, w in lst)}/{len(lst)}"  # noqa: E731
        rows.append([mod.id.upper(), r["kind"], own(r["steps"]), own(r["queries"]),
                     f"{sum(ok for *_, ok in r['routes'])}/{len(r['routes'])}", len(r["tests"]),
                     "yes" if (r["folder"] / "OPEN-QUESTIONS.md").is_file() else "–",
                     len(r["findings"]) if r["kind"] == "team" else (len(r["findings"]) or "–")])
    print(specs.table(rows, ["Module", "Kind", "Steps (own)", "Queries (own)", "Routes in spec", "Tests",
                             "OPEN-QUESTIONS", "Findings"]))
    print("\nKinds come from router.py (`STANDIN = True`, `PROVIDED = True`, else team). Details: module-map.py <module>.")
    return results


def detail(root: Path, mod: specs.Module) -> dict:
    r = analyse(root, mod)
    print(f"{mod.title}: modules/{mod.id.replace('-', '_')}/ is **{r['kind']}**\n")
    if not r["exists"]:
        print("No folder: the scaffold mounts the spec-driven fallback (steps DONE, everything else 501).")
        return r
    print(specs.table([[ "step" if op.is_step else "query", op.path, op.function_name, w] for op, w in
                       r["steps"] + r["queries"]], ["Kind", "Spec path", IFACE, "Answered by"]))
    print()
    print(specs.table([[m, p, f"router.py:{ln}", "yes" if ok else "NO"] for m, p, ln, ok in r["routes"]],
                      ["Method", "Route", "Where", "In openapi.yaml"]))
    spec_only = [o for o in mod.operations if not o.is_step and not o.is_query
                 and not any(o.matches(m, p) for m, p, _, _ in r["routes"])]
    if spec_only:
        print(f"\n{len(spec_only)} operations of the spec have no route here; the scaffold answers them "
              "(steps and queries via interface.py, everything else 501):")
        print(", ".join(f"{o.method} {o.path}" for o in spec_only))
    print(f"\nTests: {', '.join(str(t.relative_to(root)) for t in r['tests']) or 'none'}")
    print("\nFindings:\n")
    order = ["blocker", "high", "medium", "low"]
    found = sorted(r["findings"], key=lambda f: order.index(f[0]))
    print(specs.table([list(f) for f in found], ["Severity", "Finding", "Rule"]) if found else "none")
    return r


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    root = specs.repo_root()
    if not (root / "modules").is_dir() or not (root / "portal_common").is_dir():
        print(f"{root} has no modules/ and portal_common/: this checkout does not contain the scaffold yet "
              "(it arrives with the initial contribution, tx-arena-events:feature/hackathon-scaffold).")
        return 2
    mods = specs.load_modules()
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    results = [detail(root, specs.get_module(args[0], mods))] if args else overview(root, mods)
    bad = [r for r in results if r["kind"] == "team" and any(s in ("blocker", "high") for s, *_ in r["findings"])]
    return 1 if strict and bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
