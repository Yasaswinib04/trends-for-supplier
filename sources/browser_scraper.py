"""
Browser Scraper — Playwright-based Marketplace Scraping
---------------------------------------------------------
Python wrapper around Node.js Playwright scrapers for Myntra, Meesho, and Flipkart.
Launches Chromium via subprocess to extract live product data.

Falls back to empty array if:
- Node.js is not installed
- Playwright chromium is not installed
- Scrape times out
- Scraper returns no results

Usage:
    from sources.browser_scraper import BrowserScraper
    bs = BrowserScraper()
    results = bs.scrape("meesho", "cotton kurti")  # Returns list[dict]
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from datetime import datetime

SCRAPERS_DIR = Path(__file__).parent.parent / "scrapers"
CACHE_FILE = SCRAPERS_DIR / "data" / "browser_scraper_cache.json"
SCRAPE_TIMEOUT = int(os.getenv("SCRAPE_TIMEOUT_MS", "25000"))

# In-memory cache (per process)
_cache = {}
_cache_lock = threading.Lock()

_BROWSER_READY = False
_INSTALL_LOCK = threading.Lock()


class BrowserScraper:
    """Python interface to Playwright marketplace scrapers."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._ready = False
        self._error = None

        # Check Node.js availability
        self._node_available = self._check_node()

    def _check_node(self) -> bool:
        """Check if Node.js is available."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def ensure_dependencies(self):
        """Ensure npm deps are installed. Runs in background thread."""
        global _BROWSER_READY

        with _INSTALL_LOCK:
            if _BROWSER_READY or not self._node_available:
                return _BROWSER_READY

            try:
                # npm install in scrapers directory
                result = subprocess.run(
                    ["npm", "install", "--no-audit", "--no-fund"],
                    cwd=str(SCRAPERS_DIR),
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    self._error = f"npm install failed: {result.stderr[:200]}"
                    return False

                # Check playwright browsers are installed
                check = subprocess.run(
                    ["npx", "playwright", "install", "--dry-run", "chromium"],
                    cwd=str(SCRAPERS_DIR),
                    capture_output=True, text=True, timeout=30
                )
                if check.returncode != 0:
                    # Install chromium
                    subprocess.run(
                        ["npx", "playwright", "install", "chromium"],
                        cwd=str(SCRAPERS_DIR),
                        capture_output=True, text=True, timeout=120
                    )

                _BROWSER_READY = True
                self._ready = True
                print("  \U0001f4bb Browser scrapers ready")
                return True

            except Exception as e:
                self._error = str(e)[:100]
                return False

    @property
    def ready(self) -> bool:
        return _BROWSER_READY and self._node_available

    def scrape(self, source: str, keyword: str,
               use_cache: bool = True) -> list:
        """
        Scrape a marketplace for products matching the keyword.

        Args:
            source: 'myntra', 'meesho', or 'flipkart'
            keyword: search term
            use_cache: use cached results if available (default True)

        Returns:
            list of products, each with name, brand, price, discount, rating
        """
        cache_key = f"{source}|{keyword.strip().lower()}"

        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        if not self._node_available:
            return []

        if not _BROWSER_READY:
            # Try to install dependencies synchronously (slow, first call)
            self.ensure_dependencies()

        try:
            result = subprocess.run(
                ["npx", "tsx", "run.ts", f"--source={source}", f"--keyword={keyword}"],
                cwd=str(SCRAPERS_DIR),
                capture_output=True, text=True,
                timeout=SCRAPE_TIMEOUT / 1000 if SCRAPE_TIMEOUT < 60000 else 30
            )

            if result.returncode != 0:
                return []

            products = json.loads(result.stdout)
            if not isinstance(products, list):
                return []

            self._set_cache(cache_key, products)
            return products

        except subprocess.TimeoutExpired:
            return []
        except (json.JSONDecodeError, FileNotFoundError) as e:
            return []
        except Exception:
            return []

    def scrape_all(self, keyword: str) -> dict:
        """Scrape all marketplaces for a keyword (sequential to avoid memory issues)."""
        return {
            "myntra": self.scrape("myntra", keyword),
            "meesho": self.scrape("meesho", keyword),
            "flipkart": self.scrape("flipkart", keyword),
        }

    def _get_cached(self, key: str):
        """Get from in-memory cache first, then disk."""
        with _cache_lock:
            if key in _cache:
                cached = _cache[key]
                if (datetime.now() - cached["fetched_at"]).total_seconds() < 3600:
                    return cached["data"]
        # Check disk cache
        disk = self._load_disk_cache()
        if key in disk:
            entry = disk[key]
            age = (datetime.now() - datetime.fromisoformat(
                entry.get("cached_at", "2000-01-01"))).total_seconds()
            if age < 3600:
                with _cache_lock:
                    _cache[key] = {"data": entry["data"], "fetched_at": datetime.now()}
                return entry["data"]
        return None

    def _set_cache(self, key: str, data: list):
        """Set in-memory and disk cache."""
        entry = {"data": data, "cached_at": datetime.now().isoformat()}
        with _cache_lock:
            _cache[key] = {"data": data, "fetched_at": datetime.now()}

        disk = self._load_disk_cache()
        disk[key] = {"data": data, "cached_at": entry["cached_at"]}
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(disk, f, indent=2, default=str)
        except Exception:
            pass

    def _load_disk_cache(self) -> dict:
        if CACHE_FILE.exists() and CACHE_FILE.stat().st_size > 0:
            try:
                with open(CACHE_FILE) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {}


def init_scrapers():
    """Initialize scrapers in background (called from app.py)."""
    bs = BrowserScraper()
    if not bs._node_available:
        print("  \u26a0\ufe0f Browser scrapers unavailable (Node.js not found). "
              "Install Node.js v18+ for live scraping.")
        return False
    return bs.ensure_dependencies()
