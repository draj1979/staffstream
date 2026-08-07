"""SAP S/4HANA Cloud OAuth 2.0 — per-*tenant landscape*, same shape as
ServiceNow's per-instance OAuth: SAP's authorize/token endpoints live
under the tenant's own SAP BTP subaccount URL, which comes from
`TenantSkillEnablement.config` (`{"sap_base_url": "https://my123456.s4hana.cloud.sap"}`),
set once by an admin via `PUT /skills/sap/enablement`. Every call runs as
the employee's own SAP business user against that landscape's OData
services — read/write access follows their own SAP authorizations, not
a shared service-to-service credential.
"""

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec, has_real_value

_ODATA_BUSINESS_PARTNER = "/sap/opu/odata/sap/API_BUSINESS_PARTNER/A_BusinessPartner"
_ODATA_SALES_ORDER = "/sap/opu/odata/sap/API_SALES_ORDER_SRV/A_SalesOrder"


def _require_base_url(tenant_config: dict | None) -> str:
    base_url = (tenant_config or {}).get("sap_base_url")
    if not base_url:
        raise ConnectorError(
            "SAP requires the tenant's landscape base URL to be set in this skill's "
            "enablement config, e.g. PUT /skills/sap/enablement {\"config\": "
            '{"sap_base_url": "https://my123456.s4hana.cloud.sap"}}'
        )
    return base_url.rstrip("/")


class SapConnector(Connector):
    skill_id = "sap"

    def is_configured(self) -> bool:
        return has_real_value(settings.sap_client_id)

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="sap_get_business_partners",
                description=(
                    "Look up business partners in the tenant's SAP S/4HANA Cloud landscape."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "search": {"type": "string", "description": "Name filter"},
                        "top": {"type": "integer", "description": "Max results, default 10"},
                    },
                },
            ),
            ToolSpec(
                name="sap_create_sales_order",
                description="Create a sales order in the tenant's SAP S/4HANA Cloud landscape.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "sold_to_party": {"type": "string", "description": "Customer number"},
                        "sales_organization": {"type": "string"},
                        "distribution_channel": {"type": "string"},
                    },
                    "required": ["sold_to_party", "sales_organization", "distribution_channel"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        base_url = _require_base_url(tenant_config)
        params = httpx.QueryParams(
            {
                "response_type": "code",
                "client_id": settings.sap_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
            }
        )
        return f"{base_url}/sap/bc/sec/oauth2/authorize?{params}"

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
        tenant_config: dict | None = None,
    ) -> TokenSet:
        base_url = _require_base_url(tenant_config)
        resp = await http.post(
            f"{base_url}/sap/bc/sec/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.sap_client_id,
                "client_secret": settings.sap_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"SAP OAuth exchange failed: {body}")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=None,
            scope=body.get("scope"),
            external_account=None,
            extra={"sap_base_url": base_url},
        )

    async def invoke(
        self,
        *,
        tool_name: str,
        tool_input: dict,
        access_token: str,
        http: httpx.AsyncClient,
        extra: dict | None = None,
    ) -> dict:
        extra = extra or {}
        base_url = extra.get("sap_base_url")
        if not base_url:
            raise ConnectorError("SAP connection is missing its base URL — reconnect required")

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        if tool_name == "sap_get_business_partners":
            params = {"$top": tool_input.get("top", 10), "$format": "json"}
            if tool_input.get("search"):
                params["$filter"] = f"substringof('{tool_input['search']}',BusinessPartnerFullName)"
            resp = await http.get(
                f"{base_url}{_ODATA_BUSINESS_PARTNER}", params=params, headers=headers
            )
        elif tool_name == "sap_create_sales_order":
            payload = {
                "SoldToParty": tool_input["sold_to_party"],
                "SalesOrganization": tool_input["sales_organization"],
                "DistributionChannel": tool_input["distribution_channel"],
            }
            resp = await http.post(f"{base_url}{_ODATA_SALES_ORDER}", json=payload, headers=headers)
        else:
            raise ConnectorError(f"Unknown SAP tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"SAP API error: {body}")
        return body
