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
"""The HTTP contract of C3-M1 as Pydantic models (ADR-0003 "HTTP layer (FastAPI)"): one class per schema of
`components.schemas` in `spec/C3-M1-CompanyProfile/openapi.yaml`, with the same names and fields (camelCase).

Request models declare the fields, their JSON types and what the spec requires, so FastAPI answers a missing or
mistyped field with 400 `validation` and Swagger shows the contract. Value rules (patterns, lengths, the
identifier formats of README 6.4, role catalogue) stay in `validation.py`, which answers them with the field
errors of README 12. Request models keep fields the spec does not name (`extra="allow"`, the OpenAPI default):
`CompanyUpdate` needs them for 409 `field-locked`, and the interface still sees exactly what the client sent.

Response models give Swagger the answer and let FastAPI drop fields that are not in the contract.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

CompanyStatus = Literal["REQUESTED", "ACTIVE", "REJECTED", "INACTIVE"]
CoreDataSource = Literal["EBW", "MANUAL"]
DeactivationReason = Literal["MANUAL", "TRANSFERRED"]
AssignableBy = Literal["COMPANY", "SEED"]
IdentifierSource = Literal["BUSINESS_WALLET", "DECLARED"]
ChangeRequestStatus = Literal["OPEN", "APPROVED", "DECLINED", "WITHDRAWN"]
MediaType = Literal["application/pdf", "image/png", "image/jpeg"]


class Request(BaseModel):
    """Request bodies keep unknown fields (OpenAPI default); the module decides on them."""
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------- shared parts
class Identifier(BaseModel):
    type: str
    value: str
    source: IdentifierSource


class DeclaredIdentifier(Request):
    type: str
    value: str


class AddressFields(Request):
    street: str
    houseNumber: str | None = None
    addressAddition: str | None = None
    postalCode: str | None = None
    city: str
    region: str | None = None


class Address(AddressFields):
    countryCode: str


class AddressPatch(Request):
    """The address of a correction: the parts given are merged into the stored address (OPEN-QUESTIONS 13)."""
    street: str | None = None
    houseNumber: str | None = None
    addressAddition: str | None = None
    postalCode: str | None = None
    city: str | None = None
    region: str | None = None
    countryCode: str | None = None


class AddressAnswer(BaseModel):
    street: str
    houseNumber: str | None = None
    addressAddition: str | None = None
    postalCode: str | None = None
    city: str
    region: str | None = None
    countryCode: str


class CompanyRoleAssignment(BaseModel):
    companyRole: str
    status: Literal["REQUESTED", "ACTIVE", "INACTIVE"]
    activatedAt: str | None = None
    deactivatedAt: str | None = None


# ---------------------------------------------------------------- companies (README 7.1, 7.2, 7.10 - 7.12)
class Company(BaseModel):
    """The company as seen by its people."""
    id: str
    name: str
    shortName: str | None = None
    address: AddressAnswer
    identifiers: list[Identifier]
    coreDataSource: CoreDataSource
    coreDataVerifiedAt: str | None = None
    bpn: str | None = None
    status: CompanyStatus
    companyRoles: list[CompanyRoleAssignment]
    dataspaceName: str | None = None
    createdAt: str
    changedAt: str | None = None
    activatedAt: str | None = None


class CompanyDetail(Company):
    """The company as seen by OSP staff, with all fields."""
    applicationId: str | None = None
    verificationRef: str | None = None
    bpnAssignedAt: str | None = None
    deactivationReason: DeactivationReason | None = None
    rejectedAt: str | None = None
    deactivatedAt: str | None = None
    reactivatedAt: str | None = None
    openChangeRequestId: str | None = None


class CompanySummary(BaseModel):
    id: str
    name: str
    status: CompanyStatus
    bpn: str | None = None
    coreDataSource: CoreDataSource
    countryCode: str
    companyRoles: list[str] = []
    createdAt: str


class CompanyPage(BaseModel):
    items: list[CompanySummary]
    page: int
    size: int
    total: int


class CompanyUpdate(Request):
    """Only `shortName` may change; further fields give 409 `field-locked` (README 7.2)."""
    shortName: str | None = None


class AttestationUpdate(Request):
    attestation: str


class AttestationUpdateResult(BaseModel):
    changedFields: list[str]
    company: Company


class CompanyCorrection(Request):
    """Correction by OSP staff (README 6.6, 7.12)."""
    name: str | None = None
    shortName: str | None = None
    address: AddressPatch | None = None
    identifiers: list[DeclaredIdentifier] | None = None
    reason: str


class Reason(Request):
    reason: str


# ---------------------------------------------------------------- change requests (README 7.4 - 7.6, 7.14 - 7.18)
class ChangeRequestChanges(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    address: dict[str, str | None] | None = None
    identifiers: list[dict[str, str]] | None = None


class DocumentInfo(BaseModel):
    id: str
    fileName: str
    mediaType: MediaType
    sizeBytes: int


class ChangeRequest(BaseModel):
    id: str
    companyId: str
    companyName: str | None = None
    status: ChangeRequestStatus
    changes: ChangeRequestChanges
    comment: str
    documents: list[DocumentInfo]
    requestedBy: str
    decidedBy: str | None = None
    decisionReason: str | None = None
    createdAt: str
    closedAt: str | None = None


class ChangeRequestCompany(BaseModel):
    id: str
    name: str
    address: AddressAnswer
    identifiers: list[Identifier]
    coreDataSource: CoreDataSource
    status: CompanyStatus


class ChangeRequestDetail(ChangeRequest):
    """The change request with the current state of the company for comparison."""
    company: ChangeRequestCompany


class ChangeRequestPage(BaseModel):
    items: list[ChangeRequest]
    page: int
    size: int
    total: int


class ApprovalInput(Request):
    comment: str | None = None


class DeclineInput(Request):
    reason: str


# ---------------------------------------------------------------- company roles (README 7.7 - 7.9, 9.4)
class AgreementRef(Request):
    agreementKey: str
    version: str


class AgreementConsent(BaseModel):
    agreementKey: str
    version: str
    name: str
    names: dict[str, str]
    documentUrl: str
    consentStatus: Literal["ACTIVE", "INACTIVE"] | None = None
    consentedVersion: str | None = None
    consentedAt: str | None = None


class CompanyRoleState(BaseModel):
    companyRole: str
    assignableBy: AssignableBy
    status: Literal["NONE", "REQUESTED", "ACTIVE", "INACTIVE"]
    description: str
    agreements: list[AgreementConsent]


class CompanyRoleAdd(Request):
    companyRole: str
    consents: list[AgreementRef]


class CompanyRoleDefinition(BaseModel):
    companyRole: str
    assignableBy: AssignableBy
    description: str
    descriptions: dict[str, str]


# ---------------------------------------------------------------- queries for other modules (README 9)
class CompanyInternal(BaseModel):
    """The company for other modules and Process Orchestration."""
    id: str
    name: str
    shortName: str | None = None
    address: AddressAnswer
    identifiers: list[Identifier]
    coreDataSource: CoreDataSource
    status: CompanyStatus
    bpn: str | None = None
    companyRoles: list[str]
    deactivationReason: DeactivationReason | None = None
    createdAt: str
    activatedAt: str | None = None
    deactivatedAt: str | None = None


class CompanyLookupResult(BaseModel):
    items: list[CompanyInternal]
    notFound: list[str]


class MatchIdentifier(Request):
    type: str
    value: str


class IdentifierMatchQuery(Request):
    identifiers: list[MatchIdentifier]
    name: str | None = None
    excludeCompanyId: str | None = None
    statuses: list[str] | None = None


class IdentifierMatch(BaseModel):
    companyId: str
    name: str
    status: CompanyStatus
    bpn: str | None = None
    matchedOn: list[str]


class IdentifierMatchResult(BaseModel):
    matches: list[IdentifierMatch]


# ---------------------------------------------------------------- steps for Process Orchestration (README 8)
class StepRequest(Request):
    processId: UUID
    stepRunId: UUID


class StepCompanyRef(StepRequest):
    companyId: UUID


class StepCompanyApplication(StepCompanyRef):
    applicationId: UUID


class StepAssignIdentifier(StepCompanyRef):
    bpn: str


class StepDeactivateCompany(StepCompanyRef):
    reason: str


class CompanyStateResult(BaseModel):
    companyId: str
    status: CompanyStatus
    bpn: str | None = None
    coreDataSource: CoreDataSource | None = None


class IdentifierResult(BaseModel):
    companyId: str
    status: CompanyStatus
    bpn: str


class ActivationResult(BaseModel):
    companyId: str
    status: CompanyStatus
    bpn: str
    companyRoles: list[str]
    pendingCompanyRoles: list[str]


class DeactivationResult(BaseModel):
    companyId: str
    status: CompanyStatus
    deactivationReason: DeactivationReason


class ReactivationResult(BaseModel):
    companyId: str
    status: CompanyStatus
    bpn: str
    companyRoles: list[str]
    changedFields: list[str]


class StepResult(BaseModel):
    stepRunId: str
    state: Literal["DONE", "RUNNING"]


class StepResultCompanyState(StepResult):
    result: CompanyStateResult


class StepResultIdentifier(StepResult):
    result: IdentifierResult


class StepResultActivation(StepResult):
    result: ActivationResult


class StepResultDeactivation(StepResult):
    result: DeactivationResult


class StepResultReactivation(StepResult):
    result: ReactivationResult


# ---------------------------------------------------------------- errors (README 12)
class FieldErrorAnswer(BaseModel):
    """One entry of `errors` (openapi `Problem.errors`): FastAPI's request validation and the module's own rules
    (`validation.py`) both answer this shape."""
    field: str
    message: str


class Problem(BaseModel):
    """Problem Details (RFC 9457) with the extra fields of README 12."""
    type: str
    title: str
    status: int
    detail: str | None = None
    retryable: bool | None = None
    reason: str | None = None
    fields: list[str] | None = None
    missing: list[str] | None = None
    errors: list[FieldErrorAnswer] | None = None
