# Kurti Trend Judgment Engine — Disagreement Engine

A decision-support tool for category buyers at value-fashion retailers in India. It watches 6 data sources, detects where they **disagree**, and forces the buyer to make a judgment call — not by hiding uncertainty behind a score, but by making the conflicts visible.

## Sharp Edge: The Disagreement Engine

This tool does NOT average signals into a confidence score. When Nykaa shows strong premium demand but Meesho shows zero reseller activity, the UI doesn't lower a number — it flags `[CONFLICT DETECTED: HIGH]` and asks the buyer: *"Is this aspirational-only, or can it translate to ₹399-799?"*

Every claim is traceable to raw data. Every source gets a quality grade (🟢 🟡 🔴). Every conflict has explicit **Proves** / **Cannot prove** tags. The system says "I don't know" when evidence is thin.

## Demo

```bash
pip install flask python-dotenv openai pytrends
cp .env.example .env  # add your API keys
python3 app.py
# Open http://localhost:5001
```

## Navigation: 3-Tab Structure

| Tab | Purpose | What's inside |
|---|---|---|
| **Scan** | Discovery — what's moving right now? | Live Market Pulse (search momentum, Amazon listings, Google Shopping prices), Product Deep Dive (10 preset tags + custom search), Historical Search Trends (1M/3M/YTD/1Y bars with festive presets) |
| **Decisions** | Execution — which trends need action? | Risk-ranked watchlist (HIGH CONFLICT + Monitoring), sort by conflict/risk/seasonal window. Each trend → Briefing page with Disagreement Engine analysis |
| **Performance** | Calibration — how did past bets do? | Realized margin, sell-through speed, hit rate metrics. 4 past bet outcomes with lessons. 3 repeatable patterns (Cotton+Meesho, Premium≠Value, Occasion windows) |

Each trend has a dedicated **Briefing** page with the full Disagreement Engine analysis, competitor ad activity, YouTube social buzz, source-by-source reasoning trace, and override/commit controls.

## Source Strategy

The engine synthesizes **6 data sources** across 3 layers:

### Core Sources (cached + live)

| Source | Segment | Signal |
|---|---|---|
| **Nykaa Fashion** | Premium D2C ₹800–2,500 | Full-price demand = genuine willingness to pay |
| **Myntra/Ajio** | Mass retail ₹399–1,299 | Discount levels reveal price-driven vs style-driven demand |
| **Meesho** | Tier 2/3/4 ₹199–500 | Reseller growth = leading indicator for mass penetration |
| **Internal POS** | Your stores (ground truth) | Past sell-through, margins, returns — the anchor |

### Market Intel Sources (Live APIs)

| Source | Data | Integration |
|---|---|---|
| **Amazon.in (Rainforest API)** | Live products, prices, ratings, stock, sponsored flags | Decision Board live listings, Product Deep Dive, noise-cleaning pipeline |
| **Google Shopping (SearchAPI.io)** | Live price ranges across retailers | Price View on Scan tab, deep dive price context |
| **Competitor Meta Ads** | Instagram/Facebook ad activity by brand | Briefing page — who's advertising what, how long, at what price |
| **YouTube Social Buzz** | Kurti haul video counts, affiliate link density | Briefing page — creator-driven vs organic demand signal |
| **Google Trends** | 12-month search interest (live pytrends + fallback JSON) | Historical trend bars, festive season YoY comparison |

### Browser Automation (Playwright) — New

| Marketplace | Data | Role |
|---|---|---|
| **Flipkart** | Live products, prices, discounts, brands | **New source** — fills a gap where we had zero data |
| **Meesho** | Live products, prices, ratings | **Replaces static JSON** — Meesho has no API, scraping is the only way |
| **Myntra** | Live products, prices, discounts | **Fallback** — supplements cached Myntra data |

Browser automations run in a background thread (Node.js Playwright via subprocess). If Node.js is not installed, the app falls back gracefully to cached JSON. Startup is fully automatic — `pip install -r requirements.txt && python3 app.py` is still the only command.

### Noise-Cleaning Pre-Processing

Before data reaches the LLM, every product passes through a 6-tier discount context classifier (`signals/noise_cleaner.py`):

| Context | Multiplier | When |
|---|---|---|
| Genuine Volume Driver | 1.0x | High velocity + good rating at 30-59% discount |
| Strategic Value Pricing | 1.0x | Low discount + good rating |
| End-of-Life Fast Mover | 0.5x | Deep discount but was proven at full price |
| Suspect Discount | 0.5x | Moderate discount + mediocre rating |
| Subsidized Liquidation | 0.25x | Deep discount IS the demand |
| Dead Stock Clearance | 0.1x | Not selling even at discount |

## Architecture

```
Fourier/
├── app.py                          # Flask routes + startup
├── scrapers/                       # Node.js Playwright scrapers (browser automation)
│   ├── package.json
│   ├── run.ts                      # Entry: --source=meesho --keyword="cotton kurti"
│   ├── myntra.ts | meesho.ts | flipkart.ts
│   └── node_modules/
├── sources/
│   ├── browser_scraper.py          # Python → subprocess → Node.js → Playwright
│   ├── marketplace.py / meesho.py / rainforest.py / google_shopping.py
│   ├── google_trends.py / nykaa.py / internal_pos.py / meta_ads.py
│   └── reviews.py
├── signals/                        # Pre-processing (noise cleaner)
├── synthesis/                      # LLM engine + prompt
├── templates/                      # Scan, Decisions, Performance, Briefing
└── data/                           # Cache files + historical fallback JSON
```

## Key Design Decisions

1. **Chain-of-Thought Prompting**: The LLM outputs `reasoning_trace` as the FIRST key — stepping through all 6 sources with signal/proves/cannot_prove/tension per source before generating conflicts and bet recommendations.

2. **Adversarial Framing**: The prompt instructs the LLM to lead with disagreements, never average signals, and surface "I don't know" when evidence is thin.

3. **Capital-Defensive Bet Sizing**: Only 3 options — `Small Trial`, `Deeper Buy`, `Monitor Only`. No percentages, no unit counts, no confidence scores.

4. **Async Loading**: Briefing page renders instantly with spinner; LLM synthesis fetched via JS `/api/briefing/<id>`.

5. **Pre-Caching**: All 8 trend syntheses + Amazon data + Google Trends cached at startup via background threads.

6. **Disk Cache Fallback**: All live APIs gracefully degrade to cached/static data when keys are missing or rate-limited.

## API Keys

| Key | Service | Status |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek LLM | Required for synthesis |
| `YOUTUBE_API_KEY` | YouTube Data v3 | Optional — haul video parsing |
| `GOOGLE_SHOPPING_API_KEY` | SearchAPI.io | Optional — live price ranges |
| `RAPIDAPI_KEY` | Rainforest API (Amazon.in) | Optional — live product data |

Without API keys, the app runs on cached/static data with full functionality.

## Evaluation

Run `python3 evals.py` — 5 golden cases testing trap detection:
- **The Discount Trap**: High Myntra volume at 65% discount ≠ real demand
- **The Premium Mirage**: Nykaa-only demand may not translate to value-fashion
- **Mass Only, No Premium Signal**: Meesho volume without premium validation
- **The Golden Convergence**: All sources align clean → Deeper Buy
- **The Silent Meesho**: Mass-market gap for niche trends

Assertions verify conflicts detected, trap mentioned, and bet sizing appropriate.

## Business Measurement

| Metric | Target |
|---|---|
| Markdown Reduction | 15-20% reduction vs prior seasons |
| Stockout Avoidance | 10% fewer incidents on top sellers |
| Decision Velocity | <5 min per trend (vs hours of manual research) |
| Override Learning Rate | Declining quarter-over-quarter |
| Buyer Adoption | 80%+ checking weekly |

## What I Would Build Next

1. **Chrome Extension** ("Bring Your Own Signal"): Buyers clip trends from Instagram/Pinterest/Myntra while browsing
2. **Paid Google Trends API** (SerpAPI/DataForSEO): Replace pytrends with reliable live search data
3. **Bet Outcome Tracking**: Connect approved bets to actual POS sell-through for closed feedback loop
4. **Regional Allocation**: Use POS regional data for store-level buy recommendations
5. **Flipkart/Meesho Live APIs**: Add live data sources beyond Amazon.in
