# Kurti Trend Judgment Engine — Disagreement Engine

A decision-support tool for category buyers at value-fashion retailers in India. It watches 4 data sources, detects where they **disagree**, and forces the buyer to make a judgment call — not by hiding uncertainty behind a score, but by making the conflicts visible.

## Demo

```bash
# 1. Clone and install
pip install flask python-dotenv openai pytrends

# 2. Set your API key (optional — works without it using cached data)
export DEEPSEEK_API_KEY=your_key_here

# 3. Run
python app.py

# Open http://localhost:5000
```

If the prototype depends on live API calls and you don't have a key, the system will still render using cached synthesis outputs in `data/syntheses_cache.json`.

---

## Source Strategy and Why I Chose It

The tool synthesizes **4 sources**, chosen to represent fundamentally different customer segments and signal types:

| Source | What It Represents | Why It Matters | What It Can Mislead On |
|--------|-------------------|----------------|----------------------|
| **Nykaa Fashion** | Premium D2C demand (₹800–2,500) | Full-price sales = genuine premium demand | Premium appeal ≠ mass-market viability |
| **Myntra/Ajio** | Organized mass retail (₹399–1,299) | Discount levels reveal if demand is style-driven or price-driven | Sponsored placements and discounting can fake demand |
| **Meesho** | Price-sensitive mass market (₹199–500), tier-2/3/4 | Reseller network = ground-truth for mass penetration | Zero signal ≠ the trend won't work at value price |
| **Internal POS** | Our own store sales (ground truth) | Past sell-through, margins, returns, stockouts | Historical data from a *similar* SKU, not the *exact* trend |

### Why these 4?

The core insight is that **no single source is sufficient**. Competitors may be late. Social buzz may not convert. Marketplace ranks may be distorted by discounting. And even our own historical data can mislead if the design, fabric, or timing has changed.

By triangulating across premium (Nykaa), mass-organized (Myntra), mass-unorganized (Meesho), and internal (POS), the engine can detect the *shape* of a trend's demand curve — and more importantly, detect where the shape breaks down.

**Internal POS is the anchor.** External signals tell you what the market is doing. Internal data tells you what YOUR customer actually bought. When Nykaa says "strong demand" but our POS shows 38% sell-through on a similar SKU, that's the most important conflict on the screen.

---

## High-Level Technical Design

### Architecture

```
┌─────────────────────────────────────────────────┐
│                   Flask App                      │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Nykaa   │  │  Myntra  │  │  Meesho  │       │
│  │  Source   │  │  Source   │  │  Source   │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │             │
│  ┌────┴──────────────┴──────────────┴─────┐      │
│  │         Internal POS Source             │      │
│  └────────────────┬───────────────────────┘      │
│                   │                              │
│  ┌────────────────▼───────────────────────┐      │
│  │     DeepSeek LLM (Chain-of-Thought)    │      │
│  │     Disagreement Engine Prompt         │      │
│  └────────────────┬───────────────────────┘      │
│                   │                              │
│  ┌────────────────▼───────────────────────┐      │
│  │        Synthesis Cache (JSON)          │      │
│  └────────────────┬───────────────────────┘      │
│                   │                              │
│  ┌────────────────▼───────────────────────┐      │
│  │     Jinja2 Templates (Decision Board,  │      │
│  │     Briefing Screen, Override Modal)   │      │
│  └────────────────────────────────────────┘      │
│                                                  │
│  ┌────────────────────────────────────────┐      │
│  │     SQLite Telemetry (Override Log)    │      │
│  └────────────────────────────────────────┘      │
└─────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Chain-of-Thought Prompting**: The LLM is forced to output a `reasoning_trace` array as the FIRST key in its JSON response. It must step through each of the 4 sources individually — summarizing what the data shows, what it proves, what it cannot prove, and how it relates to the other sources — BEFORE generating conflicts, convergences, and the final bet recommendation. This dramatically reduces hallucination and formatting failures compared to a zero-shot approach.

2. **Adversarial Framing**: The system prompt is designed as an adversarial analyst, not a helpful summarizer. It is instructed to lead with disagreements, never average signals into a comfortable score, and explicitly state "I don't know" when evidence is insufficient (fewer than 2 sources with signal → `INSUFFICIENT DATA`).

3. **Response Caching**: LLM responses are cached to `data/syntheses_cache.json` after the first call. This ensures the briefing screens load instantly on subsequent visits and makes the demo reproducible even without an API key.

4. **Async Loading**: The briefing page renders a loading skeleton immediately and fetches the LLM synthesis via a background API call (`/api/briefing/<id>`), so the buyer sees the page structure and source data cards instantly while the AI analysis loads.

### AI/Tool Choices

- **DeepSeek Chat** (via OpenAI-compatible API): Chosen for cost-efficiency and strong JSON-mode compliance. The `response_format={"type": "json_object"}` parameter ensures structured output.
- **Flask + Jinja2**: Lightweight server-rendered app. No frontend framework needed — the tool is a workflow, not a dashboard.
- **SQLite**: For telemetry/override logging. Zero-config, file-based, perfect for a prototype that needs to persist buyer feedback without infrastructure.

---

## Evaluation and Feedback Loop

### How the Engine Learns from Buyers

The override modal is not just a "reject" button — it's a structured feedback loop:

1. **Buyer overrides the system**: When a buyer disagrees with the AI's recommendation, they select a reason from a curated list:
   - Supplier lead times
   - Too premium for our base
   - Costing/Margin break
   - Internal design direction

2. **Data is logged to SQLite**: Every override is timestamped and stored with the trend ID, system recommendation, override reason, and optional free-text notes.

3. **Pattern detection**: The `/api/telemetry` endpoint aggregates override reasons. If "Costing/Margin break" is the #1 reason buyers reject AI calls, it tells us the engine isn't weighing margin data heavily enough.

### What Failure Modes I Tested For

- **Insufficient data**: When fewer than 2 sources have signal, the engine refuses to make a call and displays `INSUFFICIENT DATA` with a prominent warning banner.
- **LLM formatting failures**: The `_clean_json()` function strips markdown fences and extracts the JSON object even if the LLM wraps it in ```json blocks.
- **Missing CoT**: If the LLM skips the `reasoning_trace` or provides fewer than 3 steps, the result is flagged with `_missing_trace: true` so we can monitor reliability.
- **API timeouts**: A 45-second timeout prevents the UI from hanging indefinitely. Errors return a graceful fallback with the error message displayed.

### What Would Improve Next Run

- **A/B testing override rates**: Compare override rates between trends where internal POS data agrees vs. disagrees with external signals. If buyers override more when internal data is absent, it proves the internal source is the most trusted.
- **Tracking bet outcomes**: Connect approved bets to actual sell-through data 90 days later to measure if the engine's recommendations correlate with commercial success.

---

## Business Measurement

### How to Measure if This Tool Works

The engine's success should be measured on **decision quality**, not prediction accuracy:

| Metric | What It Measures | Target |
|--------|-----------------|--------|
| **Markdown Reduction** | Are we buying fewer trends that end up on clearance? | 15-20% reduction in markdown rate vs. prior seasons |
| **Stockout Avoidance** | Are we catching winners earlier and buying enough? | 10% reduction in stockout incidents on top sellers |
| **Decision Velocity** | How fast can a buyer make a go/no-go call? | <5 minutes per trend (vs. hours of manual research) |
| **Override Learning Rate** | Do buyers override the system less over time? | Declining override rate quarter-over-quarter |
| **Buyer Adoption** | Do buyers actually use the tool daily? | 80%+ of category buyers checking the Decision Board weekly |

### The Core Business Case

A value-fashion retailer buying 200+ styles per season currently makes these decisions using WhatsApp groups, gut feel, and fragmented competitor screenshots. The cost of a wrong bet is either:
- **Markdown loss**: Buying a trend that doesn't sell → 30-50% margin erosion on clearance
- **Stockout loss**: Missing a trend that does sell → lost revenue + customer churn

The Disagreement Engine doesn't eliminate wrong bets. It makes them **cheaper** by forcing buyers to see the conflicts before committing capital — and by capturing every override decision so the system improves season over season.

---

## What I Would Build Next

1. **Chrome Extension** ("Bring Your Own Signal"): Let buyers clip trends from Instagram/Pinterest/Myntra while browsing and send them directly to the engine. Solves the real-time data problem without building fragile web scrapers.
2. **Live Google Trends Integration**: Replace the cached search trend data with live API calls to detect rising search terms as leading indicators.
3. **Bet Outcome Tracking**: Connect approved bets to actual POS sell-through data 90 days later to create a closed feedback loop.
4. **Regional Allocation Intelligence**: Use internal POS regional data (e.g., Bandhani works in Gujarat but dies in South India) to recommend store-level allocation, not just go/no-go.
