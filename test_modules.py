"""Quick validation test for all new modules."""
import sys, json
sys.path.insert(0, '.')

from sources.google_trends import fetch_google_trends
from sources.meta_ads import get_meta_ad_signals
from sources.marketplace import get_marketplace_data
from sources.reviews import get_review_signals
from sources.meesho import get_meesho_data
from sources.nykaa import get_nykaa_data
from synthesis.engine import synthesize, compute_bet_size
from utils.normalize import normalize_source, check_staleness
from utils.decisions import log_decision, get_decision, OVERRIDE_REASONS
from utils.urgency import compute_urgency, classify_status, compute_all_urgencies

with open('data/cached_trends.json') as f:
    trends = json.load(f)

# Test 1: Urgency scoring
print('=== Testing urgency scoring ===')
result = compute_urgency(trends[0])
print(f'Trend: {trends[0]["name"]}')
print(f'Urgency: {result["urgency_score"]}')
print(f'Status: {result["status"]}')
print(f'Micro: {result["micro_context"]}')
print()

# Test 2: Synthesis with new fields
print('=== Testing synthesis ===')
tid = trends[0]['id']
td = fetch_google_trends(trends[0].get('search_terms', []), use_cache=True)
md = get_meta_ad_signals(tid)
mkd = get_marketplace_data(tid)
med = get_meesho_data(tid)
nkd = get_nykaa_data(tid)
rvd = get_review_signals(tid)
synth = synthesize(trends[0], td, md, mkd, rvd, med, nkd)
print(f'Upside bullets: {len(synth.get("upside_bullets", []))}')
for b in synth.get('upside_bullets', []):
    print(f'  UP: {b["text"]} [{b["source_key"]}]')
print(f'Catch bullets: {len(synth.get("catch_bullets", []))}')
for b in synth.get('catch_bullets', []):
    print(f'  DN: {b["text"]} [{b["source_key"]}]')
print(f'System suggestion: {synth.get("system_suggestion")}')
print(f'Margin risk: {synth.get("margin_risk")}')
print(f'Inv velocity: {synth.get("inventory_velocity")}')
print(f'OTB impact: {synth.get("otb_impact")}')
print()

# Test 3: All urgencies sorted
print('=== All Urgencies (sorted) ===')
all_u = compute_all_urgencies(trends)
for u in all_u:
    s = u['status']
    e = {'CRITICAL DECISION': 'CRIT', 'EMERGING': 'EMRG', 'MONITOR': 'MNTR'}.get(s, '???')
    print(f'{u["urgency_score"]:5.1f} [{e}] {u["trend"]["name"]}')

print()
print('ALL TESTS PASSED')
