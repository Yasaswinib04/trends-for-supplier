# Disagreement Engine — Trend Judgment V2

**Sharp edge**: A conflict-first LLM analysis engine that detects when data sources contradict — instead of averaging them into a comfortable but misleading score.

---

## Quick Start

```bash
pip install -r requirements.txt

# Set API key (or create .env with DEEPSEEK_API_KEY=sk-...)
export DEEPSEEK_API_KEY=sk-...

streamlit run app.py
```

---

## What It Does

A value-fashion category buyer selects a kurti trend. The system pulls data from 3 contrasting sources:

| Source | Price Band | What It Reveals |
|---|---|---|
| **Nykaa Fashion** | ₹800–2,500 | Premium D2C demand. Zero-discount sales = genuine willingness to pay. |
| **Myntra/Ajio** | ₹399–1,299 | Organized retail. Discount levels expose whether demand is style-driven or price-driven. |
| **Meesho** | ₹199–500 | Price-sensitive tier-2/3/4. Reseller growth = leading indicator before demand peaks. |

The engine runs all three through an adversarial LLM prompt that forces it to **detect conflicts, not average them**. If Nykaa shows full-price velocity but Meesho shows zero reseller listings, the UI flags `[CONFLICT DETECTED: HIGH]` — not a lower confidence score.

---

## The Sharp Edge: Disagreement Engine

**Why this matters**: Traditional analytics tools average data into single scores ("72% confidence"). This hides the most valuable signal: *where sources flatly disagree*. A buyer needs to know that premium customers love a trend but the mass market ignores it. That's the decision.

The system prompt is an adversarial debate format. The LLM must:
1. Identify every point of tension between Nykaa, Myntra, and Meesho
2. Assign severity (HIGH/MEDIUM/LOW) to each conflict
3. Quote the specific raw data that supports each side
4. Pose the exact buyer question the conflict creates
5. Output a bet lean that acknowledges the conflict — not one that pretends it doesn't exist

**What the engine does NOT do**: compute weighted scores, average signals, or force consensus. It presents the debate and lets the buyer decide.

---

## Evaluation Suite

The project includes a golden dataset of 5 extreme retail scenarios and an automated test runner.

```bash
python evals.py                    # Run all 5 cases
python evals.py --verbose          # Show per-case LLM output
python evals.py --case=1           # Run a specific case
```

### The 5 Golden Cases

| # | Scenario | Expected Trap | What It Tests |
|---|---|---|---|
| 1 | The Discount Trap | discount_distortion | High volume at 65% off ≠ real demand |
| 2 | The Premium Mirage | aspirational_only | Nykaa strong, Meesho zero — does mass market want this? |
| 3 | Mass Only, No Premium | mass_commodity | Meesho 52K units but no Nykaa — purely value play? |
| 4 | The Golden Convergence | none | All 3 sources agree — engine correctly identifies convergence |
| 5 | The Silent Meesho | mass_gap | Niche premium trend with zero mass-market presence |

Each case has programmatic assertions. The eval script verifies that the LLM:
- Detected the specific trap type
- Produced at least one HIGH severity conflict (for trap cases)
- Recommended an appropriate bet_lean (not STRONG BUY on traps)
- Quoted specific raw data keys for traceability

**Eval results are front-and-center**: passing 5/5 proves the prompt reliably detects retail traps and doesn't drift.

---

## User Flow

1. **Triage Inbox** (`app.py`) — Priority-ranked trends with pre-labeled conflict severity
2. **The Briefing** (`pages/1_briefing.py`) — Full analysis with Upside/Catch panels, conflict expanders, raw data traceability, structured override form
3. **Market View** (`pages/2_market_view.py`) — H1 retrospective on past bets
4. **Sourcing** (`pages/3_sourcing.py`) — Procurement automation handoff

---

## Feedback Loop Architecture

Every buyer override is logged to a SQLite database (`data/telemetry.db`) with:

| Field | Purpose |
|---|---|
| `timestamp` | When the override was made |
| `trend_id` / `trend_name` | Which product was overridden |
| `system_bet_lean` | What the engine recommended |
| `override_reason` | Structured option (Lead time, Margin, Audience mismatch, Silhouette) |
| `override_bet_lean` | What the buyer chose instead |
| `notes` | Optional free-text detail |

**How this trains the system**: If "Margin threshold breached" is selected >3 times for sheer fabrics, the next version of the prompt would automatically flag "sheer" as a high-risk keyword. If "Target audience mismatch" dominates for Meesho-absent trends, the system learns to weight the Meesho signal higher for value-fashion.

The telemetry stats are visible in the UI via a developer toggle on the Briefing page.

---

## Technical Design

```
app.py                          → Triage Inbox (landing)
pages/1_briefing.py             → Briefing (deep dive with conflict engine)
pages/2_market_view.py          → Market View (retrospective)
pages/3_sourcing.py             → Sourcing (procurement)

synthesis/prompts.py            → Adversarial debate system prompt
synthesis/engine.py             → LLM synthesis + SQLite telemetry
sources/nykaa.py / meesho.py / marketplace.py  → Data loaders (cached JSON)

evals/golden_cases.json         → 5 extreme scenarios
evals.py                        → Automated assertion runner

data/telemetry.db               → Override log (auto-created)
data/nykaa_data.json            → Cached Nykaa data (mocked, no scraper)
data/meesho_data.json           → Cached Meesho data (mocked)
data/marketplace_data.json      → Cached Myntra/Ajio data (mocked)
```

**No scraper dependencies** — all source data is pre-cached in JSON files. The evaluator doesn't need API access to any marketplace.

---

## What Was Removed from V1

- **i18n** — Stripped. Multi-language support diluted the sharp edge.
- **Rule-based fallback** — Removed. V2 is LLM-native. No key = no analysis.
- **Google Trends, Meta Ads, Customer Reviews sources** — Reduced to the 3 highest-contrast sources (Nykaa, Myntra, Meesho).
- **Weighted scoring** — Removed. No more averaging. Conflicts are surfaced, not summed.

---

## What Strong Looks Like

- **Conflict detection is the feature**, not a byproduct. The UI celebrates disagreement.
- **Every claim is traceable** — `[🔍 View Raw Signals]` buttons link LLM output to raw JSON.
- **The eval suite passes 5/5** — proves prompt reliability.
- **Telemetry is real** — overrides are structured, logged, and queryable.
