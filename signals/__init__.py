"""
Signals Package — Modular Ingestion Layer
------------------------------------------
Pre-processing, macro demand, social bridge, and marketplace parser.
All operate BEFORE data reaches the LLM agent.
"""

from .noise_cleaner import (
    clean_discount_distortion,
    clean_sponsored_placement,
    clean_price_buzz_gap,
    apply_all_filters,
)

from .macro_demand import (
    get_macro_demand,
    load_cache as load_macro_cache,
)

from .social_bridge import (
    get_social_signals,
)

from .marketplace_parser import (
    get_clean_marketplace_data,
)
