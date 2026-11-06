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

# C1-M2 Registration: open questions of the implementation

| No. | Question | Spec | Reading implemented | Who decides |
|---|---|---|---|---|
| 1 | README 4 names the neighbour addresses `COMPANY_URL` and `REVIEW_URL`; the kit resolves `C3_M1_URL`, `C1_M3_URL` / `MODULE_URLS`. | README 4, FRAMEWORK 4.7, AGENTS.md rule 6 | Addresses through `portal_common.neighbours` only. | spec authors |
| 2 | `CATALOG_FILE` is unset in the kit, and its example path does not exist. C3-M1 maps key and version to `agreementId` from `testdata/agreements.json` (OP-46). | README 4, 14.3 | Without `CATALOG_FILE` the terms come from `tools/testdata`, the company roles from the constant of 14.3. A new version of 7.16 has no `agreementId` in C3-M1. | organisers, OP-46 |
| 3 | 7.2 generates the `companyId`, FRAMEWORK 7a names IDs for the test companies. | README 7.2, FRAMEWORK 7a | A test company takes its 7a ID once per installation (as the stand-in did), otherwise a new UUID. | spec authors |
| 4 | `AgreementVersionActivated` at start for a new version in `CATALOG_FILE`. | README 10 | Not published: the data is in memory, so every start begins with the initial values. | organisers |
| 5 | The attestation address has one `street_address`, the application has `streetName` and `streetNumber`. | README 6.5, C1-M3 14.2 | `street_address` goes into `streetName`, `streetNumber` stays empty (as in C1-M3 14.2). | spec authors |
| 6 | Accounts of 14.1: "bound account" and "account without permissions" are not in `testdata/`, and the kit's `OSP Reviewer` also holds `register_company`, so case 20 gives 404 for that person. | README 13, 14.1 | Tests create both accounts in the test IAM at run time; the 403 of case 20 uses the account without permissions. | organisers (testdata) |
| 7 | Persistence: README 4 asks for PostgreSQL and `bytea`; the kit keeps data in memory. One lock replaces the row locks and partial unique indexes. | README 4, 6.11 | In memory, one module-wide lock. | organisers |
| 8 | Case 11 "older than `ATTESTATION_MAX_AGE`" also applies the clock tolerance. | README 6.4 | `now - iat <= max age + ATTESTATION_CLOCK_SKEW_SECONDS`. | spec authors |
| 9 | A JWKS fetch failure at creation is 502, at the query `UNAVAILABLE`; the JWKS comes from a file without cache in tests. | README 6.4, 9.1 | As written; `ATTESTATION_JWKS_FILE` is read on every use, so removing a key takes effect at once. | spec authors |
| 10 | Reactivation on the documents path for a company with an EBWOID in C3-M1: nothing proves the EBWOID without a Business Wallet. | README 6.2, 6.6, 6.9, OP-35 | Allowed; the check applies to the EUID the person gives, and OSP staff review by hand. | spec authors, OSPs |
