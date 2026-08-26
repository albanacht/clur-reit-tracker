#!/usr/bin/env python3
"""CLUR daily update.

Reads data/positions.json, fetches closing prices, rewrites docs/data.json
and data/nav_history.csv. Fails loudly rather than committing partial data:
if any ticker cannot be priced, nothing is written at all.
"""
import csv
import json
import os
import sys

import yfinance as yf

ROOT = os.path.dirname(os.path.abspath(__file__))
POS = os.path.join(ROOT, "data", "positions.json")
NAV = os.path.join(ROOT, "data", "nav_history.csv")
OUT = os.path.join(ROOT, "docs", "data.json")

NAMES = {
    "APLE": "Apple Hospitality REIT",
    "CSR": "Centerspace",
    "CTO": "CTO Realty Growth",
    "EPR": "EPR Properties",
    "GTY": "Getty Realty",
    "INN": "Summit Hotel Properties",
    "PSTL": "Postal Realty Trust",
    "UE": "Urban Edge Properties",
}

FIELDS = ["date", "fund_nav", "fund_return_pct", "kbwy_price",
          "kbwy_return_pct", "vnq_price", "vnq_return_pct",
          "dividends_cumulative"]


def close_price(ticker):
    hist = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
    if hist.empty:
        raise RuntimeError("no price data returned for " + ticker)
    return float(hist["Close"].iloc[-1]), str(hist.index[-1].date())


def main():
    with open(POS) as fh:
        pos = json.load(fh)

    symbols = [p["ticker"] for p in pos["positions"]] + ["KBWY", "VNQ"]
    px = {}
    asof = ""
    for sym in symbols:
        price, day = close_price(sym)
        px[sym] = price
        asof = max(asof, day)

    base = pos["benchmark_baseline"]
    capital = pos["inception_capital_usd"]

    holdings = []
    nav = 0.0
    for p in pos["positions"]:
        tick = p["ticker"]
        value = p["shares"] * px[tick]
        nav += value
        holdings.append({
            "ticker": tick,
            "name": NAMES.get(tick, tick),
            "sector": p["sector"],
            "shares": p["shares"],
            "cost_basis": p["cost_basis"],
            "price": round(px[tick], 2),
            "value": round(value, 2),
            "gain_pct": round((px[tick] / p["cost_basis"] - 1) * 100, 2),
        })

    nav += pos.get("cash_usd", 0.0)
    for h in holdings:
        h["weight_pct"] = round(h["value"] / nav * 100, 2)

    fund_ret = round((nav / capital - 1) * 100, 2)
    kbwy_ret = round((px["KBWY"] / base["KBWY"] - 1) * 100, 2)
    vnq_ret = round((px["VNQ"] / base["VNQ"] - 1) * 100, 2)

    rows = []
    if os.path.exists(NAV):
        with open(NAV) as fh:
            rows = [r for r in csv.DictReader(fh) if r["date"] != asof]

    rows.append({
        "date": asof,
        "fund_nav": round(nav, 2),
        "fund_return_pct": fund_ret,
        "kbwy_price": round(px["KBWY"], 2),
        "kbwy_return_pct": kbwy_ret,
        "vnq_price": round(px["VNQ"], 2),
        "vnq_return_pct": vnq_ret,
        "dividends_cumulative": pos.get("cumulative_dividends_usd", 0.0),
    })
    rows.sort(key=lambda r: r["date"])

    with open(NAV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    out = {
        "fund_name": "Cluaran Capital Small-Cap REIT Factor Portfolio",
        "ticker": "CLUR",
        "inception_date": pos["inception_date"],
        "inception_capital": capital,
        "benchmark_primary": "KBWY",
        "benchmark_secondary": "VNQ",
        "drift_band": [8.5, 16.5],
        "as_of": asof,
        "current_nav": round(nav, 2),
        "cash": pos.get("cash_usd", 0.0),
        "dividends_cumulative": pos.get("cumulative_dividends_usd", 0.0),
        "fund_return_pct": fund_ret,
        "primary_return_pct": kbwy_ret,
        "secondary_return_pct": vnq_ret,
        "holdings": holdings,
        "nav_history": rows,
    }

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")

    print("%s  NAV %.2f (%+.2f%%)  KBWY %+.2f%%  VNQ %+.2f%%"
          % (asof, nav, fund_ret, kbwy_ret, vnq_ret))
    return 0


if __name__ == "__main__":
    sys.exit(main())
