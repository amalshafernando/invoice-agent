"""FinOps gateway: cheap-first model routing, per-invoice budget cap, telemetry."""
from ..config import settings
from . import telemetry
from .llm import cost_usd


class BudgetExceeded(Exception):
    pass


class Gateway:
    def __init__(self, llm, cap_usd: float | None = None):
        self.llm = llm
        self.cap = settings.budget_usd_per_invoice if cap_usd is None else cap_usd
        self.spent: dict[str, float] = {}
        self.tokens: dict[str, int] = {}

    @staticmethod
    def tier_for(task: str, attempt: int) -> str:
        # routine extraction/explanation -> cheap; escalate only on retry
        return "strong" if (task == "extract" and attempt > 0) else "cheap"

    def _charge(self, case_id, tier, usage):
        c = cost_usd(tier, usage)
        self.spent[case_id] = self.spent.get(case_id, 0.0) + c
        self.tokens[case_id] = self.tokens.get(case_id, 0) + usage.input_tokens + usage.output_tokens
        return c

    def _guard(self, case_id):
        if self.spent.get(case_id, 0.0) >= self.cap:
            raise BudgetExceeded(f"budget {self.cap} USD exhausted for {case_id}")

    def extract(self, case_id: str, pdf: bytes, attempt: int):
        self._guard(case_id)
        tier = self.tier_for("extract", attempt)
        with telemetry.llm_span(case_id, "extract", f"{self.llm.name}:{tier}") as box:
            ex, u = self.llm.extract(pdf, tier)
            box.update({"in": u.input_tokens, "out": u.output_tokens,
                        "cache_hit": u.cache_hit, "cost": self._charge(case_id, tier, u)})
        return ex

    def explain(self, case_id: str, facts: dict) -> str:
        self._guard(case_id)
        with telemetry.llm_span(case_id, "chat", f"{self.llm.name}:cheap") as box:
            txt, u = self.llm.explain(facts, "cheap")
            box.update({"in": u.input_tokens, "out": u.output_tokens,
                        "cache_hit": u.cache_hit, "cost": self._charge(case_id, "cheap", u)})
        return txt
