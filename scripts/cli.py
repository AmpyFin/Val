# scripts/cli.py
from __future__ import annotations
import os
import argparse
import sys
from typing import Dict, List

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Load .env early if available (non-fatal if missing)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

import control
import registries.adapter_registry as ar
import registries.strategy_registry as sr
from registries.pipeline_registry import apply_pipeline_registry
from pipeline.runner import run_once, run_forever
from ui.viewer import gui_run_once, gui_run_continuous  # NEW


def _parse_metric_overrides(pairs: List[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in pairs or []:
        if "=" not in p:
            raise ValueError(f"Invalid --set '{p}'. Use METRIC=PROVIDER (e.g., eps_ttm=yfinance_eps_ttm)")
        metric, provider = p.split("=", 1)
        metric = metric.strip()
        provider = provider.strip()
        if not metric or not provider:
            raise ValueError(f"Invalid --set '{p}'. Use METRIC=PROVIDER")
        out[metric] = provider
    return out


def _print_lists() -> None:
    print("\n== Available metrics & providers ==")
    for m in ar.list_available_metrics():
        providers = ", ".join(ar.get_metric_provider_names(m))
        print(f"  {m}: {providers}")

    print("\n== Available tickers sources ==")
    print("  " + ", ".join(ar.list_tickers_sources()))

    print("\n== Available strategies ==")
    print("  " + ", ".join(sr.list_all_strategy_names()))
    print()


def _print_snapshot(tag: str) -> None:
    print(f"\n[{tag}] Current selections:")
    metrics = ar.list_available_metrics()
    snap = {
        "tickers_source": ar.get_active_tickers_source_name(),
        "metric_providers": {m: ar.get_active_metric_provider_name(m) for m in metrics},
        "enabled_strategies": sr.get_enabled_strategy_names(),
    }
    print(f"  tickers_source: {snap['tickers_source']}")
    print("  metric_providers:")
    for k, v in snap["metric_providers"].items():  # type: ignore[union-attr]
        print(f"    - {k}: {v}")
    print("  enabled_strategies: " + ", ".join(snap["enabled_strategies"]))  # type: ignore[index]


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AmpyFin Val Model CLI — switch providers/strategies at runtime and run the pipeline."
    )
    parser.add_argument("--show", action="store_true", help="Print current selections and exit.")
    parser.add_argument("--list", action="store_true", help="List all metrics/providers, tickers sources, strategies and exit.")
    parser.add_argument("--tickers-source", help="Override tickers source (e.g., list_static_tickers, wiki_spy_500_tickers).")
    parser.add_argument(
        "--set",
        dest="metric_sets",
        action="append",
        help="Override a metric provider as METRIC=PROVIDER (can repeat). Example: --set eps_ttm=yfinance_eps_ttm",
    )
    parser.add_argument(
        "--strategies",
        help="Comma-separated strategy names to enable (override). Example: --strategies peter_lynch,fcf_yield",
    )
    parser.add_argument("--run-once", action="store_true", help="Run the pipeline once (default if no run flag given).")
    parser.add_argument("--loop", action="store_true", help="Run the pipeline continuously (overrides control.Run_continous).")
    parser.add_argument("--sleep", type=int, help="Seconds to sleep between runs in --loop mode (default from control.py).")

    args = parser.parse_args(argv)

    if args.list:
        _print_lists()
        return 0

    if args.show and not any([args.tickers_source, args.metric_sets, args.strategies, args.loop, args.run_once]):
        _print_snapshot("show")
        return 0

    # Build overrides dict (only for provided flags)
    overrides: Dict[str, object] = {}
    if args.tickers_source:
        overrides["tickers_source"] = args.tickers_source
    if args.metric_sets:
        overrides["metric_providers"] = _parse_metric_overrides(args.metric_sets)
    if args.strategies:
        names = [s.strip() for s in args.strategies.split(",") if s.strip()]
        overrides["enabled_strategies"] = names

    # Apply overrides (or just snapshot if none) for logging
    selections = apply_pipeline_registry(overrides if overrides else None)
    print(f"[cli] Applied selections: {selections}")

    # If GUI mode is enabled, use the GUI loop/once runners
    if getattr(control, "GUI_MODE", False):
        if args.loop or (not args.run_once and getattr(control, "RUN_CONTINUOUS", False)):
            print("[cli] GUI mode ON → live window with periodic updates.")
            gui_run_continuous(interval_seconds=args.sleep, overrides=overrides if overrides else None)
            return 0
        else:
            print("[cli] GUI mode ON → single run shown in window.")
            gui_run_once(overrides=overrides if overrides else None)
            return 0

    # Non-GUI path
    if args.loop or (not args.run_once and getattr(control, "RUN_CONTINUOUS", False)):
        print("[cli] Entering continuous loop (no GUI)...")
        run_forever(sleep_seconds=args.sleep)
        return 0

    print("[cli] Running once (no GUI)...")
    run_once()
    return 0


if __name__ == "__main__":
    sys.exit(main())
