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
#  Assisted-By: Claude Code (claude-sonnet-5-5)
#################################################################################
"""C4-M2 `create-wallet` (README 8.1, 6.1, 6.2, 6.9, 12, 13 cases 1 to 4 and 10).

Red against the stand-in (it goes ACTIVE at once, has no attempts, no store, no providers seam). Seams of
TEAM3-PLAN.md section 12 are imported lazily inside the tests.
"""
from __future__ import annotations

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("modules.c4_m2.providers") is None,
    reason="not implemented yet: modules.c4_m2.providers (provider adapters)")

import threading
import uuid

import pytest
import yaml

from portal_common import http as phttp
from portal_common import problems, spec
from portal_common.problems import Problem
from test_c4_m2_common import (COMPANIES, Clock, companies, event_errors, osp_factory, response_errors,  # noqa: F401
                               schema_errors, seam, step_input, uuid_str)

MODULE = "c4-m2"
DIV = COMPANIES["div"]
IH = COMPANIES["ih"]
CSPC = COMPANIES["csp"]
FAIL01 = COMPANIES["fail_did"]
DIV_DID = "did:web:div.example.org:did:BPNL0000000DIV01"
IH_DID = "did:web:ih.example.org:BPNL00000000IH01"
CSP_DID = "did:web:csp-wallet.example.org:BPNLIUK2REMLK3F4"
# SAP DIV callbacks only on request of the test (flush_stand_in), never by a timer or at once.
HOLD_CALLBACK = {"STUB_CALLBACK_DELAY_SECONDS": "3600"}


# ------------------------------------------------------------------------------------------ helpers
def m2():
    return seam("modules.c4_m2.interface")


def providers():
    return seam("modules.c4_m2.providers")


def service():
    return seam("modules.c4_m2.service")


class HttpSpy:
    """Records every `portal_common.http.request` (method, url, kwargs) and passes it on."""

    def __init__(self, monkeypatch) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        real = phttp.request

        def request(method, url, timeout=phttp.DEFAULT_TIMEOUT, **kw):
            self.calls.append((method.upper(), url, kw))
            return real(method, url, timeout=timeout, **kw)

        monkeypatch.setattr(phttp, "request", request)

    def urls(self) -> list[str]:
        return [u for _, u, _ in self.calls]


def create(company: dict, n: int = 1, **extra) -> dict:
    return m2().create_wallet(step_input(company["id"], n, **extra))


def row(company: dict) -> dict | None:
    return m2().store().get_wallet(company["id"])


def step_problem(company_id, n: int = 1, **extra) -> problems.Problem:
    """The Problem that the HTTP layer would answer with (also carries `retryable`)."""
    with pytest.raises(Exception) as e:
        m2().create_wallet(step_input(company_id, n, **extra))
    return problems.to_problem(MODULE, e.value, True)


def events_of(osp, type_: str, company: dict | None = None) -> list[dict]:
    return [e for e in osp.events(type_) if company is None or e["data"].get("companyId") == company["id"]]


def assert_problem(p: Problem, status: int, name: str, retryable: bool = False) -> None:
    assert p.status == status and p.name == name, (p.status, p.name, p.detail)
    assert p.ext.get("retryable") is retryable


def assert_step_result(out: dict, company: dict, n: int, state: str, provider: str) -> dict:
    # README 8.1 Result, openapi StepResultWallet: the same shape for RUNNING and DONE
    assert out["stepRunId"] == uuid_str(n)
    assert out["state"] == state
    assert schema_errors(MODULE, "StepResultWallet", out) == []
    res = out["result"]
    assert res["companyId"] == company["id"] and res["provider"] == provider
    uuid.UUID(res["walletId"])
    assert res["status"] in ("REQUESTED", "VALIDATING", "ACTIVE", "FAILED")
    return res


# ----------------------------------------------------------------------------- case 1: SAP DIV, callback
def test_case_01_sap_div_running_then_active_after_callback(osp_factory, companies):
    # README 13 case 1, 8.1, 6.2
    osp = osp_factory(env=HOLD_CALLBACK)
    out = create(DIV, 1, provider="SAP_DIV")
    res = assert_step_result(out, DIV, 1, "RUNNING", "SAP_DIV")
    assert res["status"] == "REQUESTED"            # SAP DIV: REQUESTED until the callback (6.2)
    w = row(DIV)
    assert w["status"] == "REQUESTED" and w["provider"] == "SAP_DIV" and w["attempt"] == 1
    assert w["provider_ordered_at"] and w["provider_ref"] == DIV["bpn"]      # README 8.1 step 4
    assert res["walletId"] == w["id"]
    assert providers().orders() == [{"provider": "SAP_DIV", "bpn": DIV["bpn"], "kind": "wallet"}]
    assert events_of(osp, "DataspaceWalletCreated") == []                    # not yet

    providers().flush_stand_in()                   # the stand-in calls the callback code itself (11.1)
    assert row(DIV)["status"] in ("VALIDATING", "ACTIVE")      # README 7.6 step 6: the check runs in the background
    service().run_timer_once()                     # project convention: finishes any pending DID check
    w = row(DIV)
    assert w["status"] == "ACTIVE" and w["did"] == DIV_DID and w["activated_at"] and w["did_validated_at"]
    created = events_of(osp, "DataspaceWalletCreated")
    assert len(created) == 1                       # exactly one event
    assert event_errors(MODULE, created[0]) == []  # all required fields, nothing else (README 10)
    assert created[0]["source"] == "urn:c4-m2"
    assert created[0]["data"] == {"companyId": DIV["id"], "did": DIV_DID, "walletId": w["id"],
                                  "provider": "SAP_DIV", "bpn": DIV["bpn"],
                                  "didDocumentLocation": "https://div.example.org/did/BPNL0000000DIV01/did.json"}
    assert w["did_document_location"] == created[0]["data"]["didDocumentLocation"]
    assert events_of(osp, "DataspaceWalletFailed") == []
    assert providers().orders() == [{"provider": "SAP_DIV", "bpn": DIV["bpn"], "kind": "wallet"}]


def test_case_01_event_did_is_the_did_of_get_wallet_info(osp_factory, companies):
    # README 9.1 + 10; C12 passes `steps.create-wallet.did` from the event on to register-did
    osp = osp_factory(env=HOLD_CALLBACK)
    create(DIV, 1, provider="SAP_DIV")
    providers().flush_stand_in()
    service().run_timer_once()
    info = m2().get_wallet_info(companyId=DIV["id"])
    ev = events_of(osp, "DataspaceWalletCreated")[0]
    assert ev["data"]["did"] == info["did"] == DIV_DID
    assert ev["data"]["walletId"] == info["walletId"]
    assert info["status"] == "ACTIVE" and info["provider"] == "SAP_DIV" and info["bpn"] == DIV["bpn"]
    assert schema_errors(MODULE, "WalletInfo", info) == []


def test_c12_flow_facts_create_wallet_completes_on_the_events():
    # flows.yaml (C12-M1): create-wallet completesOn DataspaceWalletCreated, failsOn DataspaceWalletFailed,
    # register-did reads the DID from the step (= the event payload)
    doc = yaml.safe_load(spec.flows_file().read_text())

    def steps(node):
        if isinstance(node, dict):
            if node.get("key") == "create-wallet":
                yield node
            for v in node.values():
                yield from steps(v)
        elif isinstance(node, list):
            for v in node:
                yield from steps(v)

    found = list(steps(doc))
    assert found
    for s in found:
        assert s["call"] == "c4-m2.create-wallet"
        assert s["completesOn"] == ["DataspaceWalletCreated"] and s["failsOn"] == ["DataspaceWalletFailed"]
    text = spec.flows_file().read_text()
    assert "did: steps.create-wallet.did" in text


# -------------------------------------------------------------------------------- case 2: repetition
def test_case_02_repeat_after_active_is_done_without_order_or_event(osp_factory, companies):
    # README 13 case 2, 8.1 step 2, 6.9
    osp = osp_factory(env=HOLD_CALLBACK)
    create(DIV, 1, provider="SAP_DIV")
    providers().flush_stand_in()
    service().run_timer_once()
    before = row(DIV)
    assert before["status"] == "ACTIVE"
    out = create(DIV, 2, provider="SAP_DIV")
    res = assert_step_result(out, DIV, 2, "DONE", "SAP_DIV")
    assert res["status"] == "ACTIVE" and res["did"] == DIV_DID
    assert res["didDocumentLocation"] == before["did_document_location"]
    assert len(providers().orders()) == 1                       # no second order
    assert len(events_of(osp, "DataspaceWalletCreated")) == 1   # no further event
    assert row(DIV)["attempt"] == 1 and row(DIV)["id"] == before["id"]


# --------------------------------------------------------------------------------- case 3: REQUESTED
def test_case_03_repeat_while_requested_is_running_without_second_order(osp_factory, companies):
    # README 13 case 3
    osp = osp_factory(env=HOLD_CALLBACK)
    create(DIV, 1, provider="SAP_DIV")
    out = create(DIV, 2, provider="SAP_DIV")
    res = assert_step_result(out, DIV, 2, "RUNNING", "SAP_DIV")
    assert res["status"] == "REQUESTED"
    assert len(providers().orders()) == 1
    assert row(DIV)["status"] == "REQUESTED" and row(DIV)["attempt"] == 1
    assert osp.events("DataspaceWalletCreated") == []


def test_case_03_requested_without_provider_ordered_at_orders_again(osp_factory, companies):
    # README 8.1 step 2: REQUESTED without provider_ordered_at -> continue with step 4 (send the order again)
    osp_factory(env=HOLD_CALLBACK)
    create(DIV, 1, provider="SAP_DIV")
    store = m2().store()
    w = row(DIV)
    w["provider_ordered_at"] = None
    store.put_wallet(w)
    out = create(DIV, 2, provider="SAP_DIV")
    assert_step_result(out, DIV, 2, "RUNNING", "SAP_DIV")
    assert len(providers().orders()) == 2
    w = row(DIV)
    assert w["provider_ordered_at"] and w["status"] == "REQUESTED" and w["attempt"] == 1


def test_validating_wallet_repeat_is_running_without_order(osp_factory, companies):
    # README 8.1 step 2: VALIDATING -> RUNNING, nothing else
    osp = osp_factory(env=HOLD_CALLBACK)
    create(DIV, 1, provider="SAP_DIV")
    w = row(DIV)
    w["status"] = "VALIDATING"
    m2().store().put_wallet(w)
    out = create(DIV, 2, provider="SAP_DIV")
    res = assert_step_result(out, DIV, 2, "RUNNING", "SAP_DIV")
    assert res["status"] == "VALIDATING"
    assert len(providers().orders()) == 1 and row(DIV)["status"] == "VALIDATING"
    assert osp.events("DataspaceWalletCreated") == []


# ------------------------------------------------------------------------------ case 4: wrong DID
def test_case_04_wrong_did_fails_then_new_attempt_is_active(osp_factory, companies, monkeypatch):
    # README 13 case 4, 6.2 (FAILED -> new attempt), 14.3 DID_MISMATCH
    osp = osp_factory(env={**HOLD_CALLBACK, "STUB_FAILURES": f"{FAIL01['bpn']}:DID_MISMATCH"})
    out = create(FAIL01, 1, provider="SAP_DIV")
    assert_step_result(out, FAIL01, 1, "RUNNING", "SAP_DIV")
    providers().flush_stand_in()
    service().run_timer_once()                     # the wrong form is decided at once; the pass changes nothing
    w = row(FAIL01)
    assert w["status"] == "FAILED" and w["failure_reason"] == "DID_MISMATCH" and w["attempt"] == 1
    failed = events_of(osp, "DataspaceWalletFailed")
    assert len(failed) == 1 and event_errors(MODULE, failed[0]) == []
    assert failed[0]["data"] == {"companyId": FAIL01["id"], "walletId": w["id"], "provider": "SAP_DIV",
                                 "reason": "DID_MISMATCH"}
    assert osp.events("DataspaceWalletCreated") == []
    info = m2().get_wallet_info(companyId=FAIL01["id"])
    assert info["status"] == "FAILED" and info["failureReason"] == "DID_MISMATCH"

    # an access of the failed attempt is deleted by the new attempt (README 6.2)
    m2().store().put_secret(w["id"], "HOLDER_ACCESS", "https://x.example/token", "cid", b"cipher", b"n" * 12, 1)
    monkeypatch.setenv("STUB_FAILURES", "")        # "failure in the stand-in reset for the test"
    out = create(FAIL01, 2, provider="SAP_DIV")
    res = assert_step_result(out, FAIL01, 2, "RUNNING", "SAP_DIV")
    assert res["status"] == "REQUESTED"
    w2 = row(FAIL01)
    assert w2["attempt"] == 2 and w2["id"] == w["id"] and w2["status"] == "REQUESTED"
    assert w2["did"] is None and w2["failure_reason"] is None                 # cleared (6.2)
    assert m2().store().get_secret(w["id"], "HOLDER_ACCESS") is None          # secrets deleted
    assert len(providers().orders()) == 2
    providers().flush_stand_in()
    service().run_timer_once()
    w3 = row(FAIL01)
    assert w3["status"] == "ACTIVE" and w3["attempt"] == 2
    assert w3["did"] == "did:web:div.example.org:did:BPNL000000FAIL01"
    created = events_of(osp, "DataspaceWalletCreated")
    assert len(created) == 1 and created[0]["data"]["did"] == w3["did"]
    assert len(events_of(osp, "DataspaceWalletFailed")) == 1


def test_failed_wallet_new_attempt_may_change_the_provider(osp_factory, companies, monkeypatch):
    # README 6.2: a new attempt "can change the provider"
    osp = osp_factory(env={**HOLD_CALLBACK, "STUB_FAILURES": f"{FAIL01['bpn']}:DID_MISMATCH"})
    create(FAIL01, 1, provider="SAP_DIV")
    providers().flush_stand_in()
    assert row(FAIL01)["status"] == "FAILED"
    out = create(FAIL01, 2, provider="CSP")
    res = assert_step_result(out, FAIL01, 2, "RUNNING", "CSP")
    w = row(FAIL01)
    assert w["provider"] == "CSP" and w["attempt"] == 2 and w["status"] == "ACTIVE"
    assert res["status"] == "ACTIVE" and w["did"] == "did:web:csp-wallet.example.org:BPNL000000FAIL01"
    assert len(events_of(osp, "DataspaceWalletCreated", FAIL01)) == 1


# ------------------------------------------------- status machine: IdentityHub and CSP within the call
@pytest.mark.parametrize("company,provider,did,mode", [
    (IH, "IDENTITY_HUB", IH_DID, "HOLDER_REQUESTS"),
    (CSPC, "CSP", CSP_DID, "HOLDER_REQUESTS"),
])
def test_identity_hub_and_csp_validate_within_the_call_but_step_answers_running(osp_factory, companies,
                                                                                company, provider, did, mode):
    # README 6.2 (VALIDATING, then ACTIVE), 6.9 (RUNNING even if complete in the same call), 8.1 steps 5 and 6
    osp = osp_factory()
    out = create(company, 1, provider=provider)
    res = assert_step_result(out, company, 1, "RUNNING", provider)
    w = row(company)
    assert w["status"] == "ACTIVE" and w["did"] == did and w["attempt"] == 1
    assert res["status"] == "ACTIVE" and res["did"] == did            # the reply reflects the row
    assert w["provider_ordered_at"] and w["validating_since"] and w["did_validated_at"] and w["activated_at"]
    assert w["credential_service_url"]
    ev = events_of(osp, "DataspaceWalletCreated")
    assert len(ev) == 1 and event_errors(MODULE, ev[0]) == []
    assert ev[0]["data"]["did"] == did and ev[0]["data"]["provider"] == provider
    assert ev[0]["data"]["didDocumentLocation"] == w["did_document_location"]
    assert m2().get_wallet_info(companyId=company["id"])["issuanceMode"] == mode
    # repetition: DONE, no event, no second order
    out2 = create(company, 2, provider=provider)
    res2 = assert_step_result(out2, company, 2, "DONE", provider)
    assert res2["status"] == "ACTIVE" and res2["did"] == did
    assert len(events_of(osp, "DataspaceWalletCreated")) == 1
    assert len(providers().orders()) == 1


def test_wallet_row_has_the_columns_of_the_spec_table(osp_factory, companies):
    # README 5 table dataspace_wallet (TEAM3-PLAN 12.2 wallet dict keys)
    osp_factory()
    create(IH, 1, provider="IDENTITY_HUB")
    w = row(IH)
    keys = {"id", "company_id", "bpn", "provider", "status", "failure_reason", "did", "did_document_location",
            "credential_service_url", "provider_ref", "control_challenge_id", "attempt", "provider_ordered_at",
            "validating_since", "did_validated_at", "next_check_at", "activated_at", "created_at", "changed_at"}
    assert keys <= set(w)
    assert w["company_id"] == IH["id"] and w["bpn"] == IH["bpn"] and w["provider_ref"] == IH["bpn"]
    assert w["did_document_location"] == "https://ih.example.org/BPNL00000000IH01/did.json"
    assert m2().store().find_wallet_by_bpn(IH["bpn"])["id"] == w["id"]
    assert m2().store().find_wallet_by_did(IH_DID)["id"] == w["id"]


def test_step_log_entry_is_written(osp_factory, companies):
    # README 5 step_log: step_run_id, process_id, step, object ID, state answered, time
    osp_factory()
    create(IH, 7, provider="IDENTITY_HUB")
    entries = [e for e in m2().store().list_step_log() if e["step_run_id"] == uuid_str(7)]
    assert len(entries) == 1
    e = entries[0]
    assert e["process_id"] == uuid_str(900) and e["step"] == "create-wallet" and e["state"] == "RUNNING"
    assert e["object_id"] in (IH["id"], row(IH)["id"]) and e["occurred_at"]


# ------------------------------------------------------------------------------- case 10: parallel
def test_case_10_div_csp_and_ih_wallets_in_one_installation(osp_factory, companies):
    # README 13 case 10 (cases 1, 8, 9 together), 9.1, 6.11 table
    osp = osp_factory(env=HOLD_CALLBACK)
    create(DIV, 1, provider="SAP_DIV")
    create(CSPC, 2, provider="CSP")
    create(IH, 3, provider="IDENTITY_HUB")
    providers().flush_stand_in()
    service().run_timer_once()
    expected = [(DIV, "SAP_DIV", "ISSUER_WRITES", DIV_DID), (CSPC, "CSP", "HOLDER_REQUESTS", CSP_DID),
                (IH, "IDENTITY_HUB", "HOLDER_REQUESTS", IH_DID)]
    walletids = set()
    for company, provider, mode, did in expected:
        info = m2().get_wallet_info(companyId=company["id"])
        assert schema_errors(MODULE, "WalletInfo", info) == []
        assert (info["provider"], info["issuanceMode"], info["did"], info["status"]) == (provider, mode, did, "ACTIVE")
        assert info["companyId"] == company["id"] and info["bpn"] == company["bpn"]
        assert info["supportsWalletAccounts"] is True
        walletids.add(info["walletId"])
    assert len(walletids) == 3
    created = osp.events("DataspaceWalletCreated")
    assert sorted(e["data"]["companyId"] for e in created) == sorted(c["id"] for c, *_ in expected)
    assert all(event_errors(MODULE, e) == [] for e in created)
    token = osp.service("sa-modules", ["query_c4_m2", "execute_steps_c4_m2", "read_wallet_holder_access"])
    for company, provider, mode, did in expected:
        r = osp.get(f"/api/c4-m2/internal/wallets/{company['id']}", token)
        assert r.status_code == 200, r.text
        assert (r.json()["provider"], r.json()["issuanceMode"], r.json()["did"]) == (provider, mode, did)
        assert response_errors(MODULE, "GET", "/internal/wallets/{companyId}", 200, r.json()) == []


# ---------------------------------------------------------------------------------- provider selection
@pytest.mark.parametrize("default,given,expected", [
    ("", None, "CSP"),                        # README 4: empty DEFAULT_PROVIDER = CSP
    ("IDENTITY_HUB", None, "IDENTITY_HUB"),   # README 6.1 item 4
    ("SAP_DIV", "CSP", "CSP"),                # README 6.1 item 3: input wins
    ("CSP", "SAP_DIV", "SAP_DIV"),
    ("CSP", "IDENTITY_HUB", "IDENTITY_HUB"),
])
def test_provider_selection_input_then_default_provider(osp_factory, companies, default, given, expected):
    osp_factory(env={**HOLD_CALLBACK, "DEFAULT_PROVIDER": default})
    extra = {"provider": given} if given else {}
    out = create(DIV, 1, **extra)
    assert out["result"]["provider"] == expected
    assert row(DIV)["provider"] == expected
    assert schema_errors(MODULE, "StepResultWallet", out) == []


def test_provider_selection_default_provider_unset_means_csp(osp_factory, companies, monkeypatch):
    # README 4: `DEFAULT_PROVIDER` empty = CSP (not set at all behaves the same)
    monkeypatch.delenv("DEFAULT_PROVIDER", raising=False)
    osp_factory()
    assert create(CSPC, 1)["result"]["provider"] == "CSP"


@pytest.mark.parametrize("enabled,default,given", [
    ("SAP_DIV", "", "CSP"),
    ("SAP_DIV,IDENTITY_HUB", "", "CSP"),
    ("CSP", "", "SAP_DIV"),
    ("SAP_DIV,IDENTITY_HUB", "CSP", None),                 # DEFAULT_PROVIDER itself not enabled
    ("SAP_DIV", "", None),                                 # empty default = CSP, not enabled
])
def test_provider_not_in_enabled_providers_is_400(osp_factory, companies, enabled, default, given):
    # README 6.1, 12: 400 provider-not-enabled, retryable false (a real provider missing from ENABLED_PROVIDERS)
    osp_factory(env={"ENABLED_PROVIDERS": enabled, "DEFAULT_PROVIDER": default})
    extra = {"provider": given} if given else {}
    assert_problem(step_problem(DIV["id"], 1, **extra), 400, "provider-not-enabled")
    assert row(DIV) is None


@pytest.mark.parametrize("enabled", ["SAP_DIV,CSP", "SAP_DIV,IDENTITY_HUB,CSP", "SAP_DIV,IDENTITY_HUB,CSP,BRING_YOUR_OWN"])
def test_provider_bring_your_own_as_input_is_400(osp_factory, companies, enabled):
    # README 6.1: BRING_YOUR_OWN is not active in version 0.2 (items 1 and 2 do not apply), 400.
    # OPEN-QUESTION: README 6.1 gives `provider-not-enabled`, but openapi `StepCreateWallet.provider` has the enum
    # [SAP_DIV, IDENTITY_HUB, CSP] only, so a schema check would answer 400 `validation`. Both are accepted.
    osp_factory(env={"ENABLED_PROVIDERS": enabled})
    p = step_problem(DIV["id"], 1, provider="BRING_YOUR_OWN")
    assert p.status == 400 and p.name in ("validation", "provider-not-enabled"), (p.status, p.name)
    assert p.ext.get("retryable") is False
    assert row(DIV) is None


def test_empty_enabled_providers_means_all_three_and_empty_default_means_csp(osp_factory, companies):
    # README 4: `ENABLED_PROVIDERS` empty = SAP_DIV,IDENTITY_HUB,CSP; `DEFAULT_PROVIDER` empty = CSP (14.2 providers seam)
    osp = osp_factory(env={**HOLD_CALLBACK, "ENABLED_PROVIDERS": "", "DEFAULT_PROVIDER": ""})
    assert sorted(providers().enabled()) == ["CSP", "IDENTITY_HUB", "SAP_DIV"]
    assert providers().default_provider() == "CSP"
    assert create(DIV, 1, provider="SAP_DIV")["result"]["provider"] == "SAP_DIV"
    assert create(IH, 2, provider="IDENTITY_HUB")["result"]["provider"] == "IDENTITY_HUB"
    assert create(CSPC, 3, provider="CSP")["result"]["provider"] == "CSP"
    assert create(FAIL01, 4)["result"]["provider"] == "CSP"                  # no input, empty default = CSP
    assert osp.events("DataspaceWalletFailed") == []


# ------------------------------------------------------------------------------------ preconditions
@pytest.mark.parametrize("bad", [
    {"processId": uuid_str(900), "stepRunId": uuid_str(1)},                                   # no companyId
    {"stepRunId": uuid_str(1), "companyId": DIV["id"]},                                        # no processId (required)
    {"processId": uuid_str(900), "companyId": DIV["id"]},                                      # no stepRunId (required)
    {"processId": uuid_str(900), "stepRunId": uuid_str(1), "companyId": "not-a-uuid"},
    {"processId": uuid_str(900), "stepRunId": uuid_str(1), "companyId": None},
    {"processId": uuid_str(900), "stepRunId": uuid_str(1), "companyId": DIV["id"], "provider": "OTHER"},
    {"processId": uuid_str(900), "stepRunId": uuid_str(1), "companyId": DIV["id"], "provider": "STUB"},
])
def test_invalid_input_is_400_validation(osp_factory, companies, bad):
    # README 8.1 step 1, 12. OPEN-QUESTION: a provider name outside the enum (STUB) is `validation`,
    # while a valid enum value that is not enabled is `provider-not-enabled`.
    osp_factory()
    with pytest.raises(Exception) as e:
        m2().create_wallet(bad)
    assert_problem(problems.to_problem(MODULE, e.value, True), 400, "validation")
    assert m2().store().get_wallet(DIV["id"]) is None


def test_unknown_company_is_404_not_found(osp_factory, companies):
    # README 8.1 step 1: neighbour answers None (404) -> 404 not-found
    osp_factory()
    unknown = "99999999-0000-4000-8000-000000000999"
    assert_problem(step_problem(unknown, 1, provider="CSP"), 404, "not-found")
    assert m2().store().get_wallet(unknown) is None


def test_company_without_bpn_is_409_company_not_ready(osp_factory, companies):
    # README 8.1 step 1, 12
    osp_factory()
    nb = COMPANIES["no_bpn"]
    assert_problem(step_problem(nb["id"], 1, provider="CSP"), 409, "company-not-ready")
    assert m2().store().get_wallet(nb["id"]) is None


def test_wallet_with_another_bpn_is_409_conflict(osp_factory, companies):
    # README 8.1 step 1: wallet for companyId with another BPN
    osp_factory()
    create(IH, 1, provider="IDENTITY_HUB")
    companies.set_bpn(IH["id"], "BPNL0000000OTHER")
    assert_problem(step_problem(IH["id"], 2, provider="IDENTITY_HUB"), 409, "conflict")
    assert row(IH)["bpn"] == IH["bpn"]
    assert len(providers().orders()) == 1


def test_bpn_of_another_company_is_409_conflict(osp_factory, companies):
    # README 8.1 step 1: wallet of another company with this BPN
    osp_factory()
    create(IH, 1, provider="IDENTITY_HUB")
    companies.set_bpn(DIV["id"], IH["bpn"])
    assert_problem(step_problem(DIV["id"], 2, provider="IDENTITY_HUB"), 409, "conflict")
    assert row(DIV) is None
    assert len(providers().orders()) == 1


def test_conflict_is_checked_before_done_for_an_active_wallet(osp_factory, companies):
    # README 8.1: step 1 (conflict) comes before step 2 (ACTIVE -> DONE)
    osp_factory()
    create(CSPC, 1, provider="CSP")
    assert row(CSPC)["status"] == "ACTIVE"
    companies.set_bpn(CSPC["id"], "BPNLIUK2REMLK3F5")
    assert_problem(step_problem(CSPC["id"], 2, provider="CSP"), 409, "conflict")


# --------------------------------------------------------------------------------------- over HTTP
def test_create_wallet_over_http_with_service_token(osp_factory, companies):
    # openapi POST /steps/create-wallet, x-permission execute_steps_c4_m2; README 8.1
    osp = osp_factory()
    token = osp.service("svc-c4-m2")
    body = step_input(IH["id"], 1, provider="IDENTITY_HUB")
    r = osp.post("/api/c4-m2/steps/create-wallet", token, json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["stepRunId"] == body["stepRunId"] and out["state"] == "RUNNING"
    assert response_errors(MODULE, "POST", "/steps/create-wallet", 200, out) == []
    assert out["result"]["provider"] == "IDENTITY_HUB" and out["result"]["companyId"] == IH["id"]
    assert row(IH)["status"] == "ACTIVE" and len(events_of(osp, "DataspaceWalletCreated")) == 1
    r2 = osp.post("/api/c4-m2/steps/create-wallet", token, json=step_input(IH["id"], 2, provider="IDENTITY_HUB"))
    assert r2.status_code == 200 and r2.json()["state"] == "DONE"
    assert r2.json()["result"]["did"] == IH_DID
    assert len(events_of(osp, "DataspaceWalletCreated")) == 1


@pytest.mark.parametrize("company_id,extra,status,name", [
    ("99999999-0000-4000-8000-000000000999", {}, 404, "not-found"),
    (COMPANIES["no_bpn"]["id"], {}, 409, "company-not-ready"),
    # OPEN-QUESTION: README 6.1 says provider-not-enabled, openapi enum of `provider` would give validation
    (DIV["id"], {"provider": "BRING_YOUR_OWN"}, 400, ("validation", "provider-not-enabled")),
    (DIV["id"], {"provider": "SAP_DIV"}, 400, "provider-not-enabled"),                         # with ENABLED_PROVIDERS=CSP
    ("not-a-uuid", {}, 400, "validation"),
])
def test_create_wallet_errors_over_http_are_problem_details(osp_factory, companies, company_id, extra, status, name):
    # README 12: type urn:c4-m2:problem:<name>, retryable false on steps (FRAMEWORK 4.5)
    osp = osp_factory(env={"ENABLED_PROVIDERS": "CSP"} if extra.get("provider") == "SAP_DIV" else None)
    r = osp.post("/api/c4-m2/steps/create-wallet", osp.service("svc-c4-m2"),
                 json=step_input(company_id, 1, **extra))
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    names = name if isinstance(name, tuple) else (name,)
    assert body["type"] in [f"urn:c4-m2:problem:{n}" for n in names] and body["status"] == status
    assert body["retryable"] is False


def test_create_wallet_over_http_needs_a_token_and_the_step_permission(osp_factory, companies):
    # README 6.8: `execute_steps_c4_m2`
    osp = osp_factory()
    body = step_input(IH["id"], 1, provider="IDENTITY_HUB")
    assert osp.post("/api/c4-m2/steps/create-wallet", json=body).status_code == 401
    no_perm = osp.service("sa-no-steps", ["query_c4_m2"])
    r = osp.post("/api/c4-m2/steps/create-wallet", no_perm, json=body)
    assert r.status_code == 403 and r.json()["type"] == "urn:c4-m2:problem:forbidden"
    assert m2().store().get_wallet(IH["id"]) is None


# ------------------------------------------------------------------ README 8.1 step 2: ACTIVE is final
def test_repeat_after_active_with_a_different_provider_is_done_with_the_existing_provider(osp_factory, companies):
    # README 8.1 step 2: ACTIVE -> DONE with the result, no event; the new `provider` input is not looked at
    osp = osp_factory()
    create(IH, 1, provider="IDENTITY_HUB")
    assert row(IH)["status"] == "ACTIVE"
    out = create(IH, 2, provider="CSP")
    res = assert_step_result(out, IH, 2, "DONE", "IDENTITY_HUB")
    assert res["status"] == "ACTIVE" and res["did"] == IH_DID
    assert row(IH)["provider"] == "IDENTITY_HUB" and row(IH)["attempt"] == 1
    assert len(providers().orders()) == 1
    assert len(events_of(osp, "DataspaceWalletCreated")) == 1


# ------------------------------------------------------------------------------ README 6.9 concurrency
def test_two_concurrent_create_wallet_calls_make_one_order_and_one_event(osp_factory, companies):
    # README 6.9: steps for the same company never run at the same time (advisory lock on company_id)
    osp = osp_factory()
    barrier = threading.Barrier(2)
    outs: list = []
    errors: list = []

    def work(n: int) -> None:
        try:
            barrier.wait(timeout=5)
            outs.append(create(IH, n, provider="IDENTITY_HUB"))
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=work, args=(n,)) for n in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert not errors and len(outs) == 2
    # one call found no wallet (RUNNING even though complete in the call, 6.9); the other saw it complete or running
    assert sorted(o["state"] for o in outs) in (["DONE", "RUNNING"], ["RUNNING", "RUNNING"])
    assert any(o["state"] == "RUNNING" for o in outs)
    assert len(providers().orders()) == 1
    assert len(events_of(osp, "DataspaceWalletCreated")) == 1
    assert row(IH)["status"] == "ACTIVE" and row(IH)["attempt"] == 1


# --------------------------------------------------------------------------- README 6.10 scheduled tasks
def test_requested_wallet_without_provider_ordered_at_is_not_timed_out(osp_factory, companies, monkeypatch):
    # README 6.10: the callback deadline selects REQUESTED with `provider_ordered_at` older than the deadline;
    # after provider-rejected (409) or a 502 the order was never accepted, so there is nothing to time out
    bpn = COMPANIES["csp_rejected"]["bpn"]
    osp = osp_factory(env={"STUB_FAILURES": f"{bpn}:CSP_REJECTED", "PROVIDER_CALLBACK_TIMEOUT_MINUTES": "1"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    rejected = COMPANIES["csp_rejected"]
    assert_problem(step_problem(rejected["id"], 1, provider="CSP"), 409, "provider-rejected")
    unreachable = COMPANIES["byo"]                       # any company with a BPN: its order fails technically (502)
    monkeypatch.setenv("STUB_FAILURES", f"{bpn}:CSP_REJECTED,{unreachable['bpn']}:ORDER_ERROR")
    assert_problem(step_problem(unreachable["id"], 2, provider="IDENTITY_HUB"), 502, "upstream-error", True)
    for c in (rejected, unreachable):
        w = row(c)
        assert w["status"] == "REQUESTED" and w["provider_ordered_at"] is None
    clock.advance(days=3)                                # far past PROVIDER_CALLBACK_TIMEOUT_MINUTES
    service().run_timer_once()
    for c in (rejected, unreachable):
        w = row(c)
        assert w["status"] == "REQUESTED" and w["failure_reason"] is None and w["attempt"] == 1
    assert osp.events("DataspaceWalletFailed") == [] and osp.events("DataspaceWalletCreated") == []


def test_failed_wallet_is_never_retried_by_the_timer(osp_factory, companies, monkeypatch):
    # README 6.2: FAILED leaves only through a new create-wallet; 6.10: the tasks select REQUESTED / VALIDATING
    osp = osp_factory(env={**HOLD_CALLBACK, "STUB_FAILURES": f"{FAIL01['bpn']}:DID_MISMATCH"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    create(FAIL01, 1, provider="SAP_DIV")
    providers().flush_stand_in()
    service().run_timer_once()
    assert row(FAIL01)["status"] == "FAILED"
    orders, events = len(providers().orders()), len(osp.events())
    for _ in range(3):
        clock.advance(days=2)
        service().run_timer_once()
    w = row(FAIL01)
    assert w["status"] == "FAILED" and w["attempt"] == 1 and w["failure_reason"] == "DID_MISMATCH"
    assert len(providers().orders()) == orders and len(osp.events()) == events


# --------------------------------------------------------------- case 1 / 6.5: no directory BPN -> DID
@pytest.mark.parametrize("company,provider", [(DIV, "SAP_DIV"), (IH, "IDENTITY_HUB"), (CSPC, "CSP")])
def test_case_01_create_wallet_calls_no_directory_bpn_to_did(osp_factory, companies, monkeypatch, company, provider):
    # README 13 case 1 "The module does not call any directory BPN -> DID", 6.5 (C3-M2 register-did does that).
    # OPEN-QUESTION: no directory address is configurable here; we assert that no request goes to a directory /
    # core-services path (`/v1/directory`, `/v1/discovery`, `bdrs`, `/holders`) or to BDRS_PUBLIC_URL.
    spy = HttpSpy(monkeypatch)
    osp = osp_factory(env={"BDRS_PUBLIC_URL": "https://bdrs.example.org/api/directory"})
    create(company, 1, provider=provider)
    providers().flush_stand_in()
    service().run_timer_once()
    assert row(company)["status"] == "ACTIVE"
    for url in spy.urls():
        low = url.lower()
        assert not any(f in low for f in ("/v1/directory", "/v1/discovery", "bdrs", "/holders", "/v1/companies")), url
    assert len(osp.events("DataspaceWalletCreated")) == 1
