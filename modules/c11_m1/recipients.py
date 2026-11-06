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
"""Recipients of personal notifications (README 6.1, 11.2): the `sub` of every person to inform.

Kinds of `Rule.recipients` (the kinds `applicant` and `staff:` are handled by `engine`):
- `company_role:<field>:<portal role>`: C2-M2 `list_company_user_refs` (9.4) for the company in
  `data[<field>]`; `userId` is the `sub` of the person (C2-M2 2);
- `it_or_company_admin:<field>`: the `IT Admin` of the company, or its `Company Admin` if it has none;
- `app_customers:<field>`: C10-M1 `find_subscriptions` (9.1) of the app `data[<field>]` with status
  `ACTIVE`, then the `Company Admin` of every customer company;
- `subscription_customer:<field>`: C10-M1 `get_subscription_internal` (9.2), then the `Company Admin`
  of its customer company.

Neighbours are called through `portal_common.neighbours` (FRAMEWORK 4.7). An empty address means
the built-in stand-in of README 11.2: C2-M2 from `stub-company-users.json` (the data of README 14),
C10-M1 an empty list. A neighbour that cannot be reached (`retryable` problem) raises
`store.Unavailable`, so the worker repeats the job (README 4); a neighbour that rejects the call
raises its `Problem` at once, since repeating cannot help. Not found or an empty list is nobody.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path

from modules.c11_m1 import store
from portal_common import neighbours
from portal_common.problems import Problem

log = logging.getLogger("portal.c11-m1")

MODULE = "c11-m1"
COMPANY_ADMIN = "Company Admin"
IT_ADMIN = "IT Admin"
STUB_COMPANY_USERS = Path(__file__).with_name("stub-company-users.json")   # README 11.2, 14


def resolve(kind: str, data: dict) -> list[str]:
    """README 6.1: the `sub` of every person who gets a personal notification; raises `store.Unavailable`."""
    name, _, arg = kind.partition(":")
    if name == "company_role":
        field, _, role = arg.partition(":")
        return company_users(_value(data, field), role)
    if name == "it_or_company_admin":
        company_id = _value(data, arg)
        return company_users(company_id, IT_ADMIN) or company_users(company_id, COMPANY_ADMIN)
    if name == "app_customers":
        return _app_customers(_value(data, arg))
    if name == "subscription_customer":
        return _subscription_customer(_value(data, arg))
    raise ValueError(f"unknown recipient kind {kind!r}")


def company_users(company_id: str | None, portal_role: str) -> list[str]:
    """README 6.1: the `sub` of the active people of the company with the portal role (C2-M2 9.4)."""
    if not company_id:
        return []
    if neighbours.is_standin("c2-m2"):
        return _stub_company_users(company_id, portal_role)
    refs = _query("c2-m2", "list_company_user_refs", companyId=company_id, portalRole=portal_role) or []
    return [r["userId"] for r in refs]


def _app_customers(app_id: str | None) -> list[str]:
    """README 6.1 "customers of the app": `appId` is the `offerId` of C10-M1 (C12-M1 flow `app-approval`)."""
    if not app_id or neighbours.is_standin("c10-m1"):
        return []
    subscriptions = _query("c10-m1", "find_subscriptions", offerId=app_id, status="ACTIVE") or []
    return _company_admins(s["customerCompanyId"] for s in subscriptions)


def _subscription_customer(subscription_id: str | None) -> list[str]:
    """README 6.2 R12: the `Company Admin` of the customer of the subscription (C10-M1 9.2)."""
    if not subscription_id or neighbours.is_standin("c10-m1"):
        return []
    subscription = _query("c10-m1", "get_subscription_internal", offerSubscriptionId=subscription_id)
    return _company_admins([subscription["customerCompanyId"]] if subscription else [])


def _company_admins(company_ids: Iterable[str | None]) -> list[str]:
    return [sub for cid in dict.fromkeys(company_ids) for sub in company_users(cid, COMPANY_ADMIN)]


def _value(data: dict, field: str) -> str | None:
    value = data.get(field)
    if value is None:
        log.info("recipients: field %s missing in the event", field)
    return value


def _query(target: str, function: str, **params) -> list | dict | None:
    """`neighbours.query` with the retry rule of README 4: unreachable -> `store.Unavailable`."""
    try:
        return neighbours.query(MODULE, target, function, **params)
    except Problem as e:
        if e.ext.get("retryable"):
            raise store.Unavailable(f"{target} {function}: {e.name}") from e
        raise


def _stub_company_users(company_id: str, portal_role: str) -> list[str]:
    """Built-in stand-in of C2-M2 (README 11.2): `companyId` -> portal role -> `sub` values."""
    table = json.loads(STUB_COMPANY_USERS.read_text(encoding="utf-8"))
    return list(table.get(company_id, {}).get(portal_role, []))
