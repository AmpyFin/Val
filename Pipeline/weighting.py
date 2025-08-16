# Pipeline/weighting.py
from __future__ import annotations
from typing import Dict, Tuple, Optional
import logging

def calculate_strategy_weights(data: Dict[str, any], config: any) -> Tuple[float, float]:
    """
    Calculate dynamic weights for Peter Lynch vs P/S Reversion strategies
    based on company characteristics.
    
    Returns: (peter_lynch_weight, psales_weight) where weights sum to 1.0
    """
    net_margin = data.get("net_margin")
    growth_pct = data.get("growth_pct")
    eps_ttm = data.get("eps_ttm")
    
    # Get configuration values with defaults
    weighting_config = getattr(config, 'weighting', {})
    low_margin_threshold = weighting_config.get('low_margin_threshold', 0.05)
    high_margin_threshold = weighting_config.get('high_margin_threshold', 0.10)
    negative_growth_penalty = weighting_config.get('negative_growth_penalty', 0.3)
    high_growth_boost = weighting_config.get('high_growth_boost', 0.2)
    default_pl_weight = weighting_config.get('default_peter_lynch_weight', 0.5)
    default_ps_weight = weighting_config.get('default_psales_weight', 0.5)
    
    # Default weights
    peter_lynch_weight = default_pl_weight
    psales_weight = default_ps_weight
    
    # If we have net margin data, use it for weighting
    if net_margin is not None:
        if net_margin < low_margin_threshold:  # < 5% net margin
            # Favor P/S reversion for low-margin companies
            peter_lynch_weight = 0.2
            psales_weight = 0.8
        elif net_margin > high_margin_threshold:  # > 10% net margin
            # Favor Peter Lynch for high-margin companies
            peter_lynch_weight = 0.8
            psales_weight = 0.2
        else:  # 5-10% net margin
            # Balanced approach
            peter_lynch_weight = 0.6
            psales_weight = 0.4
    
    # Adjust based on earnings growth if available
    if growth_pct is not None:
        if growth_pct < 0:  # Negative growth
            # Favor P/S reversion when earnings are declining
            peter_lynch_weight = max(0.1, peter_lynch_weight - negative_growth_penalty)
            psales_weight = min(0.9, psales_weight + negative_growth_penalty)
        elif growth_pct > 15:  # High growth
            # Favor Peter Lynch for high-growth companies
            peter_lynch_weight = min(0.9, peter_lynch_weight + high_growth_boost)
            psales_weight = max(0.1, psales_weight - high_growth_boost)
    
    # Adjust based on earnings quality
    if eps_ttm is not None and eps_ttm <= 0:
        # Negative EPS - heavily favor P/S reversion
        peter_lynch_weight = 0.1
        psales_weight = 0.9
    
    # Normalize weights to sum to 1.0
    total = peter_lynch_weight + psales_weight
    if total > 0:
        peter_lynch_weight /= total
        psales_weight /= total
    
    return peter_lynch_weight, psales_weight

def apply_weighted_valuation(
    valuations: Dict[str, float], 
    weights: Tuple[float, float],
    logger: Optional[logging.Logger] = None
) -> Optional[float]:
    """
    Apply weighted average to strategy valuations.
    
    Args:
        valuations: Dict mapping strategy names to fair values
        weights: Tuple of (peter_lynch_weight, psales_weight)
        logger: Optional logger for debugging
    
    Returns:
        Weighted average fair value or None if insufficient data
    """
    peter_lynch_fv = valuations.get("peter_lynch")
    psales_fv = valuations.get("psales_rev")
    
    peter_lynch_weight, psales_weight = weights
    
    # If we have both valuations, use weighted average
    if peter_lynch_fv is not None and psales_fv is not None:
        weighted_fv = (peter_lynch_fv * peter_lynch_weight) + (psales_fv * psales_weight)
        if logger:
            logger.debug(f"Weighted FV: {weighted_fv:.2f} (PL: {peter_lynch_fv:.2f}*{peter_lynch_weight:.2f} + PS: {psales_fv:.2f}*{psales_weight:.2f})")
        return round(weighted_fv, 2)
    
    # If we only have one valuation, use it with adjusted confidence
    elif peter_lynch_fv is not None:
        if logger:
            logger.debug(f"Using Peter Lynch only: {peter_lynch_fv:.2f} (weight: {peter_lynch_weight:.2f})")
        return peter_lynch_fv
    
    elif psales_fv is not None:
        if logger:
            logger.debug(f"Using P/S Reversion only: {psales_fv:.2f} (weight: {psales_weight:.2f})")
        return psales_fv
    
    return None 