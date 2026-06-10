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

  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
    Object.defineProperty(navigator, 'plugins', {
      get: () => [1, 2, 3, 4, 5],
    });
    Object.defineProperty(navigator, 'languages', {
      get: () => ['en-IN', 'en-GB', 'en-US', 'en'],
    });
    (window as any).chrome = {
      runtime: {},
      loadTimes: () => ({}),
      csi: () => ({}),
    };
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
 * Scrapes Meesho search results for a given keyword.
 * 
 * Meesho uses styled-components with dynamically generated class names
 * following the pattern: NewProductCardstyled__ComponentName-sc-HASH-N
 * 
 * We use content-based heuristics and the [class*="ProductCard"] selector
 * to identify product cards and extract fields.
 */
export async function scrapeMeesho(keyword: string): Promise<Product[]> {
  let browser: Browser | null = null;
  const startTime = Date.now();

  console.log(`[Meesho] Starting scrape for: "${keyword}"`);

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

    // Block heavy resources but keep scripts for React rendering
    await page.route('**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,eot}', (route) =>
      route.abort()
    );

    // Visit homepage first to establish session cookies
    console.log('[Meesho] Visiting homepage for session cookies...');
    await page.goto('https://www.meesho.com/', {
      waitUntil: 'domcontentloaded',
      timeout: TIMEOUT,
    });
    await page.waitForTimeout(2500);

    // Navigate to search results
    const searchUrl = `https://www.meesho.com/search?q=${encodeURIComponent(keyword)}`;
    console.log(`[Meesho] Navigating to: ${searchUrl}`);

    await page.goto(searchUrl, {
      waitUntil: 'domcontentloaded',
      timeout: TIMEOUT,
    });

    // Wait for styled-component product cards to render
    await page.waitForSelector('[class*="ProductCard"], [class*="NewProductCard"]', {
      timeout: 15000,
    }).catch(() => {
      console.log('[Meesho] ProductCard selector not found, waiting for content...');
    });

    // Allow React to fully hydrate
    await page.waitForTimeout(4000);

    // Scroll to trigger lazy loading
    for (let i = 0; i < 3; i++) {
      await page.evaluate(() => window.scrollBy(0, 400));
      await page.waitForTimeout(600);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(500);

    // Extract product data
    const products: Product[] = await page.evaluate((maxProducts: number) => {
      const items: Product[] = [];

      // ─── Find product card containers ────────────────────────────
      // Meesho's styled-components generate classes like:
      //   NewProductCardstyled__PriceRow-sc-6y2tys-7
      // Price lives in <H5> tags inside PriceRow containers.
      // We use price elements as anchors to find card boundaries.

      // Step 1: Find all price elements (H5 with ₹)
      const priceElements = Array.from(document.querySelectorAll('h5'))
        .filter(el => /^₹\s?\d/.test(el.textContent?.trim() || ''));

      if (priceElements.length === 0) {
        return items;
      }

      // Step 2: For each price element, walk up to find the card container.
      // The card container is typically an <a> tag or a <div> that contains
      // the product image, title, price, and rating.
      const cards: Element[] = [];
      const seenCards = new Set<Element>();

      for (const priceEl of priceElements) {
        // Walk up until we find an element with "ProductCard" in its class
        // or an anchor tag, whichever comes first
        let current: Element | null = priceEl;
        let cardContainer: Element | null = null;

        while (current && current !== document.body) {
          const classes = current.className?.toString() || '';
          if (classes.includes('ProductCard') && !classes.includes('ProductCards')) {
            cardContainer = current;
            break;
          }
          // Also check if it's an anchor to a product
          if (current.tagName === 'A') {
            cardContainer = current;
            break;
          }
          current = current.parentElement;
        }

        if (cardContainer && !seenCards.has(cardContainer)) {
          seenCards.add(cardContainer);
          cards.push(cardContainer);
        }
      }

      // Process cards
      const cardArray = cards.slice(0, maxProducts);

      for (const card of cardArray) {
        let title = 'N/A';
        let price = 'N/A';
        let rating = 'N/A';
        let discount = 'N/A';
        let brand = 'N/A';

        // ─── Price: H5 element starting with ₹ ──────────────────
        const priceEl = card.querySelector('h5');
        if (priceEl) {
          const text = priceEl.textContent?.trim() || '';
          if (/^₹/.test(text)) {
            price = text;
          }
        }

        // ─── Original price / Discount ──────────────────────────
        // Strikethrough price is usually in a <p> with text-decoration line-through
        // Discount percentage is usually in a <span> or <p> with "% off"
        const allText = Array.from(card.querySelectorAll('p, span'));
        for (const el of allText) {
          const text = el.textContent?.trim() || '';
          if (!text) continue;

          if (/%\s*off/i.test(text) && discount === 'N/A') {
            const match = text.match(/(\d{1,2}%\s*off)/i);
            if (match) {
              discount = match[1];
            } else {
              discount = text;
            }
          }
        }

        // ─── Rating ─────────────────────────────────────────────
        // Rating is typically a small number like "3.9" near a star icon
        for (const el of allText) {
          const text = el.textContent?.trim() || '';
          if (/^[1-5]\.\d$/.test(text) && rating === 'N/A') {
            rating = text;
          }
        }

        // ─── Title and Brand ────────────────────────────────────
        // Title is typically the longest descriptive text in <p> elements.
        // Look for <p> elements that are NOT price/discount/rating.
        const paragraphs = Array.from(card.querySelectorAll('p'));
        const textCandidates: string[] = [];

        for (const p of paragraphs) {
          const text = p.textContent?.trim() || '';
          if (
            text.length > 3 &&
            text.length < 200 &&
            !text.startsWith('₹') &&
            !/%\s*off/i.test(text) &&
            !/^[1-5]\.\d$/.test(text) &&
            !/free delivery/i.test(text) &&
            !/^\d+ reviews?$/i.test(text) &&
            !/^\d+\+? sold/i.test(text)
          ) {
            textCandidates.push(text);
          }
        }

        // The first text candidate is usually the title
        if (textCandidates.length > 0) {
          title = textCandidates[0];
        }
        // The second might be a sub-description or brand
        if (textCandidates.length > 1) {
          brand = textCandidates[1];
        }

        if (title !== 'N/A' || price !== 'N/A') {
          items.push({ title, price, rating, discount, brand });
        }
      }

      return items;
    }, MAX_PRODUCTS);

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[Meesho] Scraped ${products.length} products in ${elapsed}s`);

    return products;
  } catch (error) {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.error(`[Meesho] Scrape failed after ${elapsed}s:`, error instanceof Error ? error.message : error);
    return [];
  } finally {
    if (browser) {
      await browser.close().catch((err) =>
        console.error('[Meesho] Browser cleanup error:', err)
      );
      console.log('[Meesho] Browser closed');
    }
  }
}
