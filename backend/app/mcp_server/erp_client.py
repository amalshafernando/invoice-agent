"""MCP server's own identity towards the ERP (no token passthrough)."""
import time
import httpx
from ..config import settings

ALL = "read:po read:supplier read:invoice write:invoice_draft write:ticket"


class ErpClient:
    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(base_url=settings.erp_url, timeout=10)
        self._tok, self._exp = "", 0.0

    def _auth(self) -> dict:
        if time.time() > self._exp - 30:
            r = self.http.post("/oauth/token", data={
                "grant_type": "client_credentials", "client_id": "mcp-server",
                "client_secret": "mcp-secret", "scope": ALL})
            r.raise_for_status()
            self._tok, self._exp = r.json()["access_token"], time.time() + 900
        return {"Authorization": f"Bearer {self._tok}"}

    def get(self, path: str, **params) -> httpx.Response:
        return self.http.get(path, params=params or None, headers=self._auth())

    def post(self, path: str, json: dict) -> httpx.Response:
        return self.http.post(path, json=json, headers=self._auth())
