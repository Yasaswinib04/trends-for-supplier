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
 * Scrapes Flipkart search results for a given keyword.
 */
export async function scrapeFlipkart(keyword: string): Promise<Product[]> {
  let browser: Browser | null = null;
  const startTime = Date.now();

  console.log(`[Flipkart] Starting scrape for: "${keyword}"`);

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
    console.log('[Flipkart] Visiting homepage for session cookies...');
    await page.goto('https://www.flipkart.com/', {
      waitUntil: 'domcontentloaded',
      timeout: TIMEOUT,
    });
    await page.waitForTimeout(2000);

    // Try closing login popup if it appears
    try {
      const closeBtn = await page.$('button._2KpZ6l._2doB4z, span[role="button"]');
      if (closeBtn) await closeBtn.click();
    } catch (e) {}

    // Navigate to search results
    const searchUrl = `https://www.flipkart.com/search?q=${encodeURIComponent(keyword)}`;
    console.log(`[Flipkart] Navigating to: ${searchUrl}`);

    await page.goto(searchUrl, {
      waitUntil: 'domcontentloaded',
      timeout: TIMEOUT,
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

      // Look for product links or general container logic
      const productLinks = Array.from(document.querySelectorAll('a[href*="/p/"], a[href*="pid="]'));
      
      const seenCards = new Set<Element>();
      const cards: Element[] = [];

      for (const link of productLinks) {
        // Flipkart usually wraps cards in a div right above the link, or the link IS the card.
        // Let's use the closest parent div that has a specific dimension or multiple elements.
        let container: Element | null = link;
        if (container.parentElement && container.parentElement.children.length > 1) {
             container = container.parentElement;
        } else if (container.parentElement && container.parentElement.parentElement) {
             container = container.parentElement.parentElement;
        }

        if (container && !seenCards.has(container)) {
          // Verify it contains a price
          const text = container.textContent || '';
          if (/₹\s?\d/.test(text)) {
            seenCards.add(container);
            cards.push(container);
          }
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

        // Get all text nodes
        const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT, null);
        const textNodes: string[] = [];
        let node;
        while ((node = walker.nextNode())) {
            const text = node.textContent?.trim();
            if (text) textNodes.push(text);
        }

        // Parse extracted text nodes
        for (let i = 0; i < textNodes.length; i++) {
            const text = textNodes[i];
            
            // Price (starts with ₹)
            if (/^₹\s?\d/.test(text) && price === 'N/A') {
                price = text;
                continue;
            }

            // Discount (contains % off)
            if (/%\s*off/i.test(text) && discount === 'N/A') {
                const match = text.match(/(\d{1,2}%\s*off)/i);
                if (match) discount = match[1];
                else discount = text;
                continue;
            }

            // Rating (starts with digit, followed by star character or simply small string)
            if (/^[1-5]\.\d$/.test(text) && rating === 'N/A') {
                rating = text;
                continue;
            }

            // Brand & Title
            if (
                text.length > 2 &&
                !text.startsWith('₹') &&
                !/%\s*off/i.test(text) &&
                !/^[1-5]\.\d$/.test(text) &&
                !/^\(\d+\)$/.test(text) && // e.g., (123) review count
                !/^[1-5]\.\d\s*★$/.test(text)
            ) {
                if (brand === 'N/A' && text.length < 30) {
                    brand = text;
                } else if (title === 'N/A') {
                    title = text;
                }
            }
        }

        // Fallback for rating if it included the star
        if (rating === 'N/A') {
             const rNode = textNodes.find(t => /^[1-5]\.\d\s*★$/.test(t));
             if (rNode) rating = rNode.replace('★', '').trim();
        }

        if (title !== 'N/A' || price !== 'N/A') {
          items.push({ title, price, rating, discount, brand });
        }
      }

      return items;
    }, MAX_PRODUCTS);

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`[Flipkart] Scraped ${products.length} products in ${elapsed}s`);

    return products;
  } catch (error) {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.error(`[Flipkart] Scrape failed after ${elapsed}s:`, error instanceof Error ? error.message : error);
    return [];
  } finally {
    if (browser) {
      await browser.close().catch((err) =>
        console.error('[Flipkart] Browser cleanup error:', err)
      );
      console.log('[Flipkart] Browser closed');
    }
  }
}
