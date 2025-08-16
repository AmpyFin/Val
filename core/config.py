from pydantic import BaseModel, Field
from typing import List, Dict, Any
import yaml
import os

class Settings(BaseModel):
    mode: str = Field(default='console')
    run: str = Field(default='once')
    adapters: List[str] = Field(default_factory=lambda: ['mock_local'])
    strategies: List[str] = Field(default_factory=lambda: ['peter_lynch', 'psales_rev'])
    tickers: List[str] = Field(default_factory=lambda: ['AAPL', 'MSFT', 'NVDA'])

    thresholds: Dict[str, float] = Field(default_factory=lambda: {'min_mos': 0.20})
    caps: Dict[str, float] = Field(default_factory=lambda: {
        'max_growth_pe': 50.0,
        'min_growth_pe': 5.0,
        # keep these if you added them earlier; otherwise they’re harmless defaults
        'max_ps_fair': 15.0,
        'min_ps_fair': 0.3
    })

    schedule: Dict[str, int] = Field(default_factory=lambda: {'interval_sec': 60})
    logging: Dict[str, Any] = Field(default_factory=lambda: {'level': 'INFO'})

    # Dynamic weighting configuration
    weighting: Dict[str, Any] = Field(default_factory=lambda: {
        'low_margin_threshold': 0.05,
        'high_margin_threshold': 0.10,
        'negative_growth_penalty': 0.3,
        'high_growth_boost': 0.2,
        'default_peter_lynch_weight': 0.5,
        'default_psales_weight': 0.5
    })

    # optional flags (ok if you didn't add to YAML)
    data: Dict[str, Any] = Field(default_factory=lambda: {
        'allow_mock_fundamentals': False
    })

    # ✅ NEW: outputs config so YAML is respected
    outputs: Dict[str, Any] = Field(default_factory=lambda: {
        'json_path': 'out/results.json',
        'include_per_strategy': True
    })

def load_settings(path: str = 'config/settings.yaml'):
    fallback = 'config/settings.example.yaml'
    cfg_path = path if os.path.exists(path) else fallback
    with open(cfg_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    return Settings(**raw or {})
