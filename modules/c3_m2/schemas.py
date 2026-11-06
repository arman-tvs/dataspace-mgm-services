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
"""The API contract of C3-M2 as Pydantic models: one class per schema in `components.schemas` of
`spec/C3-M2-CSPConnection/openapi.yaml`, with the same names and fields (camelCase, as on the wire).

The router uses them so that FastAPI validates every HTTP request (400 `validation` as Problem
Details, never 422) and Swagger UI at `/docs` shows the real fields. `interface.py` keeps plain
dicts: Process Orchestration calls the interface functions in-process with dicts (call convention
of AGENTS.md), and the interface checks its input itself.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

COUNTRY = r"^[A-Z]{2}$"


# ---------------------------------------------------------------- shared parts
class Identifier(BaseModel):
    """Identifier of a company, such as `VAT_ID` or `COMMERCIAL_REG_NUMBER` (README 2, 6.5)."""
    type: str = Field(min_length=1, description="identifier type from the reference data, such as VAT_ID")
    value: str = Field(min_length=1)


class Address(BaseModel):
    """Address as the CSP takes it; C12 maps it from the C3-M1 address (flows.yaml, company-core-data)."""
    streetAddress: str | None = None
    postalCode: str | None = None
    locality: str | None = None
    country: str | None = None


# ---------------------------------------------------------------- step inputs (README 8)
class StepInput(BaseModel):
    """Every step input (FRAMEWORK 4.4)."""
    processId: UUID
    stepRunId: UUID
    companyId: UUID


class RegisterCompanyInput(StepInput):
    """README 8.1. At least `ebwoid`, `euid` or an entry in `identifiers` (README 6.5); the step
    checks this and answers 400 `validation`."""
    legalName: str = Field(min_length=1)
    country: str = Field(pattern=COUNTRY, examples=["DE"])
    ebwoid: str | None = Field(default=None, examples=["EBWOID-DE-0000000001"])
    euid: str | None = Field(default=None, examples=["DEXX001T.HRB100001"])
    identifiers: list[Identifier] | None = None
    address: Address | None = None


class TransferCompanyInput(StepInput):
    """README 8.2. `bpn` from `find-companies`."""
    bpn: str = Field(min_length=1, examples=["BPNL00000000002B"])
    ebwoid: str | None = None
    euid: str | None = None
    identifiers: list[Identifier] | None = None


class RegisterDidInput(StepInput):
    """README 8.3."""
    did: str = Field(min_length=1, examples=["did:web:wallet.example.org:BPNL00000000OSPA"])


class UpdateCompanyInput(StepInput):
    """README 8.4."""
    legalName: str = Field(min_length=1)
    euid: str | None = None
    address: Address | None = None


class ConnectorInput(StepInput):
    """README 8.6, `deregister-connector`. `companyId` is the host company of the connector."""
    connectorId: UUID


class RegisterConnectorInput(ConnectorInput):
    """README 8.6, `register-connector`."""
    endpointUrl: str = Field(pattern=r"^https://", description="address of the connector (DSP endpoint), HTTPS",
                             examples=["https://edc.beispiel-maschinenbau.example/dsp"])


# ---------------------------------------------------------------- step result (FRAMEWORK 4.4)
class StepResultData(BaseModel):
    """Fields later steps read, for example `steps.register-company.bpn` in flows.yaml."""
    bpn: str | None = None
    did: str | None = None
    connectorId: UUID | None = None


class StepResult(BaseModel):
    """Answer of every step: DONE with the result, or RUNNING until the completing event."""
    stepRunId: UUID
    state: Literal["DONE", "RUNNING"]
    result: StepResultData | None = None


# ---------------------------------------------------------------- other operations
class CspRegistration(BaseModel):
    """README 7.1: the status of a company at the CSP."""
    companyId: UUID
    bpn: str | None = None
    status: Literal["PENDING", "REGISTERED", "FAILED", "TRANSFERRED_AWAY"]
    failureReason: str | None = None
    did: str | None = None
    membership: Literal["NONE", "REGISTERED", "DEREGISTERED"]
    registeredAt: str | None = Field(default=None, description="date-time")
    updatedAt: str | None = Field(default=None, description="date-time")


class CspCompanyMatch(BaseModel):
    """README 9: one match of the duplicate check."""
    bpn: str
    legalName: str
    country: str
    matchedBy: Literal["EBWOID", "EUID", "IDENTIFIER", "NAME"]
    homeOspId: UUID
    homeOspName: str | None = None
    homeIsThisOsp: bool
    memberActive: bool | None = None


class CspNotification(BaseModel):
    """README 7.2: notification from the CSP. `operationId` and `outcome` with `OperationCompleted`."""
    notificationId: str = Field(min_length=1)
    type: Literal["OperationCompleted", "CompanyTransferredAway"]
    bpn: str | None = None
    operationId: str | None = None
    outcome: Literal["SUCCEEDED", "FAILED"] | None = None
    reason: str | None = None
