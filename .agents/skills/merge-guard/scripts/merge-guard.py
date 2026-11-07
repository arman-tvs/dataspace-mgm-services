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
"""Check a branch before its pull request to eclipse-tractusx/dataspace-mgm-service, read-only.

Usage: merge-guard.py [base] [--module <id>] [--run] [--strict]

  base          what the PR merges into (default: origin/main; upstream/main when that remote exists)
  --module id   the team's module (c3_m1); default: inferred from the changed paths under modules/
  --run         also run the definition of done: uv run pytest -q, uv run python demo.py and the quality
                gate (uv run python tools/quality/gate.py, ADR-0003)
  --strict      exit 1 on a blocker or high finding

Checks: the paths a team may change (AGENTS.md rules 1-2), the module against its spec (module-map),
license headers on new files (TRG 7.02), commit authors and the AI disclosure trailer, Conventional
Commit subjects, secrets in added lines, DEPENDENCIES when pyproject.toml or uv.lock change (TRG 7.04),
and no committed spec/ clone. The ECA itself is checked by the Eclipse bot on the PR, not here.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.dont_write_bytecode = True  # keep the repository free of __pycache__
sys.path.insert(0, str(HERE.parents[2] / "portal-spec-sources" / "scripts"))
import specs  # noqa: E402

ORDER = ["blocker", "high", "medium", "low", "info"]
PROTECTED = ("portal_common/", "scaffold/", "tools/", "iam/", "ebw/", "testdata/", "config/", "spec/")
CONVENTIONAL = re.compile(r"^(feat|fix|docs|chore|refactor|test|ci|build|perf|style|revert)(\([^)]+\))?!?: .+")
SECRETS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)client[_-]?secret[\"']?\s*[:=]\s*[\"'][^\"'\s]{8,}"), "client secret"),
    (re.compile(r"(?i)(?:x-api-key|api[_-]?key)[\"']?\s*[:=]\s*[\"'][^\"'\s]{12,}"), "API key"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "JWT"),
    (re.compile(r"(?i)password[\"']?\s*[:=]\s*[\"'][^\"'\s]{6,}"), "password"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "GitHub token"),
]
TEST_ONLY = re.compile(r"(TEST-ONLY|test-only|/test/|tests/|testdata/)")
TEST_VALUE = re.compile(r"(?i)(test-only|test_only|example|dummy|placeholder|changeme|<[a-z-]+>|\$\{)")
LEGAL = {"CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "SECURITY.md", "NOTICE.md", "LICENSE", "LICENSE_non-code",
         "CHANGELOG.md", "AUTHORS.md", "DEPENDENCIES", "CLAUDE.md", "AGENTS.md"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def default_base() -> str:
    remotes = git("remote").split()
    return "upstream/main" if "upstream" in remotes else "origin/main"


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    module = argv[argv.index("--module") + 1] if "--module" in argv else None
    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--module")]
    base = pos[0] if pos else default_base()
    root = specs.repo_root()
    try:
        mb = git("merge-base", base, "HEAD").strip()
    except subprocess.CalledProcessError:
        print(f"Cannot find a merge base with {base}. Fetch it first: git fetch {base.split('/')[0]}")
        return 2
    findings: list[tuple[str, str, str]] = []

    def add(sev: str, what: str, rule: str) -> None:
        findings.append((sev, what, rule))

    changes = [ln.split("\t") for ln in git("diff", "--name-status", "--no-renames", f"{mb}..HEAD").splitlines() if ln]
    paths = [c[-1] for c in changes]
    added = {c[-1] for c in changes if c[0] == "A"}
    dirty = git("status", "--porcelain").strip()
    if dirty:
        add("info", f"{len(dirty.splitlines())} uncommitted change(s) are not part of this check", "–")

    # --- which module, which paths
    touched = sorted({p.split("/")[1] for p in paths if p.startswith("modules/") and p.count("/") >= 2})
    if module:
        module = specs.module_id(module).replace("-", "_")
    elif len(touched) == 1:
        module = touched[0]
    if len(touched) > 1:
        sev = "high" if module else "info"
        add(sev, f"the branch changes {len(touched)} module folders ({', '.join(touched)}); a team PR changes one",
            "AGENTS.md rule 1")
    if module:
        allowed = re.compile(rf"^(modules/{module}/|tests/test_{module}_[^/]+\.py$)")
        for p in paths:
            if not allowed.match(p):
                sev = "blocker" if p.startswith(PROTECTED) or p.startswith("modules/") else "high"
                add(sev, f"{p} is outside modules/{module}/ and tests/test_{module}_*.py", "AGENTS.md rules 1-2")
    else:
        shared = sorted({p.split("/")[0] for p in paths if p.startswith(PROTECTED)})
        if shared:
            add("info", f"changes shared parts of the scaffold ({', '.join(shared)}): fine for a maintainer PR, "
                        "never for a team PR", "AGENTS.md rule 2")
    if any(p.startswith("spec/") for p in paths):
        add("blocker", "spec/ is committed; it is a read-only clone of portal-backend-spec", "AGENTS.md How to run")

    # --- module against its spec (static)
    if module and (root / "modules").is_dir():
        mm = _load_module_map()
        r = mm.analyse(root, specs.get_module(module))
        for sev, what, rule in r["findings"]:
            add(sev, f"[{module}] {what}", rule)
        if r["kind"] == "stand-in" and any(p.startswith(f"modules/{module}/") for p in paths):
            add("high", f"modules/{module}/router.py still says STANDIN = True", "AGENTS.md: the module folder")

    # --- license headers on new files
    for p in sorted(added):
        f = root / p
        if Path(p).name in LEGAL or not f.is_file() or f.stat().st_size == 0:
            continue  # legal files of TRG 7, empty __init__.py (AGENTS.md: keep it empty)
        text = f.read_text(encoding="utf-8", errors="replace")
        head = "\n".join(text.splitlines()[:25])
        if f.suffix in (".py", ".sh", ".ts", ".tsx", ".js", ".mjs", ".yaml", ".yml", ".toml"):
            has_copyright = "Copyright (c)" in head or "SPDX-FileCopyrightText" in head
            if not has_copyright or "SPDX-License-Identifier" not in head:
                add("medium", f"{p}: license header missing (Copyright + SPDX-License-Identifier)",
                    "TRG 7.02, AGENTS.md Commits")
        elif f.suffix == ".md" and "SPDX-License-Identifier" not in text:
            add("low", f"{p}: no license information (header or NOTICE section with SPDX-License-Identifier)",
                "TRG 7.02 / 7.07")

    # --- dependencies
    if {"pyproject.toml", "uv.lock"} & set(paths) and "DEPENDENCIES" not in paths:
        add("high", "pyproject.toml or uv.lock changed but DEPENDENCIES did not; run the dependencies-and-dash skill",
            "TRG 7.04, workflow dependencies.yml")

    # --- commits
    log = git("log", "--format=%H%x1f%an%x1f%ae%x1f%s%x1f%b%x1e", f"{mb}..HEAD")
    commits = [c.strip("\n").split("\x1f") for c in log.split("\x1e") if c.strip()]
    rows, noreply, unconventional = [], {}, []
    for sha, name, email, subject, body in commits:
        ai = re.search(r"(?im)^assisted-by:\s*(.+)$", body)
        coauth_ai = re.search(r"(?im)^co-authored-by:.*(claude|copilot|anthropic|openai|noreply@github)", body)
        rows.append([sha[:8], f"{name} <{email}>", subject[:70], ai.group(1).strip() if ai else "–"])
        if not CONVENTIONAL.match(subject):
            unconventional.append(sha[:8])
        if coauth_ai and not ai:
            add("medium", f"{sha[:8]} names an AI as co-author; use the trailer Assisted-by: <tool> (<model>)",
                "AGENTS.md Commits")
        if email.endswith("users.noreply.github.com"):
            noreply.setdefault(email, []).append(sha[:8])

    if unconventional:
        add("low", f"{len(unconventional)} commit subject(s) are not Conventional Commits ({', '.join(unconventional[:5])}"
                   f"{', …' if len(unconventional) > 5 else ''}); the PR title must be one", "TRG 1.03")
    for email, shas in noreply.items():
        add("low", f"{len(shas)} commit(s) authored as {email}: the ECA check matches this address against the "
                   "Eclipse account, make sure it is registered there", "AGENTS.md Commits (ECA)")

    # --- secrets in added lines
    diff = git("diff", "-U0", "--no-color", f"{mb}..HEAD")
    current = ""
    for ln in diff.splitlines():
        if ln.startswith("+++ "):
            current = ln[6:] if ln.startswith("+++ b/") else ""
            continue
        if not ln.startswith("+") or not current or TEST_ONLY.search(current):
            continue
        for rx, what in SECRETS:
            if rx.search(ln) and not TEST_VALUE.search(ln):
                add("blocker", f"{current}: added line looks like a {what}", "FRAMEWORK 4.6, AGENTS.md rule 9")
                break

    # --- report
    print(f"merge-guard: {len(commits)} commit(s), {len(paths)} changed file(s) since {base} ({mb[:8]})"
          + (f"; team module {module}" if module else "; no team module (maintainer change)") + "\n")
    if rows:
        print(specs.table(rows, ["Commit", "Author", "Subject", "Assisted-by"]) + "\n")
    findings.sort(key=lambda f: ORDER.index(f[0]))
    print(specs.table([list(f) for f in findings], ["Severity", "Finding", "Rule"]) if findings else "No findings.")
    counts = {s: sum(f[0] == s for f in findings) for s in ORDER}
    print("\n" + ", ".join(f"{n} {s}" for s, n in counts.items() if n) if findings else "")

    rc = 0
    if "--run" in argv:
        for cmd in (["uv", "run", "pytest", "-q"], ["uv", "run", "python", "demo.py"],
                    ["uv", "run", "python", "tools/quality/gate.py"]):
            print(f"\n$ {' '.join(cmd)}")
            res = subprocess.run(cmd, cwd=root)
            print(f"exit code {res.returncode}")
            rc = rc or res.returncode
    if "--strict" in argv and (counts["blocker"] or counts["high"]):
        return 1
    return rc


def _load_module_map():
    import importlib.util
    f = HERE.parents[2] / "module-map" / "scripts" / "module-map.py"
    spec = importlib.util.spec_from_file_location("module_map", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
