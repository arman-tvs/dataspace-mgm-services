#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
"""The layers inside a module (ADR-0003) and the rules between them, checked on the syntax tree.

A file's layer comes from its name below `modules/<id>/`; files without a layer name are not checked:

    router.py  schemas.py  interface.py  service.py | services/  store*.py | repository*.py
    gateways.py  adapters/  errors.py  config.py

Rules (imports point down only, ADR-0003):

- `layers`: an import of a module-internal layer the importing layer may not use (table `FORBIDDEN`),
  or of `fastapi` / `pydantic` from service, store, gateways or errors (HTTP stays at the edge);
- `neighbours`: `portal_common.neighbours` is imported outside `gateways.py` (gateway per neighbour);
- `problems`: a `Problem(...)` is built outside `errors.py` (error factories, README section 12).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import PurePosixPath

FORBIDDEN: dict[str, set[str]] = {
    "router": {"service", "store", "gateways", "adapter"},
    "schemas": {"router", "interface", "service", "store", "gateways", "adapter"},
    "interface": {"router", "store", "gateways", "adapter"},
    "service": {"router", "interface"},
    "store": {"router", "interface", "service", "gateways", "adapter"},
    "gateways": {"router", "interface", "service", "store", "adapter"},
    "adapter": {"router", "interface", "service", "store", "gateways"},
    "errors": {"router", "schemas", "interface", "service", "store", "gateways", "adapter"},
}
NO_HTTP = {"service", "store", "gateways", "errors"}
HTTP_PACKAGES = ("fastapi", "pydantic", "starlette")


@dataclass(frozen=True, slots=True)
class Violation:
    check: str      # layers | neighbours | problems
    line: int
    message: str


def layer_of(parts: tuple[str, ...]) -> str | None:
    """Layer of a module path below `modules/<id>/`, e.g. ("services", "steps") -> "service"."""
    if not parts:
        return None
    head = parts[0].removesuffix(".py")
    names = {"router": "router", "schemas": "schemas", "interface": "interface", "service": "service",
             "services": "service", "gateways": "gateways", "adapters": "adapter", "errors": "errors",
             "config": "config"}
    if head in names:
        return names[head]
    if head.startswith(("store", "repository")):
        return "store"
    return None


def _target_parts(node: ast.ImportFrom, here: tuple[str, ...], module_id: str) -> list[tuple[str, ...]]:
    """Module-internal targets of `from ... import ...`, as paths below `modules/<id>/`."""
    if node.level:
        package, up = here[:-1], node.level - 1
        if up > len(package):
            return []       # leaves the module folder: not a layer of this module
        base = package[: len(package) - up]
    elif node.module == f"modules.{module_id}" or (node.module or "").startswith(f"modules.{module_id}."):
        base = ()
    else:
        return []
    prefix = f"modules.{module_id}"
    module = node.module or ""
    if not node.level:
        module = module[len(prefix):].lstrip(".")
    dotted = base + tuple(p for p in module.split(".") if p)
    if module:
        return [dotted]
    return [dotted + (alias.name,) for alias in node.names]


def _imports(tree: ast.AST) -> list[tuple[int, str, ast.ImportFrom | None]]:
    """(line, absolute module name, node for relative or `from` imports) of every import."""
    found: list[tuple[int, str, ast.ImportFrom | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name, None) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            found.append((node.lineno, name, node))
            if name == "portal_common":
                found += [(node.lineno, f"portal_common.{a.name}", None) for a in node.names]
    return found


def _check_import(layer: str, line: int, name: str, node: ast.ImportFrom | None,
                  here: tuple[str, ...], module_id: str) -> list[Violation]:
    out: list[Violation] = []
    if layer in NO_HTTP and name.split(".")[0] in HTTP_PACKAGES:
        out.append(Violation("layers", line, f"{layer} imports {name}: HTTP models stay in router/schemas"))
    if name == "portal_common.neighbours" and here != ("gateways.py",):
        out.append(Violation("neighbours", line, "portal_common.neighbours outside gateways.py"))
    targets = _target_parts(node, here, module_id) if node is not None else []
    for target in targets:
        target_layer = layer_of(target)
        if target_layer in FORBIDDEN.get(layer, set()):
            out.append(Violation("layers", line, f"{layer} imports {'.'.join(target)} ({target_layer})"))
    return out


def _problem_calls(tree: ast.AST) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name == "Problem":
                lines.append(node.lineno)
    return lines


def check_file(path: PurePosixPath, source: str) -> list[Violation]:
    """Violations in `modules/<id>/<file>`; other paths have none."""
    parts = path.parts
    if len(parts) < 3 or parts[0] != "modules":
        return []
    module_id, here = parts[1], tuple(parts[2:])
    tree = ast.parse(source)
    out: list[Violation] = []
    layer = layer_of(here)
    for line, name, node in _imports(tree):
        if layer is not None:
            out += _check_import(layer, line, name, node, here, module_id)
        elif name == "portal_common.neighbours":
            out.append(Violation("neighbours", line, "portal_common.neighbours outside gateways.py"))
    if here != ("errors.py",):
        out += [Violation("problems", line, "Problem(...) outside errors.py") for line in _problem_calls(tree)]
    return out
