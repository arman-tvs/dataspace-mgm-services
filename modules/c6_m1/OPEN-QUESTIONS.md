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

# C6-M1 Connectors: open questions of the implementation

Points where the spec (`spec/C6-M1-Connector`, version 0.2) is unclear or where the hackathon scaffold
differs from it. Each point names the reading that is implemented and who could decide it.

| No. | Question | Spec | Implemented reading | To decide with |
|---|---|---|---|---|
| 1 | Storage: README 4 names an own PostgreSQL database `c6_m1`. | README 4, 5 | In memory (`interface.connectors`, `interface.audit`), as every module of the scaffold; cleared in `reset()`. `DATABASE_URL` is not read. | scaffold / spec authors |
| 2 | Country list for `location` (OP-13): README 4 points to `SETTINGS_FILE`, the installation settings of the scaffold have no country list. | README 4, 6.2 | The codes of `countries` in the file named by `masterDataFile` of the installation settings (`config/master-data.json`: `DE`, `US`). Without that file: any two capital letters (pattern of openapi.yaml). | C3-M1 (reference data), spec authors |
| 3 | Uniqueness of `name` with `endpoint`: README 5 does not say whether `INACTIVE` connectors count; for `technical_user_id` and `offer_subscription_id` it says "only among connectors that are not `INACTIVE`". | README 5, 6.2, case 10 | Only connectors that are not `INACTIVE` count, also for `name` with `endpoint`, so that case 10 (new connector for the same subscription after delete) works with the same data. | spec authors |
| 4 | Host company unknown to C3-M1 (C3-M1 answers 404). | README 6.2, 11 | Treated as "not `ACTIVE`": 409 `company-not-active`. Other errors of C3-M1 stay 502 (shared error rule of `portal_common.neighbours`). | C3-M1 |
| 5 | Neighbour addresses: README 4 names `COMPANY_URL`, `TECHNICAL_USER_URL`, `SUBSCRIPTION_URL`; `portal_common.neighbours` reads `C3_M1_URL`, `C2_M3_URL`, `C10_M1_URL` (AGENTS.md rule 6). | README 4, FRAMEWORK 4.7 | The module does not read address variables itself; `neighbours.query` / `neighbours.is_standin` resolve them. | scaffold |
| 6 | Built-in stand-ins (empty address, README 11): the files `stub-companies.json` and `stub-subscriptions.json` are named but not specified. | README 11 | `modules/c6_m1/stub-companies.json` (`companies`: companyId → status; default `ACTIVE`) and `modules/c6_m1/stub-subscriptions.json` (`subscriptions` with `offerSubscriptionId`, `status`, `providerCompanyId`, `customerCompanyId`; the subscription of README 14). | spec authors |
| 7 | Delete of a connector as a service whose subscription C10-M1 no longer knows (404). | README 6.2, 7.6 | Counts as "not `ACTIVE`": the connector becomes `INACTIVE`, the link stays, `ConnectorDeactivated`. | C10-M1 |
| 8 | Step 8.1 result on repetition: README 8.1 says "`DONE` with `connectorIds`" without saying which. | README 8.1, 8.2, FRAMEWORK 4.4 | `connectorIds` lists the connectors changed by this call; a repetition answers `DONE` with an empty list, as README 8.2 says for its step. | C12-M1 |
| 9 | Step 8.2 changes the connector but README 10 names no event for it. | README 8.2, 10 | No event; only `changedAt` and the audit log. | spec authors |
| 10 | `PATCH` of the endpoint to a value that another live connector with the same name already has. | README 6.2, 7.5 | 409 `duplicate`, as at registration. | spec authors |
| 11 | Hackathon scope: the hackathon page names company connectors only (no subscriptions on the day). | hackathon page | Connector as a service (7.3) and step 8.1 are implemented as well, against C10-M1 (in-process stand-in or the built-in stand-in of README 11). | – |
