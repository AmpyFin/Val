# pipeline/context.py
"""
AmpyFin — Val Model
Pipeline Context

A simple, typed container that each stage (fetch → process → result) reads/writes.
Use this instead of passing loose dicts between stages.

Typical flow per run:
    ctx = PipelineContext.new_run()
    run_fetch_stage(ctx)
    run_process_stage(ctx)
    run_result_stage(ctx)

Stages should only touch their own sections (fetch/process/result) and avoid
overwriting others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PipelineContext:
    # ---- Run identifiers / metadata ----
    run_id: str = ""                       # optional unique ID per run
    generated_at: Optional[float] = None   # epoch seconds, filled by result stage
    generated_at_iso: Optional[str] = None # ISO8601, filled by result stage

    # ---- Fetch stage outputs ----
    tickers: List[str] = field(default_factory=list)
    required_metrics: List[str] = field(default_factory=list)
    metrics_by_ticker: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)
    fetch_errors: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # ---- Process stage inputs/outputs ----
    strategy_names: List[str] = field(default_factory=list)
    # Optional per-strategy runtime overrides (e.g., {"peter_lynch": {"max_growth_pe": 30}})
    hyperparam_overrides: Dict[str, Dict[str, float]] = field(default_factory=dict)

    fair_values: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)
    strategy_errors: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # ---- Result stage outputs ----
    results_by_ticker: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    side_effects: Dict[str, Optional[str]] = field(
        default_factory=lambda: {"json_path": None, "broadcast": None, "gui": None}
    )

    # ------------------------------------------------------------------
    # Lifecycle helpers

    @classmethod
    def new_run(cls, run_id: str = "") -> "PipelineContext":
        """Factory for a fresh context instance."""
        return cls(run_id=run_id)

    # Reset sections (useful when running continuously)
    def reset_fetch(self) -> None:
        self.tickers.clear()
        self.required_metrics.clear()
        self.metrics_by_ticker.clear()
        self.fetch_errors.clear()

    def reset_process(self) -> None:
        self.strategy_names.clear()
        self.fair_values.clear()
        self.strategy_errors.clear()

    def reset_results(self) -> None:
        self.results_by_ticker.clear()
        self.side_effects = {"json_path": None, "broadcast": None, "gui": None}
        self.generated_at = None
        self.generated_at_iso = None
