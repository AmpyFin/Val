from typing import Dict, Type, List, Any, Optional
from Adapters.base import BaseAdapter
from Adapters.mock_local import MockLocalAdapter
from Adapters.polygon import PolygonAdapter
from Adapters.fmp import FMPAdapter
from Adapters.alpaca import AlpacaAdapter
from Adapters.yfinance import YFinanceAdapter
from Adapters.ibkr_webapi import IBKRAdapter
import logging


ADAPTERS: Dict[str, Type[BaseAdapter]] = {
    "yfinance": YFinanceAdapter,
    "alpaca": AlpacaAdapter,
    "polygon": PolygonAdapter,
    "fmp": FMPAdapter,
    "ibkr": IBKRAdapter,           # add this
    "mock_local": MockLocalAdapter,
}

def build_adapters(names: List[str], config: Any, logger: Optional[logging.Logger] = None) -> List[BaseAdapter]:
    out: List[BaseAdapter] = []
    for n in names:
        cls = ADAPTERS.get(n)
        if cls:
            out.append(cls(config=config, logger=logger))
        else:
            if logger:
                logger.warning(f"Adapter '{n}' not found. Skipping.")
    return out
