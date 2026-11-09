#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
"""The C3-M1 gateway of C2-M2 (README 11.2): None is 404, an object is the company, any other answer is an
upstream error, as the subscriptions gateway already treats its answer."""
import pytest

from modules.c2_m2.c2_m2_api.exception import UpstreamErrorException
from modules.c2_m2.c2_m2_impl.impl import CompanyProfileGatewayImpl, neighbour_gateway

COMPANY = "c0000001-0000-4000-8000-000000000001"


@pytest.fixture
def answer(monkeypatch):
    """Lets the neighbour C3-M1 answer what the test sets; C3-M1 counts as reachable (no built-in stand-in)."""
    box: dict[str, object] = {}
    monkeypatch.setattr(neighbour_gateway.neighbours, "is_standin", lambda target: False)
    monkeypatch.setattr(neighbour_gateway.neighbours, "query", lambda *a, **k: box["value"])
    return box


def test_an_object_is_the_company_and_none_is_unknown(answer):
    gateway = CompanyProfileGatewayImpl()
    answer["value"] = {"id": COMPANY, "status": "ACTIVE", "bpn": "BPNLIUK2REMLK3F4"}
    assert gateway.company(COMPANY) == answer["value"]
    answer["value"] = None
    assert gateway.company(COMPANY) is None


@pytest.mark.parametrize("value", [[{"id": COMPANY}], "ACTIVE", 7])
def test_any_other_answer_is_a_retryable_upstream_error(answer, value):
    answer["value"] = value
    with pytest.raises(UpstreamErrorException) as error:
        CompanyProfileGatewayImpl().company(COMPANY)
    assert error.value.retryable is True
