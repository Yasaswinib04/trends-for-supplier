/**
 * CLI entry point for marketplace scrapers.
 * Usage: npx tsx run.ts --source=meesho --keyword="cotton kurti"
 *
 * Outputs JSON array of products to stdout.
 * All debug logging goes to stderr so stdout is clean JSON.
 */

// Redirect console.log to stderr so stdout contains only JSON
const origLog = console.log;
console.log = (...args: any[]) => process.stderr.write(args.join(' ') + '\n');
const origWarn = console.warn;
console.warn = (...args: any[]) => process.stderr.write('WARN: ' + args.join(' ') + '\n');

const args: Record<string, string> = {};
process.argv.slice(2).forEach((arg) => {
  const m = arg.match(/^--(\w+)=(.+)$/);
  if (m) args[m[1]] = m[2];
});

const source = args.source || '';
const keyword = args.keyword || '';

if (!source || !keyword) {
  console.error('Usage: npx tsx run.js --source=myntra|meesho|flipkart --keyword="cotton kurti"');
  process.exit(1);
}

(async () => {
  try {
    let products: any[] = [];

    if (source === 'myntra') {
      const { scrapeMyntra } = await import('./myntra');
      products = await scrapeMyntra(keyword);
    } else if (source === 'meesho') {
      const { scrapeMeesho } = await import('./meesho');
      products = await scrapeMeesho(keyword);
    } else if (source === 'flipkart') {
      const { scrapeFlipkart } = await import('./flipkart');
      products = await scrapeFlipkart(keyword);
    } else {
      console.error(`Unknown source: ${source}. Use myntra, meesho, or flipkart.`);
      process.exit(1);
    }

    // Parse price strings to numbers for compatibility with FDE
    const normalized = products.map((p) => ({
      name: p.title || 'N/A',
      brand: p.brand || '',
      price: parseFloat((p.price || '0').replace(/[₹,\s]/g, '')) || 0,
      discount: (p.discount || '0%').includes('%') ? p.discount : `${Math.round(parseFloat(p.discount || '0'))}%`,
      discount_percentage: parseInt((p.discount || '0').replace(/[^0-9]/g, '')) || 0,
      rating: parseFloat(p.rating || '0') || 0,
      reviews: 0,
      review_velocity: 0,
      stock_status: 'In stock',
      is_sponsored: false,
      platform: source,
    }));

    process.stdout.write(JSON.stringify(normalized));
  } catch (err: any) {
    console.error(`Scraper error: ${err.message || err}`);
    process.stdout.write('[]');
    process.exit(0);
  }
})();
