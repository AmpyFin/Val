# main.py
from __future__ import annotations

import sys

import control

# Load .env early if python-dotenv is available (non-fatal if missing)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from registries.pipeline_registry import apply_pipeline_registry
from pipeline.runner import run_once, run_forever


def main() -> int:
    # Enforce selections for adapters/strategies/tickers source
    selections = apply_pipeline_registry()
    print(f"[main] Applied pipeline selections: {selections}")

    if getattr(control, "RUN_CONTINUOUS", False):
        print("[main] RUN_CONTINUOUS=True → entering loop.")
        run_forever()
        return 0
    else:
        print("[main] RUN_CONTINUOUS=False → single run.")
        run_once()
        return 0


if __name__ == "__main__":
    sys.exit(main())
