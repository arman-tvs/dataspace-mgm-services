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
"""Shared, read-only access to the specs of the Dataspace Management product.

Used by the Dataspace Captain's skill scripts in both repositories (dataspace-mgm-service and
dataspace-mgm-ui). Standard library plus PyYAML only; nothing of the repository is imported or run.

Where the specs are found (first hit wins):

  backend spec   $SPEC_DIR, <repo>/spec (the service convention), <repo>/../portal-backend-spec,
                 $DSM_SPEC_CACHE/portal-backend-spec (default cache ~/.cache/dataspace-mgm/specs)
  frontend spec  $FRONTEND_SPEC_DIR, <repo>/../portal-frontend-spec,
                 $DSM_SPEC_CACHE/portal-frontend-spec

`spec-src.py sync` clones or fast-forwards both into the cache.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the machine
    sys.exit("PyYAML is missing. Run the script with:  uv run --no-project --with pyyaml python3 "
             + " ".join(sys.argv) + "\n(or: python3 -m pip install --user pyyaml)")

REPOS = {
    "backend": "https://github.com/tx-arena-events/portal-backend-spec.git",
    "frontend": "https://github.com/tx-arena-events/portal-frontend-spec.git",
}
METHODS = ("get", "post", "put", "patch", "delete")


# --------------------------------------------------------------------------- locations

def repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parents[4]


def cache_dir() -> Path:
    return Path(os.environ.get("DSM_SPEC_CACHE") or Path.home() / ".cache" / "dataspace-mgm" / "specs")


def _candidates(kind: str) -> list[Path]:
    root = repo_root()
    if kind == "backend":
        env = [os.environ.get("SPEC_DIR")]
        local = [root / "spec", root.parent / "portal-backend-spec"]
        name = "portal-backend-spec"
    else:
        env = [os.environ.get("FRONTEND_SPEC_DIR")]
        local = [root.parent / "portal-frontend-spec"]
        name = "portal-frontend-spec"
    return [Path(p) for p in env if p] + local + [cache_dir() / name]


def find_spec(kind: str = "backend", required: bool = True) -> Path | None:
    marker = "FRAMEWORK.md" if kind == "backend" else "HACKATHON-FRONTEND.md"
    for p in _candidates(kind):
        if (p / marker).is_file():
            return p
    if required:
        sys.exit(f"The {kind} spec was not found. Looked in: "
                 + ", ".join(str(p) for p in _candidates(kind))
                 + "\nFetch it once with:  .agents/skills/portal-spec-sources/scripts/spec-src.py sync")
    return None


def git_rev(path: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(path), "log", "-1", "--format=%h %cs %s"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "(not a git checkout)"


# --------------------------------------------------------------------------- names

def snake_case(name: str) -> str:
    """Same rule as portal_common.spec.snake_case: `create-company` -> `create_company`,
    `getApplicationInternal` -> `get_application_internal`."""
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name)
    return name.replace("-", "_").lower()


def module_id(text: str) -> str:
    """`C3-M1`, `c3_m1`, `C3-M1-CompanyProfile`, `/api/c3-m1` -> `c3-m1`."""
    m = re.search(r"[cC](\d+)[-_][mM](\d+)", text)
    if not m:
        sys.exit(f"Not a module identifier: {text!r} (expected something like c3-m1)")
    return f"c{m.group(1)}-m{m.group(2)}"


# --------------------------------------------------------------------------- model

@dataclass(frozen=True)
class Operation:
    module: str
    method: str
    path: str
    operation_id: str | None
    permission: str | None
    scope: str | None
    tags: tuple[str, ...]
    summary: str | None
    sse: bool

    @property
    def is_step(self) -> bool:
        return self.path.startswith("/steps/")

    @property
    def is_query(self) -> bool:
        return self.path.startswith("/internal/")

    @property
    def function_name(self) -> str | None:
        if self.is_step:
            return snake_case(self.path.removeprefix("/steps/"))
        if self.is_query and self.operation_id:
            return snake_case(self.operation_id)
        return None

    def matches(self, method: str | None, path: str) -> bool:
        if method and method.upper() != self.method:
            return False
        a, b = self.path.strip("/").split("/"), path.strip("/").split("/")
        return len(a) == len(b) and all(
            x == y or (x[:1] == "{" and x[-1:] == "}") for x, y in zip(a, b))


@dataclass
class Module:
    id: str
    folder: Path
    base_path: str | None
    version: str | None
    kind: str | None
    title: str
    document: dict = field(repr=False)
    operations: list[Operation] = field(default_factory=list)

    def readme(self) -> str:
        f = self.folder / "README.md"
        return f.read_text(encoding="utf-8") if f.is_file() else ""


def _readme_meta(text: str) -> tuple[str, str | None, str | None]:
    title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "")
    version = re.search(r"\*\*Version:\*\*\s*([^\n]+)", text)
    kind = re.search(r"\*\*Kind:\*\*\s*([^\n]+)", text)
    return title, version.group(1).strip() if version else None, kind.group(1).strip() if kind else None


def load_modules(spec: Path | None = None) -> dict[str, Module]:
    spec = spec or find_spec("backend")
    out: dict[str, Module] = {}
    for folder in sorted(spec.iterdir(), key=lambda p: [int(x) for x in re.findall(r"\d+", p.name)[:2]] or [999]):
        if not folder.is_dir() or not re.match(r"C\d+-M\d+-", folder.name):
            continue
        mid = module_id(folder.name)
        readme = (folder / "README.md").read_text(encoding="utf-8") if (folder / "README.md").is_file() else ""
        title, version, kind = _readme_meta(readme)
        doc, base = {}, None
        api = folder / "openapi.yaml"
        if api.is_file():
            doc = yaml.safe_load(api.read_text(encoding="utf-8")) or {}
            base = ((doc.get("servers") or [{}])[0]).get("url")
        mod = Module(mid, folder, base, version, kind, title, doc)
        for path, item in (doc.get("paths") or {}).items():
            for method in METHODS:
                op = (item or {}).get(method)
                if not isinstance(op, dict):
                    continue
                content = ((op.get("responses") or {}).get("200") or {}).get("content") or {}
                mod.operations.append(Operation(
                    mid, method.upper(), path, op.get("operationId"), op.get("x-permission"),
                    op.get("x-permission-scope"), tuple(op.get("tags") or ()), op.get("summary"),
                    "text/event-stream" in content or path.endswith("/events")))
        out[mid] = mod
    return out


def get_module(mid: str, modules: dict[str, Module] | None = None) -> Module:
    modules = modules or load_modules()
    mid = module_id(mid)
    if mid not in modules:
        sys.exit(f"Module {mid} is not in the backend spec ({', '.join(modules)})")
    return modules[mid]


def all_operations(modules: dict[str, Module] | None = None) -> list[Operation]:
    modules = modules or load_modules()
    return [op for m in modules.values() for op in m.operations]


def find_operation(method: str | None, full_path: str, modules: dict[str, Module] | None = None) -> list[Operation]:
    """Operations that match `GET /api/c3-m1/companies/123` (base path included) or a path template."""
    modules = modules or load_modules()
    full_path = full_path.split("?", 1)[0]
    hits = []
    for m in modules.values():
        if not m.base_path or not full_path.startswith(m.base_path + "/"):
            continue
        rel = full_path[len(m.base_path):]
        hits += [op for op in m.operations if op.matches(method, rel)]
    return sorted(hits, key=lambda o: o.path.count("{"))  # literal segments win


def readme_section(text: str, number: str) -> str:
    """Section `<number>` of a README: `6` is `## 6.`, `4.5` is `### 4.5`; up to the next heading of
    the same or a higher level. Headings inside fenced code blocks (such as the README outline in
    FRAMEWORK 3) do not count."""
    out, level, fenced = [], 0, False
    want = re.compile(rf"(#{{2,4}})\s+{re.escape(number)}(?:[.\s]|$)")
    for ln in text.splitlines():
        if ln.lstrip().startswith("```"):
            fenced = not fenced
        heading = None if fenced else re.match(r"(#{2,4})\s", ln)
        if heading and level and len(heading.group(1)) <= level:
            break
        if heading and not level:
            m = want.match(ln)
            level = len(m.group(1)) if m else 0
        if level:
            out.append(ln)
    return "\n".join(out)


def event_catalogue(spec: Path | None = None) -> list[tuple[str, str, str]]:
    """(module, event, content) from FRAMEWORK.md section 6."""
    spec = spec or find_spec("backend")
    text = (spec / "FRAMEWORK.md").read_text(encoding="utf-8")
    sec = readme_section(text, "6")
    rows = []
    for ln in sec.splitlines():
        m = re.match(r"\|\s*(C\d+-M\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", ln)
        if not m:
            continue
        for ev in re.findall(r"`([A-Z][A-Za-z]+)`", m.group(2)):
            rows.append((module_id(m.group(1)), ev, m.group(3)))
    return rows


def flows(spec: Path | None = None) -> dict:
    spec = spec or find_spec("backend")
    f = Path(os.environ.get("FLOWS_FILE") or spec / "C12-M1-ProcessOrchestration" / "flows.yaml")
    return yaml.safe_load(f.read_text(encoding="utf-8"))


def table(rows: list[list[str]], header: list[str]) -> str:
    """Markdown table, so the output pastes into an issue or a PR as it is."""
    rows = [[("" if c is None else str(c)).replace("|", "\\|") for c in r] for r in rows]
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)
