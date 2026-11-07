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
"""Explain a 401, 403 or 404 of a portal module from the person's token, offline and read-only.

Usage: token-inspect.py <token | file | -> [--op "METHOD /api/<module>/<path>"] [--owner <companyId|sub>]
                        [--iss <expected issuer>]

  <token>     the access token (or a file holding it, or - for stdin). It is decoded, NOT verified:
              the signature check against the JWKS stays with portal_common.tokens.
  --op        the call that failed, e.g. --op "GET /api/c3-m1/companies/c0000001-0000-4000-8000-000000000001":
              the script finds x-permission and x-permission-scope in the spec and predicts the answer
  --owner     the company (scope company) or the person (scope own) that owns the object, when it is
              not in the path
  --iss       the issuer of the installation, {IAM_URL}/realms/{IAM_REALM}; default: only printed

Checks follow C2-M5 7.6 (alg RS256, iss, exp with 30 s tolerance, aud contains portal-core, typ Bearer)
and FRAMEWORK 4.3 (scopes company / osp / own). Names and other personal claims are shown as "set" only.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep the repository free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portal-spec-sources" / "scripts"))
import specs  # noqa: E402

AUDIENCE = "portal-core"
PERSONAL = ("given_name", "family_name", "name", "email", "preferred_username")


def _b64(part: str) -> dict:
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part.encode()))


def _is_file(arg: str) -> bool:
    try:
        return len(arg) < 1024 and Path(arg).is_file()
    except OSError:
        return False


def read_token(arg: str) -> str:
    if arg == "-":
        raw = sys.stdin.read()
    elif _is_file(arg):
        raw = Path(arg).read_text(encoding="utf-8")
    else:
        raw = arg
    raw = raw.strip()
    if raw.startswith("{"):  # a token response of Keycloak
        raw = json.loads(raw).get("access_token", "")
    return raw.removeprefix("Bearer ").strip()


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    opt = {k: argv[argv.index(k) + 1] for k in ("--op", "--owner", "--iss") if k in argv and argv.index(k) + 1 < len(argv)}
    token = read_token(argv[0])
    parts = token.split(".")
    if len(parts) != 3:
        print("Not a JWS compact token (three dot-separated parts). An opaque or encrypted token cannot be read here.")
        return 2
    header, claims = _b64(parts[0]), _b64(parts[1])
    now = dt.datetime.now(dt.UTC).timestamp()
    aud = claims.get("aud")
    auds = aud if isinstance(aud, list) else [aud] if aud else []
    perms = sorted(((claims.get("resource_access") or {}).get(AUDIENCE) or {}).get("roles") or [])
    checks: list[list[str]] = []

    def check(ok: bool, what: str, detail: str, status: str) -> None:
        checks.append(["ok" if ok else "FAIL", what, detail, "" if ok else status])

    check(header.get("alg") == "RS256", "alg RS256", str(header.get("alg")), "401 unauthorized")
    exp = claims.get("exp")
    if exp:
        left = exp - now
        check(left > -30, "exp not exceeded (30 s tolerance)",
              f"{dt.datetime.fromtimestamp(exp, dt.UTC):%Y-%m-%d %H:%M:%S} UTC ({int(left)} s left)", "401 unauthorized")
    else:
        check(False, "exp present", "missing", "401 unauthorized")
    check(AUDIENCE in auds, f"aud contains {AUDIENCE}", ", ".join(map(str, auds)) or "missing",
          "401 unauthorized (technical users and apps fail here, C2-M5 7.6)")
    check(claims.get("typ", "Bearer") == "Bearer", "typ Bearer", str(claims.get("typ")), "401 unauthorized")
    iss = claims.get("iss", "")
    if "--iss" in opt:
        check(iss == opt["--iss"].rstrip("/"), "iss of this installation", iss,
              "401 unauthorized (a token of another OSP's Portal IAM)")
    else:
        realm = re.search(r"/realms/([^/]+)$", iss)
        checks.append(["info", "iss", iss + (f" (realm {realm.group(1)})" if realm else ""),
                       "compare with {IAM_URL}/realms/{IAM_REALM} of the installation (--iss)"])

    def short(v) -> str:
        return v if isinstance(v, str) else json.dumps(v)

    rows = [["kid", header.get("kid")], ["sub", claims.get("sub")], ["azp", claims.get("azp")],
            ["company_id", claims.get("company_id") or "– (account not bound to a company)"],
            ["bpn", claims.get("bpn") or "–"]]
    rows += [[k, "set"] for k in PERSONAL if claims.get(k)]
    rows.append([f"resource_access.{AUDIENCE}.roles", ", ".join(perms) or "– (no permissions)"])
    other = {k: v for k, v in (claims.get("resource_access") or {}).items() if k != AUDIENCE}
    if other:
        rows.append(["other clients' roles", "; ".join(f"{k}: {', '.join(v.get('roles', []))}" for k, v in other.items())])
    print("Token (decoded, signature NOT verified):\n")
    print(specs.table([[k, short(v)] for k, v in rows], ["Claim", "Value"]))
    print("\nValidation of C2-M5 7.6:\n")
    print(specs.table(checks, ["Result", "Check", "Value", "Answer if it fails"]))

    if "--op" in opt:
        method, _, path = opt["--op"].partition(" ")
        hits = specs.find_operation(method, path.strip())
        print(f"\nCall {method.upper()} {path.strip()}:\n")
        if not hits:
            print("No operation of the spec matches; the installation answers 404 or 405 before any permission "
                  "check. List the module: spec-src.py ops <module>.")
            return 1
        op = hits[0]
        verdict = []
        if any(c[0] == "FAIL" for c in checks):
            verdict.append("401 unauthorized: the token itself fails the validation above.")
        elif op.permission not in perms:
            verdict.append(f"403 forbidden: the token lacks `{op.permission}` (portal roles bundle permissions, "
                           "C2-M5 6.3; check the role of the person or the service account).")
        elif op.scope == "company":
            owner = opt.get("--owner") or next((seg for seg in path.split("/") if re.fullmatch(r"[0-9a-f-]{36}", seg)), None)
            cid = claims.get("company_id")
            if not cid:
                verdict.append("404 not-found: scope `company` needs `company_id`, and the account is not bound to "
                               "a company (FRAMEWORK 4.3).")
            elif owner and owner != cid:
                verdict.append(f"404 not-found: the object belongs to company {owner}, the token to {cid}; another "
                               "company's object stays invisible (FRAMEWORK 4.3).")
            else:
                verdict.append(f"Allowed if the object belongs to company {cid} (scope company).")
        elif op.scope == "own":
            verdict.append(f"Allowed if the object belongs to sub {claims.get('sub')} (scope own); otherwise 404.")
        else:
            verdict.append("Allowed: scope `osp` checks the permission only.")
        print(specs.table([[op.module.upper(), op.operation_id, op.permission, op.scope]],
                          ["Module", "operationId", "x-permission", "x-permission-scope"]))
        print("\nExpected answer: " + " ".join(verdict))
    return 1 if any(c[0] == "FAIL" for c in checks) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
