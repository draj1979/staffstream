"""GitHub OAuth App — a *user* token, so every call runs against whatever
repos the employee's own GitHub account can already see (public repos,
or private ones they're a collaborator/member on). No installation
token, no org-wide credential.
"""

import httpx

from ..config import settings
from .base import Connector, ConnectorError, TokenSet, ToolSpec

_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_TOKEN_URL = "https://github.com/login/oauth/access_token"
_API_BASE = "https://api.github.com"

_SCOPES = "repo read:user"


class GitHubConnector(Connector):
    skill_id = "github"

    def is_configured(self) -> bool:
        return not settings.github_client_id.startswith("not-set")

    def tool_specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="github_list_issues",
                description="List open issues in a GitHub repo the employee has access to.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "state": {"type": "string", "description": "open|closed|all"},
                    },
                    "required": ["owner", "repo"],
                },
            ),
            ToolSpec(
                name="github_create_issue",
                description="Create an issue in a GitHub repo the employee has access to.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["owner", "repo", "title"],
                },
            ),
        ]

    def authorize_url(
        self, *, state: str, redirect_uri: str, tenant_config: dict | None = None
    ) -> str:
        params = httpx.QueryParams(
            {
                "client_id": settings.github_client_id,
                "redirect_uri": redirect_uri,
                "scope": _SCOPES,
                "state": state,
            }
        )
        return f"{_AUTHORIZE_URL}?{params}"

    async def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        http: httpx.AsyncClient,
        tenant_config: dict | None = None,
    ) -> TokenSet:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        body = resp.json()
        if "access_token" not in body:
            raise ConnectorError(f"GitHub OAuth exchange failed: {body}")

        access_token = body["access_token"]
        external_account = None
        user_resp = await http.get(
            f"{_API_BASE}/user", headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_resp.status_code < 400:
            external_account = user_resp.json().get("login")

        return TokenSet(
            access_token=access_token,
            refresh_token=None,  # classic GitHub OAuth App tokens don't expire
            expires_at=None,
            scope=body.get("scope"),
            external_account=external_account,
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
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
        }

        if tool_name == "github_list_issues":
            owner, repo = tool_input["owner"], tool_input["repo"]
            resp = await http.get(
                f"{_API_BASE}/repos/{owner}/{repo}/issues",
                params={"state": tool_input.get("state", "open")},
                headers=headers,
            )
        elif tool_name == "github_create_issue":
            owner, repo = tool_input["owner"], tool_input["repo"]
            payload = {"title": tool_input["title"]}
            if tool_input.get("body"):
                payload["body"] = tool_input["body"]
            resp = await http.post(
                f"{_API_BASE}/repos/{owner}/{repo}/issues", json=payload, headers=headers
            )
        else:
            raise ConnectorError(f"Unknown GitHub tool {tool_name!r}")

        body = resp.json()
        if resp.status_code >= 400:
            raise ConnectorError(f"GitHub API error: {body}")
        return body
