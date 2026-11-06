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
"""PostgreSQL transport of the C3-M1 repository: the module's own database `c3_m1` (README 4, 5).

Active when `DATABASE_URL` is set; the schema is `schema.sql` next to this file. The functions,
the field names and the invariants are the ones of `store_memory`, so the caller never learns
which transport runs. Timestamps leave as ISO 8601 strings and bytea as `bytes`, like the memory
transport returns them.

`psycopg` is imported at module load: `DATABASE_URL` set without the driver is an error naming the
package (store.py). Nothing here is FastAPI, HTTP or events.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import zlib
import uuid
from pathlib import Path

import psycopg
from psycopg import errors
from psycopg.rows import dict_row

from .store import (CHANGE_REQUEST_STATUSES, COMPANY_FIELDS, CONSENT_STATUSES, CORE_DATA_SOURCES,
                    DEACTIVATION_REASONS, IDENTIFIER_SOURCES, IDENTIFIER_TYPES, MEDIA_TYPES,
                    ROLE_SOURCE_KINDS, ROLE_STATUSES, STATUSES)
from .validation import value_normalized

SCHEMA = Path(__file__).with_name("schema.sql")
TABLES = ("audit_log", "used_attestation", "change_request_document", "change_request", "consent",
          "company_role_assignment", "company_identifier", "company")

COMPANY_KEYWORDS = (
    "short_name", "house_number", "address_addition", "postal_code", "region", "bpn",
    "bpn_assigned_at", "core_data_verified_at", "verification_ref", "application_id",
    "deactivation_reason", "activated_at", "rejected_at", "deactivated_at", "reactivated_at",
    "changed_at",
)

def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is empty; the PostgreSQL transport needs the database `c3_m1`")
    return dsn


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _row(row: dict | None) -> dict | None:
    """Normalise a database row to the shapes the memory transport returns."""
    if row is None:
        return None
    for key, value in row.items():
        if isinstance(value, uuid.UUID):
            row[key] = str(value)
    for key in ("content",):
        if isinstance(row.get(key), memoryview | bytearray):
            row[key] = bytes(row[key])
    for key in ("created_at", "changed_at", "occurred_at", "used_at", "closed_at",
                "activated_at", "deactivated_at", "reactivated_at", "rejected_at",
                "bpn_assigned_at", "core_data_verified_at", "consented_at"):
        if isinstance(row.get(key), dt.datetime):
            row[key] = row[key].isoformat()
    return row


@contextlib.contextmanager
def _connection():
    with psycopg.connect(_dsn(), row_factory=dict_row) as connection:
        yield connection


def _fetch_one(connection, sql: str, params: tuple | dict = ()) -> dict | None:
    return _row(connection.execute(sql, params).fetchone())


def _fetch_all(connection, sql: str, params: tuple | dict = ()) -> list[dict]:
    return [_row(row) for row in connection.execute(sql, params).fetchall()]  # type: ignore[misc]


def _check_enum(value, allowed: tuple[str, ...], field: str) -> None:
    if value is not None and value not in allowed:
        raise ValueError(f"{field}: {value!r} is not one of {', '.join(allowed)}")


def _uuid_ok(value) -> bool:
    """A path parameter may be anything; PostgreSQL refuses a non-UUID instead of answering empty."""
    try:
        uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return False
    return True


def _check_known(connection, company_id: str) -> None:
    if not _uuid_ok(company_id) or _fetch_one(
            connection, "SELECT id FROM company WHERE id = %s", (company_id,)) is None:
        raise ValueError(f"unknown company: {company_id}")


def _integrity(error: errors.IntegrityError) -> ValueError:
    """Database constraint -> ValueError, like the memory transport raises it."""
    if isinstance(error, errors.UniqueViolation):
        constraint = getattr(getattr(error, "diag", None), "constraint_name", "") or ""
        if "bpn" in constraint:
            return ValueError("bpn: belongs to another company with a status other than REJECTED")
        if "open_per_company" in constraint:
            return ValueError(f"company already has an open change request ({constraint})")
        return ValueError(f"unique violation: {constraint or error.diag.message_detail}")
    return ValueError(str(error))


def reset() -> None:
    """Drop the module's tables and apply `schema.sql` again."""
    script = SCHEMA.read_text(encoding="utf-8")
    with _connection() as connection:
        for table in TABLES:
            connection.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        connection.execute(script)


@contextlib.contextmanager
def lock(company_id: str | None = None):
    """Lock of README 6.9 for the duration of the block, one caller per company.

    A session advisory lock instead of `SELECT ... FOR UPDATE`: the write functions of this
    transport run in their own transactions, so a row lock held here would block on the very
    UPDATE of the same row the block performs. The advisory key is the company, the unlock is
    guaranteed in `finally`.
    """
    key = zlib.crc32(company_id.encode()) if company_id else 0
    with psycopg.connect(_dsn(), autocommit=True) as connection:
        if company_id:
            connection.execute("SELECT pg_advisory_lock(%s)", (key,))
        try:
            yield company_id
        finally:
            if company_id:
                connection.execute("SELECT pg_advisory_unlock(%s)", (key,))


# ------------------------------------------------------------------ company (README 5)
def get_company(company_id: str | None) -> dict | None:
    if not company_id or not _uuid_ok(company_id):
        return None
    with _connection() as connection:
        return _fetch_one(connection, "SELECT * FROM company WHERE id = %s", (company_id,))


def create_company(row: dict) -> dict:
    unknown = set(row) - set(COMPANY_FIELDS)
    if unknown:
        raise ValueError(f"unknown company fields: {', '.join(sorted(unknown))}")
    if not row.get("id"):
        raise ValueError("id: required")
    status = row.get("status") or "REQUESTED"
    _check_enum(status, STATUSES, "status")
    _check_enum(row.get("core_data_source") or "MANUAL", CORE_DATA_SOURCES, "core_data_source")
    _check_enum(row.get("deactivation_reason"), DEACTIVATION_REASONS, "deactivation_reason")
    now = _now()
    values = {field: row.get(field) for field in COMPANY_FIELDS}
    values.update({"id": row["id"], "status": status,
                   "core_data_source": row.get("core_data_source") or "MANUAL",
                   "bpn": (row.get("bpn") or "").strip().upper() or None,
                   "created_at": row.get("created_at") or now, "changed_at": row.get("changed_at") or now})
    columns = ", ".join(COMPANY_FIELDS)
    placeholders = ", ".join(f"%({field})s" for field in COMPANY_FIELDS)
    with _connection() as connection:
        try:
            created = _fetch_one(connection,
                                 f"INSERT INTO company ({columns}) VALUES ({placeholders}) RETURNING *",
                                 values)
        except errors.IntegrityError as error:
            raise _integrity(error) from None
    return created  # type: ignore[return-value]


def update_company(company_id: str, **fields) -> dict | None:
    if not fields:
        return get_company(company_id)
    if not _uuid_ok(company_id):
        return None
    unknown = set(fields) - set(COMPANY_FIELDS) - {"id", "created_at"}
    if unknown:
        raise ValueError(f"unknown company fields: {', '.join(sorted(unknown))}")
    if "status" in fields:
        _check_enum(fields["status"], STATUSES, "status")
    if "core_data_source" in fields:
        _check_enum(fields["core_data_source"], CORE_DATA_SOURCES, "core_data_source")
    if "deactivation_reason" in fields:
        _check_enum(fields["deactivation_reason"], DEACTIVATION_REASONS, "deactivation_reason")
    if "bpn" in fields:
        fields["bpn"] = (fields["bpn"] or "").strip().upper() or None
    assignments = ", ".join(f"{field} = %({field})s" for field in fields)
    with _connection() as connection:
        if _fetch_one(connection, "SELECT id FROM company WHERE id = %s", (company_id,)) is None:
            return None
        try:
            return _fetch_one(connection,
                              f"UPDATE company SET {assignments}, changed_at = %(now)s "
                              "WHERE id = %(id)s RETURNING *",
                              fields | {"now": _now(), "id": company_id})
        except errors.IntegrityError as error:
            raise _integrity(error) from None


def find_companies(*, status=None, name=None, bpn=None, has_bpn=None, company_role=None,
                   core_data_source=None, page: int = 0, size: int = 20) -> tuple[list[dict], int]:
    """7.10: filters, newest first, paged. `company_role` matches active roles only."""
    statuses = [status] if isinstance(status, str) else list(status or [])
    for value in statuses:
        _check_enum(value, STATUSES, "status")
    _check_enum(core_data_source, CORE_DATA_SOURCES, "core_data_source")
    where, params = ["TRUE"], []
    if statuses:
        where.append("c.status = ANY(%s)")
        params.append(statuses)
    if name:
        where.append("lower(regexp_replace(c.name, '\\s+', ' ', 'g')) LIKE %s")
        params.append(f"%{name.casefold()}%")
    if bpn:
        where.append("upper(c.bpn) = upper(%s)")
        params.append(bpn)
    if has_bpn is not None:
        where.append("(c.bpn IS NOT NULL) = %s")
        params.append(bool(has_bpn))
    if core_data_source:
        where.append("c.core_data_source = %s")
        params.append(core_data_source)
    if company_role:
        where.append("EXISTS (SELECT 1 FROM company_role_assignment r WHERE r.company_id = c.id "
                     "AND r.company_role = %s AND r.status = 'ACTIVE')")
        params.append(company_role)
    sql = ("SELECT c.*, count(*) OVER () AS total FROM company c WHERE " + " AND ".join(where)
           + " ORDER BY c.created_at DESC, c.id DESC LIMIT %s OFFSET %s")
    with _connection() as connection:
        rows = _fetch_all(connection, sql, (*params, size, max(page, 0) * size))
    total = int(rows[0].pop("total")) if rows else 0
    return rows, total


# ------------------------------------------------------- company_identifier (README 5, 6.4)
def list_identifiers(company_id: str) -> list[dict]:
    if not _uuid_ok(company_id):
        return []
    with _connection() as connection:
        return _fetch_all(connection, "SELECT * FROM company_identifier WHERE company_id = %s "
                                      "ORDER BY type", (company_id,))


def set_identifiers(company_id: str, identifiers: list[dict]) -> list[dict]:
    """Replace the identifiers; at most one per type (primary key `(company_id, type)`)."""
    rows: dict[str, dict] = {}
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
                      "source": entry.get("source") or "DECLARED"}
    with _connection() as connection:
        _check_known(connection, company_id)
        connection.execute("DELETE FROM company_identifier WHERE company_id = %s", (company_id,))
        now = _now()
        for row in rows.values():
            connection.execute(
                "INSERT INTO company_identifier (company_id, type, value, value_normalized, source,"
                " created_at, changed_at) VALUES (%(company_id)s, %(type)s, %(value)s,"
                " %(value_normalized)s, %(source)s, %(now)s, %(now)s)", row | {"now": now})
    return list_identifiers(company_id)


# ------------------------------------------------------- company_role_assignment (README 5, 6.5)
def get_role(company_id: str, company_role: str) -> dict | None:
    if not _uuid_ok(company_id):
        return None
    with _connection() as connection:
        return _fetch_one(connection, "SELECT * FROM company_role_assignment WHERE company_id = %s"
                                      " AND company_role = %s", (company_id, company_role))


def role_status(company_id: str, company_role: str) -> str:
    """`REQUESTED`, `ACTIVE`, `INACTIVE`, or `NONE` if the company never had the role."""
    row = get_role(company_id, company_role)
    return row["status"] if row else "NONE"


def list_roles(company_id: str) -> dict[str, str]:
    """Role -> status of every role the company has or had."""
    if not _uuid_ok(company_id):
        return {}
    with _connection() as connection:
        rows = _fetch_all(connection, "SELECT company_role, status FROM company_role_assignment "
                                      "WHERE company_id = %s", (company_id,))
    return {row["company_role"]: row["status"] for row in rows}


def add_role(company_id: str, company_role: str, *, status: str = "ACTIVE",
             source_kind: str = "COMPANY", source_ref: str | None = None) -> dict:
    if not company_role:
        raise ValueError("company_role: required")
    _check_enum(status, ROLE_STATUSES, "status")
    _check_enum(source_kind, ROLE_SOURCE_KINDS, "source_kind")
    now = _now()
    with _connection() as connection:
        _check_known(connection, company_id)
        return _fetch_one(
            connection,
            "INSERT INTO company_role_assignment (company_id, company_role, status, source_kind,"
            " source_ref, activated_at, deactivated_at, changed_at)"
            " VALUES (%(company_id)s, %(role)s, %(status)s, %(source_kind)s, %(source_ref)s,"
            " %(activated)s, %(deactivated)s, %(now)s)"
            " ON CONFLICT (company_id, company_role) DO UPDATE SET status = EXCLUDED.status,"
            " source_kind = EXCLUDED.source_kind, source_ref = EXCLUDED.source_ref,"
            " activated_at = COALESCE(company_role_assignment.activated_at, EXCLUDED.activated_at),"
            " deactivated_at = EXCLUDED.deactivated_at, changed_at = EXCLUDED.changed_at"
            " RETURNING *",
            {"company_id": company_id, "role": company_role, "status": status,
             "source_kind": source_kind, "source_ref": source_ref,
             "activated": now if status == "ACTIVE" else None,
             "deactivated": now if status == "INACTIVE" else None, "now": now},
        )  # type: ignore[return-value]


def remove_role(company_id: str, company_role: str) -> dict | None:
    """Removal keeps the row: status `INACTIVE` (README 5)."""
    now = _now()
    with _connection() as connection:
        return _fetch_one(connection,
                          "UPDATE company_role_assignment SET status = 'INACTIVE', changed_at = %s,"
                          " deactivated_at = %s WHERE company_id = %s AND company_role = %s"
                          " RETURNING *", (now, now, company_id, company_role))


# ------------------------------------------------------------------ consent (README 5, 6.5)
def get_consent(company_id: str, agreement_key: str) -> dict | None:
    if not _uuid_ok(company_id):
        return None
    with _connection() as connection:
        return _fetch_one(connection, "SELECT * FROM consent WHERE company_id = %s"
                                      " AND agreement_key = %s", (company_id, agreement_key))


def list_consents(company_id: str) -> list[dict]:
    if not _uuid_ok(company_id):
        return []
    with _connection() as connection:
        return _fetch_all(connection, "SELECT * FROM consent WHERE company_id = %s"
                                      " ORDER BY agreement_key", (company_id,))


def set_consent(company_id: str, agreement_key: str, *, version: str | None = None,
                status: str = "ACTIVE", source_kind: str = "COMPANY",
                source_ref: str | None = None, consented_by: str | None = None,
                consented_at: str | None = None) -> dict:
    """One row per company and terms, with the latest state (README 5)."""
    if not agreement_key:
        raise ValueError("agreement_key: required")
    _check_enum(status, CONSENT_STATUSES, "status")
    with _connection() as connection:
        _check_known(connection, company_id)
        return _fetch_one(
            connection,
            "INSERT INTO consent (company_id, agreement_key, agreement_version, status, source_kind,"
            " source_ref, consented_by, consented_at, changed_at)"
            " VALUES (%(company_id)s, %(key)s, %(version)s, %(status)s, %(source_kind)s,"
            " %(source_ref)s, %(consented_by)s, %(consented_at)s, %(now)s)"
            " ON CONFLICT (company_id, agreement_key) DO UPDATE SET status = EXCLUDED.status,"
            " source_kind = EXCLUDED.source_kind, source_ref = EXCLUDED.source_ref,"
            " consented_by = EXCLUDED.consented_by, consented_at = EXCLUDED.consented_at,"
            " agreement_version = COALESCE(%(version)s, consent.agreement_version),"
            " changed_at = EXCLUDED.changed_at RETURNING *",
            {"company_id": company_id, "key": agreement_key, "version": version, "status": status,
             "source_kind": source_kind, "source_ref": source_ref, "consented_by": consented_by,
             "consented_at": consented_at, "now": _now()},
        )  # type: ignore[return-value]


# ------------------------------------------------------------- change_request (README 5, 7.4)
def get_change_request(change_request_id: str | None) -> dict | None:
    if not change_request_id or not _uuid_ok(change_request_id):
        return None
    with _connection() as connection:
        return _fetch_one(connection, "SELECT * FROM change_request WHERE id = %s",
                          (change_request_id,))


def create_change_request(row: dict) -> dict:
    """At most one change request with status `OPEN` per company (partial unique index)."""
    company_id: str = row.get("company_id") or ""
    status = row.get("status") or "OPEN"
    _check_enum(status, CHANGE_REQUEST_STATUSES, "status")
    with _connection() as connection:
        _check_known(connection, company_id)
        try:
            return _fetch_one(  # type: ignore[return-value]
                connection,
                "INSERT INTO change_request (id, company_id, status, changes, comment, requested_by,"
                " decided_by, decision_reason, created_at, closed_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (row.get("id") or str(uuid.uuid4()), company_id, status,
                 json.dumps(row.get("changes") or {}), row.get("comment"), row.get("requested_by"),
                 row.get("decided_by"), row.get("decision_reason"),
                 row.get("created_at") or _now(), row.get("closed_at")))
        except errors.IntegrityError as error:
            raise _integrity(error) from None


def open_change_request(company_id: str) -> dict | None:
    if not _uuid_ok(company_id):
        return None
    with _connection() as connection:
        return _fetch_one(connection, "SELECT * FROM change_request WHERE company_id = %s"
                                      " AND status = 'OPEN'", (company_id,))


def list_change_requests(*, company_id: str | None = None, status=None,
                         page: int = 0, size: int = 20,
                         newest_first: bool = False) -> tuple[list[dict], int]:
    """7.5 (newest first) and 7.14 (oldest first, the default), paged."""
    statuses = [status] if isinstance(status, str) else list(status or [])
    for value in statuses:
        _check_enum(value, CHANGE_REQUEST_STATUSES, "status")
    where, params = ["TRUE"], []
    if company_id is not None:
        where.append("company_id = %s")
        params.append(company_id)
    if statuses:
        where.append("status = ANY(%s)")
        params.append(statuses)
    order = "DESC" if newest_first else "ASC"
    sql = ("SELECT *, count(*) OVER () AS total FROM change_request WHERE " + " AND ".join(where)
           + f" ORDER BY created_at {order}, id {order} LIMIT %s OFFSET %s")
    with _connection() as connection:
        rows = _fetch_all(connection, sql, (*params, size, max(page, 0) * size))
    total = int(rows[0].pop("total")) if rows else 0
    return rows, total


def decide_change_request(change_request_id: str, status: str, *, decided_by: str | None = None,
                          decision_reason: str | None = None,
                          closed_at: str | None = None) -> dict | None:
    """Only an `OPEN` request can be decided; `DECLINED` needs the justification (7.18)."""
    _check_enum(status, ("APPROVED", "DECLINED"), "status")
    if status == "DECLINED" and not decision_reason:
        raise ValueError("decision_reason: required with DECLINED")
    if not _uuid_ok(change_request_id):
        return None
    with _connection() as connection:
        row = _fetch_one(connection, "SELECT status FROM change_request WHERE id = %s",
                         (change_request_id,))
        if row is None:
            return None
        if row["status"] != "OPEN":
            raise ValueError(f"status: {row['status']} is not OPEN")
        return _fetch_one(connection,
                          "UPDATE change_request SET status = %s, decided_by = %s,"
                          " decision_reason = %s, closed_at = %s WHERE id = %s RETURNING *",
                          (status, decided_by, decision_reason, closed_at or _now(),
                           change_request_id))


def withdraw_change_request(change_request_id: str, *, closed_at: str | None = None) -> dict | None:
    if not _uuid_ok(change_request_id):
        return None
    with _connection() as connection:
        row = _fetch_one(connection, "SELECT status FROM change_request WHERE id = %s",
                         (change_request_id,))
        if row is None:
            return None
        if row["status"] != "OPEN":
            raise ValueError(f"status: {row['status']} is not OPEN")
        return _fetch_one(connection,
                          "UPDATE change_request SET status = 'WITHDRAWN', closed_at = %s"
                          " WHERE id = %s RETURNING *", (closed_at or _now(), change_request_id))


# ---------------------------------------------------- change_request_document (README 5, 7.4)
def add_document(change_request_id: str, *, file_name: str, media_type: str,
                 content: bytes = b"", size_bytes: int | None = None,
                 sha256: str | None = None) -> dict:
    _check_enum(media_type, MEDIA_TYPES, "media_type")
    if not _uuid_ok(change_request_id):
        raise ValueError(f"unknown change request: {change_request_id}")
    with _connection() as connection:
        if _fetch_one(connection, "SELECT id FROM change_request WHERE id = %s",
                      (change_request_id,)) is None:
            raise ValueError(f"unknown change request: {change_request_id}")
        return _fetch_one(  # type: ignore[return-value]
            connection,
            "INSERT INTO change_request_document (id, change_request_id, file_name, media_type,"
            " size_bytes, sha256, content, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " RETURNING *",
            (str(uuid.uuid4()), change_request_id, file_name, media_type,
             len(content) if size_bytes is None else size_bytes,
             sha256 or hashlib.sha256(content).hexdigest(), content, _now()))


def get_document(document_id: str | None) -> dict | None:
    if not document_id or not _uuid_ok(document_id):
        return None
    with _connection() as connection:
        return _fetch_one(connection, "SELECT * FROM change_request_document WHERE id = %s",
                          (document_id,))


def list_documents(change_request_id: str) -> list[dict]:
    if not _uuid_ok(change_request_id):
        return []
    with _connection() as connection:
        return _fetch_all(connection, "SELECT * FROM change_request_document"
                                      " WHERE change_request_id = %s ORDER BY created_at",
                          (change_request_id,))


# ------------------------------------------------------------ used_attestation (README 5, 6.7)
def add_if_unused(jti: str, company_id: str) -> bool:
    """`True` if the `jti` was free and is now used, `False` if it was used already."""
    if not jti:
        raise ValueError("jti: required")
    with _connection() as connection:
        _check_known(connection, company_id)
        row = connection.execute(
            "INSERT INTO used_attestation (jti, company_id, used_at) VALUES (%s, %s, %s)"
            " ON CONFLICT (jti) DO NOTHING RETURNING jti", (jti, company_id, _now())).fetchone()
    return row is not None


def is_used(jti: str) -> bool:
    with _connection() as connection:
        return connection.execute("SELECT 1 FROM used_attestation WHERE jti = %s",
                                  (jti,)).fetchone() is not None


# ------------------------------------------------------------------- audit_log (README 5, 4.3)
def audit(company_id: str | None, sub: str | None, operation: str,
          object_id: str | None = None, details: dict | None = None) -> dict:
    """Every changing operation, every step and every read of a document (FRAMEWORK 4.3)."""
    with _connection() as connection:
        return _fetch_one(  # type: ignore[return-value]
            connection,
            "INSERT INTO audit_log (id, occurred_at, sub, company_id, operation, object_id, details)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (str(uuid.uuid4()), _now(), sub or "", company_id, operation, object_id,
             json.dumps(details or {})))


def list_audit(company_id: str | None = None) -> list[dict]:
    if company_id is not None and not _uuid_ok(company_id):
        return []
    with _connection() as connection:
        if company_id is None:
            return _fetch_all(connection, "SELECT * FROM audit_log ORDER BY occurred_at")
        return _fetch_all(connection, "SELECT * FROM audit_log WHERE company_id = %s"
                                      " ORDER BY occurred_at", (company_id,))
