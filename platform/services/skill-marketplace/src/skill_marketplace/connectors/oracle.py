"""Oracle Fusion Cloud (ERP/SCM) OAuth 2.0 via Oracle Identity Cloud
Service (IDCS) — per-*tenant landscape*, same shape as sap.py and
servicenow.py: the IDCS authorize/token endpoints live under the
tenant's own Oracle Cloud domain, which comes from
`TenantSkillEnablement.config` (`{"oracle_base_url": "https://idcs-xxxx.identity.oraclecloud.com"}`
for auth, plus `{"oracle_fusion_base_url": "https://xxxx.fa.us2.oraclecloud.com"}`
for the REST API calls themselves, since Fusion's own hostname differs
from the IDCS one). Set once by an admin via `PUT /skills/oracle/enablement`.
Every call runs as the employee's own Oracle Fusion user.
"""

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_SUPPLIERS_PATH = "/fscmRestApi/resources/11.13.18.05/suppliers"
_PURCHASE_ORDERS_PATH = "/fscmRestApi/resources/11.13.18.05/purchaseOrders"


def _require_config(tenant_config: dict | None) -> dict:
    tenant_config = tenant_config or {}
    if not tenant_config.get("oracle_base_url"):
        raise ConnectorError(
            "Oracle requires the tenant's IDCS base URL to be set in this skill's "
            "enablement config, e.g. PUT /skills/oracle/enablement {\"config\": "
            '{"oracle_base_url": "https://idcs-xxxx.identity.oraclecloud.com", '
            '"oracle_fusion_base_url": "https://xxxx.fa.us2.oraclecloud.com"}}'
        )
    return tenant_config


class OracleConnector(Connector):
    skill_id = "oracle"
    supports_refresh = True

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="oracle_get_suppliers",
                description="Look up suppliers in the tenant's Oracle Fusion Cloud landscape.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "search": {"type": "string", "description": "Supplier name filter"},
                        "limit": {"type": "integer", "description": "Max results, default 10"},
                    },
                },
            ),
            ToolSpec(
                name="oracle_create_purchase_order",
                description=(
                    "Create a purchase order in the tenant's Oracle Fusion Cloud landscape."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "supplier": {"type": "string"},
                        "buying_legal_entity": {"type": "string"},
                        "currency_code": {"type": "string", "description": "e.g. USD"},
                    },
                    "required": ["supplier", "buying_legal_entity", "currency_code"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        cfg = _require_config(tenant_config)
        base_url = cfg["oracle_base_url"].rstrip("/")
        params = httpx.QueryParams(
            {
                "response_type": "code",
                "client_id": settings.oracle_client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": "urn:opc:idm:__myscopes__",
            }
        )
        return f"{base_url}/oauth2/v1/authorize?{params}"

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
        tenant_config: dict | None = None,
    ) -> TokenSet:
        cfg = _require_config(tenant_config)
        base_url = cfg["oracle_base_url"].rstrip("/")
        resp = await http.post(
            f"{base_url}/oauth2/v1/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.oracle_client_id,
                "client_secret": settings.oracle_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"Oracle OAuth exchange failed: {body}")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=None,
            scope=body.get("scope"),
            external_account=None,
            extra={
                "oracle_base_url": base_url,
                "oracle_fusion_base_url": cfg.get("oracle_fusion_base_url", base_url),
            },
        )

    async def refresh(
        self, *, refresh_token: str, http: httpx.AsyncClient, tenant_config: dict | None = None
    ) -> TokenSet:
        cfg = _require_config(tenant_config)
        base_url = cfg["oracle_base_url"].rstrip("/")
        resp = await http.post(
            f"{base_url}/oauth2/v1/token",
            data={
                "grant_type": "refresh_token",
                "client_id": settings.oracle_client_id,
                "client_secret": settings.oracle_client_secret,
                "refresh_token": refresh_token,
            },
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"Oracle token refresh failed: {body}")
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", refresh_token),
            expires_at=None,
            scope=body.get("scope"),
            external_account=None,
            extra={
                "oracle_base_url": base_url,
                "oracle_fusion_base_url": cfg.get("oracle_fusion_base_url", base_url),
            },
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
        fusion_base = extra.get("oracle_fusion_base_url")
        if not fusion_base:
            raise ConnectorError(
                "Oracle connection is missing its Fusion base URL — reconnect required"
            )

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        if tool_name == "oracle_get_suppliers":
            params = {"limit": tool_input.get("limit", 10)}
            if tool_input.get("search"):
                params["q"] = f"SupplierName LIKE '%{tool_input['search']}%'"
            resp = await http.get(f"{fusion_base}{_SUPPLIERS_PATH}", params=params, headers=headers)
        elif tool_name == "oracle_create_purchase_order":
            payload = {
                "Supplier": tool_input["supplier"],
                "BuyingLegalEntity": tool_input["buying_legal_entity"],
                "CurrencyCode": tool_input["currency_code"],
            }
            resp = await http.post(
                f"{fusion_base}{_PURCHASE_ORDERS_PATH}", json=payload, headers=headers
            )
        else:
            raise ConnectorError(f"Unknown Oracle tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"Oracle API error: {body}")
        return body
