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
 Assisted-By: Claude Code (claude-opus-5-5)
-->

# C1-M3 Application Review: open questions of the implementation

| No. | Question | Spec | Reading implemented | Who decides |
|---|---|---|---|---|
| 1 | README 4 names the neighbour addresses `REGISTRATION_URL`, `COMPANY_URL`, `CSP_CONNECTION_URL`; the kit resolves `C1_M2_URL`, `C3_M1_URL`, `C3_M2_URL` / `MODULE_URLS`. | README 4, FRAMEWORK 4.7, AGENTS.md rule 6 | Addresses through `portal_common.neighbours` only; the names of README 4 are not read. | spec authors |
| 2 | Where is `signatureCheck`? README 6.2 says `signatureCheck.result`; the C1-M2 schema has it in `attestation` (`AttestationDetail`). | README 6.2, C1-M2 openapi `AttestationDetail` | `attestation.signatureCheck`, falling back to a top-level `signatureCheck`. | C1-M2 |
| 3 | `ATTESTATION_VALID` with `signatureCheck` `UNAVAILABLE` gives `ERROR`, so `open-review` answers 502 `upstream-error` and Process Orchestration repeats until the JWKS is back. | README 6.2, 8.1 | As written. | OSPs, C12-M1 |
| 4 | `open-review` reads the application again only while the case is new or `OPEN`; for a decided or closed case it reads nothing (8.1 step 1 reads always). | README 8.1 | No read for a case that is not `OPEN`: nothing would change, and a closed case of a withdrawn application should not fail on C1-M2. | spec authors |
| 6 | A2 to A17 of 14.2 have no fixed `id`, `companyId`, EBWOID and EUID. | README 14.2 | Derived deterministic IDs in the tests (`standin.stable_id`). | spec authors |
| 7 | `expected` in `cspMatches` for outcomes other than `EXPECTED_MATCH`. | README 6.3 | `true` only for the match of `EXPECTED_MATCH`, otherwise `false` for every match. | spec authors |
| 8 | 7.3 step 2 reads the status at C1-M2 before the row lock; an unknown application (empty summary) is not withdrawn. | README 7.3 | Decision continues if C1-M2 does not know the application. | C1-M2 |
| 9 | No event for `AWAITING_SECOND_APPROVAL`, so Notifications cannot tell the second reviewer. | OP-49 | No event, as in README 10. | other part |
| 10 | Persistence: README 4 asks for PostgreSQL `c1_m3`; the hackathon kit keeps data in memory. One lock replaces `SELECT … FOR UPDATE`. | README 4, 6.8 | In memory, one module-wide lock. | organisers |
| 11 | A neighbour that rejects the request (4xx): README 8.1 says a check with `ERROR` always answers 502 `upstream-error` with `retryable` `true`; the error rule of the kit gives `neighbour-rejected` with `retryable` `false`. | README 8.1, 12; `portal_common.neighbours` | If every check with `ERROR` was rejected: 502 `neighbour-rejected`, `retryable` `false`, so Process Orchestration does not repeat in vain; the check stays `ERROR` and a repetition runs it again. With a temporary error among them: 502 `upstream-error`, `retryable` `true`. | spec authors, C12-M1 |
