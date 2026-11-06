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
"""Store contract of C4-M1 (TEAM3-PLAN 6.2 / 12.3): every implementation of `CredentialStore` must pass this
file. Add the class name to `STORES` to run it against a further implementation (for example a PostgreSQL store).

Data model: README 5 (tables `credential`, `credential_history`, `issuance_run`, `audit_entry`), one row per
(company_id, credential_type), README 6.6 (per-company serialisation).

OPEN-QUESTION: timestamps are timezone-aware `datetime` objects in the rows (plan 12.3 names the keys, not the
Python type); `dump()` must turn them into JSON-serialisable values.
OPEN-QUESTION: plan 6.2 says the BPN is stored upper-case (README 5: "BPN of the holder at the order, in upper case");
the test expects the store to normalise it so that `find_credential` works for status reports.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import uuid

import pytest

from test_c4_m2_common import seam

STORES = ["InMemoryStore"]
T0 = dt.datetime(2026, 11, 5, 8, 0, tzinfo=dt.UTC)
C1, C2, C3 = ("c0000001-0000-4000-8000-000000000001", "c4100004-0000-4000-8000-000000000004",
              "c4100006-0000-4000-8000-000000000006")
BPN1, BPN2, BPN3 = "BPNLIUK2REMLK3F4", "BPNL0000000000U4", "BPNL0000000000U6"


@pytest.fixture(params=STORES)
def store(request):
    return getattr(seam("modules.c4_m1.store"), request.param)()


def t(h: float) -> dt.datetime:
    return T0 + dt.timedelta(hours=h)


def row(company="c1", ctype="BPN", status="REQUESTED", changed=0.0, requested: float | None = 0.0, **kw) -> dict:
    cid, bpn = {"c1": (C1, BPN1), "c2": (C2, BPN2), "c3": (C3, BPN3)}[company]
    r = {"id": str(uuid.uuid4()), "company_id": cid, "credential_type": ctype, "status": status, "route": "STUB",
         "issuer_did": None, "wallet_provider": "STUB", "bpn": bpn, "holder_did": f"did:web:wallet.example.org:{bpn}",
         "request_ref": "stub-1", "attempt": 1, "requested_at": t(requested) if requested is not None else None,
         "issued_at": None, "failed_at": None, "revoked_at": None, "failure_reason": None, "revocation_reason": None,
         "created_at": t(-1), "changed_at": t(changed)}
    r.update(kw)
    return r


def ids(rows) -> list[str]:
    return [r["id"] for r in rows]


# -------------------------------------------------------------------------------------- credentials
def test_empty_store_answers_none_and_empty_lists(store):
    assert store.get_credential(C1, "BPN") is None
    assert store.get_credential_by_id(str(uuid.uuid4())) is None
    assert store.find_credential(BPN1, "BPN") is None
    assert store.list_credentials() == [] and store.get_run(C1) is None
    assert store.list_history(str(uuid.uuid4())) == [] and store.list_audit() == []


def test_put_and_get_by_company_type_and_by_id(store):
    r = row()
    store.put_credential(r)
    got = store.get_credential(C1, "BPN")
    assert got["id"] == r["id"] and got["status"] == "REQUESTED" and got["requested_at"] == t(0)
    assert store.get_credential_by_id(r["id"])["credential_type"] == "BPN"
    assert store.get_credential(C1, "MEMBERSHIP") is None and store.get_credential(C2, "BPN") is None


def test_one_row_per_company_and_credential_type(store):
    # README 5: company_id unique together with credential_type; put replaces the row of the key
    r = row()
    store.put_credential(r)
    store.put_credential({**r, "status": "ISSUED", "issued_at": t(1), "changed_at": t(1)})
    assert len(store.list_credentials()) == 1
    got = store.get_credential(C1, "BPN")
    assert got["status"] == "ISSUED" and got["issued_at"] == t(1) and got["id"] == r["id"]
    store.put_credential(row("c1", "MEMBERSHIP"))
    store.put_credential(row("c2", "BPN"))
    assert len(store.list_credentials()) == 3


def test_find_credential_by_bpn_and_type_with_bpn_stored_in_upper_case(store):
    # README 5 index (bpn, credential_type); 7.4 step 3: lookup by BPN in upper case
    r = row("c1", "MEMBERSHIP", bpn=BPN1.lower())
    store.put_credential(r)
    store.put_credential(row("c2", "MEMBERSHIP"))
    found = store.find_credential(BPN1, "MEMBERSHIP")
    assert found["id"] == r["id"] and found["bpn"] == BPN1
    assert store.find_credential(BPN1, "BPN") is None
    assert store.find_credential("BPNL000000000000", "MEMBERSHIP") is None
    assert store.find_credential(BPN2, "MEMBERSHIP")["company_id"] == C2


# ------------------------------------------------------------------------------------------- listing
@pytest.fixture
def filled(store):
    rows = {
        "a": row("c1", "BPN", "ISSUED", changed=1, requested=0, issued_at=t(1)),
        "b": row("c1", "MEMBERSHIP", "REQUESTED", changed=4, requested=3),
        "c": row("c2", "BPN", "FAILED", changed=0, requested=-1, route="CREDENTIAL_ISSUER"),
        "d": row("c2", "MEMBERSHIP", "REVOCATION_PENDING", changed=5, requested=-5, route="CREDENTIAL_ISSUER"),
        "e": row("c3", "MEMBERSHIP", "FAILED", changed=2, requested=1.5, route="CSP_ISSUER"),
        "f": row("c3", "BPN", "CANCELLED", changed=3, requested=None, route="CSP_ISSUER"),
    }
    for r in rows.values():
        store.put_credential(r)
    return rows


def keys(rows: dict, letters: str) -> list[str]:
    return [rows[k]["id"] for k in letters]


def test_list_is_sorted_by_changed_at_descending(store, filled):
    out = store.list_credentials()
    assert ids(out) == keys(filled, "dbfeac")
    changed = [r["changed_at"] for r in out]
    assert changed == sorted(changed, reverse=True)


@pytest.mark.parametrize("kwargs,expected", [
    ({"company_id": C2}, "dc"),
    ({"credential_type": "BPN"}, "fac"),
    ({"credential_type": "MEMBERSHIP"}, "dbe"),
    ({"route": "CSP_ISSUER"}, "fe"),
    ({"route": "STUB"}, "ba"),
    ({"statuses": ["FAILED"]}, "ec"),
    ({"statuses": ["FAILED", "REVOCATION_PENDING", "CANCELLED"]}, "dfec"),
    ({"statuses": []}, "dbfeac"),
    ({"statuses": None}, "dbfeac"),
    ({"company_id": C3, "statuses": ["FAILED"], "credential_type": "MEMBERSHIP", "route": "CSP_ISSUER"}, "e"),
    ({"company_id": C1, "statuses": ["FAILED"]}, ""),
])
def test_list_filters(store, filled, kwargs, expected):
    assert ids(store.list_credentials(**kwargs)) == keys(filled, expected)


def test_list_requested_before_is_strict_and_skips_rows_without_order(store, filled):
    # README 7.2: "requestedBefore (to find open orders)"; row f has requested_at None
    assert sorted(ids(store.list_credentials(requested_before=t(1.5)))) == sorted(keys(filled, "acd"))
    assert sorted(ids(store.list_credentials(requested_before=t(100)))) == sorted(keys(filled, "abcde"))
    assert store.list_credentials(requested_before=t(-100)) == []
    assert ids(store.list_credentials(requested_before=t(100), statuses=["REQUESTED"])) == keys(filled, "b")


def test_list_paging_pages_are_zero_based_and_follow_the_sort_order(store, filled):
    order = keys(filled, "dbfeac")
    assert ids(store.list_credentials(page=0, size=4)) == order[:4]
    assert ids(store.list_credentials(page=1, size=4)) == order[4:]
    assert store.list_credentials(page=2, size=4) == []
    assert [ids(store.list_credentials(page=p, size=1)) for p in range(6)] == [[i] for i in order]
    assert ids(store.list_credentials(company_id=C2, page=1, size=1)) == keys(filled, "c")


def test_list_default_size_is_50(store):
    for i in range(55):
        store.put_credential({**row("c1", "BPN"), "company_id": str(uuid.uuid4()), "changed_at": t(i)})
    assert len(store.list_credentials()) == 50
    assert len(store.list_credentials(page=1)) == 5
    assert store.list_credentials()[0]["changed_at"] == t(54)


# -------------------------------------------------------------------------------------------- runs
def test_run_per_company_is_replaced_by_put(store):
    # README 5 issuance_run: company_id is the primary key
    run = {"company_id": C1, "credential_types": ["BPN", "MEMBERSHIP"], "status": "RUNNING", "process_id": str(uuid.uuid4()),
           "step_run_id": str(uuid.uuid4()), "started_at": t(0), "finished_at": None}
    store.put_run(run)
    store.put_run({**run, "company_id": C2, "credential_types": ["MEMBERSHIP"]})
    assert store.get_run(C1)["status"] == "RUNNING" and store.get_run(C1)["credential_types"] == ["BPN", "MEMBERSHIP"]
    store.put_run({**run, "status": "DONE", "finished_at": t(2)})
    got = store.get_run(C1)
    assert got["status"] == "DONE" and got["finished_at"] == t(2)
    assert store.get_run(C2)["credential_types"] == ["MEMBERSHIP"] and store.get_run(C3) is None


# ----------------------------------------------------------------------------------- history, audit
def test_history_is_kept_per_credential_in_append_order(store):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())

    def h(cid, status, hours, note=None):
        return {"id": str(uuid.uuid4()), "credential_id": cid, "occurred_at": t(hours), "status": status, "attempt": 1,
                "note": note}

    for e in (h(a, "REQUESTED", 0), h(b, "REQUESTED", 0.5), h(a, "ISSUED", 1), h(a, "REVOKED", 3, "ticket 4711")):
        store.append_history(e)
    assert [(e["status"], e["note"]) for e in store.list_history(a)] == [
        ("REQUESTED", None), ("ISSUED", None), ("REVOKED", "ticket 4711")]
    assert [e["status"] for e in store.list_history(b)] == ["REQUESTED"]
    assert store.list_history(str(uuid.uuid4())) == []


def test_audit_entries_are_appended_and_listed_in_order(store):
    def a(op, n):
        return {"id": str(uuid.uuid4()), "occurred_at": t(n), "sub": f"sub-{n}", "client_id": "sa-csp-issuer",
                "company_id": None, "operation": op, "object_ref": f"{BPN1}:BPN", "result": "204"}

    store.append_audit(a("REPORT_CREDENTIAL_STATUS", 1))
    store.append_audit(a("CONFIRM_REVOCATION", 2))
    out = store.list_audit()
    assert [(e["operation"], e["sub"]) for e in out] == [("REPORT_CREDENTIAL_STATUS", "sub-1"), ("CONFIRM_REVOCATION", "sub-2")]
    assert out[0]["result"] == "204" and out[0]["client_id"] == "sa-csp-issuer"


# ------------------------------------------------------------------------------------ transaction
def run_in_thread(fn) -> threading.Thread:
    th = threading.Thread(target=fn, daemon=True)
    th.start()
    return th


def test_transaction_is_a_reentrant_context_manager(store):
    # README 6.6: steps and status reports of a company run one after the other; a step that calls the
    # report code path in the same thread must not deadlock
    done = threading.Event()

    def work():
        with store.transaction(C1):
            with store.transaction(C1):
                store.put_credential(row())
        done.set()

    th = run_in_thread(work)
    assert done.wait(5), "re-entrant transaction deadlocked"
    th.join(5)
    assert store.get_credential(C1, "BPN") is not None


def test_transaction_serialises_threads_of_the_same_company_but_not_other_companies(store):
    # README 6.6. No absence-by-timeout: the order in which the threads work inside their transactions is recorded
    # under the lock and compared after everything has finished (generous join timeouts, no short waits).
    inside, release, attempting, other_done = (threading.Event() for _ in range(4))
    order: list[str] = []

    def holder():
        with store.transaction(C1):
            inside.set()
            assert release.wait(30)
            order.append("holder-done")

    def same_company():
        attempting.set()
        with store.transaction(C1):
            order.append("same-company")

    def other_company():
        with store.transaction(C2):
            order.append("other-company")
            other_done.set()

    h = run_in_thread(holder)
    assert inside.wait(30)
    s = run_in_thread(same_company)
    assert attempting.wait(30)
    o = run_in_thread(other_company)
    assert other_done.wait(30), "another company must not be blocked by the open transaction of C1"
    release.set()
    for th in (h, s, o):
        th.join(30)
        assert not th.is_alive()
    assert order.index("other-company") < order.index("holder-done")   # C2 finished while C1 was still held
    assert order.index("holder-done") < order.index("same-company")    # the same company waited for the holder


def test_transaction_is_released_after_an_exception(store):
    with pytest.raises(RuntimeError):
        with store.transaction(C1):
            raise RuntimeError("boom")
    got = threading.Event()

    def again():
        with store.transaction(C1):
            got.set()

    run_in_thread(again)
    assert got.wait(5)


# --------------------------------------------------------------------------------- dump and reset
def test_dump_is_json_serialisable_and_contains_all_tables(store, filled):
    store.put_run({"company_id": C1, "credential_types": ["BPN"], "status": "RUNNING", "process_id": None,
                   "step_run_id": None, "started_at": t(0), "finished_at": None})
    store.append_history({"id": str(uuid.uuid4()), "credential_id": filled["a"]["id"], "occurred_at": t(1),
                          "status": "ISSUED", "attempt": 1, "note": "n"})
    store.append_audit({"id": str(uuid.uuid4()), "occurred_at": t(1), "sub": "sub-x", "client_id": "sa-csp-issuer",
                        "company_id": None, "operation": "REPORT_CREDENTIAL_STATUS", "object_ref": "x", "result": "204"})
    dumped = store.dump()
    assert isinstance(dumped, dict)
    text = json.dumps(dumped)                      # no default= : datetimes must already be converted
    for needle in (filled["a"]["id"], BPN1, "sub-x", "REPORT_CREDENTIAL_STATUS", "RUNNING", "2026-11-05"):
        assert needle in text


def test_dump_of_an_empty_store_is_json_serialisable(store):
    json.dumps(store.dump())


def test_reset_empties_everything_including_locks_in_use(store, filled):
    store.put_run({"company_id": C1, "credential_types": ["BPN"], "status": "RUNNING", "process_id": None,
                   "step_run_id": None, "started_at": t(0), "finished_at": None})
    store.append_history({"id": str(uuid.uuid4()), "credential_id": filled["a"]["id"], "occurred_at": t(1),
                          "status": "ISSUED", "attempt": 1, "note": None})
    store.append_audit({"id": str(uuid.uuid4()), "occurred_at": t(1), "sub": "s", "client_id": "c", "company_id": None,
                        "operation": "CONFIRM_REVOCATION", "object_ref": "x", "result": "200"})
    store.reset()
    assert store.list_credentials() == [] and store.get_credential(C1, "BPN") is None
    assert store.get_credential_by_id(filled["a"]["id"]) is None and store.find_credential(BPN1, "BPN") is None
    assert store.get_run(C1) is None and store.list_history(filled["a"]["id"]) == [] and store.list_audit() == []
    assert BPN1 not in json.dumps(store.dump())
    store.put_credential(row())                    # usable again
    assert len(store.list_credentials()) == 1
