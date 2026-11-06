<!--
  Copyright (c) 2026 Contributors to the Eclipse Foundation

  See the NOTICE file(s) distributed with this work for additional
  information regarding copyright ownership.

  This program and the accompanying materials are made available under the
  terms of the Apache License, Version 2.0 which is available at
  https://www.apache.org/licenses/LICENSE-2.0.

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
  License for the specific language governing permissions and limitations
  under the License.

  AI Disclosure: This file was entirely AI-generated.
  The AI-generated portions are made available under CC0-1.0 and not subject
  to the project's license. The human contributor has reviewed and verified
  that the code is correct.

  SPDX-License-Identifier: Apache-2.0 AND CC0-1.0
  Assisted-By: Claude Code (claude-sonnet-5-5)
-->

# Open questions of C4-M2 (Dataspace Wallet Interface)

Where the spec is unclear, contradicts itself or is silent, the module follows the reading named here
(AGENTS.md rule 10). Spec sections are those of `spec/C4-M2-DataspaceWalletInterface/README.md`.
"Who could decide" is the party that can settle the question.

## Core (store, crypto, DID, create-wallet, callbacks, timer, queries)

| # | Question | Spec | Reading implemented | Who could decide |
|---|---|---|---|---|
| 1 | `DID_VALIDATION_MAX_HOURS` is whole hours (example 168), but acceptance case 7 speaks of a deadline of 2 minutes. | 4, 13 case 7 | The value is read as hours (a decimal such as `0.5` also works). Tests use 1 hour and move the clock (`service.now`). | Spec authors |
| 2 | 7.6 step 6 says the DID check starts "in the background right after the commit". That is not observable. | 7.6 | The first check runs synchronously at the end of the callback, in the same per-company transaction. `run_timer_once()` finishes any check that is still due. | Spec authors |
| 3 | A SAP DIV callback can reach `ACTIVE` only if the DID document is resolvable. | 7.6, 11.1, 11.4 | The SAP DIV stand-in publishes its DID document to the built-in resolver when it accepts the order (`providers.stand_in_documents()`). | Providers owner |
| 4 | A provider name outside the enum, and `BRING_YOUR_OWN`, are both "not usable". | 6.1, 12, openapi `StepCreateWallet` | A name outside the enum gives 400 `validation`; `BRING_YOUR_OWN` gives 400 `provider-not-enabled` (README 6.1). The openapi enum would give `validation` for it. | Spec authors |
| 5 | What is the audit `object_id`? README 5 says only "object ID". | 5 | The wallet id for wallet operations and callbacks (the account id for account operations). The `step_log` `object_id` is the company id. | Spec authors |
| 6 | Is a duplicate callback (204) audited? | 7.6 | Yes: it is an accepted callback and "every callback writes an audit log entry". A rejected one (403, 404, 409) is not audited. | Spec authors |
| 7 | When is `STUB_FAILURES` read? | 4, 14.3 | At call time, never cached. | Providers owner |
| 8 | Account callback deadline variable: README 6.10 says only "the deadline". | 6.3, 6.10 | `PROVIDER_CALLBACK_TIMEOUT_MINUTES` (same as for wallets). | Spec authors |
| 9 | `WalletAccountDeletionFailed` after the deadline: repeated or only once? | 6.3 | Once after the first timer pass past the deadline. | Spec authors |
| 10 | Wallet account for a company with no wallet row at all. | 8.2 | 409 `wallet-not-active` (README 8.2); 404 would also be conceivable. | Spec authors |
| 11 | Store: uniqueness of BPN and DID, shape of `dump()`. | 5 | The store does not enforce uniqueness; the service checks BPN (409 `conflict`). Rows are detached copies, the BPN is upper-cased on put, `dump()` has the spec table names as keys and shows bytes as hex and datetimes as ISO strings. | Team |
| 12 | `SECRETS_KEY` unset. The shipped `config/osp-*/module-config.json` set none and `config/` is off-limits. | 4, 5, 6.7 | One random AES-256 key per process (generated at first use, forgotten by `crypto.reset()`). A set but malformed key raises `ValueError` naming `SECRETS_KEY` and never falls back. Nonce 12 bytes, 16-byte tag appended. | Spec authors, operations |
| 13 | Defaults for unset configuration variables (the shipped config sets none). | 4 | `DID_VALIDATION_INTERVAL_MINUTES` 10, `DID_VALIDATION_MAX_HOURS` 168, `PROVIDER_CALLBACK_TIMEOUT_MINUTES` 1440, `TIMER_INTERVAL_SECONDS` 60, `DEFAULT_PROVIDER` CSP, `ENABLED_PROVIDERS` all three (the example values of README 4). | Spec authors |
| 14 | The openapi `didDocument` of `SapDivWalletCallback` lists inner `required` fields, but 7.6 step 4 wants 204 and `FAILED`/`INVALID_DID_DOCUMENT` for an invalid document. | 7.6, openapi | README 7.6: the route does not enforce the inner `required` list; the service checks the schema of Portal 2.6.0 and fails the wallet. A body without `did`, `didDocument` or the three `authenticationDetails` fields is 400 `validation`. | Spec authors |
| 15 | `TEST_DID_DOCUMENTS_DIR` is listed under the built-in resolution in 11.4 but "used before any resolution" in 4. | 4, 11.4 | Section 4: the files are used first, even before `DID_RESOLVER_URL`. Otherwise `DID_RESOLVER_URL` takes priority over the stand-in documents. | Spec authors |
| 16 | `provider_name` of an account: README 5 says SAP DIV and CSP, 8.2 step 3 says every account. | 5, 8.2 | `tu-` + `technicalUserId` for every account (8.2). Done in `accounts.py`. | Spec authors |
| 17 | Which module name does the audit entry of `getHolderAccess` hold for an in-process call? The function has no caller argument. | 5, 9.3 | `c4-m1` (README 9.3: only C4-M1 asks). Over HTTP the claims of the token are used (`claims` argument of the route). | Spec authors |
| 18 | The check of the DID form compares case-insensitively for SAP DIV and IdentityHub; the CSP only has to start with `did:web:`. `id` of the document must equal the DID exactly. | 6.4 | As described. | Spec authors |
| 19 | A callback with a `didDocument` whose lists are empty (`service: []`, `verificationMethod: []`). | 7.6 step 4 | Accepted by the callback schema (lists are present); step 3 of 6.4 then fails the wallet with `INVALID_DID_DOCUMENT` at the first DID check. | Spec authors |
| 20 | Whether `step_log` and the audit log are written for a step that answers an error. | 5, 6.9 | Only for answers (`RUNNING`, `DONE`); an error answer writes no `step_log` entry. | Spec authors |

## Implementation choices that are not spec questions

- `interface.py` uses the new implementation only when `providers.py` exists in the module. Until then the
  old stand-in answers (so that `demo.py` keeps working with the CSP stand-in flow). When the providers
  file is merged, the new code takes over without a further change.
- Imports across the line between `service.py` and `providers.py` / `accounts.py` happen inside functions
  (`service.optional_module`), so there are no import cycles.
- The background timer thread starts in `on_startup()` of the router and is stopped by `interface.reset()`.

## Wallet accounts and providers

| # | Question | Spec | Reading implemented | Who could decide |
|---|---|---|---|---|
| 21 | Account callback deadline variable: README 6.10 says only "the deadline". | 6.3, 6.10 | `PROVIDER_CALLBACK_TIMEOUT_MINUTES` (default 1440), as for wallets (`accounts.py`). | Spec authors |
| 22 | `WalletAccountDeletionFailed` after the deadline: repeated or only once? | 6.3 | Published once: the first timer pass past the deadline sets `deletion_failed_at`, later passes skip the account. A REQUESTED account past the deadline fails with `PROVIDER_TIMEOUT`. | Spec authors |
| 23 | Wallet account for a company with no wallet row at all. | 8.2 | 409 `wallet-not-active`; 404 is also conceivable. | Spec authors |
| 24 | `provider_name` of an account: README 5 names SAP DIV and CSP, 8.2 step 3 says every account. | 5, 8.2 | `tu-` + `technicalUserId` for every provider, IdentityHub included. | Spec authors |
| 25 | `credentials_state` of an account that becomes DELETED without a retrieval. | 6.3, 6.7 | Unchanged (stays `AVAILABLE`); only the credentials row is deleted, no state transition is named. | Spec authors |
| 26 | Deleting a FAILED account: does the step answer RUNNING or DONE? | 8.3, 6.9 | The account row is deleted at once (`DELETED`), but the step still answers `RUNNING` (as for every first delete call). | Spec authors |
| 27 | `delete-wallet-account` with a wrong `walletAccountRef` on a REQUESTED account: conflict (Input paragraph) or `invalid-state` (Preconditions)? | 8.3 | Preconditions first: 409 `invalid-state`; the ref conflict is checked afterwards. | Spec authors |
| 28 | The SAP DIV stand-in answers an account deletion immediately (README 11.1: "Deletion: immediate callback"), but 11.1 also says callbacks come after `STUB_CALLBACK_DELAY_SECONDS`. | 11.1 | Every stand-in callback, the account deletion callback included, goes through `schedule()` and is delayed by `STUB_CALLBACK_DELAY_SECONDS`; only a value of 0 makes it immediate. | Spec authors |
| 29 | Defaults for unset provider and timing variables (the shipped config sets none). | 4, 11.1, 11.2 | `IDENTITYHUB_DID_BASE` `ih.example.org`; SAP DIV stand-in DID base `https://div-stub.invalid/did` (when `SAP_DIV_DID_DOCUMENT_BASE_URL` is empty); `SAP_DIV_CALLBACK_CLIENT_ID` `sa-div-callback`; `STUB_CALLBACK_DELAY_SECONDS` 1; `ACCOUNT_CREDENTIALS_RETENTION_DAYS` 30; IdentityHub credential service, identity API and STS token URL default to `https://ih.example.org/api/...`. | Spec authors, operations |
| 30 | Request building against a real SAP DIV middleware or IdentityHub (paths, bodies, headers). | 11.1, 11.2 | Built from the README text (`/setup-dim`, `/technical-user/{bpn}`, `/technical-user/{bpn}/delete`; `x-api-key` for the IdentityHub). Only the stand-ins are tested; no real endpoint was available. | Spec authors, SAP / IdentityHub operators |
| 31 | What `providers.orders()` records (README only says "no second order to the stand-in"). | 13, 14.3 | Every order a stand-in received, including repeats and an order that the stand-in then answers with 409 or 404. Not recorded: orders refused by an injected `ORDER_ERROR` (all stand-ins) or `CSP_REJECTED` (CSP wallet order). | Team |
| 32 | CSP answer 403 on a wallet account order. | 11.3 | 403 on a wallet or account creation maps to `provider-rejected` (409, not retryable) in `providers_csp.py`. The built-in CSP stand-in only injects `CSP_REJECTED` for the wallet order, not for the account order. | Spec authors |
| 33 | The test kit lists company `c0000001-...` twice: as `csp` (ACTIVE) and as `u1` (REQUESTED). | 7a, testdata | Account tests use the later entry as the CSP company and start it ACTIVE (see the comment in `tests/test_c4_m2_accounts.py`). | Kit owners |
