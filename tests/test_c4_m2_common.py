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
"""Shared test kit of team 3 (C4-M2 Dataspace Wallet Interface and C4-M1 Credentials).

The C4-M1 test files import from here as well (CLAUDE.md rule 1 allows only `tests/test_<id>_*.py`).
This file holds fixtures and helpers, no tests. Import explicitly, e.g.:

    from test_c4_m2_common import COMPANIES, companies, osp_factory, ...

Seams that the production code must provide are listed in TEAM3-PLAN.md section 12; they are reached
lazily here (`seam("modules.c4_m2.service")`) so that a missing module fails the single test that needs
it instead of breaking collection.

Contents
--------
constants      BASE, CSP_URL, OSP_A_ID, OSP_B_ID, SECRETS_KEY_HEX
COMPANIES      spec test companies of C4-M2 14.1 and C4-M1 14 (dicts with id, name, bpn, status)
companies      fixture: fake C3-M1 `query_company` (CompanyBook: add, set_status, set_bpn)
osp_factory    fixture: `start(env=None, csp=False) -> Osp` (installation OSP A, optional shared CSP stand-in)
Osp            .client, .get/.post/.put/.delete(path, token=None, ...), .events(type), .person(...), .service(...)
seam           lazy import of a production module
schema_errors  field-name check of a body against an openapi schema of a module
event_errors   same for the `data` of a CloudEvent against the spec's `Event<Name>` schema
assert_no_secret   a secret appears in none of the given haystacks
wallet_fake    fixture: fake C4-M2 `get_wallet_info` / `get_holder_access` for the C4-M1 tests
Clock          settable clock to patch `service.now`
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import importlib
import json
import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import BASE
from portal_common import csp as csp_client
from portal_common import events, spec
from portal_common import http as phttp
from portal_common.problems import Problem
from tools import test_iam
from tools.csp_standin.app import create_app as create_csp
from tools.keys import ec_jwk

CSP_URL = "http://csp.test"
OSP_A_ID = "22222222-2222-4222-8222-222222222222"
OSP_B_ID = "99a5685c-7397-402c-88de-b1b3a939ecc9"
SECRETS_KEY_HEX = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
SECRETS_KEY_HEX_V2 = "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100"


# ----------------------------------------------------------------------------------- test companies
def _c(cid: str, name: str, bpn: str | None, status: str = "ACTIVE") -> dict:
    return {"id": cid, "name": name, "bpn": bpn, "status": status}


COMPANIES: dict[str, dict] = {
    # C4-M2 README 14.1 (status ACTIVE except "inactive"; onboarding companies are REQUESTED at C3-M1,
    # but create-wallet only needs a BPN)
    "div": _c("1a2b3c4d-0001-4000-8000-000000000001", "SAP DIV Test GmbH", "BPNL0000000DIV01"),
    "ih": _c("1a2b3c4d-0002-4000-8000-000000000002", "IdentityHub Test GmbH", "BPNL00000000IH01"),
    "csp": _c("c0000001-0000-4000-8000-000000000001", "Beispiel Maschinenbau GmbH", "BPNLIUK2REMLK3F4"),
    "csp_rejected": _c("1a2b3c4d-0007-4000-8000-000000000007", "CSP Rejects GmbH", "BPNL00000000CSP2"),
    "fail_did": _c("1a2b3c4d-0004-4000-8000-000000000004", "Wrong DID GmbH", "BPNL000000FAIL01"),
    "fail_no_callback": _c("1a2b3c4d-0005-4000-8000-000000000005", "No Callback GmbH", "BPNL000000FAIL02"),
    "inactive": _c("1a2b3c4d-0006-4000-8000-000000000006", "Deactivated GmbH", "BPNL0000000INA01", "INACTIVE"),
    "byo": _c("5b0c9d1e-2f3a-4b5c-8d6e-7f8091a2b3c4", "Own Wallet GmbH", "BPNL0000000BYO01"),
    "no_bpn": _c("1a2b3c4d-0008-4000-8000-000000000008", "No BPN GmbH", None, "REQUESTED"),
    # C4-M1 README 14: U1 (= C4-M2 "csp" company, REQUESTED at onboarding), U2 to U6
    "u1": _c("c0000001-0000-4000-8000-000000000001", "Beispiel Maschinenbau GmbH", "BPNLIUK2REMLK3F4", "REQUESTED"),
    "u2": _c("c4100002-0000-4000-8000-000000000002", "U2 without BPN", None, "REQUESTED"),
    "u3": _c("c4100003-0000-4000-8000-000000000003", "U3 wallet not ready", "BPNL0000000000U3", "REQUESTED"),
    "u4": _c("c4100004-0000-4000-8000-000000000004", "U4 SAP DIV", "BPNL0000000000U4", "ACTIVE"),
    "u5": _c("c4100005-0000-4000-8000-000000000005", "U5 IdentityHub", "BPNL0000000000U5", "ACTIVE"),
    "u6": _c("c4100006-0000-4000-8000-000000000006", "U6 CSP wallet", "BPNL0000000000U6", "REQUESTED"),
    # OPEN-QUESTION: C4-M1 README 14 names "one more company with provider BRING_YOUR_OWN" without an ID;
    # this ID is a test-only choice (it is not a FRAMEWORK 7a ID).
    "u7_byo": _c("c4100007-0000-4000-8000-000000000007", "U7 own wallet", "BPNL0000000000U7", "REQUESTED"),
}


def company(key: str, **changes) -> dict:
    return {**copy.deepcopy(COMPANIES[key]), **changes}


class CompanyBook:
    """Fake C3-M1: `modules.c3_m1.interface.query_company(companyId=...)` answers from here."""

    def __init__(self) -> None:
        self.data: dict[str, dict] = {c["id"]: copy.deepcopy(c) for c in COMPANIES.values()}
        self.calls: list[str] = []

    def add(self, c: dict) -> dict:
        self.data[c["id"]] = copy.deepcopy(c)
        return c

    def set_status(self, company_id: str, status: str) -> None:
        self.data[company_id]["status"] = status

    def set_bpn(self, company_id: str, bpn: str | None) -> None:
        self.data[company_id]["bpn"] = bpn

    def remove(self, company_id: str) -> None:
        self.data.pop(company_id, None)

    def query_company(self, *, companyId: str) -> dict:
        self.calls.append(companyId)
        if companyId not in self.data:
            raise Problem("c3-m1", 404, "not-found")
        return copy.deepcopy(self.data[companyId])


@pytest.fixture
def companies(monkeypatch) -> CompanyBook:
    """Fake C3-M1. `neighbours.query` calls the interface function in-process at call time; a 404 Problem
    becomes `None` for the caller (portal_common/neighbours.py)."""
    book = CompanyBook()
    monkeypatch.setattr("modules.c3_m1.interface.query_company", book.query_company)
    return book


# ------------------------------------------------------------------------------------------- seams
def seam(name: str) -> Any:
    """Lazy import of a production module/seam, e.g. `seam("modules.c4_m2.service")`."""
    return importlib.import_module(name)


class Clock:
    """A settable UTC clock; patch it with `clock.install(monkeypatch, "modules.c4_m2.service")`."""

    def __init__(self, start: dt.datetime | None = None) -> None:
        self.t = start or dt.datetime(2026, 11, 6, 9, 0, tzinfo=dt.UTC)

    def __call__(self) -> dt.datetime:
        return self.t

    def advance(self, **kw) -> dt.datetime:
        self.t += dt.timedelta(**kw)
        return self.t

    def install(self, monkeypatch, service_module: str) -> Clock:
        monkeypatch.setattr(f"{service_module}.now", self)
        return self


# ---------------------------------------------------------------------------------------- the OSP
M2_ENV = {
    "ENABLED_PROVIDERS": "SAP_DIV,IDENTITY_HUB,CSP",           # C4-M2 14.1 test configuration
    "SAP_DIV_DID_DOCUMENT_BASE_URL": "https://div.example.org/did",
    "IDENTITYHUB_DID_BASE": "ih.example.org",
    "SAP_DIV_CALLBACK_CLIENT_ID": "sa-div-callback",
    "STUB_CALLBACK_DELAY_SECONDS": "0",
    "SECRETS_KEY": SECRETS_KEY_HEX,
    "SECRETS_KEY_VERSION": "1",
    "TIMER_INTERVAL_SECONDS": "3600",                           # tests drive the timer with run_timer_once()
    "SAP_DIV_URL": "", "IDENTITYHUB_URL": "", "CSP_WALLET_URL": "", "DID_RESOLVER_URL": "",
}
M1_ENV = {
    "ISSUER_MODE": "OWN",                                       # OSP A: empty ISSUER_ROUTES = route STUB
    "ISSUER_ROUTES": "",
    "CSP_ISSUER_URL": "",
    "ONBOARDING_CREDENTIAL_TYPES": "BPN,MEMBERSHIP",
    "STUB_ISSUER_DELAY_SECONDS": "5",
    "STUB_ISSUER_FAIL_TYPES": "",
    "RESEND_AFTER_HOURS": "24",
}

# Roles and permissions of the in-memory Portal IAM (tools/test_iam.py): `Company Admin` and `IT Admin` have
# view_credentials, view_dataspace_wallet, retrieve_wallet_credentials; `OSP Admin` has manage_credentials;
# `Member` and `Applicant` have none of these.


class Osp:
    """Installation OSP A in one process, `with TestClient(app)` already entered."""

    def __init__(self, app, client: TestClient, csp_app=None, tmp_path=None) -> None:
        self.app, self.client, self.csp_app, self.tmp_path = app, client, csp_app, tmp_path

    # --- HTTP -------------------------------------------------------------------------------
    def call(self, method: str, path: str, token: str | None = None, **kw):
        headers = dict(kw.pop("headers", {}) or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.request(method, path, headers=headers, **kw)

    def get(self, path, token=None, **kw):
        return self.call("GET", path, token, **kw)

    def post(self, path, token=None, **kw):
        return self.call("POST", path, token, **kw)

    def put(self, path, token=None, **kw):
        return self.call("PUT", path, token, **kw)

    def delete(self, path, token=None, **kw):
        return self.call("DELETE", path, token, **kw)

    # --- identities -------------------------------------------------------------------------
    def person(self, uid: str, roles: list[str] | tuple[str, ...] = (), company_id: str | None = None,
               bpn: str | None = None, given: str = "Test", family: str = "Person") -> str:
        """Creates (or updates) a test person in the in-memory Portal IAM and returns a Bearer token.
        `roles` are portal roles (`Company Admin`, `IT Admin`, `Member`, `OSP Admin`, `Applicant`)."""
        iam = test_iam.iam()
        iam.first_login(uid, given, family)
        if roles:
            iam.add_portal_roles(uid, list(roles))
        iam.bind(uid, company_id, bpn)
        return iam.person_token(uid)

    def service(self, client_id: str, permissions: list[str] | tuple[str, ...] | None = None) -> str:
        """Token of a service account. With `permissions`, the client is created or replaced with exactly
        these permissions (e.g. `sa-div-callback` with `submit_wallet_callback`)."""
        iam = test_iam.iam()
        if permissions is not None:
            iam.clients[client_id] = {"secret": "test-only-secret", "permissions": set(permissions)}
        return iam.client_token(client_id)

    # --- events -----------------------------------------------------------------------------
    @staticmethod
    def events(type_: str | None = None, source: str | None = None) -> list[dict]:
        return [e for e in events.RELAY.log
                if (not type_ or e["type"] == type_) and (not source or e["source"] == source)]

    # --- shared CSP stand-in ----------------------------------------------------------------
    @property
    def csp(self):
        """The `Csp` object of the shared CSP stand-in (only with `start(csp=True)`)."""
        return self.csp_app.state.csp

    def csp_register(self, bpn: str, did: str | None = None, osp_id: str = OSP_A_ID) -> dict:
        """Registers a company at the CSP stand-in with an explicit BPN (the stand-in derives BPNs from
        identifiers otherwise) and, optionally, its DID in the directory (C4-M1 11.5 `PUT /holders` needs both)."""
        rec = {"bpn": bpn, "legalName": bpn, "country": "DE", "ebwoid": None, "euid": None, "identifiers": [],
               "address": None, "homeOspId": osp_id, "memberActive": False, "did": did, "connectors": {}}
        self.csp.core.companies[bpn] = rec
        return rec


@pytest.fixture
def osp_factory(monkeypatch, tmp_path):
    """`start(env=None, csp=False) -> Osp`.

    Sets `M2_ENV` and `M1_ENV` (overridable by `env`), builds the installation OSP A (`scaffold.app.create_app()`)
    and enters `TestClient(app, base_url=BASE)`. Call it once per test; set anything that must exist
    before the app starts through `env`. With `csp=True` the shared CSP stand-in is registered at
    `http://csp.test` with OSP A as the only trusted OSP: `CSP_URL`, `CSP_WALLET_URL`, `CSP_ISSUER_URL`
    are NOT set (set them via `env`, e.g. `{"CSP_WALLET_URL": CSP_URL + "/wallet/v1"}`);
    `CSP_TOKEN_URL`, `OSP_SIGNING_KEY_FILE`, `DID_RESOLVER_URL`-free defaults are.
    """
    from scaffold import app as scaffold_app
    stack = contextlib.ExitStack()
    started: list[tuple[Any, Any]] = []

    def start(env: dict | None = None, csp: bool = False) -> Osp:
        merged = {**M2_ENV, **M1_ENV, **(env or {})}
        csp_app = None
        if csp:
            priv, pub = ec_jwk("osp-a")
            (tmp_path / "osp-key.json").write_text(json.dumps(priv))
            (tmp_path / "trust.json").write_text(json.dumps({OSP_A_ID: {
                "name": "OSP A", "installationUrl": BASE, "jwk": pub,
                "iamTokenUrl": f"{BASE}/auth/realms/CX-Central/protocol/openid-connect/token"}}))
            merged = {"CSP_TRUST_FILE": str(tmp_path / "trust.json"), "CSP_PUBLIC_URL": CSP_URL,
                      "CSP_TOKEN_URL": f"{CSP_URL}/oauth/token", "CSP_JWKS_URL": f"{CSP_URL}/.well-known/jwks.json",
                      "OSP_SIGNING_KEY_FILE": str(tmp_path / "osp-key.json"), "CSP_CALLBACK_DELAY_SECONDS": "0",
                      **merged}
        for k, v in merged.items():
            monkeypatch.setenv(k, str(v))
        if csp:
            csp_client.reset()
            csp_app = create_csp()
            phttp.register_local(CSP_URL, csp_app)
        app = scaffold_app.create_app()
        client = stack.enter_context(TestClient(app, base_url=BASE))
        started.append((scaffold_app, app))
        return Osp(app, client, csp_app, tmp_path)

    yield start
    for mod, app in started:
        mod.reset_all(app.state.entries)
    stack.close()


# ------------------------------------------------------------------------------- C4-M1 wallet fake
class WalletFake:
    """Fake C4-M2 for the C4-M1 tests: `get_wallet_info` and `get_holder_access` answer from `wallets`.

    Shapes: C4-M1 README 11.2 (`companyId, status, provider, issuanceMode, did, didDocumentLocation,
    providerRef`) plus the openapi `WalletInfo` required fields. `provider` `STUB` exists only here
    (C4-M1 README 6.3 rule 1): the real C4-M2 never produces it."""

    def __init__(self, book: CompanyBook) -> None:
        self.book = book
        self.wallets: dict[str, dict] = {}
        self.access: dict[str, dict] = {}
        self.holder_access_calls: list[str] = []
        self._defaults()

    def _defaults(self) -> None:
        c = COMPANIES
        self.set("u1", provider="STUB", issuanceMode="STUB")                      # README 14: U1 STUB, ACTIVE
        self.set("u3", status="REQUESTED", provider="SAP_DIV", issuanceMode="ISSUER_WRITES", did=None,
                 didDocumentLocation=None)                                         # U3: not ready
        self.set("u4", provider="SAP_DIV", issuanceMode="ISSUER_WRITES",
                 didDocumentLocation="https://wallet.example.org/BPNL0000000000U4/did.json",
                 did="did:web:div.example.org:did:BPNL0000000000U4")
        self.access[c["u4"]["id"]] = {
            "issuanceMode": "ISSUER_WRITES", "companyId": c["u4"]["id"], "bpn": c["u4"]["bpn"],
            "did": "did:web:div.example.org:did:BPNL0000000000U4", "provider": "SAP_DIV",
            "holder": "https://wallet.example.org/BPNL0000000000U4/did.json",
            "walletUrl": "https://wallet.example.org/oauth", "clientId": "u4-client",
            "clientSecret": "u4-secret-do-not-leak"}
        self.set("u5", provider="IDENTITY_HUB", issuanceMode="HOLDER_REQUESTS", providerRef="BPNL0000000000U5",
                 did="did:web:ih.example.org:BPNL0000000000U5")
        self.access[c["u5"]["id"]] = self._holder_requests("u5", "http://ih.example.org/identity",
                                                           "BPNL0000000000U5", "u5-api-key-do-not-leak")
        self.set("u6", provider="CSP", issuanceMode="HOLDER_REQUESTS", providerRef="pc-u6",
                 did="did:web:csp-wallet.example.org:BPNL0000000000U6")
        self.access[c["u6"]["id"]] = self._holder_requests("u6", "http://csp.test/identity/v1", "pc-u6",
                                                           "u6-api-key-do-not-leak")
        self.set("u7_byo", provider="BRING_YOUR_OWN", issuanceMode="CREDENTIAL_OFFER", providerRef=None)

    def _holder_requests(self, key: str, url: str, pcid: str, api_key: str) -> dict:
        c = COMPANIES[key]
        return {"issuanceMode": "HOLDER_REQUESTS", "companyId": c["id"], "bpn": c["bpn"],
                "did": self.wallets[c["id"]]["did"], "provider": self.wallets[c["id"]]["provider"],
                "identityApiUrl": url, "participantContextId": pcid, "apiKey": api_key,
                "credentialServiceUrl": f"https://example.org/credentials/{pcid}"}

    def set(self, key: str, **fields) -> dict:
        c = COMPANIES[key]
        w = {"walletId": "00000000-0000-4000-8000-" + c["id"][-12:], "companyId": c["id"], "bpn": c["bpn"],
             "provider": "STUB", "providerRef": None, "status": "ACTIVE",
             "did": f"did:web:wallet.example.org:{c['bpn']}",
             "didDocumentLocation": f"https://wallet.example.org/{c['bpn']}/did.json",
             "credentialServiceUrl": None, "issuanceMode": "STUB", "supportsWalletAccounts": False,
             "failureReason": None, "activatedAt": "2026-11-06T09:00:00Z"}
        w.update(self.wallets.get(c["id"], {}))
        w.update(fields)
        self.wallets[c["id"]] = w
        return w

    def remove(self, key_or_id: str) -> None:
        self.wallets.pop(COMPANIES[key_or_id]["id"] if key_or_id in COMPANIES else key_or_id, None)

    def get_wallet_info(self, *, companyId: str) -> dict:
        if companyId not in self.wallets:
            raise Problem("c4-m2", 404, "not-found")
        return copy.deepcopy(self.wallets[companyId])

    def get_holder_access(self, *, companyId: str) -> dict:
        self.holder_access_calls.append(companyId)
        w = self.wallets.get(companyId)
        if w is None:
            raise Problem("c4-m2", 404, "not-found")
        if w["status"] != "ACTIVE":
            raise Problem("c4-m2", 409, "wallet-not-active")
        if companyId not in self.access:
            raise Problem("c4-m2", 409, "invalid-state", detail="no holder access for this provider")
        return copy.deepcopy(self.access[companyId])


@pytest.fixture
def wallet_fake(monkeypatch, companies) -> WalletFake:
    fake = WalletFake(companies)
    monkeypatch.setattr("modules.c4_m2.interface.get_wallet_info", fake.get_wallet_info)
    monkeypatch.setattr("modules.c4_m2.interface.get_holder_access", fake.get_holder_access)
    return fake


# ----------------------------------------------------------------------------------- schema checks
def _object_schema(ms: spec.ModuleSpec, schema: dict | None) -> dict:
    return ms.resolve(schema or {})


def schema_errors(module: str, schema: dict | str, value: Any, where: str = "$") -> list[str]:
    """Field-name check of `value` against an openapi schema of `module` (given as schema dict or as the
    name under `components/schemas`): no field the schema does not name, every required field present,
    recursively. Values are not checked, except `const`/`enum` and `maxLength`. `oneOf`/`anyOf`: some
    option must fit."""
    ms = spec.module(module)
    if isinstance(schema, str):
        schema = {"$ref": f"#/components/schemas/{schema}"}
    return _check(ms, schema, value, where)


def _check(ms: spec.ModuleSpec, schema: dict, value: Any, where: str) -> list[str]:
    if value is None or not schema:
        return []
    for key in ("oneOf", "anyOf"):
        if key in schema:
            options = [_check(ms, s, value, where) for s in schema[key] if ms.resolve(s).get("type") != "null"]
            return [] if any(not o for o in options) else min(options, key=len)
    schema = ms.resolve(schema)
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}: expected {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {value!r} not in {schema['enum']}")
    if isinstance(value, str) and schema.get("maxLength") and len(value) > schema["maxLength"]:
        errors.append(f"{where}: longer than {schema['maxLength']}")
    if isinstance(value, list):
        return errors + [e for i, v in enumerate(value)
                         for e in _check(ms, schema.get("items") or {}, v, f"{where}[{i}]")]
    if not isinstance(value, dict) or "properties" not in schema:
        return errors
    props = schema["properties"]
    if schema.get("additionalProperties") is not True:
        errors += [f"{where}.{k}: not in the spec" for k in value if k not in props]
    errors += [f"{where}.{k}: required, missing" for k in schema.get("required", []) if k not in value]
    for k, v in value.items():
        if k in props:
            errors += _check(ms, props[k], v, f"{where}.{k}")
    return errors


def event_errors(module: str, event: dict) -> list[str]:
    """CloudEvent `event` against the spec's `Event<type>` schema of `module` (envelope and `data`)."""
    return schema_errors(module, f"Event{event['type']}", event)


def response_errors(module: str, method: str, path: str, status: int, body: Any) -> list[str]:
    """`body` against the response schema of the operation (path as in openapi, e.g. `/credentials`)."""
    ms = spec.module(module)
    op = ms.document["paths"][path][method.lower()]
    resp = op["responses"].get(str(status), {})
    schema = ((resp.get("content") or {}).get("application/json") or {}).get("schema")
    return _check(ms, schema, body, "$") if schema else []


# --------------------------------------------------------------------------------------- secrets
def assert_no_secret(secret: str, *haystacks: Any) -> None:
    """`secret` must not appear (as text) in any haystack: logs (`caplog.text`), events, step results,
    audit entries, `store.dump()` output, response bodies. Anything JSON-serialisable or str/bytes."""
    needle = secret.encode() if isinstance(secret, str) else secret
    for i, h in enumerate(haystacks):
        blob = h if isinstance(h, (bytes, bytearray)) else (
            h if isinstance(h, str) else json.dumps(h, default=str, sort_keys=True))
        raw = blob if isinstance(blob, (bytes, bytearray)) else blob.encode()
        assert needle not in raw, f"secret found in haystack #{i}"


BPN_RE = re.compile(r"^BPNL[0-9A-Z]{12}$")


def uuid_str(n: int) -> str:
    """A stable UUID for step runs: `uuid_str(1)` etc."""
    return f"00000000-0000-4000-8000-{n:012d}"


def step_input(company_id: str, n: int = 1, **extra) -> dict:
    """Input of a step (FRAMEWORK 4.4): `processId`, `stepRunId`, `companyId` and extra fields."""
    return {"processId": uuid_str(900), "stepRunId": uuid_str(n), "companyId": company_id, **extra}
