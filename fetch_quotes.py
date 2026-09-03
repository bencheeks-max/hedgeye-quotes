#!/usr/bin/env python3
"""Fetch real-time IEX quotes from Alpaca for every symbol in tickers.txt
and write them to quotes.json. Runs inside GitHub Actions; keys come from
repo secrets, never from the file itself."""
import json, os, sys, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

BASE = "https://data.alpaca.markets/v2/stocks"


def read_tickers():
    raw = open("tickers.txt", encoding="utf-8").read()
    seen = []
    for tok in raw.replace(",", "\n").splitlines():
        t = tok.strip().upper()
        if t and not t.startswith("#") and t not in seen:
            seen.append(t)
    return seen


def alpaca_get(path, symbols):
    key, secret = os.environ["ALPACA_KEY"], os.environ["ALPACA_SECRET"]
    q = urllib.parse.urlencode({"symbols": ",".join(symbols), "feed": "iex"})
    req = urllib.request.Request(
        f"{BASE}/{path}?{q}",
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
                 "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(f"Alpaca HTTP {e.code} on {path}: {body}", file=sys.stderr)
        raise


def main():
    syms = read_tickers()
    if not syms:
        print("tickers.txt is empty", file=sys.stderr)
        return 1
    quotes = alpaca_get("quotes/latest", syms).get("quotes", {})
    trades = alpaca_get("trades/latest", syms).get("trades", {})
    out, missing = {}, []
    for s in syms:
        q, t = quotes.get(s, {}), trades.get(s, {})
        bid, ask, last = q.get("bp"), q.get("ap"), t.get("p")
        mid = round((bid + ask) / 2, 4) if bid and ask and bid > 0 and ask > 0 else None
        found = bool(q or t)
        if not found:
            missing.append(s)
        out[s] = {"price": mid if mid is not None else last, "mid": mid,
                  "bid": bid, "ask": ask, "last": last,
                  "quote_time": q.get("t"), "trade_time": t.get("t"), "found": found}
    result = {"as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "feed": "iex", "count": len(syms), "missing": missing, "quotes": out}
    with open("quotes.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"wrote quotes.json: {len(syms)} symbols, {len(missing)} missing {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
