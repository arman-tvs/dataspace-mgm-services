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
"""Integration of C3-M2 with a long-running CSP: the whole installation OSP A in one process (every
module of the repository, C12 with its worker and the event relay) plus the shared CSP stand-in
with `asyncOperations`. The CSP answers register-company with 202. The test only plays the CSP's
operator, who finishes the operation at the CSP (`POST /admin/operations/{id}/complete` of the
stand-in); the CSP then calls back POST /api/c3-m2/csp-notifications itself, with the token of its
service account `sa-csp` from the Portal IAM, and Process Orchestration finishes the onboarding
(README 4, 7.2, 8.1, 13 case 4; FRAMEWORK 5.2). Scenario 1 of demo.py drives it and checks it."""
import contextlib
import json
import threading
import time

from fastapi.testclient import TestClient

import demo
from conftest import BASE, needs_admin_api
from modules.c12_m1 import engine as eng
from modules.c3_m2 import store
from portal_common import csp as csp_client
from portal_common import http as phttp
from scaffold import app as scaffold_app
from tools.csp_standin.app import create_app as create_csp
from tools.keys import ec_jwk

CSP = "http://csp.test"
NOTIFICATIONS = f"{BASE}/api/c3-m2/csp-notifications"


def csp_operator(csp, stop: threading.Event) -> None:
    """Finishes every operation the CSP started for C3-M2, once C3-M2 waits for it (status PENDING)."""
    done: set[str] = set()
    while not stop.is_set():
        for row in list(store.registrations.values()):
            operation = row.pending_operation_id
            if row.status == "PENDING" and operation and operation not in done:
                done.add(operation)
                csp.post(f"/admin/operations/{operation}/complete", json={"outcome": "SUCCEEDED"})
        time.sleep(0.05)


@contextlib.contextmanager
def installation_with_long_running_csp(tmp_path, monkeypatch):
    """OSP A and the shared CSP stand-in in one process, the CSP in its long-running mode."""
    priv, pub = ec_jwk("osp-a")
    (tmp_path / "key.json").write_text(json.dumps(priv))
    (tmp_path / "trust.json").write_text(json.dumps({demo.OSP_A_ID: {
        "name": "OSP A", "installationUrl": BASE, "jwk": pub,
        "iamTokenUrl": f"{BASE}/auth/realms/CX-Central/protocol/openid-connect/token"}}))
    for k, v in {"CSP_TRUST_FILE": tmp_path / "trust.json", "CSP_PUBLIC_URL": CSP, "CSP_URL": f"{CSP}/v1",
                 "CSP_TOKEN_URL": f"{CSP}/oauth/token", "CSP_JWKS_URL": f"{CSP}/.well-known/jwks.json",
                 "OSP_SIGNING_KEY_FILE": tmp_path / "key.json", "CSP_CALLBACK_DELAY_SECONDS": "0",
                 "RETRY_BASE_SECONDS": "0.2", "WORKER_POLL_SECONDS": "0.1"}.items():
        monkeypatch.setenv(k, str(v))
    csp_client.reset()
    csp_app = create_csp()
    phttp.register_local(CSP, csp_app)
    csp = TestClient(csp_app, base_url=CSP)
    assert csp.put("/admin/config", json={"asyncOperations": True}).json() == {"asyncOperations": True}
    app = scaffold_app.create_app()
    with TestClient(app, base_url=BASE):
        try:
            yield csp
        finally:
            scaffold_app.reset_all(app.state.entries)
            phttp.unregister_local(CSP)


@needs_admin_api
def test_onboarding_completes_through_the_csp_callback(tmp_path, monkeypatch):
    with installation_with_long_running_csp(tmp_path, monkeypatch) as csp:
        stop = threading.Event()
        operator = threading.Thread(target=csp_operator, args=(csp, stop), daemon=True)
        operator.start()
        try:
            t = demo.Target(osp_a=BASE, csp=CSP, quiet=True)
            ok = demo.run(t, ["1"])
        finally:
            stop.set()
            operator.join(timeout=5)
        failed = [(label, detail) for steps in t.results.values() for label, passed, detail in steps if not passed]
        assert ok and not failed, failed

        # 1. the CSP answered register-company with 202: the operation was long-running
        registered = [a for a in store.audit if a.operation == "register-company"]
        assert [a.http_status for a in registered] == [202], registered

        # 2. the CSP itself called back, authenticated as sa-csp through the Portal IAM, and C3-M2 took it
        callbacks = [c for c in csp.get("/admin/callbacks").json()
                     if c["url"] == NOTIFICATIONS and c["body"]["type"] == "OperationCompleted"]
        assert len(callbacks) == 1 and callbacks[0]["status"] == 200, callbacks
        bpn = callbacks[0]["body"]["bpn"]
        assert callbacks[0]["body"]["outcome"] == "SUCCEEDED" and bpn.startswith("BPNL")

        # 3. C3-M2 holds the company as REGISTERED with the BPN of the callback, nothing left aside
        row = store.find_by_bpn(bpn)
        assert row is not None and (row.status, row.membership) == ("REGISTERED", "REGISTERED")
        assert row.pending_operation_id is None and store.early_completions == {}

        # 4. C12: register-company first answered RUNNING, the completing event finished it with that
        #    BPN, and the rest of the onboarding ran after it
        proc = next(p for p in eng.get_engine().processes.values() if p["flowKey"] == "onboarding")
        step = next(s for s in proc["steps"] if s["stepKey"] == "register-company")
        assert proc["status"] == "COMPLETED" and step["state"] == "DONE" and step["result"]["bpn"] == bpn
        assert [a["outcome"] for a in step["attemptHistory"]] == ["RUNNING"]
