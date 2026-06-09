# Kurti Trend Judgment Engine

**What**: A decision-support tool that helps value-fashion category buyers evaluate kurti trend bets before committing inventory. Researches across 6 independent sources, surfaces where they agree and disagree, and produces a transparent bet sizing recommendation.

**Why kurtis**: India-specific category with rich signals (fabric, print, silhouette, occasion), strong seasonality, and a clear competitor set (Biba, Libas, Aurelia, Westside). Narrow scope forces depth.

---

## Quick Start

```bash
pip install -r requirements.txt

# Optional: set DeepSeek API key for AI-powered synthesis
export DEEPSEEK_API_KEY=sk-...

# Run the app
streamlit run app.py
```

If no API key is set, the app uses a rule-based fallback synthesis engine with transparent scoring.

---

## Source Strategy

| Source | What it proves | What can mislead | Data type |
|---|---|---|---|
| **Google Trends** | Search momentum for specific fabric/print/silhouette terms. Rising queries = early buyer intent. | Search ≠ purchase. Low sample sizes for niche terms. May miss vernacular/voice searches. Media noise can spike unrelated terms. | Live (pytrends) + cached fallback |
| **Meta Ad Library** (Competitor ads) | Which competitors are backing which trends with paid budget. Ad duration = conviction. | Competitors may be late, copying each other, or targeting a different customer. Geo-targeting may hide regional variation. | Cached (manually collected from facebook.com/ads/library, with trend_id linkage) |
| **Marketplace rankings** (Myntra/Ajio) | What's actually selling, review velocity, discount levels. | Discounting and stockouts distort ranks. High rank at 40% off is not full-price demand. | Cached (manually collected from bestseller pages) |
| **Meesho** (Price-sensitive mass market) | Real demand at ₹199-500 in tier-2/3/4 cities. Reseller growth is a leading indicator — resellers add products BEFORE demand peaks. Regional concentration data. | High discount % is normal on Meesho (56-63% off MRP is platform behavior). Reviews are short and often incentivized. Products churn as resellers relist. | Cached (manually collected from Meesho app) |
| **Nykaa Fashion** (Premium trickle-down) | Demand validation at ₹800-2,500. Near-zero discount = genuine willingness to pay. Editorial placements signal merchandising conviction. If a trend works at premium, a ₹599 version has proven demand pyramid. | Audience is urban/metro premium — 90% of your customers never shop there. Heavy sale distortion during events. Absence on Nykaa doesn't always mean a trend is weak. | Cached (manually collected from Nykaa Fashion) |
| **Customer reviews** | Real fit, fabric, and wash-durability feedback. Sentiment quality. | Small samples. Reviewer demographics may not match your customer base. Curated excerpts, not statistically representative. | Cached (manually collected from product pages) |

**Why this mix matters**: No single source is trusted. The recommendation lives in convergence or conflict between them. Meesho covers the mass market that Myntra/Ajio miss. Nykaa validates whether premium interest exists. Together they paint a complete demand pyramid — or expose its gaps. The system makes its level of uncertainty explicit.

---

## Technical Design

```
app.py (Streamlit UI)
├── Phase 1: Trend Picker
│   └── Surfaces 8 pre-scanned trends from cached_trends.json
│
├── Phase 2: Deep Dive (on selection)
│   ├── sources/google_trends.py     → pytrends (live) or cache fallback
│   ├── sources/meta_ads.py          → competitor_snapshot.json (cached)
│   ├── sources/marketplace.py       → marketplace_data.json (cached)
│   ├── sources/meesho.py            → meesho_data.json (cached)
│   ├── sources/nykaa.py             → nykaa_data.json (cached)
│   ├── sources/reviews.py           → reviews.json (cached)
│   │
│   ├── synthesis/engine.py
│   │   ├── synthesize() → DeepSeek chat (or rule-based fallback)
│   │   └── compute_bet_size() → transparent scoring engine
│   │
│   └── UI renders: FOR/AGAINST cards, disagreements, bet sizing,
│       missing evidence, watch-next triggers, 6 source detail expanders
│
└── utils/cache.py → JSON file cache manager
```

**AI choices**:
- **DeepSeek Chat** (`deepseek-chat`) for evidence synthesis when API key available
- **Rule-based fallback** with explicit scoring logic when no key (always usable)
- LLM is used for **structuring evidence**, not making the decision. The bet sizing is always rule-based and transparent.

**Data flow**:
1. All sources return structured dicts with `source`, `disclaimer`, and signal-specific keys
2. Synthesis engine merges into `synthesis` dict (FOR / AGAINST / DISAGREEMENTS / MISSING / WATCH_NEXT)
3. Bet sizing engine computes score from convergence, disagreement penalty
4. UI renders both raw and synthesized views

---

## Bet Sizing Logic

Transparent, not black-box. All weights and thresholds are visible to the buyer:

```
score = convergence_score - disagreement_penalty

convergence_score = strong_for × 2.5 + moderate_for × 1.5
                  - strong_against × 2.5 - moderate_against × 0.75
disagreement_penalty = disagreement_count × 1.5

IF score >= 7.5  →  DEEP BUY    (60-70% open-to-buy)
IF score >= 5.0  →  MODERATE    (30-50%, re-orderable fabric)
IF score >= 3.0  →  TRIAL       (300-500 units, top 20 stores)
ELSE             →  MONITOR     (no buy, re-check in 2-4 weeks)
```

The buyer sees the component breakdown (convergence, penalty, source counts for/against) and can override. Thresholds are documented, not hidden. Weak signals contribute to the synthesis summary but do not tilt the convergence score — only strong and moderate evidence counts.

---

## Demo Output (sample with 6 sources)

| Trend | Myntra/Ajio | Meesho | Nykaa | Verdict | Score |
|---|---|---|---|---|---|
| Chanderi Silk Straight with Zari | Strong (low discount) | Weak (imitation) | Strong (3 brands, ~0% off) | **DEEP BUY** | 10.0 |
| Ajrakh Print Cotton | Weak (organic) | Weak (early) | Emerging (5% off) | **DEEP BUY** | 8.8 |
| Organza Embroidered | Strong (low discount) | Weak | Strong (15% off) | **DEEP BUY** | 10.0 |
| Bandhani Print Straight | Moderate | Emerging (35% growth) | Emerging (25% off) | **MODERATE** | 6.0 |
| Ikat Print Anarkali | Strong (high discount) | Emerging (22% growth) | Strong (10% off) | **MODERATE** | 5.2 |
| Linen Chinese Collar | Moderate | Weak | Emerging (20% off) | **TRIAL** | 4.5 |
| Fusion Kurti with Palazzo | Strong (high discount) | Strong (28K units) | Absent | **MONITOR** | 2.8 |
| Block-Print Cotton A-Line | Strong (mixed discount) | Strong (15K units) | Absent | **MONITOR** | 0.2 |

*Scores generated by rule-based fallback. Range: 0.2–10.0 across 8 trends with 6 sources.*

**Key pattern**: Block-Print and Fusion both show strong Meesho but get downgraded for Myntra discount distortion + premium absence. Ikat and Bandhani upgraded significantly by the combined Meesho + Nykaa signal validating demand at both price extremes.

---

## Evaluation & Failure Modes

**Tested**:
- All 8 trends produce distinct bet sizes (not all collapsing to one bucket)
- Source failure: Google Trends unavailable → falls back to cache with warning badge
- Missing review data: explicitly flagged, does not break synthesis
- Empty marketplace results: handled, shown as "absent" with strong against signal
- DeepSeek API unavailable → rule-based fallback with `_note` in UI
- All cached data has `disclaimer` fields that render in the UI

**Failure modes to watch**:
- **Live pytrends rate limiting**: Google may throttle. Fallback cache prevents silent failure.
- **Cached data staleness**: Competitor and marketplace data ages. `last_updated` shown in UI.
- **Discount distortion**: If >50% of top-ranked products are deeply discounted, the marketplace signal may be unreliable. System flags this but doesn't have ground truth.
- **Vernacular/voice search gap**: pytrends captures English + Hindi text, misses voice and regional-language discovery for tier-3/4 customers.

---

## Feedback Loop

1. **Buyer override**: If a buyer overrides the recommendation (e.g., buys despite MONITOR), that decision is logged with rationale
2. **Sell-through measurement**: After 4-6 weeks, compare actual sell-through to bet sizing recommendation
3. **Rule tuning**: If TRIAL consistently overperforms and MODERATE underperforms, adjust score thresholds
4. **Source weighting**: If one source (e.g., competitor ads) consistently predicts sell-through better than others, increase its weight in convergence scoring
5. **New source integration**: Each new source (store floor notes, Instagram creator data) can be added with its own signal quality profile

---

## Business Measurement

- **Sell-through rate**: % of trial/commit inventory sold at full price within 4 weeks
- **Markdown reduction**: Compare markdown % on trend-backed buys vs. intuition-driven buys
- **Stockout avoidance**: Was re-orderable fabric used successfully?
- **Decision speed**: Time from trend surfacing to buy order placement (target: < 1 week for trial, < 2 weeks for commit)
- **Buyer adoption**: # of buying decisions made with tool vs. without

---

## What I'd Build Next

1. **Store-floor memory**: Upload buyer/store notes from past seasons. LLM matches past bet outcomes to current trends. "Last time we tried block-print cotton at ₹499, sell-through was 72% in Maharashtra stores but 35% in Delhi."
2. **Instagram-to-product bridge**: Monitor creator content velocity for specific fabric/print/silhouette combinations. Manual curation with weekly snapshots.
3. **Live competitor monitoring**: Scheduled scraping of Myntra/Ajio brand pages with change detection. Currently all cached — next step is diff-based alerts.
4. **Regional decomposition**: Split Google Trends and marketplace data by state. A trend that's winning in Gujarat may fail in Karnataka.

---

## Sources Used

- **Google Trends**: Live via pytrends (unofficial API). Cached fallback included.
- **Meta Ad Library**: Manually collected from facebook.com/ads/library on June 5, 2025. Point-in-time snapshot.
- **Marketplace data**: Manually collected from Myntra and Ajio bestseller pages on June 5, 2025. Rankings and discounts are time-sensitive.
- **Meesho data**: Manually collected from Meesho app on June 8, 2025. Reseller counts, units sold, and growth rates are platform-reported and should be treated as directional.
- **Nykaa Fashion data**: Manually collected from Nykaa Fashion website on June 7, 2025. D2C brand pricing and editorial placements.
- **Customer reviews**: Curated excerpts from Myntra and Ajio product pages. 12-40 reviews per trend, manually categorized. Not statistically representative.
- **All cached data is disclosed as such in the UI** with `disclaimer` fields and `last_updated` timestamps.
