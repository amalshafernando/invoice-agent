"""Central settings. Everything tunable lives here (policy numbers included)."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # backend/


@dataclass
class Settings:
    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT / "data"))
    erp_db: str = os.getenv("ERP_DB", str(ROOT / "data" / "erp.sqlite"))
    erp_url: str = os.getenv("ERP_URL", "http://127.0.0.1:8001")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-change-me")  # prod: JWKS from IdP
    mcp_protocol_version: str = "2026-07-28"
    # --- business policy (used by the deterministic policy gateway in Part 2) ---
    price_tolerance_pct: float = 2.0
    qty_tolerance_pct: float = 0.0
    hitl_value_threshold: float = 10_000.0
    budget_usd_per_invoice: float = 0.05
    min_confidence: float = 0.7
    # --- LLM (FakeLLM by default => runs with no API key) ---
    llm_provider: str = os.getenv("LLM_PROVIDER", "fake")        # fake | langchain
    model_cheap: str = os.getenv("MODEL_CHEAP", "")              # e.g. "google_genai:<flash-model>"
    model_strong: str = os.getenv("MODEL_STRONG", "")            # e.g. "google_genai:<pro-model>"
    mcp_url: str = os.getenv("MCP_URL", "http://127.0.0.1:8002")
    checkpoint_db: str = os.getenv("CHECKPOINT_DB", str(ROOT / "data" / "checkpoints.sqlite"))


settings = Settings()
