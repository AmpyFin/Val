from dotenv import load_dotenv
load_dotenv()

import typer
from typing import Optional, List

from core.config import load_settings
from core.logging import get_logger
from Pipeline.context import Context
from Pipeline import fetch as fetch_stage
from Pipeline import process as process_stage
from Pipeline import result as result_stage

app = typer.Typer(help="AmpyFin Val Model — run with customizable adapters & strategies")

def _parse_csv(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    return [x.strip() for x in s.split(",") if x.strip()]

def _read_tickers_file(path: str) -> List[str]:
    import re
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    parts = [p.strip() for p in re.split(r"[,\s]+", txt) if p.strip()]
    return [p.upper() for p in parts]

@app.command()
def run(
    adapters: Optional[str] = typer.Option(None, help="Comma-separated adapters, e.g. 'yfinance,alpaca'"),
    strategies: Optional[str] = typer.Option(None, help="Comma-separated strategies, e.g. 'peter_lynch,psales_rev'"),
    mode: Optional[str] = typer.Option(None, help="console|gui|broadcast"),
    run_mode: Optional[str] = typer.Option(None, "--run", help="once|continuous"),
    min_mos: Optional[float] = typer.Option(None, help="Margin of Safety threshold (0.2 = 20%)"),
    limit: int = typer.Option(50, help="Max console rows to display"),
    tickers: Optional[str] = typer.Option(None, help="Comma-separated tickers, e.g. 'AAPL,MSFT,NVDA'"),
    tickers_file: Optional[str] = typer.Option(None, help="Path to a text/csv of tickers (comma or newline separated)"),
    continuous: bool = typer.Option(False, help="Run continuously (override --run)"),
    interval: Optional[int] = typer.Option(None, help="Seconds to sleep between passes when continuous"),
):
    # Load config then apply runtime overrides
    settings = load_settings()

    a = [x.strip() for x in adapters.split(",")] if adapters else None
    s = [x.strip() for x in strategies.split(",")] if strategies else None
    if a: settings.adapters = a
    if s: settings.strategies = s
    if mode: settings.mode = mode
    if run_mode: settings.run = run_mode
    if min_mos is not None:
        settings.thresholds["min_mos"] = float(min_mos)
    if tickers:
        settings.tickers = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    elif tickers_file:
        try:
            settings.tickers = _read_tickers_file(tickers_file)
        except Exception as e:
            print(f"Failed to read tickers file '{tickers_file}': {e}")

    # Determine continuous behavior
    if continuous:
        settings.run = "continuous"
    sleep_sec = interval if interval is not None else int(settings.schedule.get("interval_sec", 60))

    logger = get_logger("ampyfin.val", level=settings.logging.get("level", "INFO"))

    def do_pass(idx: int):
        ctx = Context(tickers=settings.tickers, config=settings, logger=logger)
        logger.info(f"Val Model pass #{idx} starting")
        fetch_stage.run(ctx)
        process_stage.run(ctx)
        result_stage.run(ctx, limit=limit)
        logger.info(f"Val Model pass #{idx} completed")

    if settings.run == "continuous":
        i = 1
        try:
            while True:
                do_pass(i)
                i += 1
                logger.info(f"Sleeping {sleep_sec}s before next pass (Ctrl+C to stop)")
                import time as _time
                _time.sleep(sleep_sec)
        except KeyboardInterrupt:
            print("👋 Stopped continuous mode.")
    else:
        do_pass(1)


if __name__ == "__main__":
    app()
