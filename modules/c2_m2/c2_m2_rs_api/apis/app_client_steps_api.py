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
#  Assisted-By: GitHub Copilot
#################################################################################
"""Steps of Process Orchestration for app clients and app roles (README 8.1 to 8.7), `execute_steps_c2_m2`."""
from abc import abstractmethod

from modules.c2_m2.c2_m2_rs_api.endpoint import Claims, JsonBody, RestApi, api


class AppClientStepsApi(RestApi):
    @api.post("/steps/create-client-template")
    @abstractmethod
    def create_client_template(self, claims: Claims, body: JsonBody) -> dict: ...

    @api.post("/steps/create-instance-client")
    @abstractmethod
    def create_instance_client(self, claims: Claims, body: JsonBody) -> dict: ...

    @api.post("/steps/enable-instance-client")
    @abstractmethod
    def enable_instance_client(self, claims: Claims, body: JsonBody) -> dict: ...

    @api.post("/steps/disable-instance-client")
    @abstractmethod
    def disable_instance_client(self, claims: Claims, body: JsonBody) -> dict: ...

    @api.post("/steps/update-instance-url")
    @abstractmethod
    def update_instance_url(self, claims: Claims, body: JsonBody) -> dict: ...

    @api.post("/steps/add-app-roles")
    @abstractmethod
    def add_app_roles(self, claims: Claims, body: JsonBody) -> dict: ...

    @api.post("/steps/update-role-descriptions")
    @abstractmethod
    def update_role_descriptions(self, claims: Claims, body: JsonBody) -> dict: ...
