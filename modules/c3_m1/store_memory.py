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
#  Assisted-By: Hermes Agent (deepseek-v4.1-flash)
#################################################################################
"""In-memory transport of the C3-M1 repository (README 5), used while `DATABASE_URL` is empty.

One function per table, rows are dicts with the snake_case field names of README 5; the router and
the interface map them to camelCase. The shape mirrors the tables one-to-one, so the PostgreSQL
transport in `store_postgres.py` answers the same functions: `lock()` is the placeholder for
`SELECT ... FOR UPDATE` (README 6.9), and every constraint that the database carries (enums, one
identifier per type, one OPEN change request per company, BPN unique among companies that are not
`REJECTED`) is enforced here as well.

Reads return copies: a caller changes rows through `update_company` and the other write functions,
never by mutating a returned dict. No FastAPI, no HTTP, no events.
"""
from __future__ import annotations

import contextlib
import copy
import datetime as dt
import hashlib
import uuid

from .store import (CORE_DATA_SOURCES, CHANGE_REQUEST_STATUSES, COMPANY_FIELDS, CONSENT_SOURCE_KINDS,
                    CONSENT_STATUSES, DEACTIVATION_REASONS, IDENTIFIER_SOURCES, IDENTIFIER_TYPES,
                    MEDIA_TYPES, ROLE_SOURCE_KINDS, ROLE_STATUSES, STATUSES)
from .validation import value_normalized

companies: dict[str, dict] = {}
_identifiers: dict[str, dict[str, dict]] = {}
_roles: dict[str, dict[str, dict]] = {}
_consents: dict[tuple[str, str], dict] = {}
_change_requests: dict[str, dict] = {}
_documents: dict[str, dict] = {}
_used_attestations: dict[str, dict] = {}
_audit: list[dict] = []


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _copy(row: dict | None) -> dict | None:
    return copy.deepcopy(row) if row is not None else None


def _check_enum(value, allowed: tuple[str, ...], field: str) -> None:
    if value is not None and value not in allowed:
        raise ValueError(f"{field}: {value!r} is not one of {', '.join(allowed)}")


def _check_known(company_id: str) -> dict:
    if company_id not in companies:
        raise ValueError(f"unknown company: {company_id}")
    return companies[company_id]


def _checked_bpn(bpn, *, company_id: str | None, status: str) -> str | None:
    """Upper case and unique among the companies whose status is not `REJECTED` (README 5)."""
    if bpn in (None, ""):
        return None
    if not isinstance(bpn, str):
        raise ValueError("bpn: not a string")
    bpn = bpn.strip().upper()
    if status != "REJECTED":
        for other_id, other in companies.items():
            if other_id != company_id and other["status"] != "REJECTED" and other.get("bpn") == bpn:
                raise ValueError(f"bpn: {bpn} belongs to company {other_id}")
    return bpn


def reset() -> None:
    """Empty every table (test helper; the PostgreSQL transport drops and recreates the schema)."""
    companies.clear()
    _identifiers.clear()
    _roles.clear()
    _consents.clear()
    _change_requests.clear()
    _documents.clear()
    _used_attestations.clear()
    _audit.clear()


@contextlib.contextmanager
def lock(company_id: str | None = None):
    """Placeholder for the row lock of README 6.9 (`SELECT ... FOR UPDATE`).

    In memory there is no concurrency; the context manager only documents where the later
    database transport takes the lock. It yields the `companyId` and never looks the company up.
    """
    yield company_id


# ------------------------------------------------------------------ company (README 5)
def get_company(company_id: str | None) -> dict | None:
    return _copy(companies.get(company_id)) if company_id else None


def create_company(row: dict) -> dict:
    unknown = set(row) - set(COMPANY_FIELDS)
    if unknown:
        raise ValueError(f"unknown company fields: {', '.join(sorted(unknown))}")
    if not row.get("id"):
        raise ValueError("id: required")
    if row["id"] in companies:
        raise ValueError(f"id: company {row['id']} exists")
    status = row.get("status") or "REQUESTED"
    core_data_source = row.get("core_data_source") or "MANUAL"
    _check_enum(status, STATUSES, "status")
    _check_enum(core_data_source, CORE_DATA_SOURCES, "core_data_source")
    _check_enum(row.get("deactivation_reason"), DEACTIVATION_REASONS, "deactivation_reason")
    if row.get("deactivation_reason") and status != "INACTIVE":
        raise ValueError("deactivation_reason: only with status INACTIVE")
    now = _now()
    created: dict = {field: None for field in COMPANY_FIELDS}
    created.update({key: value for key, value in row.items() if value is not None})
    created.update({
        "id": row["id"], "status": status, "core_data_source": core_data_source,
        "bpn": _checked_bpn(row.get("bpn"), company_id=row["id"], status=status),
        "created_at": row.get("created_at") or now, "changed_at": row.get("changed_at") or now,
    })
    companies[str(created["id"])] = created
    return _copy(created)  # type: ignore[return-value]


def update_company(company_id: str, **fields) -> dict | None:
    row = companies.get(company_id)
    if row is None:
        return None
    unknown = set(fields) - set(COMPANY_FIELDS) - {"id"}
    if unknown:
        raise ValueError(f"unknown company fields: {', '.join(sorted(unknown))}")
    status = fields.get("status", row["status"])
    _check_enum(status, STATUSES, "status")
    _check_enum(fields.get("core_data_source", row["core_data_source"]), CORE_DATA_SOURCES,
                "core_data_source")
    reason = fields.get("deactivation_reason", row["deactivation_reason"])
    _check_enum(reason, DEACTIVATION_REASONS, "deactivation_reason")
    if reason and status != "INACTIVE":
        raise ValueError("deactivation_reason: only with status INACTIVE")
    if "bpn" in fields:
        fields["bpn"] = _checked_bpn(fields["bpn"], company_id=company_id, status=status)
    row.update(fields)
    row["changed_at"] = _now()
    return _copy(row)


def find_companies(*, status=None, name=None, bpn=None, has_bpn=None, company_role=None,
                   core_data_source=None, page: int = 0, size: int = 20) -> tuple[list[dict], int]:
    """7.10: filters, newest first, paged. `company_role` matches active roles only."""
    statuses = [status] if isinstance(status, str) else list(status or [])
    for value in statuses:
        _check_enum(value, STATUSES, "status")
    _check_enum(core_data_source, CORE_DATA_SOURCES, "core_data_source")
    wanted_name = " ".join(name.split()).casefold() if name else None
    items = []
    for row in companies.values():
        if statuses and row["status"] not in statuses:
            continue
        if wanted_name and wanted_name not in " ".join((row["name"] or "").split()).casefold():
            continue
        if bpn and (row["bpn"] or "").upper() != bpn.upper():
            continue
        if has_bpn is not None and bool(row["bpn"]) != bool(has_bpn):
            continue
        if core_data_source and row["core_data_source"] != core_data_source:
            continue
        if company_role and _roles.get(row["id"], {}).get(company_role, {}).get("status") != "ACTIVE":
            continue
        items.append(row)
    items.sort(key=lambda row: (row["created_at"] or "", row["id"]), reverse=True)
    total = len(items)
    start = max(page, 0) * size
    return [_copy(row) for row in items[start:start + size]], total  # type: ignore[misc]


# ------------------------------------------------------- company_identifier (README 5, 6.4)
def list_identifiers(company_id: str) -> list[dict]:
    return [_copy(row) for row in _identifiers.get(company_id, {}).values()]  # type: ignore[misc]


def set_identifiers(company_id: str, identifiers: list[dict]) -> list[dict]:
    """Replace the identifiers; at most one per type (primary key `(company_id, type)`)."""
    _check_known(company_id)
    rows: dict[str, dict] = {}
    now = _now()
    for entry in identifiers:
        kind = entry.get("type")
        _check_enum(kind, IDENTIFIER_TYPES, "type")
        if not kind:
            raise ValueError("type: required")
        if kind in rows:
            raise ValueError(f"type: {kind} given twice")
        _check_enum(entry.get("source") or "DECLARED", IDENTIFIER_SOURCES, "source")
        value = entry.get("value")
        if not isinstance(value, str) or not value:
            raise ValueError("value: required")
        rows[kind] = {"company_id": company_id, "type": kind, "value": value,
                      "value_normalized": value_normalized(value),
                      "source": entry.get("source") or "DECLARED", "created_at": now, "changed_at": now}
    _identifiers[company_id] = rows
    return list_identifiers(company_id)


# ------------------------------------------------------- company_role_assignment (README 5, 6.5)
def get_role(company_id: str, company_role: str) -> dict | None:
    return _copy(_roles.get(company_id, {}).get(company_role))


def role_status(company_id: str, company_role: str) -> str:
    """`REQUESTED`, `ACTIVE`, `INACTIVE`, or `NONE` if the company never had the role."""
    row = _roles.get(company_id, {}).get(company_role)
    return row["status"] if row else "NONE"


def list_roles(company_id: str) -> dict[str, str]:
    """Role -> status of every role the company has or had."""
    return {role: row["status"] for role, row in _roles.get(company_id, {}).items()}


def add_role(company_id: str, company_role: str, *, status: str = "ACTIVE",
             source_kind: str = "COMPANY", source_ref: str | None = None) -> dict:
    _check_known(company_id)
    if not company_role:
        raise ValueError("company_role: required")
    _check_enum(status, ROLE_STATUSES, "status")
    _check_enum(source_kind, ROLE_SOURCE_KINDS, "source_kind")
    now = _now()
    row = _roles.setdefault(company_id, {}).get(company_role) or {
        "company_id": company_id, "company_role": company_role, "status": status,
        "source_kind": source_kind, "source_ref": source_ref, "activated_at": None,
        "deactivated_at": None, "changed_at": now,
    }
    row.update({"status": status, "source_kind": source_kind, "source_ref": source_ref,
                "changed_at": now})
    if status == "ACTIVE":
        row["activated_at"] = row.get("activated_at") or now
        row["deactivated_at"] = None
    if status == "INACTIVE":
        row["deactivated_at"] = now
    _roles[company_id][company_role] = row
    return _copy(row)  # type: ignore[return-value]


def remove_role(company_id: str, company_role: str) -> dict | None:
    """Removal keeps the row: status `INACTIVE` (README 5)."""
    row = _roles.get(company_id, {}).get(company_role)
    if row is None:
        return None
    row.update({"status": "INACTIVE", "changed_at": _now(), "deactivated_at": _now()})
    return _copy(row)


# ------------------------------------------------------------------ consent (README 5, 6.5)
def get_consent(company_id: str, agreement_key: str) -> dict | None:
    return _copy(_consents.get((company_id, agreement_key)))


def list_consents(company_id: str) -> list[dict]:
    return [_copy(row) for (cid, _key), row in _consents.items() if cid == company_id]  # type: ignore[misc]


def set_consent(company_id: str, agreement_key: str, *, version: str | None = None,
                status: str = "ACTIVE", source_kind: str = "COMPANY",
                source_ref: str | None = None, consented_by: str | None = None,
                consented_at: str | None = None) -> dict:
    """One row per company and terms, with the latest state (README 5)."""
    _check_known(company_id)
    if not agreement_key:
        raise ValueError("agreement_key: required")
    _check_enum(status, CONSENT_STATUSES, "status")
    _check_enum(source_kind, CONSENT_SOURCE_KINDS, "source_kind")
    row = _consents.get((company_id, agreement_key)) or {
        "company_id": company_id, "agreement_key": agreement_key, "agreement_version": None,
        "status": status, "source_kind": source_kind, "source_ref": source_ref,
        "consented_by": consented_by, "consented_at": consented_at, "changed_at": _now(),
    }
    row.update({"status": status, "source_kind": source_kind, "source_ref": source_ref,
                "consented_by": consented_by, "consented_at": consented_at, "changed_at": _now()})
    if version is not None:
        row["agreement_version"] = version
    _consents[(company_id, agreement_key)] = row
    return _copy(row)  # type: ignore[return-value]


# ------------------------------------------------------------- change_request (README 5, 7.4)
def get_change_request(change_request_id: str | None) -> dict | None:
    return _copy(_change_requests.get(change_request_id)) if change_request_id else None


def create_change_request(row: dict) -> dict:
    """At most one change request with status `OPEN` per company (partial unique index)."""
    company_id: str = row.get("company_id") or ""
    _check_known(company_id)
    status = row.get("status") or "OPEN"
    _check_enum(status, CHANGE_REQUEST_STATUSES, "status")
    if status == "OPEN" and open_change_request(company_id):
        raise ValueError(f"company {company_id} already has an open change request")
    created = {
        "id": row.get("id") or str(uuid.uuid4()), "company_id": company_id, "status": status,
        "changes": copy.deepcopy(row.get("changes") or {}), "comment": row.get("comment"),
        "requested_by": row.get("requested_by"), "decided_by": row.get("decided_by"),
        "decision_reason": row.get("decision_reason"),
        "created_at": row.get("created_at") or _now(), "closed_at": row.get("closed_at"),
    }
    _change_requests[created["id"]] = created
    return _copy(created)  # type: ignore[return-value]


def open_change_request(company_id: str) -> dict | None:
    return next((_copy(row) for row in _change_requests.values()
                 if row["company_id"] == company_id and row["status"] == "OPEN"), None)


def list_change_requests(*, company_id: str | None = None, status=None,
                         page: int = 0, size: int = 20,
                         newest_first: bool = False) -> tuple[list[dict], int]:
    """7.5 (newest first) and 7.14 (oldest first, the default), paged."""
    statuses = [status] if isinstance(status, str) else list(status or [])
    for value in statuses:
        _check_enum(value, CHANGE_REQUEST_STATUSES, "status")
    items = [row for row in _change_requests.values()
             if (company_id is None or row["company_id"] == company_id)
             and (not statuses or row["status"] in statuses)]
    items.sort(key=lambda row: (row["created_at"] or "", row["id"]), reverse=newest_first)
    total = len(items)
    start = max(page, 0) * size
    return [_copy(row) for row in items[start:start + size]], total  # type: ignore[misc]


def decide_change_request(change_request_id: str, status: str, *, decided_by: str | None = None,
                          decision_reason: str | None = None,
                          closed_at: str | None = None) -> dict | None:
    """Only an `OPEN` request can be decided; `DECLINED` needs the justification (7.18)."""
    row = _change_requests.get(change_request_id)
    if row is None:
        return None
    _check_enum(status, ("APPROVED", "DECLINED"), "status")
    if row["status"] != "OPEN":
        raise ValueError(f"status: {row['status']} is not OPEN")
    if status == "DECLINED" and not decision_reason:
        raise ValueError("decision_reason: required with DECLINED")
    row.update({"status": status, "decided_by": decided_by, "decision_reason": decision_reason,
                "closed_at": closed_at or _now()})
    return _copy(row)


def withdraw_change_request(change_request_id: str, *, closed_at: str | None = None) -> dict | None:
    row = _change_requests.get(change_request_id)
    if row is None:
        return None
    if row["status"] != "OPEN":
        raise ValueError(f"status: {row['status']} is not OPEN")
    row.update({"status": "WITHDRAWN", "closed_at": closed_at or _now()})
    return _copy(row)


# ---------------------------------------------------- change_request_document (README 5, 7.4)
def add_document(change_request_id: str, *, file_name: str, media_type: str,
                 content: bytes = b"", size_bytes: int | None = None,
                 sha256: str | None = None) -> dict:
    if change_request_id not in _change_requests:
        raise ValueError(f"unknown change request: {change_request_id}")
    _check_enum(media_type, MEDIA_TYPES, "media_type")
    row = {"id": str(uuid.uuid4()), "change_request_id": change_request_id,
           "file_name": file_name, "media_type": media_type,
           "size_bytes": len(content) if size_bytes is None else size_bytes,
           "sha256": sha256 or hashlib.sha256(content).hexdigest(),
           "content": content, "created_at": _now()}
    _documents[row["id"]] = row
    return _copy(row)  # type: ignore[return-value]


def get_document(document_id: str | None) -> dict | None:
    return _copy(_documents.get(document_id)) if document_id else None


def list_documents(change_request_id: str) -> list[dict]:
    return [_copy(row) for row in _documents.values() if row["change_request_id"] == change_request_id]  # type: ignore[misc]


# ------------------------------------------------------------ used_attestation (README 5, 6.7)
def add_if_unused(jti: str, company_id: str) -> bool:
    """`True` if the `jti` was free and is now used, `False` if it was used already."""
    if not jti:
        raise ValueError("jti: required")
    _check_known(company_id)
    if jti in _used_attestations:
        return False
    _used_attestations[jti] = {"jti": jti, "company_id": company_id, "used_at": _now()}
    return True


def is_used(jti: str) -> bool:
    return jti in _used_attestations


# ------------------------------------------------------------------- audit_log (README 5, 4.3)
def audit(company_id: str | None, sub: str | None, operation: str,
          object_id: str | None = None, details: dict | None = None) -> dict:
    """Every changing operation, every step and every read of a document (FRAMEWORK 4.3)."""
    row = {"id": str(uuid.uuid4()), "occurred_at": _now(), "sub": sub or "",
           "company_id": company_id, "operation": operation, "object_id": object_id,
           "details": copy.deepcopy(details or {})}
    _audit.append(row)
    return _copy(row)  # type: ignore[return-value]


def list_audit(company_id: str | None = None) -> list[dict]:
    return [_copy(row) for row in _audit if company_id is None or row["company_id"] == company_id]  # type: ignore[misc]
