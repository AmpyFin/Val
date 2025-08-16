from dataclasses import dataclass, field
from typing import Dict, Any, List, Union
import logging

@dataclass
class Context:
    tickers: List[str]
    raw: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    derived: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    valuations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    config: Any = None
    logger: Union[logging.Logger, None] = None
