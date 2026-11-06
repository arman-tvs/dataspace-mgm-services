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
"""Public interface of C3-M2 CSP Connection (call convention of AGENTS.md).

Steps for Process Orchestration (README 8), the query `find-companies` (README 9), the callback
of the CSP (README 7.2) and the status of a company at the CSP (README 7.1). No token checks
here: the router checks token and permission, a caller in the same process has none.

Steps take the JSON body as a plain dict (`StepInputJson`) and answer a `StepReply`
(FRAMEWORK 4.4). The HTTP contract of the same operations is in `schemas.py`.
"""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from pydantic import ValidationError

from portal_common import events
from portal_common.problems import Problem

from . import csp_client, errors, store
from .errors import MODULE
from .schemas import CspCompanyMatch
from .store import Membership, NotificationType, Registration

__all__ = [
    "MODULE",
    "StepReply",
    "deregister_connector",
    "deregister_membership",
    "find_companies",
    "get_csp_registration",
    "receive_csp_notification",
    "register_company",
    "register_connector",
    "register_did",
    "register_membership",
    "registration_view",
    "reset",
    "transfer_company",
    "update_company",
]

StepInputJson = dict[str, Any]    # JSON body of POST /steps/<step>, incl. processId and stepRunId
StepState = Literal["DONE", "RUNNING"]


class StepReply(TypedDict):
    """Answer of a step (FRAMEWORK 4.4); `result` holds `bpn`, `did`, `connectorId` (all strings)."""
    stepRunId: str | None
    state: StepState
    result: dict[str, str]


class IdentifierJson(TypedDict):
    type: str
    value: str


COUNTRY = re.compile(r"^[A-Z]{2}$")
REASON_OTHER_OSP = "REGISTERED_AT_OTHER_OSP"
REASON_REJECTED = "REJECTED_BY_CSP"


def reset() -> None:
    """Fresh state: own tables empty, then the seed data of README 4; new built-in CSP stand-in."""
    csp_client.reset()
    store.reset()


# ---------------------------------------------------------------- input checks
def _required(input: StepInputJson, field: str) -> str:
    """A non-empty string field of the input; otherwise 400 `validation` (never a KeyError)."""
    value = input.get(field)
    if not isinstance(value, str) or not value.strip():
        raise errors.validation(f"{field} is required")
    return value


def _optional(input: StepInputJson, field: str) -> str | None:
    """An optional string field; `None` and "" both count as absent (flows pass missing lookups as None)."""
    value = input.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise errors.validation(f"{field} must be a string")
    return value


def _identifiers(value: object) -> list[IdentifierJson]:
    """`identifiers` (README 6.5): list of `type` and `value`; `None` counts as empty."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise errors.validation("identifiers must be a list")
    out: list[IdentifierJson] = []
    for item in value:
        kind = item.get("type") if isinstance(item, dict) else None
        text = item.get("value") if isinstance(item, dict) else None
        if not isinstance(kind, str) or not kind or not isinstance(text, str) or not text:
            raise errors.validation("every identifier needs type and value")
        out.append({"type": kind, "value": text})
    return out


def _registered(company_id: str) -> Registration:
    """Precondition of most steps: status `REGISTERED` (otherwise 409 `invalid-state`)."""
    row = store.registrations.get(company_id)
    if row is None or row.status != "REGISTERED" or row.bpn is None:
        status = row.status if row else "no registration"
        raise errors.invalid_state(f"company {company_id} is not REGISTERED at the CSP ({status})")
    return row


def _bpn(row: Registration) -> str:
    """BPN of a registered row (`_registered` guarantees it)."""
    assert row.bpn is not None
    return row.bpn


def _reply(input: StepInputJson, result: dict[str, str] | None = None, state: StepState = "DONE") -> StepReply:
    """Step answer of FRAMEWORK 4.4; the shape of `portal_common.standin.step_reply`, typed."""
    step_run = input.get("stepRunId")
    return {"stepRunId": step_run if isinstance(step_run, str) else None, "state": state, "result": result or {}}


# ---------------------------------------------------------------- status changes (README 6.1)
def _mark_registered(row: Registration, bpn: str) -> None:
    """Status `REGISTERED` with the BPN. The event goes out only on a change (FRAMEWORK 4.4), so a
    repeated step or a repeated callback never starts the next flow step twice. Check, change and
    event happen under `store.lock`, so two threads cannot both see a change."""
    with store.lock:
        changed = row.status != "REGISTERED" or row.bpn != bpn
        row.status, row.bpn, row.failure_reason, row.pending_operation_id = "REGISTERED", bpn, None, None
        row.returning = False
        if changed:
            row.registered_at = store.now()
            row.touch()
            events.publish(MODULE, "CompanyRegisteredAtCsp", {"companyId": row.company_id, "bpn": bpn})


def _mark_failed(row: Registration, reason: str) -> None:
    """Status `FAILED` with the reason; the event goes out only on a change, as in `_mark_registered`."""
    with store.lock:
        changed = row.status != "FAILED" or row.failure_reason != reason
        row.status, row.failure_reason, row.pending_operation_id = "FAILED", reason, None
        if changed:
            row.touch()
            events.publish(MODULE, "CompanyRegistrationAtCspFailed",
                           {"companyId": row.company_id, "reason": reason})


def _mark_rejected(row: Registration, reason: str) -> None:
    """The CSP rejected a registration or a transfer. A company that tried to come back from
    `TRANSFERRED_AWAY` stays `TRANSFERRED_AWAY`, because it still lives at the other OSP and
    deregister-membership must keep its exception of README 8.5 (README 6.1; OPEN-QUESTIONS 16).
    Any other company turns `FAILED`. The failure event goes out in both cases, only on a change."""
    with store.lock:
        if row.status == "TRANSFERRED_AWAY" or row.returning:
            changed = row.status != "TRANSFERRED_AWAY" or row.failure_reason != reason
            row.status, row.failure_reason, row.pending_operation_id = "TRANSFERRED_AWAY", reason, None
            row.returning = False
            if changed:
                row.touch()
                events.publish(MODULE, "CompanyRegistrationAtCspFailed",
                               {"companyId": row.company_id, "reason": reason})
            return
        _mark_failed(row, reason)


def _complete_operation(row: Registration, outcome: str, bpn: str | None, reason: str | None) -> bool:
    """End of a long-running operation at the CSP (README 7.2 step 3), from a callback or an early
    one. True if the company is registered now."""
    if outcome == "SUCCEEDED" and bpn:
        _mark_registered(row, bpn)
        return True
    _mark_rejected(row, reason or REASON_REJECTED)
    return False


def _mark_transferred_away(row: Registration) -> None:
    """Status `TRANSFERRED_AWAY`. The new home OSP owns the company at the CSP now (FRAMEWORK 5.6), so
    what this module knew about the company's DID, membership and connectors at the CSP is no longer
    true: forget the DID, set the membership `NONE` and mark the connectors `DEREGISTERED`. After a
    return, register-did, register-membership and register-connector then call the CSP again, even
    with unchanged values (README 6.4, 8.5; OPEN-QUESTIONS 14). No event for these resets."""
    with store.lock:
        row.status, row.did, row.membership = "TRANSFERRED_AWAY", None, "NONE"
        # A registration or return still waiting at the CSP is over: forget its operation id, so a
        # late OperationCompleted cannot find the company by it and revive it (README 6.1).
        row.pending_operation_id, row.returning = None, False
        row.touch()
        stamp = store.now()
        for con in store.connectors.values():
            if con.company_id == row.company_id and con.status == "REGISTERED":
                con.status, con.updated_at = "DEREGISTERED", stamp


def _registration_answer(input: StepInputJson, company_id: str, status: int, answer: object) -> StepReply:
    """Answer of `POST /companies` or `POST /companies/{bpn}/transfer` (README 8.1, 8.2)."""
    body: dict[str, Any] = answer if isinstance(answer, dict) else {}
    if status == 201:
        bpn = body.get("bpn")
        if not isinstance(bpn, str) or not bpn:
            raise errors.upstream_error("the CSP confirmed without a BPN")
        # Precondition of README 8.1: no other REGISTERED company with the same EBWOID or EUID. The
        # module may not store them (README 5), so the check uses the BPN the CSP derives from them
        # (OPEN-QUESTIONS 1). Nothing is changed on this path.
        if (other := store.find_by_bpn(bpn, exclude=company_id, status="REGISTERED")) is not None:
            raise errors.invalid_state(f"BPN {bpn} is already registered for company {other.company_id}")
        _mark_registered(store.registration_row(company_id), bpn)
        return _reply(input, {"bpn": bpn})
    if status == 202:
        operation_id = body.get("operationId")
        if not isinstance(operation_id, str) or not operation_id:
            raise errors.upstream_error("the CSP accepted without an operationId")
        # Storing PENDING and taking a callback that came first happen under `store.lock`; the
        # callback looks up the operation under the same lock, so it is either found here or
        # finds the row (OPEN-QUESTIONS 15). Without this the company would wait for ever.
        with store.lock:
            row = store.registration_row(company_id)
            row.status, row.pending_operation_id, row.failure_reason = "PENDING", operation_id, None
            row.touch()
            early = store.early_completions.pop(operation_id, None)
            registered = False
            if early is not None:
                registered = _complete_operation(row, early.outcome, early.bpn, early.reason)
                store.notifications[early.notification_id] = store.Notification(
                    early.notification_id, "OperationCompleted", row.bpn, store.now())
                store.record_audit("notification:OperationCompleted", company_id, row.bpn, 200, "applied-late")
        if early is not None:
            if registered and early.bpn:
                return _reply(input, {"bpn": early.bpn})
            raise errors.csp_rejected(f"the CSP rejected the operation ({row.failure_reason})", None)
        return _reply(input, state="RUNNING")
    # Final answers turn the row FAILED and publish the failure event: 409 = another OSP is the
    # home OSP, any other 4xx = business rejection (OPEN-QUESTIONS 2, 3). A 5xx or no answer
    # leaves the row as it was; raise_for answers retryable and C12 tries the step again.
    if status == 409:
        _mark_rejected(store.registration_row(company_id), REASON_OTHER_OSP)
        home = body.get("homeOspId")
        raise errors.registered_at_other_osp(home if isinstance(home, str) else None)
    if csp_client.is_business_rejection(status):
        _mark_rejected(store.registration_row(company_id), REASON_REJECTED)
    csp_client.raise_for(status, answer, ok=())
    raise AssertionError("unreachable")  # raise_for always raises with ok=()


# ---------------------------------------------------------------- steps (README 8)
def register_company(input: StepInputJson) -> StepReply:
    """Step register-company (README 8.1)."""
    company_id = _required(input, "companyId")
    legal_name = _required(input, "legalName")
    country = _required(input, "country")
    if not COUNTRY.match(country):
        raise errors.validation("country must be two upper-case letters")
    ebwoid, euid = _optional(input, "ebwoid"), _optional(input, "euid")
    identifiers = _identifiers(input.get("identifiers"))
    if not (ebwoid or euid or identifiers):
        raise errors.validation("at least ebwoid, euid or an entry in identifiers is required (README 6.5)")

    # Repetitions (README 6.4): a registered company returns its BPN, a running operation stays
    # RUNNING; neither calls the CSP again. PENDING without an operation id has no running
    # operation, so it calls the CSP again like a new one (OPEN-QUESTIONS 19). From
    # TRANSFERRED_AWAY the only way back is transfer-company (README 6.1, OPEN-QUESTIONS 6).
    # New or FAILED: call the CSP (again).
    row = store.registrations.get(company_id)
    if row is not None and row.status == "REGISTERED" and row.bpn:
        return _reply(input, {"bpn": row.bpn})
    if row is not None and row.status == "PENDING" and row.pending_operation_id:
        return _reply(input, state="RUNNING")
    if row is not None and row.status == "TRANSFERRED_AWAY":
        raise errors.invalid_state("the company moved to another OSP; a return uses transfer-company")

    payload: dict[str, Any] = {"legalName": legal_name, "country": country, "identifiers": identifiers}
    payload |= {k: v for k, v in (("ebwoid", ebwoid), ("euid", euid)) if v}
    if isinstance(input.get("address"), dict):
        payload["address"] = input["address"]
    status, answer = csp_client.call("register-company", "POST", "/companies", payload, company_id=company_id)
    return _registration_answer(input, company_id, status, answer)


def transfer_company(input: StepInputJson) -> StepReply:
    """Step transfer-company (README 8.2): the company moves to this OSP."""
    company_id = _required(input, "companyId")
    bpn = _required(input, "bpn")
    ebwoid, euid = _optional(input, "ebwoid"), _optional(input, "euid")
    identifiers = _identifiers(input.get("identifiers"))

    row = store.registrations.get(company_id)
    if row is not None and row.status == "REGISTERED":
        if row.bpn != bpn:
            raise errors.invalid_state(f"company {company_id} is registered with another BPN")
        return _reply(input, {"bpn": bpn})
    if row is not None and row.status == "PENDING" and row.pending_operation_id:   # OPEN-QUESTIONS 19
        return _reply(input, state="RUNNING")

    if row is not None and row.status == "TRANSFERRED_AWAY":
        row.returning = True   # a rejection keeps TRANSFERRED_AWAY (_mark_rejected)
    payload: dict[str, Any] = {k: v for k, v in (("ebwoid", ebwoid), ("euid", euid)) if v}
    if identifiers:
        payload["identifiers"] = identifiers
    status, answer = csp_client.call("transfer-company", "POST", f"/companies/{bpn}/transfer", payload,
                                     company_id=company_id, bpn=bpn)
    return _registration_answer(input, company_id, status, answer)


def register_did(input: StepInputJson) -> StepReply:
    """Step register-did (README 8.3): DID in the directory BPN -> DID."""
    company_id = _required(input, "companyId")
    did = _required(input, "did")
    row = _registered(company_id)
    bpn = _bpn(row)
    if row.did != did:
        status, answer = csp_client.call("register-did", "PUT", f"/companies/{bpn}/did", {"did": did},
                                         company_id=company_id, bpn=bpn)
        csp_client.raise_for(status, answer)
        with store.lock:
            if row.did != did:   # a concurrent call may have stored it meanwhile: one event only
                row.did = did
                row.touch()
                events.publish(MODULE, "CompanyDidRegistered", {"companyId": company_id, "bpn": bpn, "did": did})
    return _reply(input, {"bpn": bpn, "did": did})


def update_company(input: StepInputJson) -> StepReply:
    """Step update-company (README 8.4): changed core data to the CSP. The module keeps no core
    data (README 5), so a repetition is recognised by the `stepRunId` (FRAMEWORK 4.4)."""
    company_id = _required(input, "companyId")
    legal_name = _required(input, "legalName")
    euid = _optional(input, "euid")
    row = _registered(company_id)
    bpn = _bpn(row)
    step_run = _optional(input, "stepRunId")
    if step_run and row.last_update_step_run == step_run:
        return _reply(input)
    payload: dict[str, Any] = {"legalName": legal_name}
    if euid:
        payload["euid"] = euid
    if isinstance(input.get("address"), dict):
        payload["address"] = input["address"]
    status, answer = csp_client.call("update-company", "PATCH", f"/companies/{bpn}", payload,
                                     company_id=company_id, bpn=bpn)
    csp_client.raise_for(status, answer)
    with store.lock:
        if not (step_run and row.last_update_step_run == step_run):   # one event per stepRunId
            row.last_update_step_run = step_run
            row.touch()
            events.publish(MODULE, "CompanyUpdatedAtCsp", {"companyId": company_id, "bpn": bpn})
    return _reply(input)


def _membership(input: StepInputJson, member: bool) -> StepReply:
    """Steps register-membership and deregister-membership (README 8.5)."""
    company_id = _required(input, "companyId")
    current = store.registrations.get(company_id)
    if not member and current is not None and current.status == "TRANSFERRED_AWAY":
        # the new home OSP owns the membership now (FRAMEWORK 5.6 step 3): no call, no event
        if current.membership != "NONE":
            current.membership = "NONE"
            current.touch()
        return _reply(input)
    row = _registered(company_id)
    bpn = _bpn(row)
    target: Membership = "REGISTERED" if member else "DEREGISTERED"
    if row.membership != target:
        operation = "register-membership" if member else "deregister-membership"
        status, answer = csp_client.call(operation, "PUT", f"/companies/{bpn}/membership", {"member": member},
                                         company_id=company_id, bpn=bpn)
        csp_client.raise_for(status, answer)
        with store.lock:
            if row.membership != target:   # one event only, also with a concurrent call
                row.membership = target
                row.touch()
                events.publish(MODULE, "MembershipRegistered" if member else "MembershipDeregistered",
                               {"companyId": company_id, "bpn": bpn})
    return _reply(input)


def register_membership(input: StepInputJson) -> StepReply:
    """Step register-membership (README 8.5)."""
    return _membership(input, True)


def deregister_membership(input: StepInputJson) -> StepReply:
    """Step deregister-membership (README 8.5)."""
    return _membership(input, False)


def register_connector(input: StepInputJson) -> StepReply:
    """Step register-connector (README 8.6): connector into the discovery of the CSP."""
    company_id = _required(input, "companyId")
    connector_id = _required(input, "connectorId")
    endpoint = _required(input, "endpointUrl")
    if not endpoint.startswith("https://"):
        raise errors.validation("endpointUrl must be an HTTPS address")
    bpn = _bpn(_registered(company_id))
    # Call the CSP only for a new connector or a new address (README 6.4); the same call again
    # answers DONE without a call and without an event.
    con = store.connectors.get(connector_id)
    if con is not None and con.status == "REGISTERED" and con.company_id != company_id:
        # Entering it under the new BPN would leave it listed under the old one as well (README 6.6;
        # OPEN-QUESTIONS 17): C6-M1 deregisters it first.
        raise errors.invalid_state(f"connector {connector_id} is registered for company {con.company_id}; "
                                   "deregister it there first")
    unchanged = (con is not None and con.status == "REGISTERED" and con.endpoint_url == endpoint
                 and con.company_id == company_id and con.bpn == bpn)
    if not unchanged:
        status, answer = csp_client.call("register-connector", "PUT", f"/companies/{bpn}/connectors/{connector_id}",
                                         {"endpointUrl": endpoint}, company_id=company_id, bpn=bpn)
        csp_client.raise_for(status, answer)
        with store.lock:
            now = store.connectors.get(connector_id)
            if not (now is not None and now.status == "REGISTERED" and now.endpoint_url == endpoint
                    and now.company_id == company_id and now.bpn == bpn):   # one event only
                stamp = store.now()
                store.connectors[connector_id] = store.Connector(
                    connector_id=connector_id, company_id=company_id, bpn=bpn, endpoint_url=endpoint,
                    status="REGISTERED", registered_at=now.registered_at if now else stamp, updated_at=stamp)
                events.publish(MODULE, "ConnectorRegisteredAtCsp",
                               {"companyId": company_id, "bpn": bpn, "connectorId": connector_id})
    return _reply(input, {"bpn": bpn, "connectorId": connector_id})


def deregister_connector(input: StepInputJson) -> StepReply:
    """Step deregister-connector (README 8.6): unknown or already removed -> DONE without a call."""
    company_id = _required(input, "companyId")
    connector_id = _required(input, "connectorId")
    # Unknown or already removed: DONE without a call (README 6.4). The result carries the BPN only
    # when it is known (OPEN-QUESTIONS 8). A known connector needs a REGISTERED company
    # (OPEN-QUESTIONS 7), and it must be the connector's host company (README 8.6), otherwise the
    # event would pair one company's id with another's BPN (OPEN-QUESTIONS 17).
    con = store.connectors.get(connector_id)
    if con is None or con.status == "DEREGISTERED":
        row = store.registrations.get(company_id)
        bpn = con.bpn if con else (row.bpn if row else None)
        return _reply(input, {"connectorId": connector_id} | ({"bpn": bpn} if bpn else {}))
    if con.company_id != company_id:
        raise errors.invalid_state(f"connector {connector_id} is registered for company {con.company_id}, "
                                   f"not for {company_id}")
    _registered(company_id)
    status, answer = csp_client.call("deregister-connector", "DELETE",
                                     f"/companies/{con.bpn}/connectors/{connector_id}",
                                     company_id=company_id, bpn=con.bpn)
    csp_client.raise_for(status, answer)
    with store.lock:
        current = store.connectors.get(connector_id)   # read again: a concurrent call may have removed it
        if current is not None and current.status == "REGISTERED":   # one event only
            current.status, current.updated_at = "DEREGISTERED", store.now()
            events.publish(MODULE, "ConnectorDeregisteredAtCsp",
                           {"companyId": company_id, "bpn": con.bpn, "connectorId": connector_id})
    return _reply(input, {"bpn": con.bpn, "connectorId": connector_id})


# ---------------------------------------------------------------- query (README 9)
def find_companies(*, ebwoid: str | None = None, euid: str | None = None, identifier: list[str] | str | None = None,
                   legalName: str | None = None, country: str | None = None) -> list[dict[str, Any]]:  # openapi names
    """Query findCompanies (README 9, 6.2): duplicate check at the CSP; one `CspCompanyMatch` per match."""
    identifiers = [identifier] if isinstance(identifier, str) else list(identifier or [])
    for value in identifiers:
        kind, _, rest = value.partition(":")
        if not kind or not rest:
            raise errors.validation("identifier must have the form <type>:<value>")
    if country and not COUNTRY.match(country):
        raise errors.validation("country must be two upper-case letters")
    if not (ebwoid or euid or identifiers or (legalName and country)):
        raise errors.validation("ebwoid, euid, identifier, or legalName with country is required")
    params: dict[str, Any] = {k: v for k, v in (("ebwoid", ebwoid), ("euid", euid), ("legalName", legalName),
                                                ("country", country)) if v}
    if identifiers:
        params["identifier"] = identifiers
    status, answer = csp_client.call("find-companies", "GET", "/companies", params=params)
    if status == 400:
        raise errors.validation("the CSP rejected the search parameters")
    csp_client.raise_for(status, answer, ok=(200,))
    if not isinstance(answer, list):
        raise errors.upstream_error("the CSP answered without a list")
    if not all(isinstance(m, dict) for m in answer):
        raise errors.upstream_error("the CSP answered a match that is not an object")
    own = csp_client.osp_id()
    matches = [{"bpn": m.get("bpn"), "legalName": m.get("legalName"), "country": m.get("country"),
                "matchedBy": m.get("matchedBy"), "homeOspId": m.get("homeOspId"), "homeOspName": m.get("homeOspName"),
                "homeIsThisOsp": m.get("homeOspId") == own, "memberActive": m.get("memberActive")}
               for m in answer]
    # Every match must be a CspCompanyMatch of README 9 (the router's response model). Checked here,
    # so a CSP answer with a missing or wrong field is 502 upstream-error both in-process and over
    # HTTP, never a 500 from the response check of FastAPI.
    for match in matches:
        try:
            CspCompanyMatch.model_validate(match)
        except ValidationError as e:
            fields = ", ".join(sorted({".".join(str(x) for x in err["loc"]) for err in e.errors()}))
            raise errors.upstream_error(f"the CSP answered a match with a missing or invalid {fields}") from e
    return matches


# ---------------------------------------------------------------- callback of the CSP (README 7.2)
def receive_csp_notification(body: dict[str, Any]) -> dict[str, str | bool]:
    """Notification from the CSP; a known `notificationId` is acknowledged and not processed again.
    Every notification gets an audit entry, also a duplicate and a rejected one (README 5)."""
    try:
        with store.lock:   # duplicate check, lookup and change in one step (OPEN-QUESTIONS 15)
            return _receive_notification(body)
    except Problem as p:
        kind, bpn = body.get("type"), body.get("bpn")
        store.record_audit(f"notification:{kind if isinstance(kind, str) else 'invalid'}", None,
                           bpn if isinstance(bpn, str) else None, p.status, p.name)
        raise


def _receive_notification(body: dict[str, Any]) -> dict[str, str | bool]:
    notification_id = _required(body, "notificationId")
    kind = _required(body, "type")
    if kind == "OperationCompleted":
        kind_type: NotificationType = "OperationCompleted"
    elif kind == "CompanyTransferredAway":
        kind_type = "CompanyTransferredAway"
    else:
        raise errors.validation("type must be OperationCompleted or CompanyTransferredAway")
    bpn = _optional(body, "bpn")
    if notification_id in store.notifications:
        store.record_audit(f"notification:{kind_type}", None, bpn, 200, "duplicate")
        return {"notificationId": notification_id, "accepted": True}

    if kind_type == "OperationCompleted":
        operation_id = _required(body, "operationId")
        outcome = _required(body, "outcome")
        if outcome == "SUCCEEDED":
            result: Literal["SUCCEEDED", "FAILED"] = "SUCCEEDED"
        elif outcome == "FAILED":
            result = "FAILED"
        else:
            raise errors.validation("outcome must be SUCCEEDED or FAILED")
        reason = _optional(body, "reason")
        if outcome == "SUCCEEDED" and not bpn:
            raise errors.validation("bpn is required with outcome SUCCEEDED")
        # The operation id identifies the registration; the BPN is the fallback (README 7.2 step 2),
        # but only for a registration that still waits (PENDING): a late notification must not
        # revive a FAILED or TRANSFERRED_AWAY company (README 6.1). An unknown one answers 404 and
        # is not stored, so the CSP can send it again once it is known here (OPEN-QUESTIONS 9).
        row = store.find_by_operation(operation_id) or (
            store.find_by_bpn(bpn, status="PENDING") if bpn else None)
        if row is None:
            # Possibly earlier than the 202 answer of the step: keep it aside, the step applies it
            # when it stores the operation id (OPEN-QUESTIONS 15). The answer stays 404 (README 7.2).
            store.keep_early_completion(store.EarlyCompletion(notification_id, operation_id, result, bpn, reason,
                                                              store.now()))
            raise errors.unknown_company(f"no registration for operation {operation_id}")
        _complete_operation(row, result, bpn, reason)
    else:
        if not bpn:
            raise errors.validation("bpn is required with CompanyTransferredAway")
        # Prefer the REGISTERED row: after a company came back, an older row with the same BPN can exist.
        row = store.find_by_bpn(bpn, status="REGISTERED") or store.find_by_bpn(bpn)
        if row is None:
            raise errors.unknown_company(f"no registration for BPN {bpn}")
        if row.status != "TRANSFERRED_AWAY":
            _mark_transferred_away(row)
            events.publish(MODULE, "CompanyTransferredAway", {"companyId": row.company_id, "bpn": bpn})

    # Stored only after it was processed, so a failed processing does not swallow the notification.
    store.notifications[notification_id] = store.Notification(notification_id, kind_type, row.bpn, store.now())
    store.record_audit(f"notification:{kind_type}", row.company_id, row.bpn, 200)
    return {"notificationId": notification_id, "accepted": True}


# ---------------------------------------------------------------- status at the CSP (README 7.1)
def registration_view(row: Registration) -> dict[str, str]:
    """A registration as `CspRegistration`; empty fields are left out."""
    view: dict[str, str | None] = {
        "companyId": row.company_id, "bpn": row.bpn, "status": row.status, "failureReason": row.failure_reason,
        "did": row.did, "membership": row.membership, "registeredAt": row.registered_at, "updatedAt": row.updated_at}
    return {k: v for k, v in view.items() if v is not None}


def get_csp_registration(companyId: str) -> dict[str, str]:  # openapi name
    """Operation getCspRegistration (README 7.1); 404 `not-found` without a registration."""
    row = store.registrations.get(companyId)
    if row is None or row.status is None:
        raise errors.not_found()
    return registration_view(row)
