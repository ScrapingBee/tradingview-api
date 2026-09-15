"""TradingView symbol data from structured data, for 1 credit.

Verified live on 2026-09-15 against tradingview.com/symbols/NASDAQ-AAPL/.

Do NOT render this page. The visible price node, span.js-symbol-last with
data-qa-id="symbol-last-value", is EMPTY on load and is filled by the
websocket. The quote is already in the FinancialProduct structured data
before any script runs.
Set SCRAPINGBEE_API_KEY in your environment before running.
"""

import json
import os
import re

import requests

BASE = "https://app.scrapingbee.com/api/v1/"
HEADERS = {"Authorization": f"Bearer {os.environ['SCRAPINGBEE_API_KEY']}"}

LD_BLOCK = re.compile(r"application/ld\+json[^>]*>(.*?)</script>", re.S)


def _blocks(html):
    """Five blocks per symbol page. Match on @type, never on position."""
    out = []
    for raw in LD_BLOCK.findall(html):
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def symbol(exchange, ticker):
    """1 credit. The exchange prefix is required: NASDAQ-AAPL, NYSE-JPM.

    mode=auto settles on the plain rung here. render_js would cost 5 and
    premium_proxy 10, for a page that already returns everything.
    """
    url = f"https://www.tradingview.com/symbols/{exchange}-{ticker}/"
    r = requests.get(
        BASE, headers=HEADERS, params={"url": url, "mode": "auto"}, timeout=180
    )
    r.raise_for_status()

    out = {"url": url, "credits": r.headers.get("spb-cost")}
    for obj in _blocks(r.text):
        if not isinstance(obj, dict):
            continue

        if obj.get("@type") == "FinancialProduct":
            offers = obj.get("offers") or {}
            # identifier carries the cross reference codes you need to join
            # a scraped row against any real financial dataset.
            codes = {
                i.get("propertyID"): i.get("value")
                for i in obj.get("identifier") or []
                if isinstance(i, dict)
            }
            out.update(
                name=obj.get("name"),
                category=obj.get("category"),
                ticker=obj.get("tickerSymbol"),
                isin=codes.get("ISIN"),
                cusip=codes.get("CUSIP"),
                figi=codes.get("FIGI"),
                price=_to_float(offers.get("price")),
                currency=offers.get("priceCurrency"),
                # The timestamp the quote was valid at, which is NOT your
                # fetch time. Use it to skip symbols that have not moved.
                price_valid_until=offers.get("priceValidUntil"),
                description=obj.get("description"),
            )

        elif obj.get("@type") == "Dataset":
            # creator.name is the EXCHANGE the price came from, which
            # matters for any symbol listed in more than one place.
            out["exchange"] = (obj.get("creator") or {}).get("name")
            out["dataset"] = obj.get("name")

    return out


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def universe(pairs):
    """One credit per symbol, so a 500 name universe is 500 credits."""
    return [symbol(ex, tk) for ex, tk in pairs]


if __name__ == "__main__":
    q = symbol("NASDAQ", "AAPL")
    print(f"{q['name']} ({q['ticker']}) on {q['exchange']}  [{q['credits']} credit]")
    print(f"  {q['price']} {q['currency']}  valid until {q['price_valid_until']}")
    print(f"  category {q['category']}")
    print(f"  ISIN {q['isin']}  CUSIP {q['cusip']}  FIGI {q['figi']}")
    print(f"  dataset: {q['dataset']}")

    for ex, tk in (("NYSE", "JPM"),):
        s = symbol(ex, tk)
        print(f"\n  {s['ticker']:<6} {str(s['price']):>10} {s['currency']}  {s['exchange']}  {s['isin']}")
