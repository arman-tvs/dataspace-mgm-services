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
#  Assisted-By: Claude Code (claude-sonnet-5-5)
#################################################################################
"""Routes of C4-M1 (README 6.3): how a credential is triggered at an issuer.

`select_route(wallet)` applies the rules of README 6.3 and returns the route name. A route object has
`name`, `prepare(ctx)` (once per run, before the first order), `order(ctx, credential_type, attempt)`
(returns `(request_ref, issuer_did)`), `cancel(row)` and `revoke(row)` (True = revoked, False = the
route cannot revoke).

Configuration is read from the environment at call time (AGENTS.md rule 6).
"""
from __future__ import annotations

import logging
import os
import threading
import time

import httpx

from portal_common import csp, http, neighbours, settings
from portal_common.problems import Problem

MODULE = "c4-m1"
log = logging.getLogger("c4-m1.routes")

CREDENTIAL_ISSUER, ISSUER_SERVICE, CSP_ISSUER, STUB = "CREDENTIAL_ISSUER", "ISSUER_SERVICE", "CSP_ISSUER", "STUB"
FITS = {CREDENTIAL_ISSUER: "ISSUER_WRITES", ISSUER_SERVICE: "HOLDER_REQUESTS", CSP_ISSUER: "HOLDER_REQUESTS"}


def _no_route(detail: str) -> Problem:
    return Problem(MODULE, 409, "no-issuer-route", detail=detail, retryable=False)


def issuer_routes() -> dict[str, str]:
    """`ISSUER_ROUTES`: `SAP_DIV:CREDENTIAL_ISSUER,IDENTITY_HUB:ISSUER_SERVICE,...` as a dict."""
    out = {}
    for part in os.environ.get("ISSUER_ROUTES", "").split(","):
        if ":" in part:
            provider, route = part.split(":", 1)
            out[provider.strip()] = route.strip()
    return out


def select_route(wallet: dict) -> str:
    """README 6.3, in this order. An own wallet (`BRING_YOUR_OWN`, `CREDENTIAL_OFFER`) has no route in
    version 0.2; it is rejected before rule 2 (OPEN-QUESTIONS.md, case 5 against rule 2)."""
    provider, mode = wallet.get("provider"), wallet.get("issuanceMode")
    if provider == "STUB":                                                   # rule 1
        return STUB
    if provider == "BRING_YOUR_OWN" or mode == "CREDENTIAL_OFFER":
        raise _no_route("an own wallet has no issuer route in version 0.2")
    if os.environ.get("ISSUER_MODE", "OWN") == "CSP":                        # rule 3
        if not os.environ.get("CSP_ISSUER_URL"):
            return STUB
        if mode != "HOLDER_REQUESTS":
            raise _no_route("the CSP issuer issues only into wallets with issuance mode HOLDER_REQUESTS")
        return CSP_ISSUER
    routes = issuer_routes()                                                 # rule 2
    if not os.environ.get("ISSUER_ROUTES", "").strip():
        return STUB
    route = routes.get(provider or "")
    if route is None:
        raise _no_route(f"no entry in ISSUER_ROUTES for the wallet provider {provider}")
    if FITS.get(route) != mode:                                              # rule 4
        raise _no_route(f"route {route} does not fit the issuance mode {mode}")
    return route


# ------------------------------------------------------------------------------------------- STUB
class StubRoute:
    """Built-in stand-in of the issuer (README 11.6): remembers the order and, after
    `STUB_ISSUER_DELAY_SECONDS`, calls the processing of the status report (7.4) in the same process."""

    name = STUB

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.orders: list[dict] = []
        self._pending: list[dict] = []     # {"order", "timer", "fired"}
        self._timers: list[threading.Timer] = []   # every started timer, so that flush() can wait for them
        self._generation = 0

    def prepare(self, ctx: dict) -> None:
        """No holder access, no holder registration for the stand-in."""

    def order(self, ctx: dict, credential_type: str, attempt: int) -> tuple[str, str | None]:
        order = {"company_id": ctx["company"]["id"], "credential_type": credential_type,
                 "bpn": ctx["company"]["bpn"].upper(), "attempt": attempt}
        try:
            delay = max(0.0, float(os.environ.get("STUB_ISSUER_DELAY_SECONDS", "1")))
        except ValueError:
            delay = 1.0
        with self._lock:
            self.orders.append(order)
            entry = {"order": order, "fired": False, "generation": self._generation}
            entry["timer"] = threading.Timer(delay, self._fire, args=(entry,))
            entry["timer"].daemon = True
            self._pending.append(entry)
            self._timers.append(entry["timer"])
            entry["timer"].start()
        return f"stub-{attempt}", None

    def _fire(self, entry: dict) -> None:
        from . import service
        with self._lock:
            if entry["fired"] or entry["generation"] != self._generation:
                return
            entry["fired"] = True
            if entry in self._pending:
                self._pending.remove(entry)
        order = entry["order"]
        fail = {t.strip().upper() for t in os.environ.get("STUB_ISSUER_FAIL_TYPES", "").split(",") if t.strip()}
        failing = order["credential_type"] in fail
        try:
            # Wait for a step that is still ordering this company: with a delay of 0 the timer fires before the
            # row of the order is stored, and the report would find no order (README 6.9 per-company lock).
            with service.store().transaction(order["company_id"]):
                service.report_status(order["credential_type"].lower(), order["bpn"],
                                      "UNSUCCESSFUL" if failing else "SUCCESSFUL",
                                      "Issuance declined by the stand-in" if failing else None)
        except Problem as e:   # for example the row is gone after a reset
            log.warning("stand-in report for %s/%s not processed: %s", order["bpn"], order["credential_type"], e)

    def flush(self) -> None:
        """Fires every pending timer at once, in order of the orders, and waits for timers that already
        fired in their own thread (tests)."""
        while True:
            with self._lock:
                entry = next((e for e in self._pending if not e["fired"]), None)
            if entry is None:
                break
            entry["timer"].cancel()
            self._fire(entry)
        with self._lock:
            started = list(self._timers)
        for timer in started:
            timer.join(5)

    def cancel(self, row: dict) -> None:
        """An open order is cancelled: nothing to do at the stand-in (a late report revokes at once)."""

    def revoke(self, row: dict) -> bool:
        return True                                                          # README 11.6: always successful

    def reset(self) -> None:
        with self._lock:
            self._generation += 1
            for e in self._pending:
                e["timer"].cancel()
            self._pending.clear()
            self._timers.clear()
            self.orders.clear()


# ------------------------------------------------------------------------------------- helpers
def _upstream(detail: str) -> Problem:
    return Problem(MODULE, 502, "upstream-error", detail=detail, retryable=True)


def _callback_url(kind: str) -> str:
    """`{CALLBACK_BASE_URL}/api/c4-m1/issuer-callbacks/{kind}`; without the variable the address of the
    installation (OPEN-QUESTIONS.md)."""
    base = (os.environ.get("CALLBACK_BASE_URL") or settings.base_url()).rstrip("/")
    return f"{base}/api/c4-m1/issuer-callbacks/{kind}"


def _definitions(variable: str, default: str) -> dict[str, str]:
    out = {}
    for part in (os.environ.get(variable) or default).split(","):
        if ":" in part:
            t, ident = part.split(":", 1)
            out[t.strip().upper()] = ident.strip()
    return out


def _member_of() -> str | None:
    return (settings.get("dataspace") or {}).get("memberOf")


def _holder_access(ctx: dict) -> dict:
    """Holder access from C4-M2, once per run just before the first order; kept in memory only."""
    if "access" not in ctx:
        access = neighbours.query(MODULE, "c4-m2", "get_holder_access", companyId=ctx["company"]["id"])
        if not access:
            raise Problem(MODULE, 409, "wallet-not-ready", detail="no holder access for the wallet", retryable=False)
        ctx["access"] = access
    return ctx["access"]


def _identity_request(ctx: dict, credential_type: str, attempt: int, issuer_did: str, identifier: str) -> str:
    """Credential request in the identity interface of the holder's wallet (README 11.4); returns `holderPid`."""
    access = _holder_access(ctx)
    holder_pid = f"{ctx['company']['id']}:{credential_type}:{attempt}"
    credential = {"type": identifier, "format": os.environ.get("CREDENTIAL_FORMAT") or "VC1_0_JWT"}
    try:
        r = http.request("POST", f"{access['identityApiUrl'].rstrip('/')}/participants/{access['participantContextId']}"
                         "/credentials/request",
                         json={"issuerDid": issuer_did, "holderPid": holder_pid, "credentials": [credential]},
                         headers={"x-api-key": access["apiKey"]})
    except httpx.HTTPError as e:
        raise _upstream(f"wallet identity API: {type(e).__name__}") from e
    if not r.is_success:
        raise _upstream(f"wallet identity API answered {r.status_code}")
    return holder_pid


# ------------------------------------------------------------------------------------- CSP_ISSUER
class CspIssuerRoute:
    """CSP issuer (README 11.5): holder and grant at the CSP, request in the holder's wallet."""

    name = CSP_ISSUER

    @staticmethod
    def _csp(method: str, path: str, body: dict | None = None, revocation: bool = False) -> None:
        try:
            status, _ = csp.request(os.environ.get("CSP_ISSUER_URL", ""), method, path, body)
        except csp.CspUnavailable as e:
            raise _upstream(f"CSP issuer: {e}") from e
        if 200 <= status < 300:
            return
        if not revocation and status in (403, 404, 409, 422):
            raise Problem(MODULE, 409, "issuer-rejected", detail=f"CSP issuer answered {status}", retryable=False)
        raise _upstream(f"CSP issuer answered {status}")

    def prepare(self, ctx: dict) -> None:
        _holder_access(ctx)                       # once per run, never sent to the CSP
        self._csp("PUT", f"/holders/{ctx['company']['bpn'].upper()}", {"did": ctx["wallet"]["did"]})

    def order(self, ctx: dict, credential_type: str, attempt: int) -> tuple[str, str | None]:
        bpn, kind = ctx["company"]["bpn"].upper(), credential_type.lower()
        grant = {"callbackUrl": _callback_url(kind)}
        if kind == "membership":
            grant["memberOf"] = _member_of()
        self._csp("PUT", f"/holders/{bpn}/grants/{kind}", grant)
        issuer_did = os.environ.get("CSP_ISSUER_DID") or "did:web:issuer.csp.example.org"
        identifier = _definitions("CSP_ISSUER_CREDENTIAL_DEFINITIONS", "BPN:bpn,MEMBERSHIP:membership")[credential_type]
        return _identity_request(ctx, credential_type, attempt, issuer_did, identifier), issuer_did

    def _remove_grant(self, row: dict) -> None:
        self._csp("DELETE", f"/holders/{row['bpn']}/grants/{row['credential_type'].lower()}", revocation=True)

    def cancel(self, row: dict) -> None:
        """README 8.2: the grant is removed first, so that a request still running is no longer issued."""
        self._remove_grant(row)

    def revoke(self, row: dict) -> bool:
        self._remove_grant(row)                   # 204: removes the grant and revokes issued credentials
        return True


# ---------------------------------------------------------------------------------- CREDENTIAL_ISSUER
_issuer_tokens: dict[str, tuple[str, float]] = {}


class CredentialIssuerRoute:
    """Own Credential Issuer (README 11.3): the issuer writes into the wallet; revocation is not supported in 0.2."""

    name = CREDENTIAL_ISSUER

    @staticmethod
    def _token() -> str:
        url = os.environ.get("CREDENTIAL_ISSUER_TOKEN_URL", "")
        cached = _issuer_tokens.get(url)
        if cached and cached[1] > time.time() + 30:
            return cached[0]
        try:
            r = http.request("POST", url, data={"grant_type": "client_credentials",
                                                "client_id": os.environ.get("CREDENTIAL_ISSUER_CLIENT_ID", ""),
                                                "client_secret": os.environ.get("CREDENTIAL_ISSUER_CLIENT_SECRET", "")})
            body = r.json() if r.status_code == 200 else {}
        except (httpx.HTTPError, ValueError) as e:
            raise _upstream(f"Credential Issuer token endpoint: {type(e).__name__}") from e
        if "access_token" not in body:
            raise _upstream(f"Credential Issuer token endpoint answered {r.status_code}")
        _issuer_tokens[url] = (body["access_token"], time.time() + int(body.get("expires_in", 300)))
        return body["access_token"]

    def prepare(self, ctx: dict) -> None:
        _holder_access(ctx)

    def order(self, ctx: dict, credential_type: str, attempt: int) -> tuple[str, str | None]:
        access, kind = _holder_access(ctx), credential_type.lower()
        body = {"holder": access["holder"], "businessPartnerNumber": ctx["company"]["bpn"].upper(),
                "technicalUserDetails": {"walletUrl": access["walletUrl"], "clientId": access["clientId"],
                                         "clientSecret": access["clientSecret"]},
                "callbackUrl": _callback_url(kind)}
        if kind == "membership":
            body["memberOf"] = _member_of()
        try:
            r = http.request("POST", os.environ.get("CREDENTIAL_ISSUER_URL", "").rstrip("/") + f"/api/issuer/{kind}",
                             json=body, headers={"Authorization": "Bearer " + self._token()})
        except httpx.HTTPError as e:
            raise _upstream(f"Credential Issuer: {type(e).__name__}") from e
        if not r.is_success:                      # every 2xx counts as accepted
            raise _upstream(f"Credential Issuer answered {r.status_code}")
        return "", None

    def cancel(self, row: dict) -> None:
        """Nothing to remove at the Credential Issuer."""

    def revoke(self, row: dict) -> bool:
        return False                              # README 6.3: not supported -> REVOCATION_PENDING


# ------------------------------------------------------------------------------------ ISSUER_SERVICE
class IssuerServiceRoute:
    """Own IssuerService (README 11.4). The paths of the administration interface are provisional (the spec says
    to check them against the version in use, OPEN-QUESTIONS.md)."""

    name = ISSUER_SERVICE

    @staticmethod
    def _admin(method: str, path: str, body: dict | None = None, accept: tuple[int, ...] = ()) -> None:
        pid = os.environ.get("ISSUER_SERVICE_PARTICIPANT_ID") or "issuer"
        try:
            r = http.request(method, os.environ.get("ISSUER_SERVICE_ADMIN_URL", "").rstrip("/")
                             + f"/api/admin/participants/{pid}{path}", json=body,
                             headers={"x-api-key": os.environ.get("ISSUER_SERVICE_API_KEY", "")})
        except httpx.HTTPError as e:
            raise _upstream(f"IssuerService: {type(e).__name__}") from e
        if not (r.is_success or r.status_code in accept):
            raise _upstream(f"IssuerService answered {r.status_code}")

    def prepare(self, ctx: dict) -> None:
        _holder_access(ctx)
        company = ctx["company"]
        self._admin("POST", "/holders", {"holderId": company["bpn"].upper(), "did": ctx["wallet"]["did"],
                                         "name": company.get("name"), "properties": {"memberOf": _member_of()}},
                    accept=(409,))                # an existing holder counts as success

    def order(self, ctx: dict, credential_type: str, attempt: int) -> tuple[str, str | None]:
        issuer_did = os.environ.get("ISSUER_DID", "")
        identifier = _definitions("ISSUER_SERVICE_CREDENTIAL_DEFINITIONS", "BPN:bpn,MEMBERSHIP:membership")[credential_type]
        return _identity_request(ctx, credential_type, attempt, issuer_did, identifier), issuer_did

    def cancel(self, row: dict) -> None:
        """Nothing to remove."""

    def revoke(self, row: dict) -> bool:
        ident = _definitions("ISSUER_SERVICE_CREDENTIAL_DEFINITIONS", "BPN:bpn,MEMBERSHIP:membership")[row["credential_type"]]
        self._admin("POST", f"/holders/{row['bpn']}/credentials/revoke", {"credentialDefinition": ident})
        return True


_stub = StubRoute()


def stub_orders() -> list[dict]:
    """Every order the STUB route received (tests)."""
    return list(_stub.orders)


def get(name: str):
    if name == STUB:
        return _stub
    routes = {CSP_ISSUER: CspIssuerRoute, CREDENTIAL_ISSUER: CredentialIssuerRoute, ISSUER_SERVICE: IssuerServiceRoute}
    if name not in routes:
        raise _no_route(f"route {name} is not available")
    return routes[name]()


def reset() -> None:
    _stub.reset()
