
"""Central settings. Everything tunable lives here (policy numbers included)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]  # backend/

# Load .env from backend directory.
# Existing environment variables take precedence over .env.
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    # --- Application data ---
    data_dir: Path = Path(
        os.getenv("DATA_DIR", str(ROOT / "data"))
    )

    # --- ERP configuration ---
    erp_db: str = os.getenv(
        "ERP_DB", str(ROOT / "data" / "erp.sqlite")
    )

    erp_url: str = os.getenv(
        "ERP_URL", "http://127.0.0.1:8001"
    )

    # --- Authentication ---
    jwt_secret: str = os.getenv(
        "JWT_SECRET", "dev-only-change-me"
    )  # prod: JWKS from IdP

    # --- MCP protocol ---
    mcp_protocol_version: str = "2026-07-28"

    # --- Business policy ---
    # Used by the deterministic policy gateway in Part 2.

    price_tolerance_pct: float = float(
        os.getenv("PRICE_TOLERANCE_PCT", "2.0")
    )

    qty_tolerance_pct: float = float(
        os.getenv("QTY_TOLERANCE_PCT", "0.0")
    )

    hitl_value_threshold: float = float(
        os.getenv("HITL_VALUE_THRESHOLD", "10000.0")
    )

    budget_usd_per_invoice: float = float(
        os.getenv("BUDGET_USD_PER_INVOICE", "0.05")
    )

    min_confidence: float = float(
        os.getenv("MIN_CONFIDENCE", "0.7")
    )

    # --- LLM configuration ---
    # FakeLLM by default => runs with no API key.

    llm_provider: str = os.getenv(
        "LLM_PROVIDER", "fake"
    )  # fake | langchain

    model_cheap: str = os.getenv(
        "MODEL_CHEAP", ""
    )  # e.g. "google_genai:<flash-model>"

    model_strong: str = os.getenv(
        "MODEL_STRONG", ""
    )  # e.g. "google_genai:<pro-model>"

    # --- MCP server ---
    mcp_url: str = os.getenv(
        "MCP_URL", "http://127.0.0.1:8002"
    )

    # --- Checkpoint database ---
    checkpoint_db: str = os.getenv(
        "CHECKPOINT_DB",
        str(ROOT / "data" / "checkpoints.sqlite")
    )


settings = Settings()
