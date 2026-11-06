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
"""C4-M2 secrets at rest: AES-256-GCM, key version per row (README 4, 5 `wallet_secret`, 6.2, 6.7, case 25).

Seams (TEAM3-PLAN 12.2): `modules.c4_m2.crypto.encrypt/decrypt/reset`, the store's secret rows and
`interface.store().dump()`. Imports are lazy so that a missing module fails the single test.
"""
from __future__ import annotations

import importlib.util
import json
import logging

import pytest

from test_c4_m2_common import (COMPANIES, OSP_A_ID, SECRETS_KEY_HEX, SECRETS_KEY_HEX_V2, Clock, assert_no_secret,
                               companies, osp_factory, seam, step_input)

SECRET = "s3cr3t-api-key-0123456789-ABCDEF"
needs_providers = pytest.mark.skipif(
    importlib.util.find_spec("modules.c4_m2.providers") is None,
    reason="not implemented yet: modules.c4_m2.providers (provider adapters)")
needs_accounts = pytest.mark.skipif(
    importlib.util.find_spec("modules.c4_m2.providers") is None or importlib.util.find_spec("modules.c4_m2.accounts") is None,
    reason="not implemented yet: modules.c4_m2.accounts (wallet accounts)")


@pytest.fixture
def crypto(monkeypatch):
    """The crypto seam with key version 1 configured and no other versions."""
    monkeypatch.setenv("SECRETS_KEY", SECRETS_KEY_HEX)
    monkeypatch.setenv("SECRETS_KEY_VERSION", "1")
    for name in ("SECRETS_KEY_1", "SECRETS_KEY_2", "SECRETS_KEY_3"):
        monkeypatch.delenv(name, raising=False)
    mod = seam("modules.c4_m2.crypto")
    mod.reset()
    yield mod
    mod.reset()


# ------------------------------------------------------------------------------------ the primitive
def test_round_trip_returns_text_and_uses_the_configured_key_version(crypto):
    # README 4: AES-256-GCM, key version per row
    ciphertext, nonce, version = crypto.encrypt(SECRET)
    assert isinstance(ciphertext, bytes) and isinstance(nonce, bytes) and version == 1
    assert crypto.decrypt(ciphertext, nonce, version) == SECRET


def test_ciphertext_is_aes_gcm_shaped_nonce_96_bit_and_tag_16_bytes(crypto):
    # README 4 "AES-256-GCM": 96-bit nonce (the AESGCM default) and a 16-byte tag appended to the ciphertext
    # OPEN-QUESTION: nonce length 12 bytes and "tag appended" (len == plaintext + 16) are our convention
    # (the `cryptography` AESGCM layout); README 5 only says `secret_encrypted, nonce bytea`.
    ciphertext, nonce, _ = crypto.encrypt(SECRET)
    assert len(nonce) == 12
    assert len(ciphertext) == len(SECRET.encode()) + 16


def test_fresh_random_nonce_per_call_same_secret_gives_different_output(crypto):
    # README 5 `wallet_secret.nonce`: a nonce is never reused under one key
    first = crypto.encrypt(SECRET)
    second = crypto.encrypt(SECRET)
    assert first[1] != second[1]
    assert first[0] != second[0]
    nonces = {crypto.encrypt(SECRET)[1] for _ in range(50)}
    assert len(nonces) == 50


def test_ciphertext_and_nonce_do_not_contain_the_plaintext(crypto):
    # README 5 "secrets in plain text" are not stored; case 25
    ciphertext, nonce, _ = crypto.encrypt(SECRET)
    assert_no_secret(SECRET, ciphertext, nonce, ciphertext.hex(), nonce.hex())


def test_wrong_key_does_not_decrypt(crypto, monkeypatch):
    # README 4: authenticated encryption; another key must fail, never return garbage
    ciphertext, nonce, version = crypto.encrypt(SECRET)
    monkeypatch.setenv("SECRETS_KEY", SECRETS_KEY_HEX_V2)
    crypto.reset()
    with pytest.raises(Exception) as err:
        crypto.decrypt(ciphertext, nonce, version)
    assert SECRET not in str(err.value)


@pytest.mark.parametrize("tamper", ["ciphertext", "tag", "nonce", "truncated"])
def test_tampered_input_is_rejected(crypto, tamper):
    # GCM authenticates ciphertext, tag and nonce
    ciphertext, nonce, version = crypto.encrypt(SECRET)
    if tamper == "ciphertext":
        ciphertext = bytes([ciphertext[0] ^ 1]) + ciphertext[1:]
    elif tamper == "tag":
        ciphertext = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
    elif tamper == "nonce":
        nonce = bytes([nonce[0] ^ 1]) + nonce[1:]
    else:
        ciphertext = ciphertext[:-3]
    with pytest.raises(Exception):
        crypto.decrypt(ciphertext, nonce, version)


# ------------------------------------------------------------------------------------ key versions
def test_key_rotation_old_ciphertext_still_decrypts_through_secrets_key_version(crypto, monkeypatch):
    # README 4 configuration: "old versions stay readable through SECRETS_KEY_<version>"
    old = crypto.encrypt(SECRET)
    assert old[2] == 1
    monkeypatch.setenv("SECRETS_KEY_VERSION", "2")
    monkeypatch.setenv("SECRETS_KEY", SECRETS_KEY_HEX_V2)
    monkeypatch.setenv("SECRETS_KEY_1", SECRETS_KEY_HEX)
    crypto.reset()
    assert crypto.decrypt(*old) == SECRET
    new = crypto.encrypt(SECRET)
    assert new[2] == 2
    assert crypto.decrypt(*new) == SECRET


def test_key_rotation_without_the_old_key_cannot_read_old_rows(crypto, monkeypatch):
    old = crypto.encrypt(SECRET)
    monkeypatch.setenv("SECRETS_KEY_VERSION", "2")
    monkeypatch.setenv("SECRETS_KEY", SECRETS_KEY_HEX_V2)   # SECRETS_KEY_1 is not configured
    crypto.reset()
    with pytest.raises(Exception):
        crypto.decrypt(*old)


def test_unknown_key_version_is_rejected(crypto):
    ciphertext, nonce, _ = crypto.encrypt(SECRET)
    with pytest.raises(Exception):
        crypto.decrypt(ciphertext, nonce, 7)


# ------------------------------------------------------------------------------- SECRETS_KEY unset
# OPEN-QUESTION: the shipped config/osp-*/module-config.json set no SECRETS_KEY and config/ is off-limits.
# Reading adopted from TEAM3-PLAN section 1: unset SECRETS_KEY -> one random key per process, generated at
# first use (safe because the store is in memory). `crypto.reset()` forgets it. The README does not describe
# the unset case at all (it only lists SECRETS_KEY as the key); this is a convention, not spec.
def test_unset_secrets_key_uses_a_random_per_process_key(crypto, monkeypatch):
    monkeypatch.delenv("SECRETS_KEY")
    crypto.reset()
    first = crypto.encrypt(SECRET)
    second = crypto.encrypt(SECRET)
    assert crypto.decrypt(*first) == SECRET and crypto.decrypt(*second) == SECRET   # key is stable in the process
    assert first[1] != second[1]


def test_reset_makes_a_new_random_key_old_ciphertext_is_lost(crypto, monkeypatch):
    monkeypatch.delenv("SECRETS_KEY")
    crypto.reset()
    first = crypto.encrypt(SECRET)
    crypto.reset()
    second = crypto.encrypt(SECRET)
    assert crypto.decrypt(*second) == SECRET
    with pytest.raises(Exception):
        crypto.decrypt(*first)
    crypto.reset()
    with pytest.raises(Exception):
        crypto.decrypt(*second)


def test_unset_secrets_key_is_not_the_hex_key_of_other_tests(crypto, monkeypatch):
    # a random key, not a built-in constant: ciphertext under the kit key must not open without that key
    sealed = crypto.encrypt(SECRET)
    monkeypatch.delenv("SECRETS_KEY")
    crypto.reset()
    with pytest.raises(Exception):
        crypto.decrypt(*sealed)


@pytest.mark.parametrize("bad", ["abc", "zz" * 32, SECRETS_KEY_HEX[:-2], SECRETS_KEY_HEX + "00", "  ", "0x" + SECRETS_KEY_HEX[2:]],
                         ids=["short", "not-hex", "31-bytes", "33-bytes", "blank", "0x-prefix"])
def test_malformed_secrets_key_raises_a_clear_error_and_never_falls_back(crypto, monkeypatch, bad):
    # README 4: key = AES-256 as hex (64 hex chars); plan section 1: "A set but malformed key raises a clear error"
    # OPEN-QUESTION: the README does not say what a malformed key does; we require an error whose message names
    # SECRETS_KEY and no fallback to the random key. A whitespace-only value ("blank") counts as malformed here,
    # not as unset (an unset variable gives the per-process random key).
    monkeypatch.setenv("SECRETS_KEY", bad)
    crypto.reset()
    with pytest.raises((ValueError, RuntimeError), match="SECRETS_KEY"):
        crypto.encrypt(SECRET)


def test_secrets_key_is_read_when_used_not_at_import(monkeypatch):
    # TEAM3-PLAN 0.3: configuration is read at call time or in reset(), never at import
    mod = seam("modules.c4_m2.crypto")
    monkeypatch.setenv("SECRETS_KEY_VERSION", "1")
    monkeypatch.setenv("SECRETS_KEY", SECRETS_KEY_HEX)
    mod.reset()
    sealed = mod.encrypt(SECRET)
    monkeypatch.setenv("SECRETS_KEY", SECRETS_KEY_HEX_V2)
    mod.reset()
    with pytest.raises(Exception):
        mod.decrypt(*sealed)
    mod.reset()


# ------------------------------------------------------------------- wallet_secret rows in the store
def _create(osp, key, provider, n=1):
    r = osp.post("/api/c4-m2/steps/create-wallet", osp.service("svc-c4-m2"),
                 json=step_input(COMPANIES[key]["id"], n, companyId=COMPANIES[key]["id"], provider=provider))
    assert r.status_code == 200, r.text
    return r.json()


def _drive_to_active(key):
    """SAP DIV answers by callback of the built-in stand-in; the others are ACTIVE within the call."""
    providers, service = seam("modules.c4_m2.providers"), seam("modules.c4_m2.service")
    providers.flush_stand_in()
    service.run_timer_once()
    return seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES[key]["id"])


CASES = [("div", "SAP_DIV", ["HOLDER_ACCESS"]), ("ih", "IDENTITY_HUB", ["HOLDER_ACCESS", "STS_ACCESS"]),
         ("csp", "CSP", ["HOLDER_ACCESS"])]


@needs_providers
@pytest.mark.parametrize("key,provider,kinds", CASES, ids=[c[1] for c in CASES])
def test_case_25_wallet_secret_rows_hold_ciphertext_nonce_key_version_only(osp_factory, companies, key, provider, kinds):
    # README 5 `wallet_secret`: url and client_id plain; secret_encrypted, nonce bytea; key_version int
    osp = osp_factory(env={"STUB_CALLBACK_DELAY_SECONDS": "3600"})
    _create(osp, key, provider)
    wallet = _drive_to_active(key)
    assert wallet["status"] == "ACTIVE"
    interface, crypto = seam("modules.c4_m2.interface"), seam("modules.c4_m2.crypto")
    store = interface.store()
    plain = []
    for kind in kinds:
        row = store.get_secret(wallet["walletId"], kind)
        assert row is not None, kind
        assert isinstance(row["secret_encrypted"], bytes) and isinstance(row["nonce"], bytes)
        assert len(row["nonce"]) == 12 and row["key_version"] == 1
        assert row["client_id"] and isinstance(row["client_id"], str)
        assert row["url"] and isinstance(row["url"], str)
        secret = crypto.decrypt(row["secret_encrypted"], row["nonce"], row["key_version"])
        assert isinstance(secret, str) and len(secret) >= 8
        assert secret.encode() not in row["secret_encrypted"]
        plain.append((secret, row))
    for other in {"HOLDER_ACCESS", "STS_ACCESS"} - set(kinds):
        assert store.get_secret(wallet["walletId"], other) is None   # STS_ACCESS only with IDENTITY_HUB (README 5)
    dump = json.dumps(store.dump(), sort_keys=True)
    for secret, row in plain:
        assert_no_secret(secret, dump)                        # README 5: no secret in plain text in any table
        assert row["secret_encrypted"].hex() in dump          # dump() renders bytes as hex (TEAM3-PLAN 12.2)
        assert row["nonce"].hex() in dump
    assert_no_secret(SECRETS_KEY_HEX, dump)


@needs_providers
def test_case_25_row_key_version_follows_secrets_key_version(osp_factory, companies):
    # README 5 `wallet_secret.key_version`: "version of SECRETS_KEY"
    osp = osp_factory(env={"SECRETS_KEY_VERSION": "2", "SECRETS_KEY": SECRETS_KEY_HEX_V2,
                           "SECRETS_KEY_1": SECRETS_KEY_HEX})
    _create(osp, "ih", "IDENTITY_HUB")
    wallet = seam("modules.c4_m2.interface").get_wallet_info(companyId=COMPANIES["ih"]["id"])
    store = seam("modules.c4_m2.interface").store()
    assert [store.get_secret(wallet["walletId"], k)["key_version"] for k in ("HOLDER_ACCESS", "STS_ACCESS")] == [2, 2]


@needs_providers
def test_holder_access_still_readable_after_key_rotation(osp_factory, companies, monkeypatch):
    # README 4: old versions stay readable; rows written under version 1 are used after the switch to version 2
    osp = osp_factory()
    _create(osp, "ih", "IDENTITY_HUB")
    interface, crypto = seam("modules.c4_m2.interface"), seam("modules.c4_m2.crypto")
    before = interface.get_holder_access(companyId=COMPANIES["ih"]["id"])
    monkeypatch.setenv("SECRETS_KEY_VERSION", "2")
    monkeypatch.setenv("SECRETS_KEY", SECRETS_KEY_HEX_V2)
    monkeypatch.setenv("SECRETS_KEY_1", SECRETS_KEY_HEX)
    crypto.reset()
    assert interface.get_holder_access(companyId=COMPANIES["ih"]["id"])["apiKey"] == before["apiKey"]


@needs_providers
def test_new_attempt_after_failed_deletes_the_wallet_secret_rows(osp_factory, companies, monkeypatch):
    # README 6.2: "A new attempt deletes the rows in wallet_secret, clears did and the progress fields"
    osp = osp_factory(env={"DID_VALIDATION_MAX_HOURS": "1", "DID_VALIDATION_INTERVAL_MINUTES": "10"})
    clock = Clock().install(monkeypatch, "modules.c4_m2.service")
    interface, service = seam("modules.c4_m2.interface"), seam("modules.c4_m2.service")
    cid, bpn = COMPANIES["ih"]["id"], COMPANIES["ih"]["bpn"]
    store = interface.store()
    monkeypatch.setenv("STUB_FAILURES", f"{bpn}:DID_NOT_RESOLVABLE")
    assert _create(osp, "ih", "IDENTITY_HUB")["state"] == "RUNNING"
    wallet = store.get_wallet(cid)
    assert wallet["status"] == "VALIDATING" and wallet["attempt"] == 1
    assert store.get_secret(wallet["id"], "HOLDER_ACCESS") and store.get_secret(wallet["id"], "STS_ACCESS")
    clock.advance(hours=2)
    service.run_timer_once()
    failed = store.get_wallet(cid)
    assert failed["status"] == "FAILED" and failed["failure_reason"] == "DID_NOT_RESOLVABLE"
    # attempt 2 fails at the order (503): the row is reset, secrets of attempt 1 are gone
    monkeypatch.setenv("STUB_FAILURES", f"{bpn}:ORDER_ERROR")
    r = osp.post("/api/c4-m2/steps/create-wallet", osp.service("svc-c4-m2"),
                 json=step_input(cid, 2, companyId=cid, provider="IDENTITY_HUB"))
    assert r.status_code == 502, r.text
    again = store.get_wallet(cid)
    assert again["attempt"] == 2 and again["status"] == "REQUESTED" and again.get("provider_ordered_at") is None
    assert again["did"] is None and again["id"] == wallet["id"]       # same row (README 5)
    assert store.get_secret(wallet["id"], "HOLDER_ACCESS") is None
    assert store.get_secret(wallet["id"], "STS_ACCESS") is None


def test_log_of_a_failed_decrypt_does_not_contain_the_secret(crypto, caplog):
    caplog.set_level(logging.DEBUG)
    ciphertext, nonce, version = crypto.encrypt(SECRET)
    with pytest.raises(Exception):
        crypto.decrypt(ciphertext[:-1] + bytes([ciphertext[-1] ^ 1]), nonce, version)
    assert_no_secret(SECRET, caplog.text)
    assert_no_secret(SECRETS_KEY_HEX, caplog.text)


# ------------------------------------------------------- wallet_account_credentials rows (README 5, 6.7)
def _account_credentials_rows(osp, create_key, provider, tu_n):
    """Creates the wallet, then a wallet account through the step and returns (store, ref, plain client secret)."""
    _create(osp, create_key, provider)
    _drive_to_active(create_key)
    cid, tu = COMPANIES[create_key]["id"], f"7b0c0000-0000-4000-8000-{tu_n:012d}"
    r = osp.post("/api/c4-m2/steps/create-wallet-account", osp.service("svc-c4-m2"),
                 json=step_input(cid, 50 + tu_n, technicalUserId=tu, companyId=cid))
    assert r.status_code == 200, r.text
    seam("modules.c4_m2.providers").flush_stand_in()
    store = seam("modules.c4_m2.interface").store()
    account = store.get_account(tu)
    assert account is not None and account["status"] == "ACTIVE", account
    return store, account["id"]


@needs_accounts
@pytest.mark.parametrize("key,provider", [("ih", "IDENTITY_HUB"), ("csp", "CSP")], ids=["IDENTITY_HUB", "CSP"])
def test_case_25_wallet_account_credentials_row_is_ciphertext_nonce_key_version(osp_factory, companies, key, provider):
    # The kit lists the CSP company twice, as "csp" (ACTIVE) and as "u1" (REQUESTED); the later entry wins in the
    # fake C3-M1, and README 8.2 needs an ACTIVE company for a new wallet account.
    companies.set_status(COMPANIES["csp"]["id"], "ACTIVE")
    # README 5 `wallet_account_credentials`: client_secret_encrypted + nonce bytea, key_version; never plaintext
    osp = osp_factory(env={"SECRETS_KEY_VERSION": "2", "SECRETS_KEY": SECRETS_KEY_HEX_V2, "SECRETS_KEY_1": SECRETS_KEY_HEX})
    store, ref = _account_credentials_rows(osp, key, provider, 1)
    row = store.get_account_credentials(ref)
    assert isinstance(row["client_secret_encrypted"], bytes) and isinstance(row["nonce"], bytes)
    assert len(row["nonce"]) == 12 and row["key_version"] == 2
    assert row["client_id"] and row["token_url"]
    secret = seam("modules.c4_m2.crypto").decrypt(row["client_secret_encrypted"], row["nonce"], row["key_version"])
    assert len(secret) >= 8 and secret.encode() not in row["client_secret_encrypted"]
    dump = json.dumps(store.dump(), sort_keys=True)
    assert_no_secret(secret, dump, store.list_audit(), store.list_step_log(), [e["data"] for e in osp.events()])
    assert row["client_secret_encrypted"].hex() in dump


@needs_accounts
def test_case_25_account_credentials_use_a_fresh_nonce_per_account(osp_factory, companies):
    # The kit lists the CSP company twice, as "csp" (ACTIVE) and as "u1" (REQUESTED); the later entry wins in the
    # fake C3-M1, and README 8.2 needs an ACTIVE company for a new wallet account.
    companies.set_status(COMPANIES["csp"]["id"], "ACTIVE")
    # README 5: nonce per row; two accounts of the same company never share a nonce
    osp = osp_factory()
    store, first = _account_credentials_rows(osp, "csp", "CSP", 1)
    cid = COMPANIES["csp"]["id"]
    r = osp.post("/api/c4-m2/steps/create-wallet-account", osp.service("svc-c4-m2"),
                 json=step_input(cid, 60, technicalUserId="7b0c0000-0000-4000-8000-000000000002", companyId=cid))
    assert r.status_code == 200, r.text
    second = store.get_account("7b0c0000-0000-4000-8000-000000000002")["id"]
    assert store.get_account_credentials(first)["nonce"] != store.get_account_credentials(second)["nonce"]
