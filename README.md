# TradingView API

<p align="center">
  <a href="https://www.scrapingbee.com/">
    <img src="https://github.com/user-attachments/assets/fb56a4d1-7ae4-45c8-97f3-0a7292e15785" alt="tradingview-api" />
  </a>
</p>



[![checks](https://github.com/ScrapingBee/tradingview-api/workflows/checks/badge.svg)](https://github.com/ScrapingBee/tradingview-api/actions)
[![license](https://img.shields.io/github/license/ScrapingBee/tradingview-api.svg)](LICENSE)

TradingView looks like the hardest kind of page to scrape. It is a live charting application, the price ticks in front of you, and the obvious conclusion is that you need a headless browser and a websocket. You do not. The quote is sitting in the page's structured data, and the whole record comes back for **1 credit** with no rendering at all.

This is a [trading view api](https://www.scrapingbee.com/scrapers/tradingview-api/) client built on [ScrapingBee's web scraping API](https://www.scrapingbee.com/features/ai-web-scraping-api/), organised around that one observation.

Verified live on 2026-09-15 against `tradingview.com/symbols/NASDAQ-AAPL/`.

## The chart node is empty. The metadata is not.

Here is the price element people try to select first:

```html
<span class="last-KLji300y js-symbol-last" data-qa-id="symbol-last-value"></span>
```

Empty. It is filled after the socket connects, so a scraper pointed at it gets an empty string no matter how long it waits on a plain fetch, and a rendered fetch costs five times more for a value that may still be mid update.

Meanwhile the same page carries five `application/ld+json` blocks, and one of them is a `FinancialProduct` with the quote already in it:

```json
{
  "@type": "FinancialProduct",
  "name": "Apple Inc.",
  "category": "Stock",
  "tickerSymbol": "AAPL",
  "identifier": [
    {"@type": "PropertyValue", "propertyID": "tickerSymbol", "value": "AAPL"},
    {"@type": "PropertyValue", "propertyID": "ISIN",  "value": "US0378331005"},
    {"@type": "PropertyValue", "propertyID": "CUSIP", "value": "037833100"},
    {"@type": "PropertyValue", "propertyID": "FIGI",  "value": "BBG000B9XRY4"}
  ],
  "offers": {
    "@type": "Offer",
    "price": "333.08",
    "priceCurrency": "USD",
    "priceValidUntil": "2026-09-14T21:20:54Z"
  },
  "provider": {"@type": "Organization", "name": "TradingView"}
}
```

`offers.price` is the quote. `priceValidUntil` is the timestamp it was valid at, which is the field that stops you mistaking a stale snapshot for a live one. And `identifier` hands you ISIN, CUSIP and FIGI, which is the part that makes this genuinely useful: those are the codes you need to join a scraped row against any real financial dataset, and they are rarely free.

## The five blocks

Match on `@type`, never on array position:

| `@type` | Carries |
|---|---|
| `FinancialProduct` | Name, category, ticker, ISIN, CUSIP, FIGI, the quote, a company description |
| `Dataset` | `name` such as `AAPL price data`, and `creator.name` which is the **exchange**, `NASDAQ` |
| `Organization` | TradingView itself, skip it |
| `BreadcrumbList` | The market and sector path |
| `FAQPage` | TradingView's own questions about the symbol |

The `Dataset` block is the one people miss. Its `creator.name` tells you which exchange the price came from, which matters as soon as you scrape a symbol listed in more than one place.

```python
import json, re

for block in re.findall(r'application/ld\+json[^>]*>(.*?)</script>', html, re.S):
    obj = json.loads(block)
    if obj.get("@type") == "FinancialProduct":
        quote = obj["offers"]
```

## URL shape

```
https://www.tradingview.com/symbols/<EXCHANGE>-<TICKER>/
```

`NASDAQ-AAPL`, `NYSE-JPM`, `LSE-SHEL`. The exchange prefix is required, and it is why `Dataset.creator.name` is worth reading back: it confirms you landed on the listing you meant rather than a secondary one.

## Cost, and why it stays at 1

Measured from `spb-cost` response headers:

| Configuration | Credits | Result |
|---|---|---|
| `mode=auto` | 1 | 565,017 bytes, all five blocks, quote present |
| Rejected request | 0 | Nothing billed |

There is no reason to escalate. `render_js` would cost 5 and fill a DOM node you are not reading. `premium_proxy` would cost 10 for a page that already returns cleanly on the plain rung.

`mode=auto` bills only the rung that worked and nothing if every rung fails. It cannot be combined with `render_js`, `premium_proxy` or `stealth_proxy`, and sending both returns HTTP 400 while billing nothing.

At 1 credit a symbol, a 500 name universe is 500 credits per pass. The entry paid tier of 250,000 credits covers 500 passes, which is a pass every 20 minutes through a trading week. That is a materially different budget from most quote scraping, and it comes entirely from not rendering.

ScrapingBee does not cache, so every repeat fetch is billed. Read `priceValidUntil` and skip symbols whose quote has not moved.

## What this does not give you

Worth being straight about, since the [TradingView scraper page](https://www.scrapingbee.com/scrapers/tradingview-api/) lists three jobs and this route covers one and a half of them.

- **Historical OHLCV series.** Not in the structured data. The chart series arrives over the socket, and this route reads the page, not the socket.
- **Technical signals and chart patterns.** Not in the structured data either.
- **Price alerts and watchlists.** These are per account features, so they sit behind a login and are out of scope entirely.

What you do get, cleanly and cheaply, is the current quote with its timestamp, the full symbol identity including the cross reference codes, the exchange, the category and the company description. For building and refreshing a symbol master, or for a periodic quote snapshot, that is the job done.

For a pure quote feed, [Yahoo finance scraper API](https://www.scrapingbee.com/scrapers/yahoo-finance-scraper-api/), [Nasdaq API](https://www.scrapingbee.com/scrapers/nasdaq-api/) and [Google finance scraper](https://www.scrapingbee.com/scrapers/google-finance-scraper/) are worth comparing.

## Scope

Public symbol pages. Watchlists, alerts, saved chart layouts, Pine scripts and anything requiring a signed in session are out of reach, and scraping under login credentials is prohibited by ScrapingBee's terms of service.

Market data on these pages is licensed to TradingView by the exchanges, and `Dataset.creator.name` names the exchange it came from. Redistributing exchange data usually requires a licence from that exchange, so a scraped quote is fine as an input to your own analysis and is not automatically yours to republish. [TradingView's Terms of Use](https://www.tradingview.com/policies/) govern the service. None of this is investment advice.

Reference: [extraction rules](https://www.scrapingbee.com/documentation/data-extraction/), [data extraction feature](https://www.scrapingbee.com/features/data-extraction/), [markdown output](https://www.scrapingbee.com/features/markdown-scraper/).

Adjacent finance endpoints: [crypto API](https://www.scrapingbee.com/scrapers/crypto-api/), [crypto news API](https://www.scrapingbee.com/scrapers/crypto-news-api/), [Investopedia scraper API](https://www.scrapingbee.com/scrapers/investopedia-scraper-api/), [financial news feed API](https://www.scrapingbee.com/scrapers/financial-news-feed-api/), [forex news feed API](https://www.scrapingbee.com/scrapers/forex-news-feed-api/), [economic news API](https://www.scrapingbee.com/scrapers/economic-news-api/), [StockX scraper API](https://www.scrapingbee.com/scrapers/stockx-scraper-api/).

## FAQ

**Do I need JavaScript rendering for TradingView?**
No. The quote is in the page's structured data before any script runs. Rendering costs five times more and fills a node you do not need.

**Why is my price selector returning an empty string?**
Because `js-symbol-last` is populated by the socket after load. Read `offers.price` from the `FinancialProduct` block instead.

**Can I get historical candles?**
Not from this route. OHLCV series arrive over the websocket and are not in the page markup.

**Where do I find the ISIN?**
In the `identifier` array on the `FinancialProduct` block, alongside CUSIP and FIGI.

**Which exchange did this price come from?**
`creator.name` on the `Dataset` block, which read `NASDAQ` for `NASDAQ-AAPL`.

**How fresh is the quote?**
Read `offers.priceValidUntil`, an ISO timestamp. Do not assume it equals your fetch time.

## License

MIT. See [LICENSE](LICENSE).
