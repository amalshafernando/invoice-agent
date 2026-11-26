"""OAuth2 client-credentials (mock IdP) + deny-by-default scope checks."""
import time
import jwt
from fastapi import Header, HTTPException
from pydantic import BaseModel

from .config import settings

# client registry: which scopes each client MAY ever receive (least privilege)
CLIENTS: dict[str, dict] = {
    "invoice-agent": {
        "secret": "agent-secret",
        "allowed": {"read:po", "read:supplier", "read:invoice",
                    "write:invoice_draft", "write:ticket"},
    },
    "finance-ui": {
        "secret": "ui-secret",
        "allowed": {"read:po", "read:supplier", "read:invoice", "admin:audit"},
    },
    # the MCP server's own identity towards the ERP (NO token passthrough!)
    "mcp-server": {
        "secret": "mcp-secret",
        "allowed": {"read:po", "read:supplier", "read:invoice",
                    "write:invoice_draft", "write:ticket"},
    },
}


class Principal(BaseModel):
    sub: str
    scopes: set[str]


def issue_token(client_id: str, secret: str, requested: list[str], ttl: int = 900) -> str:
    client = CLIENTS.get(client_id)
    if not client or client["secret"] != secret:
        raise HTTPException(401, "invalid_client")
    bad = [s for s in requested if s not in client["allowed"]]
    if bad or not requested:
        raise HTTPException(400, f"invalid_scope: {bad or 'none requested'}")
    now = int(time.time())
    return jwt.encode(
        {"sub": client_id, "scope": " ".join(requested), "iat": now,
         "exp": now + ttl, "iss": "mock-ifs-idp"},
        settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Principal:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"],
                            issuer="mock-ifs-idp")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid_token: {e}")
    return Principal(sub=claims["sub"], scopes=set(claims.get("scope", "").split()))


def principal_from_header(authorization: str | None) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    return decode_token(authorization.split(" ", 1)[1])


def require_scope(scope: str):
    """FastAPI dependency factory. A route WITHOUT this dependency is a bug."""
    def dep(authorization: str | None = Header(default=None)) -> Principal:
        p = principal_from_header(authorization)
        if scope not in p.scopes:
            raise HTTPException(403, f"insufficient_scope: need {scope}")
        return p
    return dep
