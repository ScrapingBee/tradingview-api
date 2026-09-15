// TradingView symbol data from structured data, for 1 credit.
// Verified live on 2026-09-15 against tradingview.com/symbols/NASDAQ-AAPL/.
//
// Do NOT render this page. The visible price node, span.js-symbol-last with
// data-qa-id="symbol-last-value", is EMPTY on load and is filled by the
// websocket. The quote is already in the FinancialProduct structured data.

const axios = require('axios');

const BASE = 'https://app.scrapingbee.com/api/v1/';
const headers = { Authorization: `Bearer ${process.env.SCRAPINGBEE_API_KEY}` };

// Five blocks per symbol page. Match on @type, never on position.
function ldBlocks(html) {
  const out = [];
  const blocks = html.match(/application\/ld\+json[^>]*>[\s\S]*?<\/script>/g) || [];
  for (const block of blocks) {
    const body = block.replace(/^application\/ld\+json[^>]*>/, '').replace(/<\/script>$/, '');
    try {
      out.push(JSON.parse(body));
    } catch {
      // skip malformed block
    }
  }
  return out;
}

const toFloat = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};

// 1 credit. The exchange prefix is required: NASDAQ-AAPL, NYSE-JPM.
// mode=auto settles on the plain rung. render_js would cost 5 and
// premium_proxy 10, for a page that already returns everything.
async function symbol(exchange, ticker) {
  const url = `https://www.tradingview.com/symbols/${exchange}-${ticker}/`;
  const res = await axios.get(BASE, {
    headers,
    params: { url, mode: 'auto' },
    timeout: 180000,
    responseType: 'text',
    transformResponse: [(d) => d],
  });

  const out = { url, credits: res.headers['spb-cost'] };
  for (const obj of ldBlocks(String(res.data))) {
    if (!obj || typeof obj !== 'object') continue;

    if (obj['@type'] === 'FinancialProduct') {
      const offers = obj.offers || {};
      // identifier carries the cross reference codes needed to join a
      // scraped row against any real financial dataset.
      const codes = {};
      for (const i of obj.identifier || []) if (i && i.propertyID) codes[i.propertyID] = i.value;

      Object.assign(out, {
        name: obj.name,
        category: obj.category,
        ticker: obj.tickerSymbol,
        isin: codes.ISIN,
        cusip: codes.CUSIP,
        figi: codes.FIGI,
        price: toFloat(offers.price),
        currency: offers.priceCurrency,
        // The timestamp the quote was valid at, NOT your fetch time.
        price_valid_until: offers.priceValidUntil,
        description: obj.description,
      });
    } else if (obj['@type'] === 'Dataset') {
      // creator.name is the EXCHANGE the price came from.
      out.exchange = (obj.creator || {}).name;
      out.dataset = obj.name;
    }
  }
  return out;
}

// One credit per symbol, so a 500 name universe is 500 credits.
async function universe(pairs) {
  const out = [];
  for (const [ex, tk] of pairs) out.push(await symbol(ex, tk));
  return out;
}

(async () => {
  const q = await symbol('NASDAQ', 'AAPL');
  console.log(`${q.name} (${q.ticker}) on ${q.exchange}  [${q.credits} credit]`);
  console.log(`  ${q.price} ${q.currency}  valid until ${q.price_valid_until}`);
  console.log(`  ISIN ${q.isin}  CUSIP ${q.cusip}  FIGI ${q.figi}`);

  const more = await universe([['NYSE', 'JPM']]);
  more.forEach((s) => console.log(`\n  ${s.ticker} ${s.price} ${s.currency} ${s.exchange} ${s.isin}`));
})();

module.exports = { symbol, universe };
