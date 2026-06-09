import json
from pathlib import Path

TRANSLATIONS_FILE = Path(__file__).parent / "translations.json"

with open(TRANSLATIONS_FILE) as f:
    _STRINGS = json.load(f)

SUPPORTED_LANGS = ["en", "hi", "te", "ta"]
LANG_LABELS = {"en": "English", "hi": "हिन्दी", "te": "తెలుగు", "ta": "தமிழ்"}
LANG_FALLBACK = "en"


def t(key, lang="en"):
    if lang not in SUPPORTED_LANGS:
        lang = LANG_FALLBACK

    entry = _STRINGS.get(key)
    if entry is None:
        return key

    if isinstance(entry, dict):
        if "en" in entry or "hi" in entry:
            return entry.get(lang, entry.get(LANG_FALLBACK, key))
        return key

    return entry


def get_lang_from_state():
    try:
        import streamlit as st
        return st.session_state.get("lang", "en")
    except ImportError:
        return "en"
