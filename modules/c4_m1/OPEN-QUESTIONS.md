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

# C4-M1 Credentials: open questions and decisions

Each entry names the reading that is implemented (AGENTS.md rule 10).

## Decisions (spec against repo)

1. **Storage is in memory** (repo README "Where is the data stored?"; no module uses a database). `store.py` defines
   `CredentialStore` and `InMemoryStore` with the table and column names of README 5 and a `transaction(company_id)`
   seam (per-company `RLock`, stands in for the advisory lock of README 6.6). A PostgreSQL store can replace it
   without touching `service.py`. No `DATABASE_URL` handling.
2. **Outbox is `events.publish`** (the shared relay of the repo).
3. **Defaults in code** (config files are not ours): `ISSUER_MODE=OWN`, `ONBOARDING_CREDENTIAL_TYPES=BPN,MEMBERSHIP`,
   `RESEND_AFTER_HOURS=24`, `STUB_ISSUER_DELAY_SECONDS=1` (spec example 5; well below the 60 s demo timeout),
   `CSP_ISSUER_CREDENTIAL_DEFINITIONS=BPN:bpn,MEMBERSHIP:membership` (what the shared CSP stand-in accepts; the spec
   example `bpn-credential` is honoured when set), `CREDENTIAL_FORMAT=VC1_0_JWT`,
   `CSP_ISSUER_DID=did:web:issuer.csp.example.org`, `CALLBACK_BASE_URL` falls back to `BASE_URL`.
4. **Wallet provider `STUB`** exists only in test fakes; the real C4-M2 never returns it (README 6.3 rule 1 is still implemented).

## Interpretations

5. Unknown company (neighbour answers 404) gives `company-not-ready`; missing wallet gives `wallet-not-ready` (README 8.1 is silent).
6. README 6.3 rule 2 (OWN with empty `ISSUER_ROUTES` gives STUB) against case 5 (`BRING_YOUR_OWN` gives 409
   `no-issuer-route`): an own wallet (`BRING_YOUR_OWN` / `CREDENTIAL_OFFER`) is rejected before rule 2.
7. `ISSUER_MODE=CSP` with empty `CSP_ISSUER_URL`, and `OWN` with empty `ISSUER_ROUTES`, give STUB for any other wallet.
8. Invalid `credentialTypes` (empty, duplicate, unknown) and invalid `companyId` give 400 `validation`, `retryable=false`.
9. A resend (REQUESTED to REQUESTED, `attempt` + 1) writes a history entry (README 6.1 lists no such transition).
10. Re-ordering a row clears `issued_at`, `failed_at`, `revoked_at`, `failure_reason`, `revocation_reason`; the history keeps the past.
11. Audit entries are written for accepted (204) status reports and for `CONFIRM_REVOCATION` with 200 only. Reports
    answered 404/409 write none (README 5 `result` could imply them). STUB timer reports are in-process and not audited.
    `company_id` of a service-account report is `None`.
12. `REVOCATION_PENDING` row in `revoke-credentials` stays unchanged and is listed again under `manualRevocation`.
13. Person without `company_id` but with the permission gets 404; a person without `view_credentials` (README 14 P3,
    `Applicant`) gets 403 (README 6.5 order, case 8 names 404 for P3).
14. Case 14 uses OSP B in the spec; the kit and `installation.json` use OSP A. The code uses `ospId` of the settings.
15. `revoke-credentials` sets a running round to `CANCELLED` only if its types overlap the revoked types.
16. A report without `message` on `UNSUCCESSFUL` publishes `reason` "issuance failed" (the event field is required).
17. Revocation through `CSP_ISSUER`: every non-2xx answer of the `DELETE` is 502 `upstream-error` (README: technical error).

## Provisional (spec says to check against the version in use)

18. Body of the credential request at the wallet identity API: `{issuerDid, holderPid, credentials: [{type, format}]}`.
19. Administration interface of the own IssuerService (README 11.4): holder `POST /api/admin/participants/{id}/holders`
    (409 counts as success) and revocation `POST .../holders/{bpn}/credentials/revoke`. Paths are guesses, untested against a real IssuerService.
20. Own-issuer routes `CREDENTIAL_ISSUER` / `ISSUER_SERVICE` have only route-selection tests (no test server): README cases 11 to 13 as test-server cases are not covered.

## Tests

21. Five tests patch `portal_common.http.request` before the first token check, so the signing keys are loaded
    through the fake and the call answers 401 (`test_readme_8_1_credential_issuer_route_needs_the_did_document_location`,
    `test_case_14_unit_request_carries_...`, three `test_readme_6_3_rule_2_non_empty_issuer_routes_...`). With the
    keys pre-loaded they pass. Resolved: the three test sites now call `tokens._load_jwks()` before they install
    their fake (a test fix; the product code is not affected).
22. `tests/test_c4_m2_flow.py` needs the real C4-M2 (Tasks A and B). Resolved: C4-M2 is merged and the flow tests pass.
    The stand-in issuer reports under the per-company lock and `flush()` waits for timers that already fired,
    so a delay of 0 no longer loses the report.
