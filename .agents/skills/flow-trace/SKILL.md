---
name: flow-trace
description: Trace the flows of Process Orchestration (C12-M1 flows.yaml) across the portal modules - onboarding, transfer, return, reactivation, deactivation, wallet access, app approval, subscriptions, connectors in the discovery. Use for "what happens after ApplicationApproved", "which module runs next", "why does the process wait", "which steps does C4-M2 take part in", "which flow does this event start", "where does the bpn input of assign-identifier come from", "is flows.yaml consistent with the specs", or to explain a process state the UI shows.
---

<!--
 Copyright (c) 2026 Catena-X Automotive Network e.V.
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

# Flow trace

Flows are data (FRAMEWORK 1): every step runs through Process Orchestration (C12-M1), modules only describe their
steps with preconditions, and an event moves the process on. This skill reads `flows.yaml` and joins it with the module
specs and the event catalogue, so a question like "why is my company still `REQUESTED`" gets an exact answer.

```bash
F=.agents/skills/flow-trace/scripts/flow-trace.py
$F list                         # 25 flows: trigger (with condition), subject, steps, early end
$F show onboarding              # step by step: module, condition, waitFor, completesOn/failsOn, every input source
$F module c3-m2                 # every step of C3-M2 in every flow, the lookups that query it, flows its events start
$F event ApplicationApproved    # which flows the event starts, unblocks, completes, fails or ends
$F check                        # flows.yaml against the specs, like C12-M1 at start-up (README 6.2); exit 1 on a problem
```

## How to read a flow

| Field | Meaning (C12-M1 README 6.1) |
|---|---|
| `trigger` | event (with `when` condition on the fields of its `data`) that starts a process |
| `subject`, `correlateBy` | what the process is about; which field of `data` assigns later events to it |
| `when` on a step | the step runs only if the condition holds, otherwise `SKIPPED` |
| `waitFor` | the step waits for this event (e.g. the decision `ApplicationApproved`); no time limit |
| `completesOn` / `failsOn` | events that end a `RUNNING` (long-running) step; `set` adds process variables |
| `endOn` | events that end the process early, but only while a `waitFor` event is still open (6.5) |
| input sources | `name` process variable, `steps.<key>.<field>` earlier result, `lookup.<name>.<field>` query, `=VALUE` fixed |

## Diagnosing a stuck process

1. `show <flow>` and find the step: which module, which event it waits for or completes on.
2. A `waitFor` step waits for a human decision or a callback; a `completesOn` step waits for the module's own event.
   Check that the module published it with the exact name in `type` and the `correlateBy` field in `data` (events are
   CloudEvents, FRAMEWORK 6; `GET /scaffold/events?type=<Name>` in the scaffold lists what was published).
3. An input with no source value is left out; if the step needs it, the step answers 400 and the run is `FAILED`
   (README 6.1). Follow the source back with `show`.
4. Retries: `retryable: true` errors are retried with back-off up to `maxAttempts`; `false` is final, OSP staff can
   retrigger (`POST /api/c12-m1/processes/{processId}/steps/{stepKey}/retrigger`, `retrigger_process_steps`).
5. In the UI, the process state arrives as SSE event `process-changed` (C12-M1 7.6 to 7.8); the UI never decides the
   next step itself.

## Requirements

Same as `portal-spec-sources` (python3 + PyYAML, the backend spec; `FLOWS_FILE` replaces flows.yaml like in the scaffold).
