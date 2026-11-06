#################################################################################
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
#  Assisted-By: GitHub Copilot (claude-opus-5-5)
#################################################################################
"""Reader of `application.properties` files: `key=value` (or `key: value`) lines, `#` and `!` comments, `\\` line
continuation, and placeholders `${NAME}` / `${NAME:default}` resolved from the process environment (nested defaults
such as `${A:${B:x}}` are allowed). An environment variable that is unset or empty takes the default."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


def load(path: str | Path, env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ if env is None else env
    raw = parse(Path(path).read_text(encoding="utf-8"))
    return {key: expand(value, env) for key, value in raw.items()}


def parse(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    pending = ""
    for line in text.splitlines():
        line = line.strip() if not pending else line.lstrip()
        if not pending and (not line or line[0] in "#!"):
            continue
        if line.endswith("\\") and not line.endswith("\\\\"):
            pending += line[:-1]
            continue
        line, pending = pending + line, ""
        cut = min((i for i in (line.find("="), line.find(":")) if i >= 0), default=-1)
        key, value = (line, "") if cut < 0 else (line[:cut], line[cut + 1:])
        props[key.strip()] = value.strip()
    if pending:
        raise ValueError("application.properties ends inside a continued line")
    return props


def expand(value: str, env: Mapping[str, str]) -> str:
    out, _ = _expand(value, 0, env, inside=False)
    return out


def _expand(s: str, i: int, env: Mapping[str, str], inside: bool) -> tuple[str, int]:
    """Expands from `i` up to the end, or up to the `}` that closes the enclosing placeholder when `inside`."""
    out: list[str] = []
    while i < len(s):
        if s.startswith("${", i):
            text, i = _placeholder(s, i + 2, env)
            out.append(text)
        elif inside and s[i] == "}":
            return "".join(out), i
        else:
            out.append(s[i])
            i += 1
    if inside:
        raise ValueError(f"unclosed placeholder in {s!r}")
    return "".join(out), i


def _placeholder(s: str, i: int, env: Mapping[str, str]) -> tuple[str, int]:
    end = i
    while end < len(s) and s[end] not in ":}":
        end += 1
    name = s[i:end].strip()
    if end >= len(s) or not name:
        raise ValueError(f"malformed placeholder in {s!r}")
    default = None
    if s[end] == ":":
        default, end = _expand(s, end + 1, env, inside=True)
    if default is None and not env.get(name):
        raise ValueError(f"placeholder ${{{name}}} has no default and {name} is not set")
    return env.get(name) or default or "", end + 1


def as_list(value: str) -> tuple[str, ...]:
    """Comma-separated value as tuple, blanks dropped; empty gives ()."""
    return tuple(x.strip() for x in value.split(",") if x.strip())


def as_int(value: str) -> int:
    return int(value)


def as_bool(value: str) -> bool:
    text = value.strip().lower()
    if text not in ("true", "false"):
        raise ValueError(f"expected true or false, got {value!r}")
    return text == "true"
