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
"""Calls of the core services API of the CSP (README 11.1).

With `CSP_URL` set, the call goes over HTTP through `portal_common.csp` (client credentials with
`private_key_jwt`, README 4; timeout 10 s from `portal_common.http`). With an empty `CSP_URL`,
the built-in stand-in of README 11.3 answers in memory, with the companies of `CSP_STUB_FILE`.
Every call writes an audit entry (README 5) with the HTTP status and the CSP's error type only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jwt

from portal_common import csp, settings
from tools.csp_standin.core import CoreServices

from . import errors, store

CspAnswer = tuple[int, object]   # (HTTP status, JSON body or None) of one call of the core services API
JsonObject = dict[str, Any]

_builtin: CoreServices | None = None


class BuiltinConfigError(Exception):
    """A file the built-in CSP stand-in reads is unusable. The message names the variable or setting
    (never the path); `kind` is the audit error type (OPEN-QUESTIONS 11)."""

    def __init__(self, variable: str, kind: str, reason: str):
        super().__init__(f"the built-in CSP stand-in cannot use {variable}: {reason}")
        self.kind = kind


def reset() -> None:
    global _builtin
    _builtin = None


def osp_id() -> str:
    """`ospId` of this installation (FRAMEWORK 4.8); `settings.load()` refuses to start without it."""
    return str(settings.get("ospId"))


def _read_json(path: Path) -> object:
    data: object = json.loads(path.read_text(encoding="utf-8"))
    return data


def _stub_companies() -> list[JsonObject]:
    """`CSP_STUB_FILE` (README 4, 14): a list of companies, or an object with `companies`."""
    path = os.environ.get("CSP_STUB_FILE", "")
    if not path:
        return []
    try:
        data = _read_json(Path(path))
    except (OSError, ValueError) as e:   # missing, unreadable or no JSON
        raise BuiltinConfigError("CSP_STUB_FILE", "stub-file", type(e).__name__) from e
    items = data.get("companies", []) if isinstance(data, dict) else data
    if not isinstance(items, list) or not all(
            isinstance(c, dict) and isinstance(c.get("bpn"), str) and isinstance(c.get("homeOspId"), str)
            for c in items):
        raise BuiltinConfigError("CSP_STUB_FILE", "stub-file", "not a list of companies with bpn and homeOspId")
    return items


def _osp_company() -> list[JsonObject]:
    """The OSP company of `ospCompanyFile`: the CSP knows it from the admission of the OSP
    (README 4 "Seed data", FRAMEWORK 5.1), so the built-in stand-in knows it as well."""
    path = settings.resolve_path(settings.get("ospCompanyFile"))
    if path is None or not path.exists():
        return []
    try:
        c = _read_json(path)
    except (OSError, ValueError) as e:   # unreadable or no JSON
        raise BuiltinConfigError("ospCompanyFile", "osp-company-file", type(e).__name__) from e
    if not isinstance(c, dict) or not c.get("bpn"):
        return []
    address = raw if isinstance(raw := c.get("address"), dict) else {}
    return [{"bpn": c["bpn"], "legalName": c.get("name"), "country": address.get("countryCode"),
             "identifiers": c.get("identifiers") or [], "homeOspId": osp_id(), "memberActive": True}]


def _builtin_core() -> CoreServices:
    """The built-in CSP stand-in (README 11.3), created on first use, so tests can set
    `CSP_STUB_FILE` first; `reset()` drops it."""
    global _builtin
    if _builtin is None:
        stub = _stub_companies()
        known = {s.get("bpn") for s in stub}
        stub += [c for c in _osp_company() if c["bpn"] not in known]
        osps: dict[str, JsonObject] = {osp_id(): {"name": settings.get("ospName")}}
        for c in stub:
            osps.setdefault(str(c["homeOspId"]), {"name": c.get("homeOspName")})
        _builtin = CoreServices(osps, stub)
    return _builtin


def csp_type(answer: object) -> str | None:
    """`type` of a Problem Details answer of the CSP, if any."""
    if isinstance(answer, dict) and isinstance(answer.get("type"), str):
        return str(answer["type"])
    return None


def call(operation: str, method: str, path: str, body: JsonObject | None = None, params: JsonObject | None = None,
         *, company_id: str | None = None, bpn: str | None = None) -> CspAnswer:
    """One call of the core services API (README 11.1).
    No answer from the CSP (timeout, connection, token endpoint, unreadable signing key) and, with the
    built-in stand-in, an unusable `CSP_STUB_FILE` or `ospCompanyFile`: 502 `upstream-error`,
    retryable, naming the file's variable, with an audit entry (README 12; OPEN-QUESTIONS 11)."""
    base = os.environ.get("CSP_URL", "")
    if base:
        try:
            status, answer = csp.request(base, method, path, body, params)
        except csp.CspUnavailable as e:
            store.record_audit(operation, company_id, bpn, None, "unavailable")
            raise errors.upstream_error(f"CSP not reachable: {e}") from e
        except (OSError, ValueError, jwt.PyJWTError) as e:   # OSP_SIGNING_KEY_FILE missing, no JSON or no usable key
            store.record_audit(operation, company_id, bpn, None, "signing-key")
            raise errors.upstream_error("the signing key of the OSP (OSP_SIGNING_KEY_FILE) is not readable") from e
        if status == 401:
            # The CSP refused the access token. portal_common.csp would reuse it until it expires, so
            # every retry of C12 would fail the same way: drop it, the retry fetches a new one.
            csp.reset()
    else:
        try:
            core = _builtin_core()
        except BuiltinConfigError as e:   # only the stand-in's own files; a settings fault stays as it is
            store.record_audit(operation, company_id, bpn, None, e.kind)
            raise errors.upstream_error(str(e)) from e
        status, answer = core.dispatch(osp_id(), method, path, body, params)
    store.record_audit(operation, company_id, bpn, int(status), csp_type(answer))
    return int(status), answer


def is_business_rejection(status: int) -> bool:
    """README 12: a 4xx of the CSP is a business rejection, except a token problem (401) and
    temporary answers (408, 429), which may pass on a retry (OPEN-QUESTIONS 4)."""
    return 400 <= status < 500 and status not in (401, 408, 429)


def raise_for(status: int, answer: object, ok: tuple[int, ...] = (200, 201, 204)) -> None:
    """Maps an unexpected answer of the CSP to README 12: business rejection -> `csp-rejected`
    (not retryable); everything else (5xx, 401, 408, 429) -> `upstream-error` (retryable)."""
    if status in ok:
        return
    if is_business_rejection(status):
        raise errors.csp_rejected(f"the CSP rejected the call with {status}", csp_type(answer))
    raise errors.upstream_error(f"the CSP answered {status}")
