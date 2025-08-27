# pipeline/runner.py
from __future__ import annotations

import time
import uuid
from typing import Optional

import control
from pipeline.context import PipelineContext
from pipeline.stages.fetch_stage import run_fetch_stage
from pipeline.stages.process_stage import run_process_stage
from pipeline.stages.result_stage import run_result_stage


def run_once(run_id: Optional[str] = None) -> PipelineContext:
    """
    Execute one full pipeline cycle: fetch -> process -> result.
    Returns the PipelineContext with results populated.
    """
    rid = run_id or uuid.uuid4().hex[:12]
    ctx = PipelineContext.new_run(run_id=rid)

    run_fetch_stage(ctx)
    run_process_stage(ctx)
    run_result_stage(ctx)  # no JSON export

    return ctx


def run_forever(sleep_seconds: Optional[int] = None) -> None:
    """
    Execute the pipeline in an infinite loop with a sleep between runs.
    Ctrl+C to exit.
    """
    delay = int(sleep_seconds or getattr(control, "LOOP_SLEEP_SECONDS", 180))
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("\nExiting on user interrupt.")
            break
        except Exception as e:
            # Keep the loop alive, but surface the issue.
            print(f"[runner] Unhandled error in run: {e!r}")
        time.sleep(delay)
