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
"""App clients and app roles: steps 8.1 to 8.7 and queries 9.1 to 9.3 (README 6.1 to 6.4)."""
from __future__ import annotations

from modules.c2_m2.c2_m2_api.exception import (InstanceExistsException, InvalidStateException, NotFoundException,
                                               RoleNotFoundException, TemplateMissingException)
from modules.c2_m2.c2_m2_api.model import (AddAppRolesResult, AppInstanceClient as AppInstanceClientModel,
                                           AppRoles, TemplateResult, UpdateRoleDescriptionsResult)
from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_api.model.constants import InstanceClientStatus, InstanceKind
from modules.c2_m2.c2_m2_api.service import AppClientService
from modules.c2_m2.c2_m2_impl.config.properties import as_int, as_list
from modules.c2_m2.c2_m2_impl.context import Context
from modules.c2_m2.c2_m2_impl.internal.model import (AppClientTemplate, AppInstanceClient, AppRoleRepresentation,
                                                     new_id, now)
from modules.c2_m2.c2_m2_impl.utils.validation_utils import invalid


class AppClientServiceImpl(AppClientService):
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

    # -- client settings (6.3) -----------------------------------------------------------------
    @staticmethod
    def _common() -> dict:
        return {"protocol": "openid-connect", "implicitFlowEnabled": False, "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False, "fullScopeAllowed": False, "consentRequired": False,
                "frontchannelLogout": False}

    def _template_settings(self, t: AppClientTemplate) -> dict:
        return self._common() | {
            "clientId": t.iam_client_id, "name": t.app_name, "description": f"Template of app {t.app_id}. Not for sign-in.",
            "enabled": False, "publicClient": False, "standardFlowEnabled": False,
            "defaultClientScopes": [], "optionalClientScopes": []}

    @staticmethod
    def _redirect(url: str) -> list[str]:
        return [f"{url.rstrip('/')}/*"]

    def _instance_settings(self, ic: AppInstanceClient, t: AppClientTemplate) -> dict:
        description = f"App {ic.app_id}" if ic.instance_kind == InstanceKind.SINGLE else \
            f"App {ic.app_id}, subscription {ic.offer_subscription_id}"
        return self._common() | {
            "clientId": ic.iam_client_id, "name": t.app_name, "description": description, "enabled": False,
            "publicClient": True, "standardFlowEnabled": True, "baseUrl": ic.instance_url,
            "redirectUris": self._redirect(ic.instance_url), "webOrigins": ["+"],
            "attributes": {"use.refresh.tokens": "true", "backchannel.logout.session.required": "true"},
            "defaultClientScopes": list(as_list(self.ctx.config.from_properties("instance.client.default.scopes"))),
            "optionalClientScopes": list(as_list(self.ctx.config.from_properties("instance.client.optional.scopes")))}

    @staticmethod
    def _audience_mapper(client_id: str) -> dict:
        """6.3.1"""
        return {"name": f"{client_id}-mapper", "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
                "config": {"included.client.audience": client_id, "access.token.claim": "true",
                           "id.token.claim": "false"}}

    def _ensure_client(self, client_id: str, settings: dict) -> str:
        found = self.ctx.iam.find_client(client_id)
        return found["id"] if found else self.ctx.iam.create_client(settings)

    # -- roles on a client ---------------------------------------------------------------------
    def _ensure_role(self, client_uuid: str, name: str, descriptions: list[dict]) -> bool:
        """Creates the role or aligns description and attributes; True if it was created."""
        iam = self.ctx.iam
        existing = iam.client_role(client_uuid, name)
        wanted = AppRoleRepresentation.build(name, descriptions, existing)
        if existing is None:
            iam.create_client_role(client_uuid, name, wanted["description"])
            iam.update_client_role(client_uuid, name, wanted)
            return True
        if not AppRoleRepresentation.same(existing, wanted):
            iam.update_client_role(client_uuid, name, wanted)
        return False

    def _copy_role(self, client_uuid: str, template_role: dict) -> bool:
        descriptions = AppRoleRepresentation.descriptions(template_role)
        if descriptions:
            return self._ensure_role(client_uuid, template_role["name"], descriptions)
        # left over from an interrupted run without attributes; add-app-roles completes it (8.6)
        if self.ctx.iam.client_role(client_uuid, template_role["name"]) is None:
            self.ctx.iam.create_client_role(client_uuid, template_role["name"], template_role.get("description"))
            return True
        return False

    def template(self, app_id: str) -> AppClientTemplate:
        """The client template with a stored `iam_client_uuid`, otherwise `TemplateMissingException`."""
        t = self.ctx.dao.templates.get(app_id)
        if t is None or t.iam_client_uuid is None:
            raise TemplateMissingException(f"no client template for app {app_id}")
        return t

    def _instance_client(self, input: dict) -> AppInstanceClient:
        iid = self.ctx.validate.uuid(input, "appInstanceClientId")
        ic = self.ctx.dao.instance_clients.get(iid)
        if ic is None:
            raise NotFoundException(f"instance client {iid} unknown")
        return ic

    @staticmethod
    def _model(ic: AppInstanceClient) -> AppInstanceClientModel:
        return AppInstanceClientModel.model_validate(ic.to_api())

    # -- steps ---------------------------------------------------------------------------------
    def create_client_template(self, input: dict) -> TemplateResult:
        """8.1"""
        v, dao, iam = self.ctx.validate, self.ctx.dao, self.ctx.iam
        app_id = v.uuid(input, "appId")
        provider = v.uuid(input, "providerCompanyId")
        app_name = v.text(input, "appName")
        roles = v.role_inputs(input)
        actor = Actor.process(input)
        with dao.lock(("app", app_id)):
            t = dao.templates.get(app_id)
            if t is None:
                prefix = self.ctx.config.from_properties("template.client.id.prefix")
                t = AppClientTemplate(app_id, provider, app_name, f"{prefix}{app_id}")
                dao.templates.save(t)
            was_empty = t.iam_client_uuid is None
            client_uuid = self._ensure_client(t.iam_client_id, self._template_settings(t))
            created = [r["name"] for r in roles if self._ensure_role(client_uuid, r["name"], r["descriptions"])]
            t.iam_client_uuid, t.changed_at = client_uuid, now()
            dao.templates.save(t)
            names = sorted(r["name"] for r in iam.client_roles(client_uuid))
            if was_empty:
                self.ctx.audit(actor, "create-client-template", t.provider_company_id, t.app_id)
                self.ctx.publish("AppClientTemplateCreated",
                                 {"appId": app_id, "iamClientId": t.iam_client_id, "roleNames": names})
            elif created:
                self.ctx.audit(actor, "create-client-template", t.provider_company_id, t.app_id)
                self.ctx.publish("AppRolesAdded", {"appId": app_id, "roleNames": created})
        return TemplateResult(app_id=app_id, iam_client_id=t.iam_client_id, role_names=names)

    def create_instance_client(self, input: dict) -> AppInstanceClientModel:
        """8.2"""
        v, dao = self.ctx.validate, self.ctx.dao
        app_id = v.uuid(input, "appId")
        try:
            kind = InstanceKind(input.get("instanceKind"))
        except ValueError:
            raise invalid("instanceKind: SINGLE or SUBSCRIPTION") from None
        url = v.instance_url(input)
        sid, customer = v.optional_uuid(input, "offerSubscriptionId"), v.optional_uuid(input, "customerCompanyId")
        if kind == InstanceKind.SUBSCRIPTION and not (sid and customer):
            raise invalid("offerSubscriptionId and customerCompanyId are required for SUBSCRIPTION")
        if kind == InstanceKind.SINGLE and (sid or customer):
            raise invalid("offerSubscriptionId and customerCompanyId are not allowed for SINGLE")
        actor = Actor.process(input)
        with dao.lock(("app", app_id)):
            t = self.template(app_id)
            ic = dao.instance_clients.find_by_subscription(sid) if sid else dao.instance_clients.find_single(app_id)
            if ic is not None:
                if ic.status == InstanceClientStatus.DISABLED:
                    raise InvalidStateException("the instance client of this subscription is disabled")
                if (ic.app_id, ic.customer_company_id, ic.instance_url) != (app_id, customer, url):
                    raise InstanceExistsException("an instance client exists with different data")
            else:
                number = dao.instance_clients.next_client_number()   # stored before the client exists (6.1)
                ic = AppInstanceClient(new_id(), app_id, kind, sid, customer,
                                       f"{self.ctx.config.from_properties("instance.client.id.prefix")}{number}", url)
                dao.instance_clients.save(ic)
            was_empty = ic.iam_client_uuid is None
            client_uuid = self._ensure_client(ic.iam_client_id, self._instance_settings(ic, t))
            if not any(m.get("protocolMapper") == "oidc-audience-mapper"
                       for m in self.ctx.iam.protocol_mappers(client_uuid)):
                self.ctx.iam.create_protocol_mapper(client_uuid, self._audience_mapper(ic.iam_client_id))
            for role in self.ctx.iam.client_roles(t.iam_client_uuid):
                self._copy_role(client_uuid, role)
            ic.iam_client_uuid, ic.changed_at = client_uuid, now()
            dao.instance_clients.save(ic)
            if was_empty:
                self.ctx.audit(actor, "create-instance-client", customer, ic.id)
                self.ctx.publish("AppInstanceClientCreated", {
                    "appInstanceClientId": ic.id, "appId": app_id, "instanceKind": str(kind),
                    "offerSubscriptionId": sid, "customerCompanyId": customer, "iamClientId": ic.iam_client_id,
                    "instanceUrl": url})
            return self._model(ic)

    def _set_enabled(self, ic: AppInstanceClient, enabled: bool) -> None:
        client_uuid = ic.iam_client_uuid or (self.ctx.iam.find_client(ic.iam_client_id) or {}).get("id")
        if client_uuid is None:
            return
        rep = self.ctx.iam.get_client(client_uuid)
        if rep.get("enabled") != enabled:
            self.ctx.iam.update_client(client_uuid, rep | {"enabled": enabled})

    @staticmethod
    def _client_event(ic: AppInstanceClient) -> dict:
        return {"appInstanceClientId": ic.id, "appId": ic.app_id, "offerSubscriptionId": ic.offer_subscription_id,
                "iamClientId": ic.iam_client_id}

    def enable_instance_client(self, input: dict) -> AppInstanceClientModel:
        """8.3"""
        ic = self._instance_client(input)
        with self.ctx.dao.lock(("app", ic.app_id)):
            if ic.status == InstanceClientStatus.DISABLED:
                raise InvalidStateException("the instance client is disabled")
            if ic.status == InstanceClientStatus.PENDING:
                if ic.iam_client_uuid is None:
                    raise InvalidStateException("the creation of the instance client has not finished")
                self._set_enabled(ic, True)
                ic.status, ic.changed_at = InstanceClientStatus.ACTIVE, now()
                self.ctx.dao.instance_clients.save(ic)
                self.ctx.audit(Actor.process(input), "enable-instance-client", ic.customer_company_id, ic.id)
                self.ctx.publish("AppInstanceClientEnabled", self._client_event(ic))
            return self._model(ic)

    def disable_instance_client(self, input: dict) -> AppInstanceClientModel:
        """8.4: the client and the role assignments stay in the Portal IAM."""
        ic = self._instance_client(input)
        with self.ctx.dao.lock(("app", ic.app_id)):
            if ic.status != InstanceClientStatus.DISABLED:
                self._set_enabled(ic, False)
                ic.status, ic.changed_at = InstanceClientStatus.DISABLED, now()
                self.ctx.dao.instance_clients.save(ic)
                self.ctx.audit(Actor.process(input), "disable-instance-client", ic.customer_company_id, ic.id)
                self.ctx.publish("AppInstanceClientDisabled", self._client_event(ic))
            return self._model(ic)

    def update_instance_url(self, input: dict) -> AppInstanceClientModel:
        """8.5"""
        ic = self._instance_client(input)
        url = self.ctx.validate.instance_url(input)
        with self.ctx.dao.lock(("app", ic.app_id)):
            if ic.status == InstanceClientStatus.DISABLED or ic.iam_client_uuid is None:
                raise InvalidStateException("the instance client is disabled or not created")
            if ic.instance_url != url:
                rep = self.ctx.iam.get_client(ic.iam_client_uuid)
                self.ctx.iam.update_client(ic.iam_client_uuid,
                                           rep | {"baseUrl": url, "redirectUris": self._redirect(url)})
                ic.instance_url, ic.changed_at = url, now()
                self.ctx.dao.instance_clients.save(ic)
                self.ctx.audit(Actor.process(input), "update-instance-url", ic.customer_company_id, ic.id)
                self.ctx.publish("AppInstanceUrlUpdated", {
                    "appInstanceClientId": ic.id, "appId": ic.app_id, "offerSubscriptionId": ic.offer_subscription_id,
                    "instanceUrl": url})
            return self._model(ic)

    def add_app_roles(self, input: dict) -> AddAppRolesResult:
        """8.6: roles are only added; existing roles keep their descriptions."""
        app_id = self.ctx.validate.uuid(input, "appId")
        roles = self.ctx.validate.role_inputs(input)
        iam = self.ctx.iam
        with self.ctx.dao.lock(("app", app_id)):
            t = self.template(app_id)
            added, skipped = [], []
            for r in roles:
                existing = iam.client_role(t.iam_client_uuid, r["name"])
                if existing is not None and AppRoleRepresentation.descriptions(existing):
                    skipped.append(r["name"])
                    continue
                self._ensure_role(t.iam_client_uuid, r["name"], r["descriptions"])
                added.append(r["name"])
            template_roles = {r["name"]: r for r in iam.client_roles(t.iam_client_uuid)}
            for ic in self.ctx.dao.instance_clients.list_of_app(app_id):
                if ic.iam_client_uuid is None:
                    continue
                present = {r["name"] for r in iam.client_roles(ic.iam_client_uuid)}
                for name, role in template_roles.items():
                    if name not in present or name in added:
                        self._copy_role(ic.iam_client_uuid, role)
            if added:
                self.ctx.audit(Actor.process(input), "add-app-roles", t.provider_company_id, app_id)
                self.ctx.publish("AppRolesAdded", {"appId": app_id, "roleNames": added})
        return AddAppRolesResult(app_id=app_id, added_roles=added, skipped_roles=skipped)

    def update_role_descriptions(self, input: dict) -> UpdateRoleDescriptionsResult:
        """8.7"""
        app_id = self.ctx.validate.uuid(input, "appId")
        roles = self.ctx.validate.role_inputs(input)
        iam = self.ctx.iam
        with self.ctx.dao.lock(("app", app_id)):
            t = self.template(app_id)
            missing = [r["name"] for r in roles if iam.client_role(t.iam_client_uuid, r["name"]) is None]
            if missing:
                raise RoleNotFoundException(f"roles not on the template: {missing}")
            clients = [t.iam_client_uuid] + [ic.iam_client_uuid for ic in self.ctx.dao.instance_clients.list_of_app(app_id)
                                             if ic.iam_client_uuid]
            updated = []
            for r in roles:
                wanted = AppRoleRepresentation.build(r["name"], r["descriptions"])
                changed = False
                for client_uuid in clients:
                    existing = iam.client_role(client_uuid, r["name"])
                    if existing is None or not AppRoleRepresentation.same(existing, wanted):
                        self._ensure_role(client_uuid, r["name"], r["descriptions"])
                        changed = True
                if changed:
                    updated.append(r["name"])
            if updated:
                self.ctx.audit(Actor.process(input), "update-role-descriptions", t.provider_company_id, app_id)
                self.ctx.publish("AppRoleDescriptionsUpdated", {"appId": app_id, "roleNames": updated})
        return UpdateRoleDescriptionsResult(app_id=app_id, updated_roles=updated)

    # -- queries -------------------------------------------------------------------------------
    def template_roles(self, app_id: str, lang: str) -> list[dict] | None:
        """Roles of the template sorted by name, None without a template."""
        t = self.ctx.dao.templates.get(app_id)
        if t is None or t.iam_client_uuid is None:
            return None
        return sorted((AppRoleRepresentation.to_api(r, lang) for r in self.ctx.iam.client_roles(t.iam_client_uuid)),
                      key=lambda r: r["name"])

    def list_app_roles(self, app_ids: list[str], lang: str | None) -> list[AppRoles]:
        """9.1"""
        if not app_ids or len(app_ids) > as_int(self.ctx.config.from_properties("query.max.apps")):
            raise invalid(f"appId: 1 to {as_int(self.ctx.config.from_properties("query.max.apps"))} apps")
        lang = self.ctx.validate.lang(lang)
        out = []
        for app_id in app_ids:
            roles = self.template_roles(app_id, lang)
            out.append(AppRoles.model_validate({"appId": app_id, "templateExists": roles is not None,
                                                "roles": roles or []}))
        return out

    def list_app_instance_clients(self, *, app_id: str | None, offer_subscription_id: str | None,
                                  customer_company_id: str | None, instance_kind: str | None,
                                  statuses: list[str] | None) -> list[AppInstanceClientModel]:
        """9.2"""
        if not app_id and not offer_subscription_id:
            raise invalid("appId or offerSubscriptionId is required")
        wanted = set(statuses or [InstanceClientStatus.PENDING, InstanceClientStatus.ACTIVE])
        found = [c for c in self.ctx.dao.instance_clients.list_all()
                 if (not app_id or c.app_id == app_id)
                 and (not offer_subscription_id or c.offer_subscription_id == offer_subscription_id)
                 and (not customer_company_id or c.customer_company_id == customer_company_id)
                 and (not instance_kind or c.instance_kind == instance_kind) and c.status in wanted]
        return [self._model(c) for c in sorted(found, key=lambda c: c.created_at)]

    def get_app_instance_client(self, id: str) -> AppInstanceClientModel:  # noqa: A002 - openapi name
        """9.3"""
        ic = self.ctx.dao.instance_clients.get(id)
        if ic is None:
            raise NotFoundException(f"instance client {id} unknown")
        return self._model(ic)

    # -- target clients (6.10) ------------------------------------------------------------------
    def target_clients(self, company_id: str, app_id: str) -> list[AppInstanceClient]:
        subscriptions = self.ctx.subscriptions.active_subscriptions(company_id, app_id)
        if not subscriptions:
            return []
        ids = {s["offerSubscriptionId"] for s in subscriptions}
        return [c for c in self.ctx.dao.instance_clients.list_of_app(app_id)
                if c.status == InstanceClientStatus.ACTIVE and c.iam_client_uuid
                and (c.instance_kind == InstanceKind.SINGLE or c.offer_subscription_id in ids)]
