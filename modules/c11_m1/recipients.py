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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""Recipients of personal notifications (README 6.1, 11.2). STARTER VERSION: nobody yet.

Still to do (owner: Rafa): the kinds of `Rule.recipients` other than `applicant` and `staff:`:
- `company_role:<field>:<portal role>`: C2-M2 `list_company_user_refs(companyId, portalRole)`, the
  `userId` of every active person (it is the `sub`);
- `it_or_company_admin:<field>`: `IT Admin`, and `Company Admin` if the company has no `IT Admin`;
- `app_customers:<field>`: C10-M1 active subscriptions of the offer, then `Company Admin` of each
  `customerCompanyId`;
- `subscription_customer:<field>`: C10-M1 subscription by id, then `Company Admin` of its customer.
A neighbour that does not answer raises `store.Unavailable`, so the worker retries the job.
"""
from __future__ import annotations


def resolve(kind: str, data: dict) -> list[str]:
    """The `sub` of every person who gets a personal notification; raises `store.Unavailable`."""
    return []
