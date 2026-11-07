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
"""Connectors in the discovery of the CSP: steps register-connector and deregister-connector (README 8.6)."""
from __future__ import annotations

from modules.c3_m2 import errors, store
from modules.c3_m2.adapters import csp
from modules.c3_m2.errors import MODULE
from portal_common import events

from . import csp_calls
from .common import StepInputJson, StepReply, bpn_of, registered, reply, required


def register_connector(input: StepInputJson) -> StepReply:
    """Step register-connector (README 8.6): connector into the discovery of the CSP."""
    company_id = required(input, "companyId")
    connector_id = required(input, "connectorId")
    endpoint = required(input, "endpointUrl")
    if not endpoint.startswith("https://"):
        raise errors.validation("endpointUrl must be an HTTPS address")
    bpn = bpn_of(registered(company_id))
    # Call the CSP only for a new connector or a new address (README 6.4); the same call again
    # answers DONE without a call and without an event.
    con = store.connectors.get(connector_id)
    if con is not None and con.status == "REGISTERED" and con.company_id != company_id:
        # Entering it under the new BPN would leave it listed under the old one as well (README 6.6;
        # OPEN-QUESTIONS 17): C6-M1 deregisters it first.
        raise errors.invalid_state(f"connector {connector_id} is registered for company {con.company_id}; "
                                   "deregister it there first")
    if not _registered_as(connector_id, company_id, bpn, endpoint):
        status, answer = csp_calls.call("register-connector", "PUT", f"/companies/{bpn}/connectors/{connector_id}",
                                        {"endpointUrl": endpoint}, company_id=company_id, bpn=bpn)
        csp.raise_for(status, answer)
        with store.lock:
            if not _registered_as(connector_id, company_id, bpn, endpoint):   # one event only
                now = store.connectors.get(connector_id)
                stamp = store.now()
                store.connectors[connector_id] = store.Connector(
                    connector_id=connector_id, company_id=company_id, bpn=bpn, endpoint_url=endpoint,
                    status="REGISTERED", registered_at=now.registered_at if now else stamp, updated_at=stamp)
                events.publish(MODULE, "ConnectorRegisteredAtCsp",
                               {"companyId": company_id, "bpn": bpn, "connectorId": connector_id})
    return reply(input, {"bpn": bpn, "connectorId": connector_id})


def _registered_as(connector_id: str, company_id: str, bpn: str, endpoint: str) -> bool:
    """The connector is registered with exactly this company, BPN and address (README 6.4)."""
    con = store.connectors.get(connector_id)
    return (con is not None and con.status == "REGISTERED" and con.endpoint_url == endpoint
            and con.company_id == company_id and con.bpn == bpn)


def deregister_connector(input: StepInputJson) -> StepReply:
    """Step deregister-connector (README 8.6): unknown or already removed -> DONE without a call."""
    company_id = required(input, "companyId")
    connector_id = required(input, "connectorId")
    # Unknown or already removed: DONE without a call (README 6.4). The result carries the BPN only
    # when it is known (OPEN-QUESTIONS 8). A known connector needs a REGISTERED company
    # (OPEN-QUESTIONS 7), and it must be the connector's host company (README 8.6), otherwise the
    # event would pair one company's id with another's BPN (OPEN-QUESTIONS 17).
    con = store.connectors.get(connector_id)
    if con is None or con.status == "DEREGISTERED":
        row = store.registrations.get(company_id)
        bpn = con.bpn if con else (row.bpn if row else None)
        return reply(input, {"connectorId": connector_id} | ({"bpn": bpn} if bpn else {}))
    if con.company_id != company_id:
        raise errors.invalid_state(f"connector {connector_id} is registered for company {con.company_id}, "
                                   f"not for {company_id}")
    registered(company_id)
    status, answer = csp_calls.call("deregister-connector", "DELETE",
                                    f"/companies/{con.bpn}/connectors/{connector_id}",
                                    company_id=company_id, bpn=con.bpn)
    csp.raise_for(status, answer)
    with store.lock:
        current = store.connectors.get(connector_id)   # read again: a concurrent call may have removed it
        if current is not None and current.status == "REGISTERED":   # one event only
            current.status, current.updated_at = "DEREGISTERED", store.now()
            events.publish(MODULE, "ConnectorDeregisteredAtCsp",
                           {"companyId": company_id, "bpn": con.bpn, "connectorId": connector_id})
    return reply(input, {"bpn": con.bpn, "connectorId": connector_id})
