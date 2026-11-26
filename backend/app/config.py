
"""Central settings. Everything tunable lives here (policy numbers included)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

@dataclass
class Settings:
    # --- Application data ---
    data_dir: Path = Path(
        os.getenv("DATA_DIR", str(BACKEND_ROOT / "data"))
    )

    # --- ERP configuration ---
    erp_db: str = os.getenv(
        "ERP_DB", str(BACKEND_ROOT / "data" / "erp.sqlite")
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

    docling_url: str = os.getenv(
        "DOCLING_URL", "http://127.0.0.1:5001"
    )

    docling_api_key: str = os.getenv("DOCLING_API_KEY", "")

    docling_timeout_s: float = float(
        os.getenv("DOCLING_TIMEOUT_S", "120")
    )

    # --- MCP server ---
    mcp_url: str = os.getenv(
        "MCP_URL", "http://127.0.0.1:8002"
    )

    # --- Checkpoint database ---
    checkpoint_db: str = os.getenv(
        "CHECKPOINT_DB",
        str(BACKEND_ROOT / "data" / "checkpoints.sqlite")
    )

    # --- Part 3: Episodic Memory, Semantic Matching & HF Guardrails ---
    memory_db: str = os.getenv(
        "MEMORY_DB",
        str(BACKEND_ROOT / "data" / "memory.sqlite")
    )
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")  # local | hf
    hf_token: str = os.getenv("HF_TOKEN", "")
    hf_embed_model: str = os.getenv("HF_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
    hf_guardrail_model: str = os.getenv(
        "HF_GUARDRAIL_MODEL", "protectai/deberta-v3-base-prompt-injection-v2"
    )
    guardrail_mode: str = os.getenv("GUARDRAIL_MODE", "hybrid")  # hybrid | hf | local
    semantic_match_threshold: float = float(
        os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.42")
    )
    manual_cost_per_invoice: float = float(
        os.getenv("MANUAL_COST_PER_INVOICE", "15.0")
    )


settings = Settings()
