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
"""Change requests with supporting documents (README 7.4 - 7.6) and their review by OSP staff (7.14 - 7.18)."""
from __future__ import annotations

from modules.c3_m1 import config, errors, store, validation
from modules.c3_m1.errors import MODULE
from portal_common import events

from .changes import _changed_fields, _identifier_core_changed, _validate_merge, _wallet_identifier_conflict
from .common import _address, _identifiers, _now, get_company


# ------------------------------------------------------------ change requests (7.4 - 7.6, 7.14 - 7.18)
def _document_info(row: dict) -> dict:
    return {"id": row["id"], "fileName": row["file_name"], "mediaType": row["media_type"],
            "sizeBytes": row["size_bytes"]}


def _change_request_view(row: dict, *, osp: bool = False, company: dict | None = None) -> dict:
    """`ChangeRequest` (7.5: without `decidedBy`, without document content)."""
    view = {"id": row["id"], "companyId": row["company_id"], "status": row["status"],
            "changes": row["changes"], "comment": row["comment"],
            "documents": [_document_info(document)
                          for document in store.list_documents(row["id"])],
            "requestedBy": row["requested_by"], "createdAt": row["created_at"],
            "closedAt": row["closed_at"], "decisionReason": row["decision_reason"]}
    if osp:
        view |= {"companyName": (company or {}).get("name"), "decidedBy": row["decided_by"]}
    return view




def _differs_field(row: dict, key: str, value: object) -> bool:
    """`True` if this part of a request differs from the current state (7.4 point 5/6)."""
    if key == "address":
        return any(not validation.same_value(row.get(field), entry)
                   for field, entry in validation.flat_fields({"address": value}).items())
    return not validation.same_value(row.get(validation.field_name(key)), value)


def _differs_identifiers(row: dict, identifiers: list[dict]) -> bool:
    """Compare with the declared identifiers only; wallet identifiers are not part of a request."""
    before = {(entry["type"], entry["value_normalized"])
              for entry in store.list_identifiers(row["id"])
              if entry["source"] != "BUSINESS_WALLET"}
    after = {(entry["type"], validation.value_normalized(entry["value"])) for entry in identifiers}
    return before != after


def _changes_differs(row: dict, changes: dict) -> bool:
    """`True` if any part of the request differs from the current company (7.4 point 6)."""
    for key, value in changes.items():
        if key == "identifiers":
            if _differs_identifiers(row, value):
                return True
        elif _differs_field(row, key, value):
            return True
    return False






def create_change_request(companyId: str, data: dict,
                          documents: list[tuple[str, bytes, str | None]],
                          sub: str | None = None) -> dict:
    """7.4: a change request with supporting documents."""
    if not config.change_requests_enabled():
        raise errors.change_requests_disabled()
    with store.lock(companyId):
        row = get_company(companyId)
        if row["status"] != "ACTIVE":
            raise errors.invalid_state(detail=row["status"])
        if store.open_change_request(companyId):
            raise errors.change_request_open()

        changes = {key: value for key, value in data.items() if key in ("name", "address", "identifiers")}
        _check_requested_changes(companyId, row, data, changes)
        _check_documents(documents)

        created = store.create_change_request({
            "company_id": companyId, "changes": changes, "comment": data.get("comment"),
            "requested_by": sub, "status": "OPEN"})
        for file_name, content, stated in documents:
            store.add_document(created["id"], file_name=file_name,
                               media_type=validation.detect_media_type(content) or stated or "",
                               content=content)
        store.audit(companyId, sub, "createChangeRequest", created["id"],
                    {"changedFields": sorted(changes)})
        events.publish(MODULE, "CompanyChangeRequestSubmitted",
                       {"companyId": companyId, "changeRequestId": created["id"]})
    return _change_request_view(created)


def _check_requested_changes(companyId: str, row: dict, data: dict, changes: dict) -> None:
    """400 `validation` for invalid or empty changes; 409 `attestation-required` for EBW core data (6.3)."""
    identifiers = changes.get("identifiers")
    wallet = [{"type": entry["type"], "value": entry["value"], "source": entry["source"]}
              for entry in store.list_identifiers(companyId) if entry["source"] == "BUSINESS_WALLET"]
    invalid = validation.validate_change_request(data, row["country_code"])
    if identifiers is not None:
        if not identifiers and wallet:
            # "afterwards at least one identifier" counts the wallet identifiers that stay
            invalid = [error for error in invalid
                       if not (error["field"] == "identifiers" and error["reason"] == "missing")]
        invalid += _wallet_identifier_conflict(row, identifiers)
    if invalid:
        raise errors.validation(errors=invalid)
    core_changed = any(_differs_field(row, key, value)
                       for key, value in changes.items() if key != "identifiers")
    if identifiers is not None and _identifier_core_changed(row, identifiers):
        core_changed = True
    if core_changed and row["core_data_source"] == "EBW":
        raise errors.attestation_required()
    if not _changes_differs(row, changes):
        raise errors.validation(errors=[{"field": "changes", "reason": "no change"}])


def _check_documents(documents: list[tuple[str, bytes, str | None]]) -> None:
    """400 `document-invalid`: 1 to CHANGE_REQUEST_MAX_DOCUMENTS documents of an allowed type and size."""
    invalid = []
    if not 1 <= len(documents) <= config.change_request_max_documents():
        maximum = config.change_request_max_documents()
        invalid.append({"field": "documents", "reason": f"1 to {maximum} documents"})
    for file_name, content, stated in documents:
        invalid += validation.validate_document(file_name, content, stated_media_type=stated,
                                               max_bytes=config.change_request_max_document_bytes())
    if invalid:
        raise errors.document_invalid(errors=invalid)


def list_own_change_requests(companyId: str, page: int = 0, size: int = 20) -> dict:
    """7.5: own change requests, newest first, without `decidedBy`."""
    get_company(companyId)
    items, total = store.list_change_requests(company_id=companyId, page=page, size=size,
                                              newest_first=True)
    return {"items": [_change_request_view(item) for item in items], "page": page, "size": size,
            "total": total}


def _own_change_request(companyId: str, changeRequestId: str) -> dict:
    row = store.get_change_request(changeRequestId)
    if row is None or row["company_id"] != companyId:
        raise errors.not_found()
    return row


def withdraw_change_request(companyId: str, changeRequestId: str, sub: str | None = None) -> dict:
    """7.6"""
    with store.lock(companyId):
        row = _own_change_request(companyId, changeRequestId)
        if row["status"] == "WITHDRAWN":
            return _change_request_view(row)
        if row["status"] != "OPEN":
            raise errors.invalid_state(detail=row["status"])
        closed = store.withdraw_change_request(changeRequestId)
        store.audit(companyId, sub, "withdrawChangeRequest", changeRequestId)
        events.publish(MODULE, "CompanyChangeRequestClosed",
                       {"companyId": companyId, "changeRequestId": changeRequestId,
                        "outcome": "WITHDRAWN"})
    return _change_request_view(closed)


# ----------------------------------------------------------------------- review by OSP staff (7.14 - 7.18)
def _reviewed(changeRequestId: str) -> dict:
    row = store.get_change_request(changeRequestId)
    if row is None:
        raise errors.not_found()
    return row


def list_change_requests(*, status: list[str] | str | None = None,
                         companyId: str | None = None, page: int | str = 0,
                         size: int | str = 20) -> dict:
    """7.14: all change requests, oldest first."""
    try:
        items, total = store.list_change_requests(status=status, company_id=companyId,
                                                  page=int(page or 0), size=int(size or 20))
    except ValueError as error:
        raise errors.validation(errors=[{"field": "filter", "reason": str(error)}]) from error
    return {"items": [_change_request_view(item, osp=True,
                                           company=store.get_company(item["company_id"]))
                      for item in items],
            "page": int(page or 0), "size": int(size or 20), "total": total}


def get_change_request(changeRequestId: str) -> dict:
    """7.15: the request with the current state of the company."""
    row = _reviewed(changeRequestId)
    company = store.get_company(row["company_id"]) or {}
    view = _change_request_view(row, osp=True, company=company)
    view["company"] = {"id": company.get("id"), "name": company.get("name"),
                       "address": _address(company), "identifiers": _identifiers(company),
                       "coreDataSource": company.get("core_data_source"),
                       "status": company.get("status")}
    return view


def get_change_request_document(changeRequestId: str, documentId: str,
                                sub: str | None = None) -> dict:
    """7.16: content, media type and file name; the read is audited."""
    request = _reviewed(changeRequestId)
    document = store.get_document(documentId)
    if document is None or document["change_request_id"] != changeRequestId:
        raise errors.not_found()
    store.audit(request["company_id"], sub, "getChangeRequestDocument", documentId)
    return {"content": document["content"], "media_type": document["media_type"],
            "file_name": document["file_name"]}


def _apply_changes(companyId: str, row: dict, changes: dict) -> tuple[list[str], bool]:
    """Apply the request and return the changed field names and whether core data changed (7.17)."""
    fields = {key: value for key, value in changes.items() if key in ("name", "address")}
    identifiers = changes.get("identifiers")
    stored = store.list_identifiers(companyId)
    wallet = [{"type": entry["type"], "value": entry["value"], "source": entry["source"]}
              for entry in stored if entry["source"] == "BUSINESS_WALLET"]
    merged_identifiers = (list(identifiers) + wallet) if identifiers is not None else \
        [{"type": entry["type"], "value": entry["value"], "source": entry["source"]} for entry in stored]
    invalid = validation.validate_company(_validate_merge(row, fields), partial=False)
    invalid += validation.validate_identifiers(merged_identifiers, row["country_code"])
    if identifiers is not None:
        invalid += _wallet_identifier_conflict(row, identifiers)
    if invalid:
        raise errors.validation(errors=invalid)

    core_changed = any(_differs_field(row, key, value) for key, value in fields.items())
    if identifiers is not None and _identifier_core_changed(row, identifiers):
        core_changed = True
    if core_changed and row["core_data_source"] == "EBW":
        raise errors.attestation_required()
    changed = _changed_fields(row, fields, identifiers)
    updates = validation.flat_fields(fields)
    if core_changed:
        updates |= {"core_data_source": "MANUAL", "core_data_verified_at": _now()}
    if updates:
        store.update_company(companyId, **updates)
    if identifiers is not None:
        store.set_identifiers(companyId, merged_identifiers)
    return changed, core_changed


def approve_change_request(changeRequestId: str, body: dict | None = None,
                           sub: str | None = None) -> dict:
    """7.17"""
    with store.lock((store.get_change_request(changeRequestId) or {}).get("company_id")):
        row = _reviewed(changeRequestId)
        if row["status"] == "APPROVED":
            return _change_request_view(row, osp=True)
        if row["status"] != "OPEN":
            raise errors.invalid_state(detail=row["status"])
        if row["requested_by"] and row["requested_by"] == sub:
            raise errors.same_person()
        company = get_company(row["company_id"])
        if company["status"] != "ACTIVE":
            raise errors.invalid_state(detail=company["status"])

        changed, core_changed = _apply_changes(row["company_id"], company, row["changes"])
        decided = store.decide_change_request(changeRequestId, "APPROVED", decided_by=sub,
                                              decision_reason=None)
        store.audit(row["company_id"], sub, "approveChangeRequest", changeRequestId,
                    {"changedFields": changed, "comment": (body or {}).get("comment")})
        if changed:
            events.publish(MODULE, "CompanyDataChanged",
                           {"companyId": row["company_id"], "changedFields": changed,
                            "coreDataChanged": core_changed,
                            "coreDataSource": "MANUAL" if core_changed
                            else company["core_data_source"]})
        events.publish(MODULE, "CompanyChangeRequestClosed",
                       {"companyId": row["company_id"], "changeRequestId": changeRequestId,
                        "outcome": "APPROVED"})
    return _change_request_view(decided, osp=True)


def decline_change_request(changeRequestId: str, body: dict | None = None,
                           sub: str | None = None) -> dict:
    """7.18"""
    with store.lock((store.get_change_request(changeRequestId) or {}).get("company_id")):
        row = _reviewed(changeRequestId)
        reason = (body or {}).get("reason")
        if row["status"] == "DECLINED":
            return _change_request_view(row, osp=True)
        if row["status"] != "OPEN":
            raise errors.invalid_state(detail=row["status"])
        invalid = validation.validate_decision_reason(reason)
        if invalid:
            raise errors.validation(errors=invalid)
        decided = store.decide_change_request(changeRequestId, "DECLINED", decided_by=sub,
                                              decision_reason=reason)
        store.audit(row["company_id"], sub, "declineChangeRequest", changeRequestId,
                    {"reason": reason})
        events.publish(MODULE, "CompanyChangeRequestClosed",
                       {"companyId": row["company_id"], "changeRequestId": changeRequestId,
                        "outcome": "DECLINED"})
    return _change_request_view(decided, osp=True)
