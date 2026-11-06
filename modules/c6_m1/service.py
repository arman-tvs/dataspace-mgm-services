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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""Operations of people on the connector register (README 7) with the checks of README 6.2 and the
calls to the neighbours C3-M1, C2-M3 and C10-M1 (README 11). No token checks here; the router passes
the calling company and person."""
from __future__ import annotations

import json
import uuid
from urllib.parse import urlparse

from portal_common import events, neighbours, settings
from portal_common.problems import Problem

from .interface import (
    ACTIVE,
    COMPANY_CONNECTOR,
    CONNECTOR_AS_A_SERVICE,
    INACTIVE,
    LOCK,
    MODULE,
    canonical,
    connectors,
    deleted_technical_users,
    ended_subscriptions,
    now,
    publish_deactivated,
    stub_companies,
    stub_subscriptions,
    view,
    write_audit,
)


# ---------------------------------------------------------------- neighbours (README 11)
def company_status(company_id: str) -> str | None:
    """C3-M1 `query_company`: status of the company; None if C3-M1 does not know it."""
    if neighbours.is_standin("c3-m1"):
        return stub_companies.get(company_id, ACTIVE)
    company = neighbours.query(MODULE, "c3-m1", "query_company", companyId=company_id)
    return (company or {}).get("status")


def technical_user_usable(technical_user_id: str, host_company_id: str, offer_subscription_id: str | None) -> bool:
    """C2-M3 `check_technical_user` (C2-M3 9.1): `usableForConnector`."""
    if neighbours.is_standin("c2-m3"):
        return True
    params = {"id": technical_user_id, "companyId": host_company_id}
    if offer_subscription_id:
        params["offerSubscriptionId"] = offer_subscription_id
    answer = neighbours.query(MODULE, "c2-m3", "check_technical_user", **params)
    return bool(answer and answer.get("usableForConnector"))


def subscription(offer_subscription_id: str) -> dict | None:
    """C10-M1 `get_subscription_internal`: `status`, `providerCompanyId`, `customerCompanyId`."""
    if neighbours.is_standin("c10-m1"):
        return stub_subscriptions.get(offer_subscription_id)
    return neighbours.query(MODULE, "c10-m1", "get_subscription_internal", offerSubscriptionId=offer_subscription_id)


# ---------------------------------------------------------------- checks (README 6.2)
def _known_countries() -> set[str] | None:
    """Country codes of the reference data (`masterDataFile` of the installation settings, OP-13)."""
    path = settings.resolve_path(settings.get("masterDataFile"))
    if not path or not path.exists():
        return None
    return {c["code"] for c in json.loads(path.read_text(encoding="utf-8")).get("countries", [])}


def _check_input(name, endpoint, location, technical_user_id=None) -> None:
    errors = []
    if not isinstance(name, str) or not name or len(name) > 255:
        errors.append({"field": "name", "message": "1 to 255 characters"})
    endpoint = endpoint if isinstance(endpoint, str) else ""
    try:
        url = urlparse(endpoint)
        _ = url.port   # raises ValueError for an invalid port
    except ValueError:
        url = None
    if url is None or url.scheme != "https" or not url.hostname or len(endpoint) > 2000:
        errors.append({"field": "endpoint", "message": "HTTPS URL"})
    elif url.username is not None or url.password is not None:   # no credentials in data or events (FRAMEWORK 4.6)
        errors.append({"field": "endpoint", "message": "must not contain user information"})
    countries = _known_countries()
    if technical_user_id is not None and not _is_uuid(technical_user_id):
        errors.append({"field": "technicalUserId", "message": "UUID"})
    if not isinstance(location, str) or len(location) != 2 or not (location.isalpha() and location.isupper()) or (countries is not None and location not in countries):
        errors.append({"field": "location", "message": "unknown country code"})
    if errors:
        raise Problem(MODULE, 400, "validation", errors=errors)


def _is_uuid(value) -> bool:
    try:
        uuid.UUID(str(value))
        return isinstance(value, str)
    except ValueError:
        return False


def _live() -> list[dict]:
    with LOCK:   # a concurrent insert or delete must not change the dict while it is read
        return [c for c in connectors.values() if c["status"] != INACTIVE]


def _check_duplicate(name: str, endpoint: str, ignore: str | None = None) -> None:
    if any(c["name"] == name and c["endpoint"] == endpoint and c["id"] != ignore for c in _live()):
        raise Problem(MODULE, 409, "duplicate", detail="a connector with this name and endpoint exists")


def _check_technical_user(tu_id: str | None, host: str, sub_id: str | None) -> None:
    if not tu_id:
        return
    linked = any(c["technical_user_id"] == tu_id for c in _live())
    if linked or not technical_user_usable(tu_id, host, sub_id):
        raise Problem(MODULE, 409, "technical-user-not-usable")


def _check_host_active(host: str) -> None:
    if company_status(host) != ACTIVE:
        raise Problem(MODULE, 409, "company-not-active")


def _own_company(company_id: str | None) -> str:
    if not company_id:
        raise Problem(MODULE, 403, "forbidden", detail="the token has no company_id")
    return company_id


def _visible(connector_id: str, company_id: str) -> dict:
    c = connectors.get(canonical(connector_id)) if _is_uuid(connector_id) else None
    if not c or company_id not in (c["provider_company_id"], c["host_company_id"]):
        raise Problem(MODULE, 404, "not-found")
    return c


# ---------------------------------------------------------------- operations (README 7)
def _register(*, name, endpoint, location, technical_user_id, ctype, provider, host, sub_id, sub) -> dict:
    """The final uniqueness checks of README 5 and the insert as one unit under LOCK: of two concurrent
    requests that both passed the earlier checks, the second gets 409."""
    with LOCK:
        if sub_id in ended_subscriptions:
            raise Problem(MODULE, 409, "invalid-state", detail="subscription ended or declined")
        if sub_id and any(c["offer_subscription_id"] == sub_id for c in _live()):
            raise Problem(MODULE, 409, "subscription-linked")
        _check_duplicate(name, endpoint)
        if technical_user_id in deleted_technical_users:
            raise Problem(MODULE, 409, "technical-user-not-usable", detail="technical user was deleted")
        if technical_user_id and any(c["technical_user_id"] == technical_user_id for c in _live()):
            raise Problem(MODULE, 409, "technical-user-not-usable")
        return _insert(name=name, endpoint=endpoint, location=location, technical_user_id=technical_user_id,
                       ctype=ctype, provider=provider, host=host, sub_id=sub_id, sub=sub)


def _insert(*, name, endpoint, location, technical_user_id, ctype, provider, host, sub_id, sub) -> dict:
    c = {"id": str(uuid.uuid4()), "name": name, "endpoint": endpoint, "location": location, "type": ctype,
         "status": ACTIVE, "provider_company_id": provider, "host_company_id": host,
         "technical_user_id": technical_user_id, "offer_subscription_id": sub_id,
         "created_at": now(), "changed_at": None}
    connectors[c["id"]] = c
    write_audit("register-connector", c["id"], sub, provider)
    events.publish(MODULE, "ConnectorRegistered", {
        "connectorId": c["id"], "companyId": host, "providerCompanyId": provider, "type": ctype,
        "endpoint": endpoint, "location": location})
    return view(c)


def list_connectors(company_id: str | None, *, role: str | None = None, type: str | None = None,
                    status: str | None = None, page: int = 0, size: int = 20) -> dict:
    """7.1"""
    own = _own_company(company_id)

    def matches(c: dict) -> bool:
        as_provider = c["provider_company_id"] == own
        as_host = c["host_company_id"] == own and c["type"] == CONNECTOR_AS_A_SERVICE and not as_provider
        if role == "provider" and not as_provider or role == "host" and not as_host or not (as_provider or as_host):
            return False
        if type and c["type"] != type:
            return False
        return c["status"] == status if status else c["status"] != INACTIVE

    with LOCK:   # filter and serialize from the same state
        items = sorted((c for c in connectors.values() if matches(c)), key=lambda c: (c["created_at"], c["id"]))
        return {"items": [view(c) for c in items[page * size:(page + 1) * size]], "page": page, "size": size,
                "total": len(items)}


def register_connector(company_id: str | None, sub: str | None, body: dict) -> dict:
    """7.2: company connector of the own company."""
    own = _own_company(company_id)
    _check_input(body.get("name"), body.get("endpoint"), body.get("location"), body.get("technicalUserId"))
    body = body | {"technicalUserId": canonical(body["technicalUserId"]) if body.get("technicalUserId") else None}
    _check_host_active(own)
    _check_duplicate(body["name"], body["endpoint"])
    _check_technical_user(body.get("technicalUserId"), own, None)
    return _register(name=body["name"], endpoint=body["endpoint"], location=body["location"],
                     technical_user_id=body.get("technicalUserId"), ctype=COMPANY_CONNECTOR, provider=own,
                     host=own, sub_id=None, sub=sub)


def register_connector_as_a_service(company_id: str | None, sub: str | None, body: dict) -> dict:
    """7.3: provider = own company, host = customer of the subscription of an own offer."""
    own = _own_company(company_id)
    _check_input(body.get("name"), body.get("endpoint"), body.get("location"), body.get("technicalUserId"))
    sub_id = body.get("offerSubscriptionId")
    if not _is_uuid(sub_id):
        raise Problem(MODULE, 400, "validation", errors=[{"field": "offerSubscriptionId", "message": "UUID"}])
    sub_id = canonical(sub_id)
    body = body | {"technicalUserId": canonical(body["technicalUserId"]) if body.get("technicalUserId") else None}
    s = subscription(sub_id)
    if not s or s.get("providerCompanyId") != own:
        raise Problem(MODULE, 404, "not-found", detail="subscription unknown or not of an own offer")
    if s.get("status") not in ("PENDING", "ACTIVE"):
        raise Problem(MODULE, 409, "invalid-state", detail=f"subscription is {s.get('status')}")
    if any(c["offer_subscription_id"] == sub_id for c in _live()):
        raise Problem(MODULE, 409, "subscription-linked")
    host = s["customerCompanyId"]
    _check_host_active(host)
    _check_duplicate(body["name"], body["endpoint"])
    _check_technical_user(body.get("technicalUserId"), host, sub_id)
    return _register(name=body["name"], endpoint=body["endpoint"], location=body["location"],
                     technical_user_id=body.get("technicalUserId"), ctype=CONNECTOR_AS_A_SERVICE, provider=own,
                     host=host, sub_id=sub_id, sub=sub)


def get_connector(company_id: str | None, connector_id: str) -> dict:
    """7.4"""
    with LOCK:
        return view(_visible(connector_id, _own_company(company_id)))


def change_endpoint(company_id: str | None, sub: str | None, connector_id: str, body: dict) -> dict:
    """7.5 under LOCK, so that its duplicate check and change do not interleave with other changes."""
    with LOCK:
        return _change_endpoint(company_id, sub, connector_id, body)


def _change_endpoint(company_id: str | None, sub: str | None, connector_id: str, body: dict) -> dict:
    """7.5: only the provider company; same value = 200 without change."""
    own = _own_company(company_id)
    c = _visible(connector_id, own)
    if c["provider_company_id"] != own:
        raise Problem(MODULE, 403, "forbidden", detail="only the provider company changes the endpoint")
    if c["status"] == INACTIVE:
        raise Problem(MODULE, 409, "invalid-state", detail="connector is INACTIVE")
    endpoint = body.get("endpoint")
    _check_input(c["name"], endpoint, c["location"])
    if endpoint == c["endpoint"]:
        return view(c)
    _check_duplicate(c["name"], endpoint, ignore=c["id"])
    c.update(endpoint=endpoint, changed_at=now())
    write_audit("change-endpoint", c["id"], sub, own)
    events.publish(MODULE, "ConnectorEndpointChanged", {"connectorId": c["id"], "companyId": c["host_company_id"],
                                                        "endpoint": endpoint})
    return view(c)


def delete_connector(company_id: str | None, sub: str | None, connector_id: str) -> None:
    """7.6: C10-M1 is asked outside LOCK (it may be slow); the change runs under LOCK on the current row."""
    own = _own_company(company_id)
    with LOCK:
        sub_id = _visible(connector_id, own)["offer_subscription_id"]
    s = subscription(sub_id) if sub_id else None
    with LOCK:
        _delete_connector(company_id, sub, connector_id, s)


def _delete_connector(company_id: str | None, sub: str | None, connector_id: str, s: dict | None) -> None:
    """7.6: with a linked subscription the connector becomes INACTIVE and keeps the link; otherwise removed."""
    own = _own_company(company_id)
    c = _visible(connector_id, own)   # may have been deleted meanwhile: 404
    if c["offer_subscription_id"]:
        if s and s.get("status") == ACTIVE:
            raise Problem(MODULE, 409, "subscription-active")
        if c["status"] != INACTIVE:
            c.update(status=INACTIVE, changed_at=now())
            write_audit("delete-connector", c["id"], sub, own)
            publish_deactivated(c)
        return
    del connectors[c["id"]]
    write_audit("delete-connector", c["id"], sub, own)
    events.publish(MODULE, "ConnectorDeleted", {"connectorId": c["id"], "companyId": c["host_company_id"]})
    return
