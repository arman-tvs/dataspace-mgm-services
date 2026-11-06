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
"""Seam test C4-M2 -> C4-M1 -> C12 with the real modules (no wallet fake): `create-wallet`, then
`issue-credentials` (C4-M1 route STUB: ISSUER_MODE OWN with empty ISSUER_ROUTES), default wallet provider CSP with
the built-in CSP stand-in of C4-M2 (C4-M2 README 11.3, 14.1).

The wallet-account flows `wallet-access` and `wallet-access-removal` and the failure path of `create-wallet`
(`failsOn DataspaceWalletFailed`) run through the same engine on reduced copies of the real flows.

Covers: C4-M2 README 10 (event `DataspaceWalletCreated` with all required fields), 9 / C4-M1 11.2 (contract
`get_wallet_info`), C4-M1 README 10 (`CredentialsIssued` once), FRAMEWORK 5.2 + flows.yaml `onboarding` (`register-did`
takes `steps.create-wallet.did` from the event payload; demo.py check "CSP: DID in the directory = wallet DID"),
and C4-M2 README 8.3 (event `WalletAccountCreated`).

The flow test runs the in-process C12 engine (`modules.c12_m1.engine.Engine`) on a flow file derived from the
`onboarding` flow of `spec/C12-M1-ProcessOrchestration/flows.yaml`, reduced to the three steps under test; the
events of the relay are handed to the engine by the test (the app's own engine only knows the real flows).
"""
from __future__ import annotations

import uuid

import yaml

import pytest

from portal_common import events, neighbours, spec
from test_c4_m2_common import (
    COMPANIES,
    CSP_URL,
    OSP_A_ID,
    companies,  # noqa: F401  (fixture)
    event_errors,
    osp_factory,  # noqa: F401  (fixture)
    response_errors,
    seam,
    step_input,
)

U1 = COMPANIES["u1"]
BPN = U1["bpn"]
WALLET_DID = f"did:web:csp-wallet.example.org:{BPN}"
ENV = {"STUB_ISSUER_DELAY_SECONDS": "0", "CSP_URL": CSP_URL + "/v1"}   # CSP_URL: C3-M2 core services API
WALLET_CREATED_FIELDS = {"companyId", "did", "walletId", "provider", "didDocumentLocation", "bpn"}   # README 10


def assert_reached_in_process(*modules: str) -> None:
    """A module that is not reached in-process would make the engine call a stand-in or an HTTP address and the
    test fail somewhere far from the cause; fail here with a clear message instead."""
    for m in modules:
        assert neighbours.in_process(m), (f"module {m} is not reached in-process (address "
                                          f"{neighbours.address(m)!r}, stand-in: {neighbours.is_standin(m)}); "
                                          "the seam test needs the real module")


def start(osp_factory, env: dict | None = None):
    osp = osp_factory({**ENV, **(env or {})}, csp=True)
    assert_reached_in_process("c4-m2", "c4-m1", "c3-m1")
    osp.csp_register(BPN, osp_id=OSP_A_ID)        # the company is registered at the CSP by C3-M2 (here: directly)
    return osp, osp.service("svc-c12-m1")


def _routed(r, what: str):
    assert r.status_code not in (404, 405, 501), f"{what} is not served by the real module: {r.status_code} {r.text}"
    return r


def create_wallet(osp, svc, n: int = 1):
    return _routed(osp.post("/api/c4-m2/steps/create-wallet", svc, json=step_input(U1["id"], n)), "create-wallet")


def issue(osp, svc, n: int = 2):
    return _routed(osp.post("/api/c4-m1/steps/issue-credentials", svc, json=step_input(U1["id"], n)), "issue-credentials")


def wallet_created(osp) -> dict:
    evs = osp.events("DataspaceWalletCreated")
    assert len(evs) == 1, f"expected exactly one DataspaceWalletCreated, got {len(evs)}"
    return evs[0]


# ------------------------------------------------------------------------------------ create-wallet
def test_create_wallet_event_has_all_required_fields_and_did_equals_wallet_info(osp_factory, companies):
    # README 10, openapi EventDataspaceWalletCreated; C12 `register-did` needs `did` from this payload
    osp, svc = start(osp_factory)
    r = create_wallet(osp, svc)
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"          # README 8.1: C12 completes on the event
    assert response_errors("c4-m2", "POST", "/steps/create-wallet", 200, r.json()) == []
    ev = wallet_created(osp)
    assert ev["source"] == "urn:c4-m2"
    assert event_errors("c4-m2", ev) == []
    assert WALLET_CREATED_FIELDS <= set(ev["data"]), f"missing: {WALLET_CREATED_FIELDS - set(ev['data'])}"
    info = seam("modules.c4_m2.interface").get_wallet_info(companyId=U1["id"])
    assert ev["data"]["did"] == info["did"] == WALLET_DID
    assert ev["data"]["companyId"] == U1["id"] and ev["data"]["bpn"] == BPN and ev["data"]["provider"] == "CSP"
    assert ev["data"]["walletId"] == info["walletId"] and ev["data"]["didDocumentLocation"]


def test_c4_m1_sees_the_wallet_through_the_contract(osp_factory, companies):
    # C4-M1 README 11.2: status ACTIVE, provider, issuanceMode, did, didDocumentLocation, providerRef
    osp, svc = start(osp_factory)
    create_wallet(osp, svc)
    info = seam("modules.c4_m2.interface").get_wallet_info(companyId=U1["id"])
    assert info["status"] == "ACTIVE" and info["provider"] == "CSP" and info["issuanceMode"] == "HOLDER_REQUESTS"
    assert info["did"] == WALLET_DID and info["didDocumentLocation"] and info["providerRef"]
    from portal_common import neighbours
    via = neighbours.query("c4-m1", "c4-m2", "get_wallet_info", companyId=U1["id"])
    assert via == info
    access = neighbours.query("c4-m1", "c4-m2", "get_holder_access", companyId=U1["id"])
    assert access["issuanceMode"] == "HOLDER_REQUESTS" and access["did"] == WALLET_DID and access["bpn"] == BPN
    assert {"identityApiUrl", "participantContextId", "apiKey"} <= set(access)


# ------------------------------------------------------------------------------------ issue-credentials
def test_credentials_are_issued_exactly_once_after_the_wallet_is_created(osp_factory, companies):
    osp, svc = start(osp_factory)
    create_wallet(osp, svc)
    r = issue(osp, svc)
    assert r.status_code == 200 and r.json()["state"] == "RUNNING"
    seam("modules.c4_m1.service").flush_timers()
    body = osp.get(f"/api/c4-m1/internal/companies/{U1['id']}/credentials", svc).json()
    assert {c["credentialType"]: c["status"] for c in body["credentials"]} == {"BPN": "ISSUED", "MEMBERSHIP": "ISSUED"}
    assert body["run"]["status"] == "DONE"
    done = osp.events("CredentialsIssued")
    assert len(done) == 1
    assert sorted(done[0]["data"]["credentialTypes"]) == ["BPN", "MEMBERSHIP"] and done[0]["data"]["companyId"] == U1["id"]
    assert event_errors("c4-m1", done[0]) == []
    # the OSP sees what C4-M1 took from the wallet contract (README 5: wallet_provider, holder_did)
    items = osp.get("/api/c4-m1/credentials", osp.person("p2-osp", ["OSP Admin"]), params={"companyId": U1["id"]})
    assert {(i["route"], i["walletProvider"], i["holderDid"]) for i in items.json()["items"]} == {("STUB", "CSP", WALLET_DID)}
    assert issue(osp, svc, 3).json()["state"] == "DONE" and len(osp.events("CredentialsIssued")) == 1


def test_event_order_wallet_created_before_credentials_issued(osp_factory, companies):
    osp, svc = start(osp_factory)
    create_wallet(osp, svc)
    issue(osp, svc)
    seam("modules.c4_m1.service").flush_timers()
    types = [e["type"] for e in events.RELAY.log if e["type"] in ("DataspaceWalletCreated", "CredentialsIssued")]
    assert types == ["DataspaceWalletCreated", "CredentialsIssued"]


def test_issue_credentials_before_the_wallet_exists_is_wallet_not_ready(osp_factory, companies):
    # C4-M1 README 8.1: wallet not ACTIVE / missing -> 409 wallet-not-ready (the flow order guarantees create-wallet first)
    osp, svc = start(osp_factory)
    r = issue(osp, svc)
    assert r.status_code == 409 and r.json()["type"] == "urn:c4-m1:problem:wallet-not-ready"
    assert r.json()["retryable"] is False and osp.events("CredentialsIssued") == []


# ------------------------------------------------------------------------- the onboarding flow (C12)
def mini_flow(tmp_path):
    doc = yaml.safe_load(spec.flows_file().read_text(encoding="utf-8"))
    onboarding = next(f for f in doc["flows"] if f["key"] == "onboarding")
    onboarding["steps"] = [s for s in onboarding["steps"] if s["key"] in ("create-wallet", "register-did", "issue-credentials")]
    doc["flows"], doc["lookups"] = [onboarding], {}
    path = tmp_path / "flows.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def pump(engine, timers: bool = True) -> None:
    """Hands the events of the relay to the engine and fires the STUB issuer timers (C4-M1; `timers=False` for
    flows that do not touch C4-M1) until nothing changes."""
    flush = seam("modules.c4_m1.service").flush_timers if timers else (lambda: None)
    seen = -1
    while seen != len(events.RELAY.log):
        seen = len(events.RELAY.log)
        for ev in list(events.RELAY.log):
            engine.on_event(ev)
        flush()


def test_onboarding_flow_register_did_gets_the_wallet_did_from_the_event_payload(osp_factory, companies, tmp_path):
    # flows.yaml onboarding: create-wallet (completesOn DataspaceWalletCreated) -> register-did {did: steps.create-wallet.did}
    # -> issue-credentials (completesOn CredentialsIssued); demo.py: "CSP: DID in the directory = wallet DID"
    from modules.c12_m1 import engine as eng
    osp, _svc = start(osp_factory)
    engine = eng.Engine(mini_flow(tmp_path))
    engine.on_event(events.cloudevent("c1-m2", "ApplicationSubmitted", {
        "applicationId": str(uuid.uuid4()), "companyId": U1["id"], "kind": "ONBOARDING", "existingCompany": False,
        "applicantSub": "ebw.test-erika"}))
    pump(engine)
    (proc,) = engine.processes.values()
    states = {s["stepKey"]: s["state"] for s in proc["steps"]}
    assert states == {"create-wallet": "DONE", "register-did": "DONE", "issue-credentials": "DONE"}, proc["steps"]
    assert proc["status"] == "COMPLETED"
    created = wallet_created(osp)
    register = [d for call, d in engine.call_log if call == "c3-m2.register-did"]
    assert len(register) == 1 and register[0]["did"] == created["data"]["did"] == WALLET_DID
    assert register[0]["companyId"] == U1["id"]
    row = osp.csp.core.companies[BPN]
    assert row["did"] == WALLET_DID == seam("modules.c4_m2.interface").get_wallet_info(companyId=U1["id"])["did"]
    assert row["homeOspId"] == OSP_A_ID
    assert len(osp.events("CompanyDidRegistered")) == 1 and len(osp.events("CredentialsIssued")) == 1
    order = [e["type"] for e in events.RELAY.log
             if e["type"] in ("DataspaceWalletCreated", "CompanyDidRegistered", "CredentialsIssued")]
    assert order == ["DataspaceWalletCreated", "CompanyDidRegistered", "CredentialsIssued"]


# ------------------------------------------------------------------------------------- wallet account
def test_create_wallet_account_after_create_wallet_publishes_wallet_account_created(osp_factory, companies):
    # C4-M2 README 8.2 / flows.yaml wallet-access: step input {technicalUserId, companyId} (+ processId, stepRunId);
    # event WalletAccountCreated with technicalUserId, companyId, walletAccountRef (openapi EventWalletAccountFields)
    osp, svc = start(osp_factory)
    create_wallet(osp, svc)
    companies.set_status(U1["id"], "ACTIVE")      # kit: U1 is REQUESTED at C3-M1; 8.2 needs an ACTIVE company
    tu = str(uuid.uuid4())
    r = osp.post("/api/c4-m2/steps/create-wallet-account", svc,
                 json={**step_input(U1["id"], 5), "technicalUserId": tu})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "RUNNING" and r.json()["result"]["status"] == "ACTIVE"      # CSP: ACTIVE within the call
    evs = osp.events("WalletAccountCreated")
    assert len(evs) == 1 and evs[0]["source"] == "urn:c4-m2"
    assert event_errors("c4-m2", evs[0]) == []
    data = evs[0]["data"]
    assert data["technicalUserId"] == tu and data["companyId"] == U1["id"] and data["walletAccountRef"]


# --------------------------------------------------------- wallet-access flows and create-wallet failure (C12)
def reduced_flow(tmp_path, key: str, steps: list[str]):
    """The REAL flow `key` of flows.yaml, cut down to `steps` (the rest stays as it is, including trigger,
    correlateBy, inputs, completesOn with `set`, failsOn)."""
    doc = yaml.safe_load(spec.flows_file().read_text(encoding="utf-8"))
    flow = next(f for f in doc["flows"] if f["key"] == key)
    flow["steps"] = [st for st in flow["steps"] if st["key"] in steps]
    assert [st["key"] for st in flow["steps"]] == steps, f"flows.yaml has no flow {key} with steps {steps}"
    doc["flows"], doc["lookups"] = [flow], {}
    path = tmp_path / f"{key}.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def engine_for(tmp_path, key: str, steps: list[str]):
    from modules.c12_m1 import engine as eng
    return eng.Engine(reduced_flow(tmp_path, key, steps))


def calls(engine, name: str) -> list[dict]:
    return [d for call, d in engine.call_log if call == name]


def step_states(proc: dict) -> dict:
    return {s["stepKey"]: s["state"] for s in proc["steps"]}


# C2-M3 is not under test: its steps are answered by the engine's own stand-in (C2_M3_URL empty); the test reads
# what the engine handed to it from `engine.call_log`.
C2_M3_STANDIN = {"C2_M3_URL": ""}


def test_wallet_access_flow_hands_outcome_and_wallet_account_ref_to_apply_wallet_access(osp_factory, companies, tmp_path):
    # flows.yaml wallet-access: create-wallet-account {technicalUserId, companyId} completesOn
    # {WalletAccountCreated set outcome ACTIVE | WalletAccountFailed set outcome FAILED}
    # -> c2-m3.apply-wallet-access {technicalUserId, outcome, walletAccountRef: steps.create-wallet-account.walletAccountRef}
    osp, svc = start(osp_factory, C2_M3_STANDIN)
    assert neighbours.is_standin("c2-m3"), "c2-m3 must be answered by the engine stand-in, not by a real module"
    assert create_wallet(osp, svc).json()["state"] == "RUNNING"
    companies.set_status(U1["id"], "ACTIVE")          # README 8.2: company ACTIVE at C3-M1
    engine = engine_for(tmp_path, "wallet-access", ["create-wallet-account", "apply-wallet-access"])
    tu = str(uuid.uuid4())
    engine.on_event(events.cloudevent("c2-m3", "WalletAccessRequested", {"technicalUserId": tu, "companyId": U1["id"]}))
    assert [c for c, _ in engine.call_log][:1] == ["c4-m2.create-wallet-account"], engine.call_log
    pump(engine, timers=False)
    (proc,) = engine.processes.values()
    assert step_states(proc) == {"create-wallet-account": "DONE", "apply-wallet-access": "DONE"}, proc["steps"]
    assert proc["status"] == "COMPLETED"
    created = osp.events("WalletAccountCreated")
    assert len(created) == 1 and created[0]["data"]["technicalUserId"] == tu
    ref = created[0]["data"]["walletAccountRef"]
    assert ref and ref == seam("modules.c4_m2.interface").get_wallet_account_internal(technicalUserId=tu)["walletAccountRef"]
    first = calls(engine, "c4-m2.create-wallet-account")
    assert len(first) == 1 and first[0]["technicalUserId"] == tu and first[0]["companyId"] == U1["id"]
    applied = calls(engine, "c2-m3.apply-wallet-access")
    assert len(applied) == 1, engine.call_log
    assert applied[0]["outcome"] == "ACTIVE" and applied[0]["walletAccountRef"] == ref
    assert applied[0]["technicalUserId"] == tu
    assert "clientSecret" not in repr(engine.call_log) and "clientId" not in repr(engine.call_log)   # no credentials


def test_wallet_access_removal_flow_completes_on_wallet_account_deleted(osp_factory, companies, tmp_path):
    # flows.yaml wallet-access-removal: delete-wallet-account {technicalUserId, companyId} (no walletAccountRef)
    # completesOn WalletAccountDeleted, failsOn WalletAccountDeletionFailed -> c2-m3.delete {technicalUserId}
    osp, svc = start(osp_factory, C2_M3_STANDIN)
    assert neighbours.is_standin("c2-m3"), "c2-m3 must be answered by the engine stand-in, not by a real module"
    create_wallet(osp, svc)
    companies.set_status(U1["id"], "ACTIVE")
    tu = str(uuid.uuid4())
    r = osp.post("/api/c4-m2/steps/create-wallet-account", svc, json={**step_input(U1["id"], 5), "technicalUserId": tu})
    assert r.status_code == 200, r.text
    ref = osp.events("WalletAccountCreated")[0]["data"]["walletAccountRef"]
    engine = engine_for(tmp_path, "wallet-access-removal", ["delete-wallet-account", "delete-technical-user"])
    step = engine.flows["wallet-access-removal"]["steps"][0]
    assert step["completesOn"] == ["WalletAccountDeleted"] and step["failsOn"] == ["WalletAccountDeletionFailed"]
    engine.on_event(events.cloudevent("c2-m3", "WalletAccessRemovalRequested",
                                      {"technicalUserId": tu, "companyId": U1["id"]}))
    assert [c for c, _ in engine.call_log][:1] == ["c4-m2.delete-wallet-account"], engine.call_log
    pump(engine, timers=False)
    (proc,) = engine.processes.values()
    assert step_states(proc) == {"delete-wallet-account": "DONE", "delete-technical-user": "DONE"}, proc["steps"]
    assert proc["status"] == "COMPLETED"
    sent = calls(engine, "c4-m2.delete-wallet-account")
    assert len(sent) == 1 and sent[0]["technicalUserId"] == tu and sent[0]["companyId"] == U1["id"]
    assert "walletAccountRef" not in sent[0]          # the flow does not pass it (it is optional, README 8.3)
    deleted = osp.events("WalletAccountDeleted")
    assert len(deleted) == 1 and deleted[0]["data"]["walletAccountRef"] == ref
    assert event_errors("c4-m2", deleted[0]) == []
    assert [d["technicalUserId"] for d in calls(engine, "c2-m3.delete")] == [tu]


def test_create_wallet_failure_event_fails_the_step_through_the_engine(osp_factory, companies, tmp_path):
    # flows.yaml onboarding: create-wallet failsOn DataspaceWalletFailed; README 14.3 `<BPN>:DID_MISMATCH` (SAP DIV stand-in)
    # The default provider decides (README 6.1, flows name none): SAP DIV, whose stand-in answers with a wrong DID.
    osp, _svc = start(osp_factory, {"DEFAULT_PROVIDER": "SAP_DIV", "STUB_FAILURES": f"{BPN}:DID_MISMATCH"})
    engine = engine_for(tmp_path, "onboarding", ["create-wallet"])
    engine.on_event(events.cloudevent("c1-m2", "ApplicationSubmitted", {
        "applicationId": str(uuid.uuid4()), "companyId": U1["id"], "kind": "ONBOARDING", "existingCompany": False,
        "applicantSub": "ebw.test-erika"}))
    assert [c for c, _ in engine.call_log] == ["c4-m2.create-wallet"], engine.call_log
    seam("modules.c4_m2.providers").flush_stand_in()              # the SAP DIV callback (wrong DID)
    pump(engine, timers=False)
    failed = osp.events("DataspaceWalletFailed")
    assert len(failed) == 1 and failed[0]["data"]["reason"] == "DID_MISMATCH" and failed[0]["data"]["companyId"] == U1["id"]
    assert osp.events("DataspaceWalletCreated") == []
    (proc,) = engine.processes.values()
    (sr,) = proc["steps"]
    assert sr["stepKey"] == "create-wallet" and sr["state"] == "FAILED", proc["steps"]
    assert sr["lastError"]["type"] == "event:DataspaceWalletFailed" and sr["lastError"]["title"] == "DID_MISMATCH"
    assert proc["status"] == "FAILED"
    assert [c for c, _ in engine.call_log] == ["c4-m2.create-wallet"]     # nothing after the failed step
