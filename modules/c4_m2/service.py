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
"""Business logic of C4-M2: the single clock, the store, the audit log and the step log.

The router stays a thin HTTP layer and `interface.py` the public functions; the rules of the wallet
(README 6, 8) live here. Every time read of the module goes through `now()` so that tests can move the
clock. `providers` and `accounts` (written by another person) are imported only inside functions.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import threading
import uuid

from portal_common import events

from . import crypto, did, errors, gateways, providers
from .adapters.common import Callbacks
from .store import InMemoryStore, WalletStore

log = logging.getLogger(__name__)

MODULE = "c4-m2"
PROVIDERS = ("SAP_DIV", "IDENTITY_HUB", "CSP")
HOLDER_ACCESS, STS_ACCESS = "HOLDER_ACCESS", "STS_ACCESS"

_store: WalletStore | None = None
_store_lock = threading.Lock()


def now() -> dt.datetime:
    """The clock of the module: timezone-aware UTC. All time reads go through this function."""
    return dt.datetime.now(dt.UTC)


def get_store() -> WalletStore:
    """The active store (in memory today, a database store later)."""
    global _store
    with _store_lock:
        if _store is None:
            _store = InMemoryStore()
        return _store


def reset() -> None:
    """Stop the timer and clear the store."""
    stop_timer()
    get_store().reset()


def reset_all() -> None:
    """`interface.reset()`: the store and the timer, the key cache, the state of the providers."""
    reset()
    crypto.reset()
    providers.reset()


def audit(claims: dict | str | None, operation: str, company_id: str | None, object_id: str | None) -> None:
    """Write an audit entry (README 5 `audit_log`). `claims` is the token claims dict of an HTTP call, or
    the name of the calling module for an in-process call (then the entry holds that name). No secrets."""
    if isinstance(claims, dict):
        sub, azp = claims.get("sub"), claims.get("azp")
    else:
        sub = azp = claims
    get_store().append_audit({"occurred_at": now(), "sub": sub, "azp": azp, "company_id": company_id,
                              "operation": operation, "object_id": object_id})


def log_step(input: dict, step: str, object_id: str | None, state: str) -> None:
    """Write a step-log entry (README 5 `step_log`)."""
    get_store().append_step_log({"step_run_id": input.get("stepRunId"), "process_id": input.get("processId"),
                                 "step": step, "object_id": object_id, "state": state, "occurred_at": now()})


# --------------------------------------------------------------------------------------- helpers
def _number(name: str, default: float) -> float:
    """A positive number from the environment at call time; the default for unset or unusable values."""
    try:
        value = float(os.environ.get(name, "").strip())
    except ValueError:
        return default
    return value if value > 0 else default


def _when(value: dt.datetime | str | None) -> dt.datetime | None:
    """A timezone-aware datetime from a datetime or an ISO string, None if there is none."""
    if isinstance(value, str):
        try:
            value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, dt.datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def iso(value: dt.datetime | str | None) -> str | None:
    moment = _when(value)
    return moment.isoformat() if moment else None



def enabled_providers() -> list[str]:
    """README 4: `ENABLED_PROVIDERS`, empty = `SAP_DIV,IDENTITY_HUB,CSP`."""
    return list(providers.enabled())


def default_provider() -> str:
    """README 4: `DEFAULT_PROVIDER`, empty = `CSP`."""
    return providers.default_provider()


def get_company(company_id: str) -> dict | None:
    """The view of C3-M1 (`name`, `bpn`, `status`); None if the company does not exist (gateways.py)."""
    return gateways.company(company_id)


def get_wallet(company_id: str) -> dict | None:
    """The wallet row of a company."""
    return get_store().get_wallet(company_id)


def wallet_secret(wallet_id: str, kind: str) -> dict | None:
    """The decrypted secret of a wallet: `{url, client_id, secret}`, None if there is none."""
    row = get_store().get_secret(wallet_id, kind)
    if row is None:
        return None
    return {"url": row["url"], "client_id": row["client_id"],
            "secret": crypto.decrypt(row["secret_encrypted"], row["nonce"], row["key_version"])}


def store_secret(wallet_id: str, kind: str, access: dict) -> None:
    """Encrypt and store `{url, client_id, secret}` (README 5 `wallet_secret`)."""
    ciphertext, nonce, key_version = crypto.encrypt(access["secret"])
    get_store().put_secret(wallet_id, kind, access["url"], access["client_id"], ciphertext, nonce, key_version)


def save_wallet(wallet: dict) -> dict:
    wallet["changed_at"] = now()
    get_store().put_wallet(wallet)
    return wallet


def did_web_location(did_value: str | None) -> str | None:
    """Location of the DID document by the `did:web` rules."""
    if not did_value or not did_value.lower().startswith("did:web:"):
        return None
    parts = did_value.split(":")[2:]
    return "https://" + "/".join(parts) + "/did.json" if parts else None


def credential_service_url(document: dict) -> str | None:
    """Endpoint of the service of type `CredentialService` in a DID document, if there is one."""
    services = document.get("service") if isinstance(document, dict) else None
    if isinstance(services, dict):
        services = [services]
    for entry in services if isinstance(services, list) else []:
        kind = entry.get("type") if isinstance(entry, dict) else None
        if kind == did.CREDENTIAL_SERVICE or (isinstance(kind, list) and did.CREDENTIAL_SERVICE in kind):
            endpoint = entry.get("serviceEndpoint")
            if isinstance(endpoint, str) and endpoint:
                return endpoint
    return None


# ----------------------------------------------------------------------------- events and status
def _wallet_created(wallet: dict) -> None:
    events.publish(MODULE, "DataspaceWalletCreated", {
        "companyId": wallet["company_id"], "did": wallet["did"], "walletId": wallet["id"],
        "provider": wallet["provider"], "didDocumentLocation": wallet["did_document_location"],
        "bpn": wallet["bpn"]})


def fail_wallet(wallet: dict, reason: str) -> dict:
    """Status `FAILED` with the reason and the event `DataspaceWalletFailed` (README 6.2, 10)."""
    wallet.update(status="FAILED", failure_reason=reason, next_check_at=None)
    save_wallet(wallet)
    events.publish(MODULE, "DataspaceWalletFailed", {
        "companyId": wallet["company_id"], "walletId": wallet["id"], "provider": wallet["provider"],
        "reason": reason})
    return wallet


def _activate(wallet: dict, document: dict) -> dict:
    """README 6.4 step 4: `did_validated_at`, the credential service of the document, status `ACTIVE`."""
    moment = now()
    wallet.update(status="ACTIVE", did_validated_at=moment, activated_at=moment, next_check_at=None,
                  credential_service_url=credential_service_url(document) or wallet.get("credential_service_url"))
    save_wallet(wallet)
    _wallet_created(wallet)
    return wallet


def check_did(wallet: dict) -> dict:
    """One DID check of a `VALIDATING` wallet (README 6.4). Call it inside `transaction(company_id)`.

    Wrong form: `FAILED` `DID_MISMATCH`. Not resolvable: the next attempt after
    `DID_VALIDATION_INTERVAL_MINUTES`, after `DID_VALIDATION_MAX_HOURS` from `validating_since` `FAILED`
    `DID_NOT_RESOLVABLE`. Invalid content: `FAILED` `INVALID_DID_DOCUMENT`. Otherwise `ACTIVE`."""
    if not did.check_form(wallet["provider"], wallet["did"], wallet["bpn"]):
        return fail_wallet(wallet, "DID_MISMATCH")
    document = did.resolve(wallet["did"])
    moment = now()
    if document is None:
        started = _when(wallet.get("validating_since")) or moment
        if moment >= started + dt.timedelta(hours=_number("DID_VALIDATION_MAX_HOURS", 168)):
            return fail_wallet(wallet, "DID_NOT_RESOLVABLE")
        wallet["next_check_at"] = moment + dt.timedelta(minutes=_number("DID_VALIDATION_INTERVAL_MINUTES", 10))
        return save_wallet(wallet)
    if did.check_document(wallet["provider"], wallet["did"], document):
        return fail_wallet(wallet, did.INVALID_DID_DOCUMENT)
    return _activate(wallet, document)


# ------------------------------------------------------------------------------------ create-wallet
def _validate_create_input(input: dict) -> tuple[str, str | None]:
    """README 8.1 step 1: the input of the step; returns `(companyId, provider or None)`."""
    if not isinstance(input, dict):
        raise errors.validation("the input must be a JSON object")
    for name in ("processId", "stepRunId", "companyId"):
        value = input.get(name)
        try:
            if not isinstance(value, str):
                raise ValueError
            uuid.UUID(value)
        except ValueError:
            raise errors.validation(f"{name} must be a UUID") from None
    provider = input.get("provider")
    if provider is None:
        return input["companyId"], None
    if provider == "BRING_YOUR_OWN":
        raise errors.provider_not_enabled("BRING_YOUR_OWN is not available yet")
    if provider not in PROVIDERS:
        raise errors.validation("provider must be SAP_DIV, IDENTITY_HUB or CSP")
    return input["companyId"], provider


def _choose_provider(requested: str | None) -> str:
    """README 6.1: the provider of the input, otherwise `DEFAULT_PROVIDER`; it must be enabled."""
    provider = requested or default_provider()
    if provider not in enabled_providers():
        raise errors.provider_not_enabled(f"{provider} is not in ENABLED_PROVIDERS")
    return provider


def _new_wallet(company_id: str, bpn: str, provider: str) -> dict:
    moment = now()
    return {"id": str(uuid.uuid4()), "company_id": company_id, "bpn": bpn, "provider": provider,
            "status": "REQUESTED", "failure_reason": None, "did": None, "did_document_location": None,
            "credential_service_url": None, "provider_ref": None, "control_challenge_id": None, "attempt": 1,
            "provider_ordered_at": None, "validating_since": None, "did_validated_at": None,
            "next_check_at": None, "activated_at": None, "created_at": moment, "changed_at": moment}


def _reset_for_new_attempt(wallet: dict, provider: str) -> dict:
    """README 6.2: a new attempt after `FAILED` deletes the secrets, clears `did` and the progress fields."""
    get_store().delete_secrets(wallet["id"])
    wallet.update(provider=provider, status="REQUESTED", failure_reason=None, did=None,
                  did_document_location=None, credential_service_url=None, provider_ref=None,
                  provider_ordered_at=None, validating_since=None, did_validated_at=None, next_check_at=None,
                  activated_at=None, attempt=int(wallet.get("attempt") or 1) + 1)
    return save_wallet(wallet)


def _order(wallet: dict, company: dict) -> dict:
    """README 8.1 step 4: the order to the adapter. `provider_ordered_at` is set only after it accepted."""
    answer = providers.get(wallet["provider"]).order_wallet({
        "company_id": wallet["company_id"], "bpn": wallet["bpn"], "company_name": company.get("name"),
        "attempt": wallet["attempt"], "wallet_id": wallet["id"]})
    # An in-process stand-in may already have called back while ordering: continue from the stored row.
    wallet = get_store().get_wallet(wallet["company_id"]) or wallet
    moment = now()
    if answer.get("result") == "CREATED":
        for kind, access in (answer.get("secrets") or {}).items():
            store_secret(wallet["id"], kind, access)
        wallet.update(status="VALIDATING", did=answer["did"], did_document_location=answer.get("did_document_location"),
                      credential_service_url=answer.get("credential_service_url"),
                      provider_ref=answer.get("provider_ref"), provider_ordered_at=moment,
                      validating_since=moment, next_check_at=moment)
        save_wallet(wallet)
        return check_did(wallet)           # README 8.1 step 5: try the DID check at once
    wallet["provider_ordered_at"] = wallet.get("provider_ordered_at") or moment
    wallet["provider_ref"] = wallet.get("provider_ref") or wallet["bpn"]
    return save_wallet(wallet)


def _step_result(wallet: dict) -> dict:
    """README 8.1 result (openapi `StepResultWallet`); no secrets."""
    result = {"walletId": wallet["id"], "companyId": wallet["company_id"], "provider": wallet["provider"],
              "status": wallet["status"]}
    if wallet.get("did"):
        result["did"] = wallet["did"]
    if wallet.get("did_document_location"):
        result["didDocumentLocation"] = wallet["did_document_location"]
    if wallet.get("failure_reason"):
        result["failureReason"] = wallet["failure_reason"]
    return result


def create_wallet(input: dict) -> dict:
    """The step `create-wallet` (README 8.1). Long-running: `RUNNING` unless the wallet was already `ACTIVE`."""
    company_id, requested = _validate_create_input(input)
    store = get_store()
    with store.transaction(company_id):
        company = get_company(company_id)
        if company is None:
            raise errors.not_found("company not found")
        if not company.get("bpn"):
            raise errors.company_not_ready("the company has no BPN yet")
        bpn = str(company["bpn"]).upper()
        wallet = store.get_wallet(company_id)
        other = store.find_wallet_by_bpn(bpn)
        if (wallet and wallet["bpn"] != bpn) or (other and other["company_id"] != company_id):
            raise errors.conflict("the BPN does not match the existing wallets")
        state = "RUNNING"
        if wallet is None:
            wallet = save_wallet(_new_wallet(company_id, bpn, _choose_provider(requested)))
            wallet = _order(wallet, company)
        elif wallet["status"] == "ACTIVE":
            state = "DONE"
        elif wallet["status"] == "FAILED":
            wallet = _reset_for_new_attempt(wallet, _choose_provider(requested))
            wallet = _order(wallet, company)
        elif wallet["status"] == "REQUESTED" and not wallet.get("provider_ordered_at"):
            wallet = _order(wallet, company)
        # REQUESTED with `provider_ordered_at` and VALIDATING: nothing else (RUNNING)
        log_step(input, "create-wallet", company_id, state)
        return {"stepRunId": input["stepRunId"], "state": state, "result": _step_result(wallet)}


def _wallet_callback(bpn: str, body: dict, caller: str) -> None:
    from modules.c4_m2.services import sap_div_callback  # it imports this file: imported at call time
    sap_div_callback.accept_wallet_callback(bpn, body, caller)


def _account_created(reference: str, body: dict, caller: str) -> None:
    from modules.c4_m2.services import accounts  # accounts imports this file: imported at call time
    accounts.accept_account_created(reference, body, caller)


def _account_deleted(reference: str, caller: str) -> None:
    from modules.c4_m2.services import accounts
    accounts.accept_account_deleted(reference, caller)


providers.register_callbacks(Callbacks(wallet=_wallet_callback, account_created=_account_created,
                                                 account_deleted=_account_deleted))


# -------------------------------------------------------------------------- scheduled tasks
def _timer_pass_requested(moment: dt.datetime) -> None:
    """README 6.10 callback deadline: `REQUESTED` with an order older than the deadline."""
    deadline = dt.timedelta(minutes=_number("PROVIDER_CALLBACK_TIMEOUT_MINUTES", 1440))
    store = get_store()
    for candidate in store.list_wallets(["REQUESTED"]):
        ordered = _when(candidate.get("provider_ordered_at"))
        if ordered is None or moment - ordered <= deadline:
            continue
        with store.transaction(candidate["company_id"]):
            wallet = store.get_wallet(candidate["company_id"])
            if wallet and wallet["status"] == "REQUESTED" and _when(wallet.get("provider_ordered_at")) == ordered:
                fail_wallet(wallet, "PROVIDER_TIMEOUT")


def _timer_pass_validating(moment: dt.datetime) -> None:
    """README 6.10 DID check: `VALIDATING`, no `did_validated_at`, `next_check_at` reached."""
    store = get_store()
    for candidate in store.list_wallets(["VALIDATING"]):
        due = _when(candidate.get("next_check_at"))
        if candidate.get("did_validated_at") or due is None or due > moment:
            continue
        with store.transaction(candidate["company_id"]):
            wallet = store.get_wallet(candidate["company_id"])
            if wallet and wallet["status"] == "VALIDATING" and not wallet.get("did_validated_at"):
                check_did(wallet)


def run_timer_once() -> None:
    """One pass of every scheduled task (README 6.10). The background thread calls it every
    `TIMER_INTERVAL_SECONDS`; tests call it directly."""
    moment = now()
    _timer_pass_requested(moment)
    _timer_pass_validating(now())
    from modules.c4_m2.services import accounts  # accounts imports this file: imported at call time
    accounts.run_tasks()


_timer: threading.Thread | None = None
_timer_stop = threading.Event()


def _timer_loop(stop: threading.Event) -> None:
    while not stop.wait(_number("TIMER_INTERVAL_SECONDS", 60)):
        try:
            run_timer_once()
        except Exception:  # noqa: BLE001 - a failing pass must not end the timer
            log.exception("scheduled tasks of C4-M2 failed")


def start_timer() -> None:
    """Start the background thread of the scheduled tasks if it is not running."""
    global _timer, _timer_stop
    if _timer is not None and _timer.is_alive():
        return
    _timer_stop = threading.Event()
    _timer = threading.Thread(target=_timer_loop, args=(_timer_stop,), name="c4-m2-timer", daemon=True)
    _timer.start()


def stop_timer() -> None:
    """Stop the background thread (used by `reset()`)."""
    global _timer
    _timer_stop.set()
    _timer = None
