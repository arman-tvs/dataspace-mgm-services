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
"""The fixed rules R1 to R17 of C11-M1 (README 6.1, 6.2).

`recipients` is `"applicant"`, `"staff:<permission>"` or a kind of `recipients.resolve`:
`"company_role:<field>:<portal role>"`, `"it_or_company_admin:<field>"`, `"app_customers:<field>"`,
`"subscription_customer:<field>"`. `closers` lists the events that close a task of the rule, with the
fields of `data` that must equal the task's `content` (README 6.2, "same object").
R14 has two entries (two events, two types) under one rule id, so `DISABLED_RULES=R14` switches off both.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    event: str
    ntype: str
    topic: str
    recipients: str
    subject_type: str | None = None
    subject_field: str | None = None
    company_field: str | None = None
    closers: tuple[tuple[str, tuple[str, ...]], ...] = ()


_APPLICATION_CLOSERS = tuple((e, ("applicationId",)) for e in
                             ("ApplicationApproved", "ApplicationDeclined", "ApplicationWithdrawn"))
_SUBSCRIPTION_CLOSERS = tuple((e, ("offerSubscriptionId",)) for e in
                              ("SubscriptionActivated", "SubscriptionDeclined", "SubscriptionDeactivated"))

RULES: list[Rule] = [
    Rule("R1", "ApplicationSubmitted", "APPLICATION_SUBMITTED", "INFO", "applicant",
         "APPLICATION", "applicationId", "companyId"),
    Rule("R2", "ApplicationSubmitted", "REVIEW_CASE_OPENED", "ACTION", "staff:review_application",
         "APPLICATION", "applicationId", "companyId", _APPLICATION_CLOSERS),
    Rule("R3", "ApplicationDeclined", "APPLICATION_DECLINED", "INFO", "applicant",
         "APPLICATION", "applicationId", "companyId"),
    Rule("R4", "ApplicationCompleted", "APPLICATION_COMPLETED", "INFO", "applicant",
         "APPLICATION", "applicationId", "companyId"),
    Rule("R5", "CompanyChangeRequestSubmitted", "CHANGE_REQUEST_OPENED", "ACTION", "staff:review_company_changes",
         "CHANGE_REQUEST", "changeRequestId", "companyId",
         (("CompanyChangeRequestClosed", ("changeRequestId",)),)),
    Rule("R6", "OfferSubmitted", "OFFER_REVIEW_REQUESTED", "ACTION", "staff:approve_offers",
         "OFFER", "offerId", "providerCompanyId",
         (("OfferApproved", ("offerId",)), ("OfferDeclined", ("offerId",)))),
    Rule("R7", "OfferApproved", "OFFER_APPROVED", "INFO", "company_role:providerCompanyId:Company Admin",
         "OFFER", "offerId", "providerCompanyId"),
    Rule("R8", "OfferDeclined", "OFFER_DECLINED", "INFO", "company_role:providerCompanyId:Company Admin",
         "OFFER", "offerId", "providerCompanyId"),
    Rule("R9", "SubscriptionRequested", "SUBSCRIPTION_REQUESTED", "ACTION",
         "company_role:providerCompanyId:Company Admin",
         "SUBSCRIPTION", "offerSubscriptionId", "providerCompanyId", _SUBSCRIPTION_CLOSERS),
    Rule("R10", "SubscriptionActivated", "SUBSCRIPTION_ACTIVATED", "INFO",
         "company_role:customerCompanyId:Company Admin",
         "SUBSCRIPTION", "offerSubscriptionId", "customerCompanyId"),
    Rule("R11", "SubscriptionDeclined", "SUBSCRIPTION_DECLINED", "INFO",
         "company_role:customerCompanyId:Company Admin",
         "SUBSCRIPTION", "offerSubscriptionId", "customerCompanyId"),
    Rule("R12", "SubscriptionInstanceUrlChanged", "SUBSCRIPTION_URL_CHANGED", "INFO",
         "subscription_customer:offerSubscriptionId", "SUBSCRIPTION", "offerSubscriptionId"),
    Rule("R13", "AppRolesAdded", "APP_ROLES_ADDED", "INFO", "app_customers:appId", "OFFER", "appId"),
    Rule("R14", "WalletAccountCreated", "TECHNICAL_USER_WALLET_READY", "INFO", "it_or_company_admin:companyId",
         "TECHNICAL_USER", "technicalUserId", "companyId"),
    Rule("R14", "WalletAccountFailed", "TECHNICAL_USER_WALLET_FAILED", "INFO", "it_or_company_admin:companyId",
         "TECHNICAL_USER", "technicalUserId", "companyId"),
    Rule("R15", "CredentialRevoked", "CREDENTIAL_REVOKED", "INFO", "company_role:companyId:Company Admin",
         "COMPANY", "companyId", "companyId"),
    Rule("R16", "ConnectorRegistered", "CONNECTOR_REGISTERED", "INFO", "it_or_company_admin:companyId",
         "CONNECTOR", "connectorId", "companyId"),
    Rule("R17", "ProcessStepFailed", "PROCESS_STEP_FAILED", "ACTION", "staff:retrigger_process_steps",
         "PROCESS", "processId", None,
         (("ProcessStepRetriggered", ("processId", "stepKey")), ("ProcessCompleted", ("processId",)),
          ("ProcessEnded", ("processId",)))),
]


def for_event(event_type: str) -> list[Rule]:
    """The rules that create a notification for this event type, in table order."""
    return [r for r in RULES if r.event == event_type]
