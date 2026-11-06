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
#  Assisted-By: GitHub Copilot (claude-opus-5-5)
#################################################################################
from __future__ import annotations

import threading
import time
from urllib.parse import quote

import httpx

from modules.c2_m2.c2_m2_impl.config import Config
from modules.c2_m2.c2_m2_impl.internal.services import PortalIam, iam_error
from portal_common import http, tokens

PAGE = 100


class KeycloakPortalIam(PortalIam):
    """Keycloak Admin REST API under `{IAM_URL}/admin/realms/{IAM_REALM}`, with the service account `C2_M2_CLIENT_ID`."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._token: tuple[str, float] | None = None

    def _realm_url(self, admin: bool = False) -> str:
        base = self.config.from_properties("iam.url").rstrip("/")
        realm = self.config.from_properties("iam.realm") or tokens.realm()
        return f"{base}/admin/realms/{realm}" if admin else f"{base}/realms/{realm}"

    def _access_token(self) -> str:
        with self._lock:
            if self._token and self._token[1] > time.time() + 30:
                return self._token[0]
        url = f"{self._realm_url()}/protocol/openid-connect/token"
        # test installation fallback: the shared secret of the service accounts (C2-M5 14.1)
        secret = self.config.from_properties("c2-m2.client.secret") or tokens.DEFAULT_SERVICE_SECRET
        try:
            r = http.request("POST", url, data={"grant_type": "client_credentials",
                                                "client_id": self.config.from_properties("c2-m2.client.id"),
                                                "client_secret": secret})
        except httpx.HTTPError as e:
            raise iam_error(f"token endpoint: {type(e).__name__}") from e
        if r.status_code != 200:
            raise iam_error(f"token endpoint answered {r.status_code}")
        body = r.json()
        with self._lock:
            self._token = (body["access_token"], time.time() + int(body.get("expires_in", 60)))
        return body["access_token"]

    def _call(self, method: str, path: str, ok: tuple[int, ...] = (200, 201, 204), allow_404: bool = False,
              **kw) -> httpx.Response | None:
        url = f"{self._realm_url(admin=True)}{path}"
        try:
            r = http.request(method, url, headers={"Authorization": f"Bearer {self._access_token()}"}, **kw)
        except httpx.HTTPError as e:
            raise iam_error(f"{method} {path}: {type(e).__name__}") from e
        if allow_404 and r.status_code == 404:
            return None
        if r.status_code not in ok:
            raise iam_error(f"{method} {path} answered {r.status_code}")
        return r

    def find_client(self, client_id: str) -> dict | None:
        found = self._call("GET", "/clients", params={"clientId": client_id}).json()
        return found[0] if found else None

    def create_client(self, representation: dict) -> str:
        r = self._call("POST", "/clients", ok=(201, 409), json=representation)
        if r.status_code == 409:   # created by an interrupted run: find it again by client ID
            found = self.find_client(representation["clientId"])
            if not found:
                raise iam_error("client exists but cannot be found")
            return found["id"]
        return r.headers["Location"].rstrip("/").rsplit("/", 1)[-1]

    def get_client(self, uuid: str) -> dict:
        return self._call("GET", f"/clients/{uuid}").json()

    def update_client(self, uuid: str, representation: dict) -> None:
        self._call("PUT", f"/clients/{uuid}", json=representation)

    def protocol_mappers(self, uuid: str) -> list[dict]:
        return self._call("GET", f"/clients/{uuid}/protocol-mappers/models").json()

    def create_protocol_mapper(self, uuid: str, mapper: dict) -> None:
        self._call("POST", f"/clients/{uuid}/protocol-mappers/models", ok=(201, 409), json=mapper)

    def client_roles(self, uuid: str) -> list[dict]:
        return self._call("GET", f"/clients/{uuid}/roles", params={"briefRepresentation": "false", "max": 1000}).json()

    def client_role(self, uuid: str, name: str) -> dict | None:
        r = self._call("GET", f"/clients/{uuid}/roles/{quote(name, safe='')}", allow_404=True)
        return r.json() if r is not None else None

    def create_client_role(self, uuid: str, name: str, description: str | None) -> None:
        self._call("POST", f"/clients/{uuid}/roles", ok=(201, 409), json={"name": name, "description": description})

    def update_client_role(self, uuid: str, name: str, representation: dict) -> None:
        self._call("PUT", f"/clients/{uuid}/roles/{quote(name, safe='')}", json=representation)

    def users_with_client_role(self, uuid: str, name: str) -> list[dict]:
        out, first = [], 0
        while True:
            r = self._call("GET", f"/clients/{uuid}/roles/{quote(name, safe='')}/users", allow_404=True,
                           params={"first": first, "max": PAGE})
            page = r.json() if r is not None else []
            if not page:
                return out
            out += page
            first += PAGE

    def get_user(self, user_id: str) -> dict | None:
        r = self._call("GET", f"/users/{user_id}", allow_404=True)
        return r.json() if r is not None else None

    def update_user(self, user_id: str, representation: dict) -> None:
        self._call("PUT", f"/users/{user_id}", json=representation)

    def logout_user(self, user_id: str) -> None:
        self._call("POST", f"/users/{user_id}/logout", allow_404=True)

    def role_mappings(self, user_id: str) -> dict | None:
        r = self._call("GET", f"/users/{user_id}/role-mappings", allow_404=True)
        return r.json() if r is not None else None

    def client_role_mappings(self, user_id: str, uuid: str) -> list[dict]:
        return self._call("GET", f"/users/{user_id}/role-mappings/clients/{uuid}").json()

    def add_client_role_mappings(self, user_id: str, uuid: str, roles: list[dict]) -> None:
        self._call("POST", f"/users/{user_id}/role-mappings/clients/{uuid}",
                   json=[{"id": r["id"], "name": r["name"]} for r in roles])

    def remove_client_role_mappings(self, user_id: str, uuid: str, roles: list[dict]) -> None:
        self._call("DELETE", f"/users/{user_id}/role-mappings/clients/{uuid}",
                   json=[{"id": r["id"], "name": r["name"]} for r in roles])
