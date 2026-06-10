import { chromium, Browser, Page, BrowserContext } from 'playwright';

export interface Product {
  title: string;
  price: string;
  rating: string;
  discount: string;
  brand: string;
}

const TIMEOUT = parseInt(process.env.SCRAPE_TIMEOUT_MS || '30000', 10);
const MAX_PRODUCTS = parseInt(process.env.MAX_PRODUCTS || '10', 10);
const HEADLESS = process.env.HEADLESS !== 'false';

/**
 * Creates a stealth browser context that avoids common bot detection.
 */
async function createStealthContext(browser: Browser): Promise<BrowserContext> {
  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 900 },
    locale: 'en-IN',
    timezoneId: 'Asia/Kolkata',
    geolocation: { latitude: 12.9716, longitude: 77.5946 },
    permissions: ['geolocation'],
    extraHTTPHeaders: {
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
      'Accept-Language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
      'Accept-Encoding': 'gzip, deflate, br',
      'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
      'sec-ch-ua-mobile': '?0',
      'sec-ch-ua-platform': '"macOS"',
      'Sec-Fetch-Dest': 'document',
      'Sec-Fetch-Mode': 'navigate',
      'Sec-Fetch-Site': 'none',
      'Sec-Fetch-User': '?1',
      'Upgrade-Insecure-Requests': '1',
    },
  });

  // Stealth: override navigator properties to avoid headless detection
  await context.addInitScript(() => {
    // Override webdriver flag
    Object.defineProperty(navigator, 'webdriver', { get: () => false });

    // Override plugins to look like a real browser
    Object.defineProperty(navigator, 'plugins', {
      get: () => [1, 2, 3, 4, 5],
    });

    // Override languages
    Object.defineProperty(navigator, 'languages', {
      get: () => ['en-IN', 'en-GB', 'en-US', 'en'],
    });

    // Chrome runtime
    (window as any).chrome = {
      runtime: {},
      loadTimes: () => ({}),
      csi: () => ({}),
    };

    // Permissions
    const originalQuery = window.navigator.permissions?.query;
    if (originalQuery) {
      window.navigator.permissions.query = (parameters: any) =>
        parameters.name === 'notifications'
          ? Promise.resolve({ state: 'denied' } as PermissionStatus)
          : originalQuery(parameters);
    }
  });

  return context;
}

/**
 * Scrapes Myntra search results for a given keyword.
 * Returns up to MAX_PRODUCTS product entries.
 */
export async function scrapeMyntra(keyword: string): Promise<Product[]> {
  let browser: Browser | null = null;
  const startTime = Date.now();

  console.log(`[Myntra] Starting scrape for: "${keyword}"`);

  try {
    browser = await chromium.launch({
      headless: HEADLESS,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--disable-features=IsolateOrigins,site-per-process',
      ],
    });

    const context = await createStealthContext(browser);
    const page: Page = await context.newPage();

    // Block heavy resources but NOT scripts (needed for React rendering)
    await page.route('**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,eot}', (route) =>
      route.abort()
    );

    // First visit homepage to get cookies/session
    console.log('[Myntra] Visiting homepage first for cookies...');
    await page.goto('https://www.myntra.com/', {
      waitUntil: 'domcontentloaded',
      timeout: TIMEOUT,
    });
    await page.waitForTimeout(2000);

    // Now navigate to search results using the search functionality
    const searchSlug = keyword.trim().toLowerCase().replace(/\s+/g, '-');
    const searchUrl = `https://www.myntra.com/${searchSlug}`;
    console.log(`[Myntra] Navigating to: ${searchUrl}`);

    await page.goto(searchUrl, {
      waitUntil: 'domcontentloaded',
      timeout: TIMEOUT,
    });

    // Wait for product grid to appear
    await page.waitForSelector('.product-base, .results-base, li[class*="product"]', {
      timeout: 15000,
    }).catch(() => {
      console.log('[Myntra] Primary selectors not found, waiting for any content...');
    });

    // Allow dynamic content to fully render
    await page.waitForTimeout(3000);

    // Scroll to trigger lazy loading
    await page.evaluate(() => window.scrollBy(0, 500));
    await page.waitForTimeout(1000);

    // Extract products
    const products: Product[] = await page.evaluate((maxProducts: number) => {
      const items: Product[] = [];

      // Strategy 1: Standard Myntra product cards
      let productCards = document.querySelectorAll('li.product-base');

      // Strategy 2: Try broader selector
      if (productCards.length === 0) {
        productCards = document.querySelectorAll('[class*="product-base"]');
      }

      // Strategy 3: Look for the results container and find product links
      if (productCards.length === 0) {
        const resultsContainer = document.querySelector('.results-base, .search-searchProductsContainer, [class*="results-base"]');
        if (resultsContainer) {
          productCards = resultsContainer.querySelectorAll('li, [class*="product"]');
        }
      }

      // Strategy 4: Find by anchor links to product pages
      if (productCards.length === 0) {
        const allLinks = Array.from(document.querySelectorAll('a[href*="/buy/"]'));
        const uniqueCards: Element[] = [];
        const seen = new Set<string>();
        for (const link of allLinks) {
          const parent = link.closest('li') || link.parentElement;
          const href = link.getAttribute('href') || '';
          if (parent && !seen.has(href)) {
            seen.add(href);
            uniqueCards.push(parent);
          }
        }
        productCards = uniqueCards as unknown as NodeListOf<Element>;
      }

      const cards = Array.from(productCards).slice(0, maxProducts);

      for (const card of cards) {
        // Extract brand
        const brand =
          card.querySelector('.product-brand')?.textContent?.trim() ||
          card.querySelector('[class*="product-brand"]')?.textContent?.trim() ||
          card.querySelector('h3')?.textContent?.trim() ||
          'N/A';

        // Extract title/product name
        const title =
          card.querySelector('.product-product')?.textContent?.trim() ||
          card.querySelector('[class*="product-product"]')?.textContent?.trim() ||
          card.querySelector('h4')?.textContent?.trim() ||
          card.querySelector('[class*="product-title"]')?.textContent?.trim() ||
          'N/A';

        // Extract price
        const discountedPrice =
          card.querySelector('.product-discountedPrice')?.textContent?.trim() ||
          card.querySelector('[class*="discountedPrice"]')?.textContent?.trim() ||
          '';
        const strikePrice =
          card.querySelector('.product-strike')?.textContent?.trim() || '';
        
        // Fallback: find any element containing ₹ or Rs.
        let price = discountedPrice || strikePrice;
        if (!price) {
          const priceEls = Array.from(card.querySelectorAll('span, div, p'));
          const priceEl = priceEls.find(el => /^₹|^Rs\.?\s?\d/.test(el.textContent?.trim() || ''));
          price = priceEl?.textContent?.trim() || 'N/A';
        }

        // Extract discount
        const discount =
          card.querySelector('.product-discountPercentage')?.textContent?.trim() ||
          card.querySelector('[class*="discountPercentage"]')?.textContent?.trim() ||
          (() => {
            const els = Array.from(card.querySelectorAll('span'));
            const discEl = els.find(el => /%\s*off/i.test(el.textContent || ''));
            return discEl?.textContent?.trim() || 'N/A';
          })();

        // Extract rating
        const rating =
          card.querySelector('.product-ratingsContainer span')?.textContent?.trim() ||
          card.querySelector('[class*="product-rating"]')?.textContent?.trim() ||
          (() => {
            const els = Array.from(card.querySelectorAll('span'));
            const ratingEl = els.find(el => /^[1-5]\.\d/.test(el.textContent?.trim() || '') && (el.textContent?.trim().length || 0) < 6);
            return ratingEl?.textContent?.trim() || 'N/A';
          })();

        if (title !== 'N/A' || price !== 'N/A' || brand !== 'N/A') {
          items.push({ title, price, rating, discount, brand });
        }
      }

      return items;
    }, MAX_PRODUCTS);

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[Myntra] Scraped ${products.length} products in ${elapsed}s`);

    return products;
  } catch (error) {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.error(`[Myntra] Scrape failed after ${elapsed}s:`, error instanceof Error ? error.message : error);
    return [];
  } finally {
    if (browser) {
      await browser.close().catch((err) =>
        console.error('[Myntra] Browser cleanup error:', err)
      );
      console.log('[Myntra] Browser closed');
    }
  }
}
