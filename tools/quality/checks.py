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
"""The checks of the quality gate. Each returns findings; `gate.py` counts them per area and check.

| Check | Source | Rule |
|---|---|---|
| `ruff` | `ruff check` with `[tool.ruff]` of pyproject.toml | style, bugs, imports, complexity <= 10 |
| `mypy` | `mypy` with `[tool.mypy]` of pyproject.toml | type hints required, types consistent |
| `file-size` | line count | a Python file has at most `FILE_LINES` lines |
| `function-size` | syntax tree | a function has at most `FUNCTION_LINES` lines |
| `layers`, `neighbours`, `problems` | `layers.py` | the layers inside a module (ADR-0003) |
| `module-map` | `module-map` skill | call convention, routes and configuration names against the spec |
| `http-body`, `http-route`, `contract` | `http_layer.py` | FastAPI: typed bodies and responses, spec operationIds |
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import ModuleType

from tools.quality import http_layer, layers

ROOT = Path(__file__).resolve().parents[2]
FILE_LINES = 500
FUNCTION_LINES = 60
CODE_AREAS = ("portal_common", "scaffold", "tools", "controllers", "iam")
ROOT_FILES = ("demo.py", "check.py")
MODULE_MAP = ROOT / ".claude" / "skills" / "module-map" / "scripts" / "module-map.py"
_MYPY_LINE = re.compile(r"^(?P<path>[^:]+\.py):(?P<line>\d+): error: (?P<message>.*)$")


@dataclass(frozen=True, slots=True)
class Finding:
    area: str
    check: str
    location: str       # path:line
    message: str


def area_of(path: PurePosixPath) -> str | None:
    """`modules/<id>`, a top-level code folder, `tests` or `root`; None for files the gate does not check."""
    parts = path.parts
    if not parts or path.suffix != ".py":
        return None
    if parts[0] == "modules" and len(parts) > 2:
        return f"modules/{parts[1]}"
    if parts[0] in CODE_AREAS or parts[0] == "tests":
        return parts[0]
    if len(parts) == 1 and parts[0] in ROOT_FILES:
        return "root"
    return None


def area_paths(area: str) -> list[str]:
    return list(ROOT_FILES) if area == "root" else [area]


def all_areas() -> list[str]:
    modules = sorted(f"modules/{p.name}" for p in (ROOT / "modules").iterdir()
                     if p.is_dir() and not p.name.startswith(("_", ".")))
    return [*modules, *CODE_AREAS, "tests", "root"]


def python_files(areas: Iterable[str]) -> list[PurePosixPath]:
    files: list[PurePosixPath] = []
    for area in areas:
        for name in area_paths(area):
            target = ROOT / name
            found = [target] if target.is_file() else sorted(target.rglob("*.py"))
            files += [PurePosixPath(p.relative_to(ROOT).as_posix()) for p in found if "__pycache__" not in p.parts]
    return files


def _run(command: list[str]) -> str:
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return done.stdout


def ruff(areas: list[str]) -> list[Finding]:
    paths = [p for area in areas for p in area_paths(area)]
    raw = _run([sys.executable, "-m", "ruff", "check", "--output-format", "json", "--exit-zero", *paths])
    findings = []
    for item in json.loads(raw or "[]"):
        path = PurePosixPath(Path(item["filename"]).resolve().relative_to(ROOT).as_posix())
        area = area_of(path)
        if area is not None:
            line = item["location"]["row"]
            findings.append(Finding(area, "ruff", f"{path}:{line}", f"{item['code']} {item['message']}"))
    return findings


def mypy(areas: list[str]) -> list[Finding]:
    code_areas = [a for a in areas if a != "tests"]
    if not code_areas:
        return []
    paths = [p for area in code_areas for p in area_paths(area)]
    raw = _run([sys.executable, "-m", "mypy", "--no-error-summary", "--no-color-output", *paths])
    findings = []
    for text in raw.splitlines():
        match = _MYPY_LINE.match(text)
        if not match:
            continue
        path = PurePosixPath(match["path"])
        area = area_of(path)
        if area in code_areas:
            findings.append(Finding(area, "mypy", f"{path}:{match['line']}", match["message"]))
    return findings


def sizes_and_layers(areas: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in python_files(a for a in areas if a != "tests"):
        area = area_of(path)
        if area is None:
            continue
        source = (ROOT / path).read_text(encoding="utf-8")
        lines = source.count("\n")
        if lines > FILE_LINES:
            findings.append(Finding(area, "file-size", f"{path}:1", f"{lines} lines > {FILE_LINES}"))
        findings += _long_functions(area, path, source)
        findings += [Finding(area, v.check, f"{path}:{v.line}", v.message) for v in layers.check_file(path, source)]
    return findings


def _long_functions(area: str, path: PurePosixPath, source: str) -> list[Finding]:
    findings = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.end_lineno is not None:
            length = node.end_lineno - node.lineno + 1
            if length > FUNCTION_LINES:
                findings.append(Finding(area, "function-size", f"{path}:{node.lineno}",
                                        f"{node.name} has {length} lines > {FUNCTION_LINES}"))
    return findings


def _load_module_map() -> ModuleType | None:
    if not MODULE_MAP.is_file():
        return None
    spec = importlib.util.spec_from_file_location("module_map", MODULE_MAP)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module_map(areas: list[str]) -> list[Finding]:
    """Findings of the module-map skill for the team modules among `areas` (needs the spec clone in spec/)."""
    wanted = {a.split("/", 1)[1] for a in areas if a.startswith("modules/")}
    if not wanted:
        return []
    mm = _load_module_map()
    if mm is None:
        return []
    findings = []
    for mod in mm.specs.load_modules().values():
        package = mod.id.replace("-", "_")
        if package not in wanted:
            continue
        result = mm.analyse(ROOT, mod)
        if result["kind"] != "team":
            continue
        findings += [Finding(f"modules/{package}", "module-map", f"modules/{package}", f"{severity}: {text}")
                     for severity, text, *_ in result["findings"]]
    return findings


def _team_module(package: str) -> bool:
    router = ROOT / "modules" / package / "router.py"
    text = router.read_text(encoding="utf-8") if router.is_file() else ""
    return bool(text) and "STANDIN = True" not in text and "PROVIDED = True" not in text


def http_findings(areas: list[str]) -> list[Finding]:
    """FastAPI conventions and the contract against the spec, for team modules only (ADR-0003)."""
    findings: list[Finding] = []
    for area in areas:
        package = area.removeprefix("modules/")
        if not area.startswith("modules/") or not _team_module(package):
            continue
        for path in python_files([area]):
            source = (ROOT / path).read_text(encoding="utf-8")
            if "@" in source and "router" in source:
                findings += [Finding(area, f.check, f"{path}:{f.line}", f.message)
                             for f in http_layer.check_router(path, source)]
        contract = http_layer.check_contract(package.replace("_", "-"))
        findings += [Finding(area, f.check, area, f.message) for f in contract]
    return findings


def collect(areas: list[str]) -> list[Finding]:
    return [*ruff(areas), *mypy(areas), *sizes_and_layers(areas), *module_map(areas), *http_findings(areas)]
