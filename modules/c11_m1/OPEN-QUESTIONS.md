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

# C11-M1 Notifications: open questions

Points where the spec (`spec/C11-M1-Notifications/README.md`, as of 6 Nov 2026) leaves a choice, and
the reading this implementation uses. A spec change goes to the spec repository, not here.

| No. | Question | Spec | What this implementation does |
|---|---|---|---|
| 1 | Persistence | README 4, 5 | Data in memory, not in the database `c11_m1`. A restart loses the inbox, the applicants, the processed event ids and queued jobs. `RETENTION_DAYS` is not applied yet. |
| 2 | Subject and company of each rule | README 5 (`subject_type`, `subject_id`, `company_id`), 6.2 | 6.2 does not name them per rule. `rules.py` sets them per rule: the object the rule is about (for example `OFFER` / `offerId` for R6 to R8, `COMPANY` / `companyId` for R15), and the company field the recipients come from. |
| 3 | `companyId` without a company field | README 5 | R12, R13 and R17 events carry no company field that the rule uses, so `companyId` is empty (`null`). |
| 4 | `done` of an information | README 5, openapi `Notification.done` | `null` for topic `INFO`, in 7.1 and in `notification-created`; `true`/`false` only for tasks. |
| 5 | Delivery that keeps failing | README 4 | After 10 attempts the job is logged as not delivered (rule id and event id only). The event keeps `processed_event.status` `DONE`, because the event itself was processed. |
| 6 | Remembered closing events | README 6.2 | Kept 24 hours in memory. An event without `time` counts as received now. |
| 7 | `applicantSub` in `content` | README 5 (`content`: "never names") | `content` is the whole `data` of the event, so R2 (a staff task) carries the `sub` of the applicant. It is an ID, not a name, and the reviewer needs no person data; to be confirmed. |
| 8 | Second approval of an offer | OP-49 | No event exists for it, so there is no notification. |
| 9 | Staff permission removed while a stream is open | README 7.6 | The stream uses the permissions of the token that opened it until `exp`; the next token decides. |
