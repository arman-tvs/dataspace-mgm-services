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
"""Repository of C3-M1 (README 5) with two transports behind one function list.

`DATABASE_URL` selects the transport, read at call time and never at import (AGENTS.md 6):

- empty: `store_memory`, the in-memory transport. Every state is in the process, so the module
  runs without a database (tests, `demo.py`, the hackathon installation).
- set: `store_postgres`, the module's own database `c3_m1` (README 4) with the tables of
  `schema.sql`. The database user of the module owns that schema; nothing else reads it.

Both transports answer the same functions and the same invariants; only the storage differs. A
caller therefore never learns which one runs, except through `backend_name()`. Field names are the
snake_case ones of README 5 — the interface and router map them to camelCase.

Nothing here is FastAPI, HTTP or events, and nothing is cached across a `reset()`.
"""
from __future__ import annotations

import importlib
import os
from types import ModuleType

from portal_common.problems import Problem

MODULE = "c3-m1"

STATUSES = ("REQUESTED", "ACTIVE", "REJECTED", "INACTIVE")
DEACTIVATION_REASONS = ("MANUAL", "TRANSFERRED")
CORE_DATA_SOURCES = ("EBW", "MANUAL")
IDENTIFIER_TYPES = ("EUID", "EBWOID", "VAT_ID", "COMMERCIAL_REG_NUMBER", "LEI_CODE", "EORI")
IDENTIFIER_SOURCES = ("BUSINESS_WALLET", "DECLARED")
ROLE_STATUSES = ("REQUESTED", "ACTIVE", "INACTIVE")
ROLE_SOURCE_KINDS = ("APPLICATION", "COMPANY", "SEED")
CONSENT_SOURCE_KINDS = ("APPLICATION", "COMPANY")
CONSENT_STATUSES = ("ACTIVE", "INACTIVE")
CHANGE_REQUEST_STATUSES = ("OPEN", "APPROVED", "DECLINED", "WITHDRAWN")
MEDIA_TYPES = ("application/pdf", "image/png", "image/jpeg")

#: All fields of table `company` (README 5), in the order of the table.
COMPANY_FIELDS = (
    "id", "name", "short_name", "street", "house_number", "address_addition", "postal_code",
    "city", "region", "country_code", "status", "bpn", "bpn_assigned_at", "core_data_source",
    "core_data_verified_at", "verification_ref", "application_id", "deactivation_reason",
    "created_at", "changed_at", "activated_at", "rejected_at", "deactivated_at", "reactivated_at",
)

_cache: tuple[str, ModuleType] | None = None


def backend_name() -> str:
    """Name of the transport that `DATABASE_URL` selects right now: `memory` or `postgres`."""
    return "postgres" if os.environ.get("DATABASE_URL") else "memory"


def backend() -> ModuleType:
    """The transport module for the current `DATABASE_URL`; imported on first use."""
    global _cache
    name = backend_name()
    if _cache is not None and _cache[0] == name:
        return _cache[1]
    try:
        module = importlib.import_module(f".store_{name}", __package__)
    except ModuleNotFoundError as error:
        if name == "postgres" and error.name in ("psycopg", "psycopg.rows"):
            # Not part of the scaffold yet: answer like every other unimplemented operation.
            raise Problem(MODULE, 501, "not-implemented",
                          detail="DATABASE_URL is set but the PostgreSQL transport is not usable: "
                                 "install `psycopg[binary]` (see OPEN-QUESTIONS.md 1 and 2)") from error
        raise
    _cache = (name, module)
    return module


def backend_memory() -> ModuleType:
    """The in-memory transport, also while `DATABASE_URL` selects the unusable database one."""
    return importlib.import_module(".store_memory", __package__)


def _delegate(name: str):
    def call(*args, **kwargs):
        return getattr(backend(), name)(*args, **kwargs)

    call.__name__ = call.__qualname__ = name
    call.__doc__ = f"Delegates to the transport's `{name}`."
    return call


reset = _delegate("reset")
lock = _delegate("lock")
get_company = _delegate("get_company")
create_company = _delegate("create_company")
update_company = _delegate("update_company")
find_companies = _delegate("find_companies")
list_identifiers = _delegate("list_identifiers")
set_identifiers = _delegate("set_identifiers")
get_role = _delegate("get_role")
role_status = _delegate("role_status")
list_roles = _delegate("list_roles")
add_role = _delegate("add_role")
remove_role = _delegate("remove_role")
get_consent = _delegate("get_consent")
list_consents = _delegate("list_consents")
set_consent = _delegate("set_consent")
get_change_request = _delegate("get_change_request")
create_change_request = _delegate("create_change_request")
open_change_request = _delegate("open_change_request")
list_change_requests = _delegate("list_change_requests")
decide_change_request = _delegate("decide_change_request")
withdraw_change_request = _delegate("withdraw_change_request")
add_document = _delegate("add_document")
get_document = _delegate("get_document")
list_documents = _delegate("list_documents")
add_if_unused = _delegate("add_if_unused")
is_used = _delegate("is_used")
audit = _delegate("audit")
list_audit = _delegate("list_audit")
