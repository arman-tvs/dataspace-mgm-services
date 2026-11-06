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
"""Store contract of C4-M2 (TEAM3-PLAN 1 "Storage sits behind an abstraction", 12.2).

Every implementation of `store.WalletStore` must pass these tests. A future database store only
needs its class name added to `STORES` (instantiated without arguments from `modules.c4_m2.store`).
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import uuid

import pytest

from test_c4_m2_common import assert_no_secret, osp_factory, seam  # noqa: F401  (osp_factory is a fixture)

STORES = ["InMemoryStore"]

BPN_A, BPN_B = "BPNL0000000DIV01", "BPNL00000000IH01"
DID_A, DID_B = "did:web:div.example.org:did:BPNL0000000DIV01", "did:web:ih.example.org:BPNL00000000IH01"
JOIN_SECONDS = 5


@pytest.fixture(params=STORES)
def store(request):
    st = getattr(seam("modules.c4_m2.store"), request.param)()
    yield st
    st.reset()


def wallet(n: int = 1, **changes) -> dict:
    """A `dataspace_wallet` row with every column of README 5 (TEAM3-PLAN 12.2 wallet dict keys)."""
    row = {"id": str(uuid.UUID(int=n)), "company_id": f"1a2b3c4d-{n:04d}-4000-8000-{n:012d}", "bpn": BPN_A,
           "provider": "SAP_DIV", "status": "REQUESTED", "failure_reason": None, "did": None,
           "did_document_location": None, "credential_service_url": None, "provider_ref": None,
           "control_challenge_id": None, "attempt": 1, "provider_ordered_at": None, "validating_since": None,
           "did_validated_at": None, "next_check_at": None, "activated_at": None,
           "created_at": "2026-11-06T09:00:00Z", "changed_at": "2026-11-06T09:00:00Z"}
    return {**row, **changes}


def secret_args(wallet_id: str, kind: str = "HOLDER_ACCESS", **changes) -> dict:
    args = {"wallet_id": wallet_id, "kind": kind, "url": "https://auth.example.org/oauth", "client_id": "client-1",
            "secret_encrypted": bytes(range(40)), "nonce": bytes(range(12)), "key_version": 1}
    return {**args, **changes}


# ----------------------------------------------------------------------------------------- wallets
def test_put_and_get_wallet_by_company_id(store):
    # README 5 `dataspace_wallet`: one row per company
    w = wallet(1)
    assert store.get_wallet(w["company_id"]) is None
    assert store.put_wallet(w) is None
    assert store.get_wallet(w["company_id"]) == w
    assert store.get_wallet(wallet(2)["company_id"]) is None


def test_put_wallet_replaces_the_row_of_the_same_company(store):
    # README 5: "A new attempt after FAILED uses the same row"
    w = wallet(1)
    store.put_wallet(w)
    store.put_wallet({**w, "status": "FAILED", "failure_reason": "PROVIDER_TIMEOUT", "attempt": 2})
    got = store.get_wallet(w["company_id"])
    assert (got["status"], got["failure_reason"], got["attempt"]) == ("FAILED", "PROVIDER_TIMEOUT", 2)
    assert len(store.list_wallets()) == 1


def test_find_wallet_by_bpn(store):
    a, b = wallet(1, bpn=BPN_A), wallet(2, bpn=BPN_B)
    store.put_wallet(a)
    store.put_wallet(b)
    assert store.find_wallet_by_bpn(BPN_A)["company_id"] == a["company_id"]
    assert store.find_wallet_by_bpn(BPN_B)["company_id"] == b["company_id"]
    assert store.find_wallet_by_bpn("BPNL000000000000") is None


def test_find_wallet_by_did(store):
    a, b = wallet(1, did=DID_A), wallet(2, bpn=BPN_B, did=DID_B)
    store.put_wallet(a)
    store.put_wallet(b)
    assert store.find_wallet_by_did(DID_A)["id"] == a["id"]
    assert store.find_wallet_by_did(DID_B)["id"] == b["id"]
    assert store.find_wallet_by_did("did:web:nobody.example") is None


def test_lookups_follow_updates_no_stale_index_entries(store):
    # README 6.2: a new attempt "clears did"; README 5: did unique "when set". After the row is rewritten the old
    # BPN and the old DID must not find it any more, the new ones must.
    w = wallet(1, did=DID_A)
    store.put_wallet(w)
    store.put_wallet({**w, "did": None, "bpn": BPN_B})
    assert store.find_wallet_by_did(DID_A) is None
    assert store.find_wallet_by_bpn(BPN_A) is None
    assert store.find_wallet_by_bpn(BPN_B)["id"] == w["id"]
    store.put_wallet({**w, "did": DID_B, "bpn": BPN_B})
    assert store.find_wallet_by_did(DID_B)["id"] == w["id"]


def test_find_returns_the_same_row_as_get(store):
    w = wallet(1, did=DID_A, status="ACTIVE", provider_ref=BPN_A)
    store.put_wallet(w)
    assert store.find_wallet_by_bpn(BPN_A) == store.get_wallet(w["company_id"]) == store.find_wallet_by_did(DID_A)


# OPEN-QUESTION: README 5 says company_id, bpn and did are unique. The seam contract (TEAM3-PLAN 12.2) gives
# `put_wallet` no error type and README 8.1 step 1 does the cross-company BPN check in the service
# (409 `conflict`). So uniqueness is not tested as an error of the store; only that lookups stay consistent
# (above) and that company_id is the key (put replaces). If a DB store enforces the unique indexes, its own
# tests may extend this file.

def test_get_wallet_returns_a_copy(store):
    # OPEN-QUESTION: not stated in the plan; a database store returns detached rows, so an in-memory store must
    # not let callers change stored state without `put_wallet`.
    w = wallet(1)
    store.put_wallet(w)
    got = store.get_wallet(w["company_id"])
    got["status"] = "ACTIVE"
    assert store.get_wallet(w["company_id"])["status"] == "REQUESTED"
    w["status"] = "FAILED"   # the caller's dict after put is not the stored one either
    assert store.get_wallet(w["company_id"])["status"] == "REQUESTED"


def test_list_wallets_without_filter_returns_every_row(store):
    for n in (1, 2, 3):
        store.put_wallet(wallet(n, bpn=f"BPNL00000000000{n}"))
    assert sorted(w["id"] for w in store.list_wallets()) == sorted(wallet(n)["id"] for n in (1, 2, 3))


def test_list_wallets_filters_by_status_for_the_timer(store):
    # README 6.10: the timer selects REQUESTED (callback deadline) and VALIDATING (DID check)
    statuses = {1: "REQUESTED", 2: "VALIDATING", 3: "ACTIVE", 4: "FAILED"}
    for n, s in statuses.items():
        store.put_wallet(wallet(n, status=s, bpn=f"BPNL00000000000{n}"))
    ids = {n: wallet(n)["id"] for n in statuses}
    timer = store.list_wallets(["REQUESTED", "VALIDATING"])
    assert sorted(w["id"] for w in timer) == sorted([ids[1], ids[2]])
    assert [w["id"] for w in store.list_wallets(["ACTIVE"])] == [ids[3]]
    assert store.list_wallets(["VALIDATING", "FAILED"]) and {w["status"] for w in store.list_wallets(["VALIDATING", "FAILED"])} == {"VALIDATING", "FAILED"}
    assert store.list_wallets(["NO_SUCH_STATUS"]) == []


def test_list_wallets_reflects_a_status_change(store):
    w = wallet(1, status="VALIDATING")
    store.put_wallet(w)
    assert len(store.list_wallets(["VALIDATING"])) == 1
    store.put_wallet({**w, "status": "ACTIVE"})
    assert store.list_wallets(["VALIDATING"]) == []
    assert len(store.list_wallets(["ACTIVE"])) == 1


# ----------------------------------------------------------------------------------------- secrets
def test_put_and_get_secret_keeps_bytes_and_key_version(store):
    # README 5 `wallet_secret`: secret_encrypted, nonce bytea; key_version int; PK (wallet_id, kind)
    w = wallet(1)
    store.put_wallet(w)
    store.put_secret(**secret_args(w["id"], key_version=3))
    row = store.get_secret(w["id"], "HOLDER_ACCESS")
    assert row["secret_encrypted"] == bytes(range(40)) and isinstance(row["secret_encrypted"], bytes)
    assert row["nonce"] == bytes(range(12)) and isinstance(row["nonce"], bytes)
    assert row["key_version"] == 3
    assert (row["wallet_id"], row["kind"]) == (w["id"], "HOLDER_ACCESS")
    assert (row["url"], row["client_id"]) == ("https://auth.example.org/oauth", "client-1")


def test_get_secret_of_an_unknown_wallet_or_kind_is_none(store):
    w = wallet(1)
    store.put_secret(**secret_args(w["id"]))
    assert store.get_secret(w["id"], "STS_ACCESS") is None
    assert store.get_secret(wallet(2)["id"], "HOLDER_ACCESS") is None


def test_both_secret_kinds_of_a_wallet_coexist(store):
    # README 5: kind HOLDER_ACCESS or STS_ACCESS (IdentityHub)
    wid = wallet(1)["id"]
    store.put_secret(**secret_args(wid, "HOLDER_ACCESS", client_id="ctx"))
    store.put_secret(**secret_args(wid, "STS_ACCESS", client_id="sts-client", secret_encrypted=b"\x09" * 20))
    assert store.get_secret(wid, "HOLDER_ACCESS")["client_id"] == "ctx"
    assert store.get_secret(wid, "STS_ACCESS")["secret_encrypted"] == b"\x09" * 20


def test_put_secret_with_the_same_primary_key_replaces_the_row(store):
    wid = wallet(1)["id"]
    store.put_secret(**secret_args(wid, secret_encrypted=b"old-old-old", key_version=1))
    store.put_secret(**secret_args(wid, secret_encrypted=b"new-new-new", key_version=2))
    row = store.get_secret(wid, "HOLDER_ACCESS")
    assert (row["secret_encrypted"], row["key_version"]) == (b"new-new-new", 2)


def test_delete_secrets_removes_every_kind_of_that_wallet_only(store):
    # README 6.2: a new attempt deletes the rows in wallet_secret
    one, two = wallet(1)["id"], wallet(2)["id"]
    for wid in (one, two):
        store.put_secret(**secret_args(wid, "HOLDER_ACCESS"))
        store.put_secret(**secret_args(wid, "STS_ACCESS"))
    store.delete_secrets(one)
    assert store.get_secret(one, "HOLDER_ACCESS") is None and store.get_secret(one, "STS_ACCESS") is None
    assert store.get_secret(two, "HOLDER_ACCESS") and store.get_secret(two, "STS_ACCESS")
    store.delete_secrets(one)   # idempotent
    store.delete_secrets(wallet(9)["id"])


# -------------------------------------------------------------------------------- audit, step log
def _audit(n: int) -> dict:
    return {"occurred_at": f"2026-11-06T09:00:{n:02d}Z", "sub": f"sub-{n}", "azp": "svc-c4-m1",
            "company_id": wallet(1)["company_id"], "operation": "READ_HOLDER_ACCESS", "object_id": wallet(1)["id"]}


def _step(n: int) -> dict:
    return {"step_run_id": str(uuid.UUID(int=n)), "process_id": str(uuid.UUID(int=900)), "step": "create-wallet",
            "object_id": wallet(1)["company_id"], "state": "RUNNING", "occurred_at": f"2026-11-06T09:00:{n:02d}Z"}


def test_audit_entries_keep_their_order(store):
    # README 5 `audit_log`
    assert store.list_audit() == []
    entries = [_audit(n) for n in range(5)]
    for e in entries:
        store.append_audit(e)
    assert store.list_audit() == entries


def test_step_log_entries_keep_their_order(store):
    # README 5 `step_log`
    assert store.list_step_log() == []
    entries = [_step(n) for n in range(5)]
    for e in entries:
        store.append_step_log(e)
    assert store.list_step_log() == entries


def test_audit_and_step_log_are_separate_and_copies(store):
    store.append_audit(_audit(1))
    store.append_step_log(_step(1))
    assert len(store.list_audit()) == 1 and len(store.list_step_log()) == 1
    store.list_audit().clear()
    store.list_audit()[0]["sub"] = "tampered"
    assert store.list_audit()[0]["sub"] == "sub-1"     # OPEN-QUESTION: copies, like detached DB rows
    assert len(store.list_step_log()) == 1


# ---------------------------------------------------------------------------------- transactions
def _run_thread(fn):
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    return t


def test_transaction_is_a_context_manager_and_re_entrant(store):
    # README 6.9: steps and callbacks of one company never run at the same time; a step calls helpers that open
    # the same transaction again, so the lock must be re-entrant (RLock in memory)
    done = []

    def work():
        with store.transaction("c-1"):
            with store.transaction("c-1"):
                with store.transaction("c-1"):
                    done.append("inner")
            done.append("outer")

    t = _run_thread(work)
    t.join(JOIN_SECONDS)
    assert not t.is_alive(), "deadlock: transaction(company_id) is not re-entrant"
    assert done == ["inner", "outer"]


def test_transaction_serialises_threads_of_the_same_company(store):
    # README 6.9 (advisory lock on company_id). Thread A holds the lock; thread B must not enter until A leaves.
    log: list[str] = []
    a_in, a_release, b_about, b_in = (threading.Event() for _ in range(4))

    def a():
        with store.transaction("c-1"):
            log.append("A-in")
            a_in.set()
            a_release.wait(JOIN_SECONDS)
            log.append("A-out")

    def b():
        b_about.set()
        with store.transaction("c-1"):
            log.append("B-in")
            b_in.set()

    ta = _run_thread(a)
    assert a_in.wait(JOIN_SECONDS)
    tb = _run_thread(b)
    assert b_about.wait(JOIN_SECONDS)
    assert not b_in.wait(0.2), "thread B entered the transaction of company c-1 while thread A held it"
    a_release.set()
    ta.join(JOIN_SECONDS)
    tb.join(JOIN_SECONDS)
    assert not ta.is_alive() and not tb.is_alive()
    assert log == ["A-in", "A-out", "B-in"]


def test_transaction_does_not_block_other_companies(store):
    held, release, other_in = (threading.Event() for _ in range(3))

    def holder():
        with store.transaction("c-1"):
            held.set()
            release.wait(JOIN_SECONDS)

    def other():
        with store.transaction("c-2"):
            other_in.set()

    t1 = _run_thread(holder)
    assert held.wait(JOIN_SECONDS)
    t2 = _run_thread(other)
    assert other_in.wait(JOIN_SECONDS), "transaction of company c-2 was blocked by company c-1"
    release.set()
    t1.join(JOIN_SECONDS)
    t2.join(JOIN_SECONDS)


def test_transaction_is_released_after_an_exception(store):
    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        with store.transaction("c-1"):
            raise Boom
    entered = threading.Event()

    def again():
        with store.transaction("c-1"):
            entered.set()

    t = _run_thread(again)
    assert entered.wait(JOIN_SECONDS), "the lock of company c-1 stayed held after an exception"
    t.join(JOIN_SECONDS)


# ------------------------------------------------------------------------------------ dump, reset
def test_dump_is_json_serialisable_with_bytes_as_hex(store):
    # OPEN-QUESTION: `store.dump()` and its shape (a dict of table name -> rows, bytes as hex) are a TEAM3-PLAN 12.2
    # convention for secret scans; the README (5) only fixes the tables and that secrets are not stored in plain text.
    # TEAM3-PLAN 12.2 dump(): "JSON-serialisable full state, bytes as hex; for secret scans"
    w = wallet(1, did=DID_A, status="VALIDATING")
    store.put_wallet(w)
    store.put_secret(**secret_args(w["id"], secret_encrypted=bytes.fromhex("deadbeef" * 5), nonce=bytes.fromhex("0a" * 12)))
    store.append_audit(_audit(1))
    store.append_step_log(_step(1))
    text = json.dumps(store.dump())            # must not raise
    assert w["id"] in text and DID_A in text
    assert "deadbeef" * 5 in text and "0a" * 12 in text
    assert "operation" in text and "create-wallet" in text


def test_dump_names_the_tables_of_the_spec(store):
    # TEAM3-PLAN 1 decisions: the spec's table names are the dict keys of the store state.
    # OPEN-QUESTION: the plan fixes the table names but not the shape of dump(); a dict with these four keys is assumed.
    w = wallet(1)
    store.put_wallet(w)
    store.put_secret(**secret_args(w["id"]))
    store.append_audit(_audit(1))
    store.append_step_log(_step(1))
    dump = store.dump()
    assert {"dataspace_wallet", "wallet_secret", "audit_log", "step_log"} <= set(dump)
    assert len(dump["dataspace_wallet"]) == 1 and len(dump["wallet_secret"]) == 1
    assert len(dump["audit_log"]) == 1 and len(dump["step_log"]) == 1


def test_dump_handles_datetime_values(store):
    # the service stores timestamps from `service.now()`; dump() must still serialise them
    when = dt.datetime(2026, 11, 6, 9, 0, tzinfo=dt.UTC)
    store.put_wallet(wallet(1, provider_ordered_at=when, validating_since=when))
    assert "2026-11-06" in json.dumps(store.dump())


def test_dump_contains_no_plaintext_secret(store):
    # README 5 "Not stored: secrets in plain text"; the store only ever sees ciphertext
    plain = "plain-client-secret-xyz"
    w = wallet(1)
    store.put_wallet(w)
    ciphertext = bytes(b ^ 0x5A for b in plain.encode())   # stands for the AES-GCM output of the crypto seam
    store.put_secret(**secret_args(w["id"], secret_encrypted=ciphertext))
    assert_no_secret(plain, store.dump(), json.dumps(store.dump()))


def test_reset_empties_everything(store):
    w = wallet(1, did=DID_A)
    store.put_wallet(w)
    store.put_secret(**secret_args(w["id"]))
    store.append_audit(_audit(1))
    store.append_step_log(_step(1))
    store.reset()
    assert store.get_wallet(w["company_id"]) is None
    assert store.find_wallet_by_bpn(BPN_A) is None and store.find_wallet_by_did(DID_A) is None
    assert store.list_wallets() == [] and store.list_wallets(["REQUESTED"]) == []
    assert store.get_secret(w["id"], "HOLDER_ACCESS") is None
    assert store.list_audit() == [] and store.list_step_log() == []
    assert all(not v for v in store.dump().values())
    store.put_wallet(w)                     # usable again
    with store.transaction(w["company_id"]):
        assert store.get_wallet(w["company_id"]) == w


def test_stores_are_independent_instances():
    mod = seam("modules.c4_m2.store")
    one, two = getattr(mod, STORES[0])(), getattr(mod, STORES[0])()
    one.put_wallet(wallet(1))
    assert two.get_wallet(wallet(1)["company_id"]) is None


def test_the_module_store_is_a_wallet_store_and_reset_clears_it(osp_factory):
    # TEAM3-PLAN 12.2: `interface.store()` returns the active store; `interface.reset()` clears it
    osp_factory()
    interface, store = seam("modules.c4_m2.interface"), seam("modules.c4_m2.store")
    active = interface.store()
    assert isinstance(active, tuple(getattr(store, name) for name in STORES))
    active.put_wallet(wallet(1))
    interface.reset()
    assert interface.store().get_wallet(wallet(1)["company_id"]) is None


# ====================================================================== wallet accounts (README 5, 6.3, 7.2, 7.3)
TU_1, TU_2 = str(uuid.UUID(int=0x7001)), str(uuid.UUID(int=0x7002))


def account(n: int = 1, **changes) -> dict:
    """A `wallet_account` row with every column of README 5 (`id` is the walletAccountRef)."""
    row = {"id": str(uuid.UUID(int=0xA000 + n)), "technical_user_id": TU_1, "company_id": wallet(1)["company_id"],
           "wallet_id": wallet(1)["id"], "provider": "CSP", "status": "REQUESTED", "failure_reason": None,
           "provider_name": f"tu-{TU_1}", "provider_ordered_at": None, "deletion_ordered_at": None,
           "credentials_state": "NONE", "created_at": f"2026-11-06T09:00:0{n}Z", "changed_at": f"2026-11-06T09:00:0{n}Z"}
    return {**row, **changes}


def creds(ref: str, **changes) -> dict:
    args = {"wallet_account_id": ref, "token_url": "https://sts.example.org/token", "client_id": "sts-client",
            "client_secret_encrypted": bytes(range(30)), "nonce": bytes(range(12)), "key_version": 1,
            "created_at": "2026-11-06T09:00:00Z", "expires_at": "2026-12-06T09:00:00Z"}
    return {**args, **changes}


def test_put_and_get_account_by_technical_user_and_by_ref(store):
    a = account(1)
    assert store.get_account(TU_1) is None and store.get_account_by_ref(a["id"]) is None
    assert store.put_account(a) is None
    assert store.get_account(TU_1) == a
    assert store.get_account_by_ref(a["id"]) == a                     # README 5: id is the walletAccountRef
    assert store.get_account(TU_2) is None
    assert store.get_account_by_ref(account(9)["id"]) is None


def test_put_account_with_the_same_id_replaces_the_row(store):
    a = account(1)
    store.put_account(a)
    store.put_account({**a, "status": "ACTIVE", "credentials_state": "AVAILABLE"})
    got = store.get_account_by_ref(a["id"])
    assert (got["status"], got["credentials_state"]) == ("ACTIVE", "AVAILABLE")
    assert len(store.list_accounts()) == 1


def test_get_account_prefers_the_row_that_is_not_deleted(store):
    # README 7.2 step 2: "the row with a status other than DELETED, otherwise the latest one"
    old_deleted = account(1, status="DELETED", created_at="2026-11-01T09:00:00Z")
    current = account(2, status="ACTIVE", created_at="2026-11-02T09:00:00Z")
    store.put_account(old_deleted)
    store.put_account(current)
    assert store.get_account(TU_1)["id"] == current["id"]
    # the not-deleted row wins even when a deleted one is newer
    store.reset()
    store.put_account(account(1, status="ACTIVE", created_at="2026-11-01T09:00:00Z"))
    store.put_account(account(2, status="DELETED", created_at="2026-11-05T09:00:00Z"))
    assert store.get_account(TU_1)["id"] == account(1)["id"]


def test_get_account_returns_the_latest_when_all_are_deleted(store):
    store.put_account(account(1, status="DELETED", created_at="2026-11-01T09:00:00Z"))
    store.put_account(account(2, status="DELETED", created_at="2026-11-03T09:00:00Z"))
    store.put_account(account(3, status="DELETED", created_at="2026-11-02T09:00:00Z"))
    assert store.get_account(TU_1)["id"] == account(2)["id"]


def test_accounts_of_different_technical_users_do_not_mix(store):
    store.put_account(account(1))
    store.put_account(account(2, technical_user_id=TU_2, provider_name=f"tu-{TU_2}"))
    assert store.get_account(TU_1)["id"] == account(1)["id"]
    assert store.get_account(TU_2)["id"] == account(2)["id"]


def test_list_accounts_filters_by_wallet_and_status(store):
    w1, w2 = wallet(1)["id"], wallet(2)["id"]
    store.put_account(account(1, wallet_id=w1, status="REQUESTED"))
    store.put_account(account(2, wallet_id=w1, status="ACTIVE", technical_user_id=TU_2))
    store.put_account(account(3, wallet_id=w2, status="DELETING", technical_user_id=str(uuid.UUID(int=0x7003))))
    assert len(store.list_accounts()) == 3
    assert {a["id"] for a in store.list_accounts(wallet_id=w1)} == {account(1)["id"], account(2)["id"]}
    # README 6.10: the timer selects REQUESTED or DELETING accounts
    assert {a["id"] for a in store.list_accounts(statuses=["REQUESTED", "DELETING"])} == {account(1)["id"], account(3)["id"]}
    assert [a["id"] for a in store.list_accounts(wallet_id=w1, statuses=["ACTIVE"])] == [account(2)["id"]]
    assert store.list_accounts(wallet_id=w2, statuses=["ACTIVE"]) == []
    assert store.list_accounts(wallet_id=wallet(9)["id"]) == []


def test_get_account_returns_a_copy(store):
    # OPEN-QUESTION: as for wallets, rows are detached (a DB store cannot do otherwise)
    a = account(1)
    store.put_account(a)
    got = store.get_account(TU_1)
    got["status"] = "ACTIVE"
    a["status"] = "FAILED"
    assert store.get_account(TU_1)["status"] == "REQUESTED"


def test_put_get_account_credentials_keeps_bytes_and_key_version(store):
    # README 5 `wallet_account_credentials`: secret and nonce are bytea, key_version int, expires_at
    ref = account(1)["id"]
    assert store.get_account_credentials(ref) is None
    assert store.put_account_credentials(**creds(ref, key_version=4)) is None
    row = store.get_account_credentials(ref)
    assert row["client_secret_encrypted"] == bytes(range(30)) and isinstance(row["client_secret_encrypted"], bytes)
    assert row["nonce"] == bytes(range(12)) and isinstance(row["nonce"], bytes)
    assert row["key_version"] == 4
    assert (row["token_url"], row["client_id"]) == ("https://sts.example.org/token", "sts-client")
    assert (row["created_at"], row["expires_at"]) == ("2026-11-06T09:00:00Z", "2026-12-06T09:00:00Z")
    assert row["wallet_account_id"] == ref
    assert store.get_account_credentials(account(2)["id"]) is None
    assert store.get_account_credentials(ref) is not None           # a read does not consume (only pop does)


def test_put_account_credentials_replaces_the_row_of_the_account(store):
    ref = account(1)["id"]
    store.put_account_credentials(**creds(ref, client_secret_encrypted=b"old-old-old"))
    store.put_account_credentials(**creds(ref, client_secret_encrypted=b"new-new-new"))
    assert store.get_account_credentials(ref)["client_secret_encrypted"] == b"new-new-new"


def test_delete_account_credentials_removes_only_that_row(store):
    one, two = account(1)["id"], account(2)["id"]
    store.put_account_credentials(**creds(one))
    store.put_account_credentials(**creds(two))
    store.delete_account_credentials(one)
    assert store.get_account_credentials(one) is None and store.get_account_credentials(two) is not None
    store.delete_account_credentials(one)                           # idempotent
    store.delete_account_credentials(account(9)["id"])


def test_pop_account_credentials_reads_and_deletes(store):
    # README 7.3 step 4: read and decrypt the row, delete the row
    ref = account(1)["id"]
    assert store.pop_account_credentials(ref) is None
    store.put_account_credentials(**creds(ref, client_secret_encrypted=b"\x07" * 24))
    row = store.pop_account_credentials(ref)
    assert row["client_secret_encrypted"] == b"\x07" * 24 and row["client_id"] == "sts-client"
    assert store.get_account_credentials(ref) is None
    assert store.pop_account_credentials(ref) is None


def test_pop_account_credentials_gives_the_row_to_exactly_one_of_two_threads(store):
    # README 7.3 "Concurrent calls: only one gets the data, the other gets 410"; case 15 "exactly one gets 200"
    ref = account(1)["id"]
    for _ in range(25):
        store.put_account_credentials(**creds(ref))
        start, results = threading.Barrier(2), []

        def pop():
            start.wait(JOIN_SECONDS)
            results.append(store.pop_account_credentials(ref))

        threads = [_run_thread(pop) for _ in range(2)]
        for t in threads:
            t.join(JOIN_SECONDS)
        assert len(results) == 2
        assert sum(r is not None for r in results) == 1, results


def test_dump_shows_accounts_and_credentials_as_hex_without_plaintext(store):
    # README 5 "secrets in plain text" are never stored; TEAM3-PLAN 12.2 dump(): bytes as hex
    # OPEN-QUESTION: dump keys are the spec table names `wallet_account` and `wallet_account_credentials`.
    plain = "plain-sts-client-secret-xyz"
    a = account(1, status="ACTIVE", credentials_state="AVAILABLE")
    store.put_account(a)
    cipher = bytes(b ^ 0x3C for b in plain.encode())
    store.put_account_credentials(**creds(a["id"], client_secret_encrypted=cipher, nonce=bytes.fromhex("0b" * 12)))
    dump = store.dump()
    text = json.dumps(dump)
    assert len(dump["wallet_account"]) == 1 and len(dump["wallet_account_credentials"]) == 1
    assert a["id"] in text and cipher.hex() in text and "0b" * 12 in text
    assert_no_secret(plain, dump, text)


def test_reset_empties_accounts_and_credentials(store):
    a = account(1)
    store.put_account(a)
    store.put_account_credentials(**creds(a["id"]))
    store.reset()
    assert store.get_account(TU_1) is None and store.get_account_by_ref(a["id"]) is None
    assert store.list_accounts() == [] and store.get_account_credentials(a["id"]) is None
    assert store.pop_account_credentials(a["id"]) is None
    assert all(not v for v in store.dump().values())
