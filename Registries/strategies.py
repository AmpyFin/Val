from typing import Dict, Type, List, Any, Optional
from Strategies.base import BaseStrategy
from Strategies.peter_lynch import PeterLynchSimple
from Strategies.psales_reversion import PSalesReversion
import logging

STRATEGIES: Dict[str, Type[BaseStrategy]] = {
    "peter_lynch": PeterLynchSimple,
    "psales_rev": PSalesReversion,
}

def build_strategies(names: List[str], config: Any, logger: Optional[logging.Logger] = None) -> List[BaseStrategy]:
    out: List[BaseStrategy] = []
    for n in names:
        cls = STRATEGIES.get(n)
        if cls:
            out.append(cls(config=config, logger=logger))
        else:
            if logger:
                logger.warning(f"Strategy '{n}' not found. Skipping.")
    return out 
