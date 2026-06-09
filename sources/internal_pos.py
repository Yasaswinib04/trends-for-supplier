"""
Internal POS (Point-of-Sale) Data Source
-----------------------------------------
Ground truth from the retailer's own stores.

This is the most trusted signal in the engine because it reflects
actual customer purchases — not marketplace rankings or social buzz.

Data is cached/mocked for the prototype. In production, this would
connect to the retailer's ERP/POS system (e.g., Unicommerce, Increff,
or a custom warehouse management system).
"""


def get_internal_pos_data(trend_id: str) -> dict:
    """Return internal sales data for a trend, if any past/similar buys exist."""
    return INTERNAL_DATA.get(trend_id, {
        "has_internal_data": False,
        "note": "No prior buy history for this trend. First-time category entry.",
    })


# --- Mocked Internal POS Data ---
# Designed to create intentional conflicts with external signals:
#   - chanderi-straight: Nykaa says strong premium demand, but internal POS shows
#     premium kurtis have historically underperformed in our value stores.
#   - fusion-palazzo: Meesho shows saturation, but our internal data shows
#     it's still our #1 seller — the external "over-saturation" signal is noise for us.
#   - organza-embroidered: Strong festive signal externally, and internal data
#     confirms festive kurtis sell well — but only in a 3-week window.

INTERNAL_DATA = {
    "chanderi-straight": {
        "has_internal_data": True,
        "similar_past_sku": "Chanderi Silk A-line Kurti (SS24)",
        "stores_stocked": 84,
        "total_stores": 220,
        "sell_through_pct": 38,
        "target_sell_through_pct": 65,
        "outcome": "underperformed",
        "avg_days_to_first_sale": 12,
        "margin_achieved_pct": 22,
        "target_margin_pct": 40,
        "markdown_pct": 35,
        "stockout_stores": 0,
        "top_performing_regions": ["Mumbai", "Bangalore"],
        "worst_performing_regions": ["Lucknow", "Patna", "Indore"],
        "buyer_note": "Chanderi fabric reads premium but our core customer found it too delicate for daily wear. Returned units had complaints about wash durability. Worked only in metro stores with higher ASP tolerance.",
        "key_insight": "Premium fabric ≠ value customer willingness. Our base wants the LOOK of premium, not the maintenance burden.",
        "repeat_buy_rate_pct": 8,
        "return_rate_pct": 18,
        "proves": "Chanderi silk has a narrow addressable market within our store base. Metro-only viability.",
        "cannot_prove": "Whether a different price point (sub-₹599) or blended fabric would change the outcome.",
    },

    "blockprint-cotton": {
        "has_internal_data": True,
        "similar_past_sku": "Jaipur Block Print Cotton Kurti (AW23)",
        "stores_stocked": 210,
        "total_stores": 220,
        "sell_through_pct": 78,
        "target_sell_through_pct": 65,
        "outcome": "success",
        "avg_days_to_first_sale": 3,
        "margin_achieved_pct": 44,
        "target_margin_pct": 40,
        "markdown_pct": 8,
        "stockout_stores": 45,
        "top_performing_regions": ["Jaipur", "Delhi", "Pune", "Hyderabad"],
        "worst_performing_regions": [],
        "buyer_note": "Our bread-and-butter category. Consistent performer across all tiers. Stockouts in 45 stores suggest we under-bought by ~20%. Cotton + block print is evergreen for our customer.",
        "key_insight": "We under-ordered last time. This is a proven winner — the question is quantity, not whether to buy.",
        "repeat_buy_rate_pct": 34,
        "return_rate_pct": 4,
        "proves": "Block print cotton is a core category for our base. High sell-through, low returns, strong repeat.",
        "cannot_prove": "Whether the CURRENT batch of block print designs will perform as well as the last (design fatigue risk).",
    },

    "fusion-palazzo": {
        "has_internal_data": True,
        "similar_past_sku": "Printed Kurti + Palazzo Set (SS24)",
        "stores_stocked": 200,
        "total_stores": 220,
        "sell_through_pct": 82,
        "target_sell_through_pct": 65,
        "outcome": "success",
        "avg_days_to_first_sale": 1,
        "margin_achieved_pct": 38,
        "target_margin_pct": 40,
        "markdown_pct": 12,
        "stockout_stores": 68,
        "top_performing_regions": ["Delhi", "Mumbai", "Pune", "Bangalore", "Hyderabad"],
        "worst_performing_regions": [],
        "buyer_note": "Top seller. Stockouts in 68 stores. External signals say 'over-saturated' but our customer keeps buying. The set format (kurti+palazzo) is the value proposition — not the individual kurti.",
        "key_insight": "External saturation ≠ internal saturation. Our customer sees this as a COMPLETE OUTFIT at one price, which is the real value prop.",
        "repeat_buy_rate_pct": 41,
        "return_rate_pct": 6,
        "proves": "Kurti+palazzo sets are a proven top-seller for our base regardless of marketplace saturation.",
        "cannot_prove": "Whether the next season's designs will maintain the same velocity, or if design fatigue will finally kick in.",
    },

    "organza-embroidered": {
        "has_internal_data": True,
        "similar_past_sku": "Organza Embroidered Anarkali (Diwali 23)",
        "stores_stocked": 120,
        "total_stores": 220,
        "sell_through_pct": 71,
        "target_sell_through_pct": 65,
        "outcome": "success",
        "avg_days_to_first_sale": 2,
        "margin_achieved_pct": 48,
        "target_margin_pct": 40,
        "markdown_pct": 5,
        "stockout_stores": 22,
        "top_performing_regions": ["Delhi", "Mumbai", "Kolkata", "Lucknow"],
        "worst_performing_regions": ["Tier-3 towns"],
        "buyer_note": "Strong festive performer but ONLY during the 3-week Diwali window. After Diwali, velocity dropped 90%. We had to markdown remaining stock post-Navratri. Timing is everything.",
        "key_insight": "Organza festive kurtis are a 3-week play, not a season play. Buy tight, sell fast, don't over-commit.",
        "repeat_buy_rate_pct": 5,
        "return_rate_pct": 12,
        "proves": "Organza embroidered kurtis sell well in a tight festive window with strong margins.",
        "cannot_prove": "Whether the window will be longer this year, or whether a pre-Diwali launch could capture more demand.",
    },

    "bandhani-straight": {
        "has_internal_data": True,
        "similar_past_sku": "Bandhej Print Kurti (Navratri 23)",
        "stores_stocked": 95,
        "total_stores": 220,
        "sell_through_pct": 52,
        "target_sell_through_pct": 65,
        "outcome": "mixed",
        "avg_days_to_first_sale": 7,
        "margin_achieved_pct": 32,
        "target_margin_pct": 40,
        "markdown_pct": 22,
        "stockout_stores": 8,
        "top_performing_regions": ["Ahmedabad", "Surat", "Jaipur"],
        "worst_performing_regions": ["Chennai", "Bangalore", "Kolkata"],
        "buyer_note": "Very regional. Flew off shelves in Gujarat/Rajasthan but sat dead in South and East India. National rollout was a mistake — should have been a regional buy.",
        "key_insight": "Bandhani is a REGIONAL bet, not a national bet. Allocate by geography, not uniformly.",
        "repeat_buy_rate_pct": 19,
        "return_rate_pct": 9,
        "proves": "Bandhani has strong demand in Western India but does not travel nationally.",
        "cannot_prove": "Whether a different colorway or modern interpretation could unlock South/East demand.",
    },

    "ajrakh-cotton": {
        "has_internal_data": False,
        "note": "No prior buy history. Ajrakh print is a new category entry for us. Closest proxy: Block print cotton (which performed well).",
    },

    "ikat-anarkali": {
        "has_internal_data": False,
        "note": "No prior buy history for Ikat print. Closest proxy: Bandhani (regional performer — mixed results nationally).",
    },

    "linen-chinese-collar": {
        "has_internal_data": True,
        "similar_past_sku": "Linen Straight Kurti (SS23)",
        "stores_stocked": 60,
        "total_stores": 220,
        "sell_through_pct": 29,
        "target_sell_through_pct": 65,
        "outcome": "underperformed",
        "avg_days_to_first_sale": 18,
        "margin_achieved_pct": 15,
        "target_margin_pct": 40,
        "markdown_pct": 45,
        "stockout_stores": 0,
        "top_performing_regions": ["Mumbai"],
        "worst_performing_regions": ["Everywhere else"],
        "buyer_note": "Linen at value price point was a mistake. Our customer doesn't iron. Linen wrinkles = returns. Only worked in South Mumbai stores. Heavy markdowns.",
        "key_insight": "Our customer optimizes for low-maintenance. Linen is aspirational but impractical for our base.",
        "repeat_buy_rate_pct": 3,
        "return_rate_pct": 24,
        "proves": "Linen kurtis do not work for our value-fashion customer base at scale.",
        "cannot_prove": "Whether a linen-BLEND (less wrinkling) at a lower price point could change the outcome.",
    },
}
