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
"""C11-M1 recipients (README 6.1, 11.2; acceptance 13.12): the four kinds, the built-in stand-in of
C2-M2, the IT Admin fallback and the retry rule for neighbour errors (README 4)."""
import os

import pytest
from conftest import needs_admin_api

from modules.c11_m1 import recipients, store
from modules.c11_m1 import router as c11
from portal_common import neighbours
from portal_common.problems import Problem

OSP_COMPANY = "11111111-1111-4111-8111-111111111111"   # FRAMEWORK 7a, provider company in README 14
COMPANY = "c0000001-0000-4000-8000-000000000001"       # FRAMEWORK 7a, Beispiel Maschinenbau GmbH
OTTO = "5a1c0012-0000-4000-8000-000000000012"           # README 14: Company Admin of the OSP company
ERIKA = "5a1c0001-0000-4000-8000-000000000001"          # README 14: Company Admin of Beispiel Maschinenbau
PIA = "5a1c0021-0000-4000-8000-000000000021"            # scaffold-only: Company Admin of the OSP company in the test IAM
APP = "44444444-4444-4444-8444-444444444444"
SUBSCRIPTION = "55555555-5555-4555-8555-555555555555"


@pytest.fixture(autouse=True)
def _fresh():
    """conftest does not reset module state."""
    c11.reset()
    yield
    c11.reset()


@pytest.fixture
def standin_c2_m2(monkeypatch):
    """Empty address of C2-M2: the built-in stand-in of README 11.2 with the data of README 14."""
    monkeypatch.setenv("C2_M2_URL", "")


class FakeNeighbours:
    """Replaces `neighbours.query`; answers per (target, function) and records every call."""

    def __init__(self, answers: dict):
        self.answers, self.calls = answers, []

    def __call__(self, caller, target, function, /, **params):
        self.calls.append((caller, target, function, params))
        answer = self.answers[(target, function)]
        if isinstance(answer, Exception):
            raise answer
        return answer(**params) if callable(answer) else answer


@pytest.fixture
def fake(monkeypatch):
    def install(answers: dict) -> FakeNeighbours:
        f = FakeNeighbours(answers)
        monkeypatch.setattr(neighbours, "query", f)
        return f
    return install


def refs(*subs: str) -> list[dict]:
    return [{"userId": s, "status": "ACTIVE"} for s in subs]


# ---- built-in stand-in of C2-M2 (README 11.2, 14)

def test_standin_company_admin_of_the_provider_is_otto(standin_c2_m2):
    assert recipients.resolve("company_role:providerCompanyId:Company Admin",
                              {"providerCompanyId": OSP_COMPANY}) == [OTTO]


def test_standin_without_it_admin_falls_back_to_company_admin(standin_c2_m2):
    assert recipients.resolve("it_or_company_admin:companyId", {"companyId": COMPANY}) == [ERIKA]   # 13.12


def test_standin_unknown_company_or_role_is_nobody(standin_c2_m2):
    assert recipients.resolve("company_role:companyId:Company Admin", {"companyId": "unknown"}) == []
    assert recipients.resolve("company_role:companyId:IT Admin", {"companyId": COMPANY}) == []


def test_standin_file_is_parsed_once_and_again_after_a_change(standin_c2_m2, monkeypatch, tmp_path):
    stub = tmp_path / "stub-company-users.json"
    stub.write_text('{"%s": {"Company Admin": ["a"]}}' % COMPANY, encoding="utf-8")
    monkeypatch.setattr(recipients, "STUB_COMPANY_USERS", stub)
    monkeypatch.setattr(recipients, "_stub_cache", None)
    loads = []
    real_loads = recipients.json.loads
    monkeypatch.setattr(recipients.json, "loads", lambda s: loads.append(1) or real_loads(s))
    kind, data = "company_role:companyId:Company Admin", {"companyId": COMPANY}
    assert recipients.resolve(kind, data) == ["a"] and recipients.resolve(kind, data) == ["a"]
    assert len(loads) == 1
    stub.write_text('{"%s": {"Company Admin": ["b"]}}' % COMPANY, encoding="utf-8")
    os.utime(stub, ns=(stub.stat().st_atime_ns, stub.stat().st_mtime_ns + 1_000_000))
    assert recipients.resolve(kind, data) == ["b"] and len(loads) == 2


def test_standin_c10_is_an_empty_list(monkeypatch, fake):
    monkeypatch.setenv("C10_M1_URL", "")
    f = fake({})
    assert recipients.resolve("app_customers:appId", {"appId": APP}) == []
    assert recipients.resolve("subscription_customer:offerSubscriptionId", {"offerSubscriptionId": SUBSCRIPTION}) == []
    assert f.calls == []


# ---- C2-M2 over the call convention (in-process here)

@needs_admin_api
def test_in_process_c2_m2_reads_the_bound_people():
    """The scaffold's C2-M2 stand-in answers from the test IAM, where Pia is the OSP company's Company Admin."""
    assert recipients.resolve("company_role:providerCompanyId:Company Admin",
                              {"providerCompanyId": OSP_COMPANY}) == [PIA]


def test_company_role_asks_c2_m2_with_company_and_role(fake):
    f = fake({("c2-m2", "list_company_user_refs"): refs("a", "b")})
    assert recipients.resolve("company_role:customerCompanyId:Company Admin", {"customerCompanyId": COMPANY}) == ["a", "b"]
    assert f.calls == [("c11-m1", "c2-m2", "list_company_user_refs",
                        {"companyId": COMPANY, "portalRole": "Company Admin"})]


def test_it_admin_is_preferred_when_the_company_has_one(fake):
    f = fake({("c2-m2", "list_company_user_refs"):
              lambda companyId, portalRole: refs("it") if portalRole == "IT Admin" else refs("admin")})
    assert recipients.resolve("it_or_company_admin:companyId", {"companyId": COMPANY}) == ["it"]
    assert [c[3]["portalRole"] for c in f.calls] == ["IT Admin"]


def test_not_found_or_missing_field_is_nobody(fake):
    f = fake({("c2-m2", "list_company_user_refs"): None})   # neighbours.query gives None for 404
    assert recipients.resolve("company_role:companyId:Company Admin", {"companyId": COMPANY}) == []
    assert recipients.resolve("company_role:companyId:Company Admin", {}) == []
    assert len(f.calls) == 1


def test_unreachable_neighbour_raises_unavailable(fake):
    fake({("c2-m2", "list_company_user_refs"): Problem("c11-m1", 502, "upstream-error", retryable=True)})
    with pytest.raises(store.Unavailable):
        recipients.resolve("company_role:companyId:Company Admin", {"companyId": COMPANY})


def test_rejecting_neighbour_raises_its_problem_without_retry(fake):
    fake({("c2-m2", "list_company_user_refs"): Problem("c11-m1", 502, "neighbour-rejected", retryable=False)})
    with pytest.raises(Problem) as e:
        recipients.resolve("company_role:companyId:Company Admin", {"companyId": COMPANY})
    assert not isinstance(e.value, store.Unavailable) and e.value.name == "neighbour-rejected"


# ---- C10-M1 kinds

def test_app_customers_are_the_company_admins_of_active_subscribers(fake):
    other = "c0000002-0000-4000-8000-000000000002"
    f = fake({("c10-m1", "find_subscriptions"): [
                  {"offerSubscriptionId": "s1", "offerId": APP, "customerCompanyId": COMPANY, "status": "ACTIVE"},
                  {"offerSubscriptionId": "s2", "offerId": APP, "customerCompanyId": other, "status": "ACTIVE"},
                  {"offerSubscriptionId": "s3", "offerId": APP, "customerCompanyId": COMPANY, "status": "ACTIVE"}],
              ("c2-m2", "list_company_user_refs"): lambda companyId, portalRole: refs(f"admin-of-{companyId}")})
    assert recipients.resolve("app_customers:appId", {"appId": APP}) == [f"admin-of-{COMPANY}", f"admin-of-{other}"]
    assert f.calls[0] == ("c11-m1", "c10-m1", "find_subscriptions", {"offerId": APP, "status": "ACTIVE"})
    assert len(f.calls) == 3   # each customer company asked once


def test_subscription_customer_is_the_company_admin_of_its_customer(fake):
    f = fake({("c10-m1", "get_subscription_internal"): {"offerSubscriptionId": SUBSCRIPTION, "customerCompanyId": COMPANY},
              ("c2-m2", "list_company_user_refs"): refs(ERIKA)})
    assert recipients.resolve("subscription_customer:offerSubscriptionId",
                              {"offerSubscriptionId": SUBSCRIPTION}) == [ERIKA]
    assert f.calls[0][2:] == ("get_subscription_internal", {"offerSubscriptionId": SUBSCRIPTION})


def test_unknown_subscription_is_nobody(fake):
    fake({("c10-m1", "get_subscription_internal"): None})
    assert recipients.resolve("subscription_customer:offerSubscriptionId", {"offerSubscriptionId": "x"}) == []


def test_unknown_kind_is_a_programming_error():
    with pytest.raises(ValueError):
        recipients.resolve("everyone", {})
