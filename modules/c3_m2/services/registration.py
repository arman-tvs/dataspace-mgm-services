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
"""Registration of a company at the CSP: status changes (README 6.1) and the steps register-company,
transfer-company, register-did, update-company and the membership steps (README 8.1-8.5)."""
from __future__ import annotations

from typing import Any, NoReturn

from modules.c3_m2 import errors, store
from modules.c3_m2.adapters import csp
from modules.c3_m2.errors import MODULE
from modules.c3_m2.store import Membership, Registration
from portal_common import events

from . import csp_calls
from .common import COUNTRY, StepInputJson, StepReply, bpn_of, identifiers, optional, registered, reply, required

REASON_OTHER_OSP = "REGISTERED_AT_OTHER_OSP"
REASON_REJECTED = "REJECTED_BY_CSP"


# ---------------------------------------------------------------- status changes (README 6.1)
def mark_registered(row: Registration, bpn: str) -> None:
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


def mark_failed(row: Registration, reason: str) -> None:
    """Status `FAILED` with the reason; the event goes out only on a change, as in `mark_registered`."""
    with store.lock:
        changed = row.status != "FAILED" or row.failure_reason != reason
        row.status, row.failure_reason, row.pending_operation_id = "FAILED", reason, None
        if changed:
            row.touch()
            events.publish(MODULE, "CompanyRegistrationAtCspFailed",
                           {"companyId": row.company_id, "reason": reason})


def mark_rejected(row: Registration, reason: str) -> None:
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
        mark_failed(row, reason)


def complete_operation(row: Registration, outcome: str, bpn: str | None, reason: str | None) -> bool:
    """End of a long-running operation at the CSP (README 7.2 step 3), from a callback or an early
    one. True if the company is registered now."""
    if outcome == "SUCCEEDED" and bpn:
        mark_registered(row, bpn)
        return True
    mark_rejected(row, reason or REASON_REJECTED)
    return False


def mark_transferred_away(row: Registration) -> None:
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


# ---------------------------------------------------------------- answer of the CSP (README 8.1, 8.2)
def _confirmed(input: StepInputJson, company_id: str, body: dict[str, Any]) -> StepReply:
    """201: the CSP registered the company right away."""
    bpn = body.get("bpn")
    if not isinstance(bpn, str) or not bpn:
        raise errors.upstream_error("the CSP confirmed without a BPN")
    # Precondition of README 8.1: no other REGISTERED company with the same EBWOID or EUID. The
    # module may not store them (README 5), so the check uses the BPN the CSP derives from them
    # (OPEN-QUESTIONS 1). Nothing is changed on this path.
    if (other := store.find_by_bpn(bpn, exclude=company_id, status="REGISTERED")) is not None:
        raise errors.invalid_state(f"BPN {bpn} is already registered for company {other.company_id}")
    mark_registered(store.registration_row(company_id), bpn)
    return reply(input, {"bpn": bpn})


def _accepted(input: StepInputJson, company_id: str, body: dict[str, Any]) -> StepReply:
    """202: the CSP runs the operation and calls back (README 7.2)."""
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
        registered_now = False
        if early is not None:
            registered_now = complete_operation(row, early.outcome, early.bpn, early.reason)
            store.notifications[early.notification_id] = store.Notification(
                early.notification_id, "OperationCompleted", row.bpn, store.now())
            store.record_audit("notification:OperationCompleted", company_id, row.bpn, 200, "applied-late")
    if early is not None:
        if registered_now and early.bpn:
            return reply(input, {"bpn": early.bpn})
        raise errors.csp_rejected(f"the CSP rejected the operation ({row.failure_reason})", None)
    return reply(input, state="RUNNING")


def _refused(company_id: str, status: int, body: dict[str, Any], answer: object) -> NoReturn:
    """Final answers turn the row FAILED and publish the failure event: 409 = another OSP is the
    home OSP, any other 4xx = business rejection (OPEN-QUESTIONS 2, 3). A 5xx or no answer
    leaves the row as it was; raise_for answers retryable and C12 tries the step again."""
    if status == 409:
        mark_rejected(store.registration_row(company_id), REASON_OTHER_OSP)
        home = body.get("homeOspId")
        raise errors.registered_at_other_osp(home if isinstance(home, str) else None)
    if csp.is_business_rejection(status):
        mark_rejected(store.registration_row(company_id), REASON_REJECTED)
    csp.raise_for(status, answer, ok=())
    raise AssertionError("unreachable")  # raise_for always raises with ok=()


def registration_answer(input: StepInputJson, company_id: str, status: int, answer: object) -> StepReply:
    """Answer of `POST /companies` or `POST /companies/{bpn}/transfer` (README 8.1, 8.2)."""
    body: dict[str, Any] = answer if isinstance(answer, dict) else {}
    if status == 201:
        return _confirmed(input, company_id, body)
    if status == 202:
        return _accepted(input, company_id, body)
    _refused(company_id, status, body, answer)


# ---------------------------------------------------------------- steps (README 8.1-8.5)
def register_company(input: StepInputJson) -> StepReply:
    """Step register-company (README 8.1)."""
    company_id = required(input, "companyId")
    legal_name = required(input, "legalName")
    country = required(input, "country")
    if not COUNTRY.match(country):
        raise errors.validation("country must be two upper-case letters")
    ebwoid, euid = optional(input, "ebwoid"), optional(input, "euid")
    ids = identifiers(input.get("identifiers"))
    if not (ebwoid or euid or ids):
        raise errors.validation("at least ebwoid, euid or an entry in identifiers is required (README 6.5)")

    # Repetitions (README 6.4): a registered company returns its BPN, a running operation stays
    # RUNNING; neither calls the CSP again. PENDING without an operation id has no running
    # operation, so it calls the CSP again like a new one (OPEN-QUESTIONS 19). From
    # TRANSFERRED_AWAY the only way back is transfer-company (README 6.1, OPEN-QUESTIONS 6).
    # New or FAILED: call the CSP (again).
    row = store.registrations.get(company_id)
    if row is not None and row.status == "REGISTERED" and row.bpn:
        return reply(input, {"bpn": row.bpn})
    if row is not None and row.status == "PENDING" and row.pending_operation_id:
        return reply(input, state="RUNNING")
    if row is not None and row.status == "TRANSFERRED_AWAY":
        raise errors.invalid_state("the company moved to another OSP; a return uses transfer-company")

    payload: dict[str, Any] = {"legalName": legal_name, "country": country, "identifiers": ids}
    payload |= {k: v for k, v in (("ebwoid", ebwoid), ("euid", euid)) if v}
    if isinstance(input.get("address"), dict):
        payload["address"] = input["address"]
    status, answer = csp_calls.call("register-company", "POST", "/companies", payload, company_id=company_id)
    return registration_answer(input, company_id, status, answer)


def transfer_company(input: StepInputJson) -> StepReply:
    """Step transfer-company (README 8.2): the company moves to this OSP."""
    company_id = required(input, "companyId")
    bpn = required(input, "bpn")
    ebwoid, euid = optional(input, "ebwoid"), optional(input, "euid")
    ids = identifiers(input.get("identifiers"))

    row = store.registrations.get(company_id)
    if row is not None and row.status == "REGISTERED":
        if row.bpn != bpn:
            raise errors.invalid_state(f"company {company_id} is registered with another BPN")
        return reply(input, {"bpn": bpn})
    if row is not None and row.status == "PENDING" and row.pending_operation_id:   # OPEN-QUESTIONS 19
        return reply(input, state="RUNNING")

    if row is not None and row.status == "TRANSFERRED_AWAY":
        row.returning = True   # a rejection keeps TRANSFERRED_AWAY (mark_rejected)
    payload: dict[str, Any] = {k: v for k, v in (("ebwoid", ebwoid), ("euid", euid)) if v}
    if ids:
        payload["identifiers"] = ids
    status, answer = csp_calls.call("transfer-company", "POST", f"/companies/{bpn}/transfer", payload,
                                    company_id=company_id, bpn=bpn)
    return registration_answer(input, company_id, status, answer)


def register_did(input: StepInputJson) -> StepReply:
    """Step register-did (README 8.3): DID in the directory BPN -> DID."""
    company_id = required(input, "companyId")
    did = required(input, "did")
    row = registered(company_id)
    bpn = bpn_of(row)
    if row.did != did:
        status, answer = csp_calls.call("register-did", "PUT", f"/companies/{bpn}/did", {"did": did},
                                        company_id=company_id, bpn=bpn)
        csp.raise_for(status, answer)
        with store.lock:
            if row.did != did:   # a concurrent call may have stored it meanwhile: one event only
                row.did = did
                row.touch()
                events.publish(MODULE, "CompanyDidRegistered", {"companyId": company_id, "bpn": bpn, "did": did})
    return reply(input, {"bpn": bpn, "did": did})


def update_company(input: StepInputJson) -> StepReply:
    """Step update-company (README 8.4): changed core data to the CSP. The module keeps no core
    data (README 5), so a repetition is recognised by the `stepRunId` (FRAMEWORK 4.4)."""
    company_id = required(input, "companyId")
    legal_name = required(input, "legalName")
    euid = optional(input, "euid")
    row = registered(company_id)
    bpn = bpn_of(row)
    step_run = optional(input, "stepRunId")
    if step_run and row.last_update_step_run == step_run:
        return reply(input)
    payload: dict[str, Any] = {"legalName": legal_name}
    if euid:
        payload["euid"] = euid
    if isinstance(input.get("address"), dict):
        payload["address"] = input["address"]
    status, answer = csp_calls.call("update-company", "PATCH", f"/companies/{bpn}", payload,
                                    company_id=company_id, bpn=bpn)
    csp.raise_for(status, answer)
    with store.lock:
        if not (step_run and row.last_update_step_run == step_run):   # one event per stepRunId
            row.last_update_step_run = step_run
            row.touch()
            events.publish(MODULE, "CompanyUpdatedAtCsp", {"companyId": company_id, "bpn": bpn})
    return reply(input)


def membership(input: StepInputJson, member: bool) -> StepReply:
    """Steps register-membership and deregister-membership (README 8.5)."""
    company_id = required(input, "companyId")
    current = store.registrations.get(company_id)
    if not member and current is not None and current.status == "TRANSFERRED_AWAY":
        # the new home OSP owns the membership now (FRAMEWORK 5.6 step 3): no call, no event
        if current.membership != "NONE":
            current.membership = "NONE"
            current.touch()
        return reply(input)
    row = registered(company_id)
    bpn = bpn_of(row)
    target: Membership = "REGISTERED" if member else "DEREGISTERED"
    if row.membership != target:
        operation = "register-membership" if member else "deregister-membership"
        status, answer = csp_calls.call(operation, "PUT", f"/companies/{bpn}/membership", {"member": member},
                                        company_id=company_id, bpn=bpn)
        csp.raise_for(status, answer)
        with store.lock:
            if row.membership != target:   # one event only, also with a concurrent call
                row.membership = target
                row.touch()
                events.publish(MODULE, "MembershipRegistered" if member else "MembershipDeregistered",
                               {"companyId": company_id, "bpn": bpn})
    return reply(input)
