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
"""Business rules of C4-M1 Credentials (README 6, 7.4, 8).

Talks only to the `CredentialStore` interface (`store()`), never to dicts. Every change of a row
writes `credential_history` (README 6.1); every operation for one company runs inside
`store().transaction(company_id)` (README 6.6). All time reads go through `now()`.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
import uuid

from portal_common import events, neighbours
from portal_common.problems import Problem

from . import routes
from .store import CredentialStore, InMemoryStore

MODULE = "c4-m1"
log = logging.getLogger("c4-m1")
TYPES = ("BPN", "MEMBERSHIP")
BPN_RE = re.compile(r"^BPNL[A-Za-z0-9]{12}$", re.IGNORECASE)

_store: CredentialStore | None = None


def now() -> dt.datetime:
    """The single clock of the module (timezone-aware UTC); tests patch it."""
    return dt.datetime.now(dt.UTC)


def store() -> CredentialStore:
    global _store
    if _store is None:
        _store = InMemoryStore()
    return _store


def reset() -> None:
    """Empties the store and cancels pending STUB timers."""
    routes.reset()
    store().reset()


def flush_timers() -> None:
    """Fires every pending STUB issuer timer now, through the code path of the HTTP callback (tests)."""
    routes._stub.flush()


# ------------------------------------------------------------------------------------- configuration
def onboarding_types() -> list[str]:
    raw = os.environ.get("ONBOARDING_CREDENTIAL_TYPES") or "BPN,MEMBERSHIP"
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def resend_after() -> dt.timedelta:
    try:
        return dt.timedelta(hours=float(os.environ.get("RESEND_AFTER_HOURS") or 24))
    except ValueError:
        return dt.timedelta(hours=24)


# ------------------------------------------------------------------------------------------ helpers
def _validation(detail: str) -> Problem:
    return Problem(MODULE, 400, "validation", detail=detail, retryable=False)


def valid_uuid(value: object, name: str) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError(name)
        return str(uuid.UUID(value))
    except ValueError:
        raise _validation(f"{name} must be a UUID") from None


def valid_types(value: object, default: list[str]) -> list[str]:
    """`credentialTypes` of a step: absent = `default`; else a non-empty list of unique known types."""
    if value is None:
        return list(default)
    if not isinstance(value, list) or not value or len(set(map(str, value))) != len(value) \
            or any(t not in TYPES for t in value):
        raise _validation("credentialTypes must be a non-empty list of unique values from BPN, MEMBERSHIP")
    return list(value)


def _truncate(text: str | None, n: int) -> str | None:
    return None if text is None else text[:n]


def _change(row: dict, status: str, note: str | None = None, **fields) -> dict:
    """Sets the status of a row and writes the history entry (README 6.1)."""
    t = now()
    row.update(fields)
    row.update(status=status, changed_at=t)
    store().put_credential(row)
    store().append_history({"id": str(uuid.uuid4()), "credential_id": row["id"], "occurred_at": t,
                            "status": status, "attempt": row["attempt"], "note": _truncate(note, 1000)})
    return row


def _put_run(cid: str, types: list[str], status: str, process_id=None, step_run_id=None,
             started_at=None, finished_at=None) -> dict:
    run = {"company_id": cid, "credential_types": list(types), "status": status, "process_id": process_id,
           "step_run_id": step_run_id, "started_at": started_at, "finished_at": finished_at}
    store().put_run(run)
    return run


def _check_round(cid: str) -> None:
    """README 6.2: the round is `DONE` as soon as all its types are `ISSUED`; then, and only then, there is
    exactly one `CredentialsIssued` with the types of the round. A `CANCELLED` round stays as it is."""
    run = store().get_run(cid)
    if not run or run["status"] not in ("RUNNING", "FAILED"):
        return
    rows = [store().get_credential(cid, t) for t in run["credential_types"]]
    if not all(r and r["status"] == "ISSUED" for r in rows):
        return
    run.update(status="DONE", finished_at=now())
    store().put_run(run)
    events.publish(MODULE, "CredentialsIssued", {"companyId": cid, "credentialTypes": list(run["credential_types"])})


# ------------------------------------------------------------------------------------ neighbours
def get_company(cid: str) -> dict | None:
    return neighbours.query(MODULE, "c3-m1", "query_company", companyId=cid)


def get_wallet(cid: str) -> dict | None:
    return neighbours.query(MODULE, "c4-m2", "get_wallet_info", companyId=cid)


def _preconditions(cid: str) -> tuple[dict, dict, str]:
    """README 8.1: company, then wallet, then route. Returns (company, wallet, route name)."""
    company = get_company(cid)
    if not company or not company.get("bpn") or company.get("status") not in ("REQUESTED", "ACTIVE"):
        raise Problem(MODULE, 409, "company-not-ready", detail="company without BPN or not REQUESTED/ACTIVE",
                      retryable=False)
    wallet = get_wallet(cid)
    if not wallet or wallet.get("status") != "ACTIVE" or not wallet.get("did"):
        raise Problem(MODULE, 409, "wallet-not-ready", detail="dataspace wallet not ACTIVE or without DID",
                      retryable=False)
    route = routes.select_route(wallet)
    if route == routes.CREDENTIAL_ISSUER and not wallet.get("didDocumentLocation"):
        raise Problem(MODULE, 409, "wallet-not-ready", detail="wallet without location of the DID document",
                      retryable=False)
    return company, wallet, route


# ---------------------------------------------------------------------------------- issue-credentials
def issue_credentials(input: dict) -> dict:
    """README 8.1."""
    from portal_common import standin
    cid = valid_uuid(input.get("companyId"), "companyId")
    types = valid_types(input.get("credentialTypes"), onboarding_types())
    with store().transaction(cid):
        company, wallet, route_name = _preconditions(cid)
        rows = {t: store().get_credential(cid, t) for t in types}
        if any(r and r["status"] == "REVOCATION_PENDING" for r in rows.values()):
            raise Problem(MODULE, 409, "invalid-state", detail="a credential waits for the confirmation of its "
                          "revocation (confirm-revocation)", retryable=False)
        t_now = now()
        to_order = [t for t in types if not (rows[t] and (
            rows[t]["status"] == "ISSUED"
            or (rows[t]["status"] == "REQUESTED" and t_now - rows[t]["requested_at"] < resend_after())))]
        if to_order:
            route = routes.get(route_name)
            ctx = {"company": company, "wallet": wallet, "route": route_name}
            route.prepare(ctx)
            for t in to_order:
                _order(ctx, route, rows[t], t)
        rows = {t: store().get_credential(cid, t) for t in types}
        all_issued = all(r["status"] == "ISSUED" for r in rows.values())
        run = store().get_run(cid)
        if all_issued:
            started = run["started_at"] if run else now()
            finished = run["finished_at"] if run and run["status"] == "DONE" and run["finished_at"] else now()
            _put_run(cid, types, "DONE", input.get("processId"), input.get("stepRunId"), started, finished)
        else:
            started = run["started_at"] if run and run["status"] == "RUNNING" else now()
            _put_run(cid, types, "RUNNING", input.get("processId"), input.get("stepRunId"), started)
        result = {"companyId": cid, "credentials": [{"credentialType": t, "status": rows[t]["status"]} for t in types]}
        return standin.step_reply(input, result, "DONE" if all_issued else "RUNNING")


def _order(ctx: dict, route, row: dict | None, ctype: str) -> None:
    """Sends the order through the route; only after success the row becomes `REQUESTED` (README 8.1 step 2)."""
    attempt = (row["attempt"] if row else 0) + 1
    request_ref, issuer_did = route.order(ctx, ctype, attempt)
    t = now()
    company, wallet = ctx["company"], ctx["wallet"]
    new = dict(row) if row else {"id": str(uuid.uuid4()), "company_id": company["id"], "credential_type": ctype,
                                 "created_at": t}
    new.update(route=ctx["route"], issuer_did=issuer_did, wallet_provider=wallet.get("provider"),
               bpn=company["bpn"].upper(), holder_did=wallet.get("did"), request_ref=request_ref, attempt=attempt,
               requested_at=t, issued_at=None, failed_at=None, revoked_at=None, failure_reason=None,
               revocation_reason=None)
    _change(new, "REQUESTED")


# ------------------------------------------------------------------------------------ revoke-credentials
def revoke_credentials(input: dict) -> dict:
    """README 8.2. No precondition on company or wallet; per given type (default MEMBERSHIP): `ISSUED` is revoked
    through the route of the order (or waits for OSP staff), `REQUESTED`/`FAILED` become `CANCELLED`."""
    from portal_common import standin
    cid = valid_uuid(input.get("companyId"), "companyId")
    reason = input.get("reason")
    if reason not in ("COMPANY_DEACTIVATED", "OTHER"):
        raise _validation("reason must be COMPANY_DEACTIVATED or OTHER")
    types = valid_types(input.get("credentialTypes"), ["MEMBERSHIP"])
    revoked: list[str] = []
    cancelled: list[str] = []
    manual: list[str] = []
    with store().transaction(cid):
        for t in types:
            row = store().get_credential(cid, t)
            if row is None:
                continue
            if row["status"] == "ISSUED":
                if routes.get(row["route"]).revoke(row):
                    _change(row, "REVOKED", revoked_at=now(), revocation_reason=reason)
                    events.publish(MODULE, "CredentialRevoked", {"companyId": cid, "credentialType": t,
                                                                  "revocationReason": reason})
                    revoked.append(t)
                else:
                    _change(row, "REVOCATION_PENDING", revocation_reason=reason)
                    manual.append(t)
            elif row["status"] in ("REQUESTED", "FAILED"):
                routes.get(row["route"]).cancel(row)
                _change(row, "CANCELLED", revocation_reason=reason)
                cancelled.append(t)
            elif row["status"] == "REVOCATION_PENDING":
                manual.append(t)
        run = store().get_run(cid)
        if run and run["status"] == "RUNNING" and set(run["credential_types"]) & set(types):
            run.update(status="CANCELLED", finished_at=now())
            store().put_run(run)
    return standin.step_reply(input, {"companyId": cid, "revoked": revoked, "cancelled": cancelled,
                                      "manualRevocation": manual})


# -------------------------------------------------------------------------------------- status report
def report_status(kind: str, bpn: str, status: str, message: str | None = None) -> None:
    """README 7.4 steps 3 and 4 (the HTTP layer checks token and input and writes the audit entry)."""
    ctype = kind.upper()
    found = store().find_credential(bpn.upper(), ctype)
    if found is None:
        raise Problem(MODULE, 404, "unknown-request", detail="no order for this BPN and credential type")
    cid = found["company_id"]
    with store().transaction(cid):
        row = store().get_credential(cid, ctype)
        if row is None:
            raise Problem(MODULE, 404, "unknown-request", detail="no order for this BPN and credential type")
        state, ok = row["status"], status == "SUCCESSFUL"
        if state == "REQUESTED":
            if ok:
                _change(row, "ISSUED", message, issued_at=now())
                _check_round(cid)
            else:
                _fail(row, message)
        elif state == "ISSUED":
            if not ok:
                raise Problem(MODULE, 409, "invalid-state", detail="credential is already issued")
        elif state == "FAILED":
            if ok:
                _change(row, "ISSUED", message, issued_at=now())
                _check_round(cid)
        elif state == "CANCELLED" and ok:
            _revoke_now(row)
        # REVOCATION_PENDING, REVOKED, and the remaining combinations: nothing


def validate_report(kind: str, body: object) -> tuple[str, str, str | None]:
    """README 7.4 step 2: unknown kind 404 `not-found`; invalid `bpn` or `status` 400 `validation`.
    Returns (BPN in upper case, status, message)."""
    if kind not in ("bpn", "membership"):
        raise Problem(MODULE, 404, "not-found", detail="credentialKind must be bpn or membership")
    if not isinstance(body, dict):
        raise _validation("the body must be an object")
    bpn, status, message = body.get("bpn"), body.get("status"), body.get("message")
    if not isinstance(bpn, str) or not BPN_RE.match(bpn):
        raise _validation("bpn must be BPNL followed by 12 letters or digits")
    if status not in ("SUCCESSFUL", "UNSUCCESSFUL"):
        raise _validation("status must be SUCCESSFUL or UNSUCCESSFUL")
    if message is not None and not isinstance(message, str):
        raise _validation("message must be a string")
    return bpn.upper(), status, message


def audit(claims: dict, operation: str, company_id: str | None, object_ref: str, result: int) -> None:
    """Audit log entry of a changing operation over HTTP (README 5 `audit_entry`): identifiers only, no names."""
    store().append_audit({"id": str(uuid.uuid4()), "occurred_at": now(), "sub": claims.get("sub"),
                          "client_id": claims.get("azp"), "company_id": claims.get("company_id") or company_id,
                          "operation": operation, "object_ref": object_ref, "result": str(result)})


def _fail(row: dict, message: str | None) -> None:
    _change(row, "FAILED", message, failed_at=now(), failure_reason=_truncate(message, 1000))
    events.publish(MODULE, "CredentialIssuanceFailed", {
        "companyId": row["company_id"], "credentialType": row["credential_type"],
        "reason": _truncate(message, 200) or "issuance failed"})
    run = store().get_run(row["company_id"])
    if run and run["status"] == "RUNNING":
        run["status"] = "FAILED"
        store().put_run(run)


def _revoke_now(row: dict) -> None:
    """A success report for a `CANCELLED` row: revoked immediately (README 6.1 last row, 7.4)."""
    if routes.get(row["route"]).revoke(row):
        _change(row, "REVOKED", revoked_at=now())
        events.publish(MODULE, "CredentialRevoked", {
            "companyId": row["company_id"], "credentialType": row["credential_type"],
            "revocationReason": row.get("revocation_reason") or "OTHER"})
    else:
        _change(row, "REVOCATION_PENDING")


# ------------------------------------------------------------------------------------------------ reads
def _iso(value: dt.datetime | None) -> str | None:
    return value.isoformat() if value else None


def _status_view(row: dict) -> dict:
    return {"credentialType": row["credential_type"], "status": row["status"], "requestedAt": _iso(row.get("requested_at")),
            "issuedAt": _iso(row.get("issued_at")), "revokedAt": _iso(row.get("revoked_at"))}


def _rows_of(cid: str) -> list[dict]:
    rows = store().list_credentials(company_id=cid, size=1000)
    return sorted(rows, key=lambda r: TYPES.index(r["credential_type"]) if r["credential_type"] in TYPES else len(TYPES))


def query_company_credentials(*, companyId: str) -> dict:
    """README 9.1: status per credential type and the last round; an unknown company gives an empty list."""
    run = store().get_run(companyId)
    return {"companyId": companyId, "credentials": [_status_view(r) for r in _rows_of(companyId)],
            "run": None if run is None else {
                "status": run["status"], "credentialTypes": list(run["credential_types"]),
                "startedAt": _iso(run["started_at"]), "finishedAt": _iso(run.get("finished_at"))}}


def list_company_credentials(company_id: str) -> list[dict]:
    """README 7.1: no messages of the issuer, no routes; onboarding types without a row show `NONE`."""
    views = {r["credential_type"]: _status_view(r) for r in _rows_of(company_id)}
    for t in onboarding_types():
        views.setdefault(t, {"credentialType": t, "status": "NONE", "requestedAt": None, "issuedAt": None,
                             "revokedAt": None})
    return [views[t] for t in sorted(views, key=lambda t: TYPES.index(t) if t in TYPES else len(TYPES))]


def _detail_view(row: dict) -> dict:
    """OSP view (README 7.2): every field except secrets (`CredentialDetail`)."""
    return {"id": row["id"], "companyId": row["company_id"], "credentialType": row["credential_type"],
            "status": row["status"], "route": row["route"], "issuerDid": row.get("issuer_did") or None,
            "walletProvider": row.get("wallet_provider"), "bpn": row.get("bpn"), "holderDid": row.get("holder_did"),
            "requestRef": row.get("request_ref") or None, "attempt": row["attempt"],
            "requestedAt": _iso(row.get("requested_at")), "issuedAt": _iso(row.get("issued_at")),
            "failedAt": _iso(row.get("failed_at")), "revokedAt": _iso(row.get("revoked_at")),
            "failureReason": row.get("failure_reason"), "revocationReason": row.get("revocation_reason"),
            "createdAt": _iso(row["created_at"]), "changedAt": _iso(row["changed_at"])}


def list_credentials(statuses=None, credential_type=None, company_id=None, route=None, requested_before=None,
                     page: int = 0, size: int = 20) -> dict:
    """README 7.2: filters, sorted by `changedAt` descending, paged."""
    if requested_before is not None and requested_before.tzinfo is None:
        requested_before = requested_before.replace(tzinfo=dt.UTC)
    filters = dict(company_id=company_id, statuses=statuses, credential_type=credential_type, route=route,
                   requested_before=requested_before)
    rows = store().list_credentials(page=page, size=size, **filters)
    return {"items": [_detail_view(r) for r in rows], "page": page, "size": size,
            "total": store().count_credentials(**filters)}


# ---------------------------------------------------------------------------------- confirm-revocation
def confirm_revocation(credential_id: str, body: object, claims: dict) -> dict:
    """README 7.3: `REVOCATION_PENDING` becomes `REVOKED` (history with the note, audit entry with `sub` of the
    person, `CredentialRevoked`); `REVOKED` stays as it is (200); any other status is 409 `invalid-state`."""
    note = body.get("note") if isinstance(body, dict) else None
    if not isinstance(note, str) or not 1 <= len(note) <= 500:
        raise _validation("note must be a string of 1 to 500 characters")
    found = store().get_credential_by_id(credential_id)
    if found is None:
        raise Problem(MODULE, 404, "not-found", detail="unknown credential")
    with store().transaction(found["company_id"]):
        row = store().get_credential_by_id(credential_id)
        if row["status"] == "REVOKED":
            return _detail_view(row)
        if row["status"] != "REVOCATION_PENDING":
            raise Problem(MODULE, 409, "invalid-state", detail=f"credential is {row['status']}, not REVOCATION_PENDING")
        _change(row, "REVOKED", note, revoked_at=now())
        audit(claims, "CONFIRM_REVOCATION", None, row["id"], 200)
        events.publish(MODULE, "CredentialRevoked", {
            "companyId": row["company_id"], "credentialType": row["credential_type"],
            "revocationReason": row.get("revocation_reason") or "OTHER"})
        return _detail_view(row)
