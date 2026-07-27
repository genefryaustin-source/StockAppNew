"""
modules/crypto/crypto_service.py

Enhanced crypto data service.

Sources (all free, no new keys):
  CoinGecko  — prices, market data, OHLC, global stats, trending, DeFi
  Alternative.me — Fear & Greed Index
  DeFi Llama — DeFi protocol TVL
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests

_CACHE: dict = {}
_TTL = {
    "quote":    60,
    "markets":  120,
    "global":   180,
    "trending": 300,
    "history":  900,
    "defi":     600,
    "fear":     3600,
    "detail":   300,
    "categories": 600,
}

# 250 top coins (CoinGecko IDs) — expanded from original 5
TOP_COINS = [
    "bitcoin","ethereum","tether","binancecoin","solana","ripple",
    "usd-coin","staked-ether","dogecoin","tron","cardano","avalanche-2",
    "shiba-inu","polkadot","bitcoin-cash","chainlink","near","litecoin",
    "uniswap","internet-computer","leo-token","dai","ethereum-classic",
    "stellar","okb","monero","cosmos","hedera-hashgraph","aptos",
    "mantle","filecoin","arbitrum","vechain","the-graph","injective-protocol",
    "algorand","render-token","fantom","aave","maker","theta-token",
    "optimism","quant-network","sui","kaspa","celestia","immutable-x",
    "thorchain","bittensor","floki","fetch-ai","pyth-network","wormhole",
    "worldcoin-wld","bonk","sei-network","ondo-finance","jupiter-exchange-solana",
    "pendle","axelar","stacks","kava","oasis-network","enjincoin",
    "blur","dydx","frax-share","blur","sandbox","decentraland",
    "gala","axie-infinity","stepn","the-sandbox","illuvium",
]

COIN_SYMBOLS = {
    "bitcoin":"BTC","ethereum":"ETH","tether":"USDT","binancecoin":"BNB",
    "solana":"SOL","ripple":"XRP","usd-coin":"USDC","staked-ether":"stETH",
    "dogecoin":"DOGE","tron":"TRX","cardano":"ADA","avalanche-2":"AVAX",
    "shiba-inu":"SHIB","polkadot":"DOT","bitcoin-cash":"BCH","chainlink":"LINK",
    "near":"NEAR","litecoin":"LTC","uniswap":"UNI","internet-computer":"ICP",
    "dai":"DAI","ethereum-classic":"ETC","stellar":"XLM","monero":"XMR",
    "cosmos":"ATOM","hedera-hashgraph":"HBAR","aptos":"APT","filecoin":"FIL",
    "arbitrum":"ARB","vechain":"VET","the-graph":"GRT","injective-protocol":"INJ",
    "algorand":"ALGO","render-token":"RNDR","fantom":"FTM","aave":"AAVE",
    "maker":"MKR","theta-token":"THETA","optimism":"OP","sui":"SUI",
    "kaspa":"KAS","celestia":"TIA","immutable-x":"IMX","bittensor":"TAO",
    "fetch-ai":"FET","pyth-network":"PYTH","worldcoin-wld":"WLD","bonk":"BONK",
    "sei-network":"SEI","ondo-finance":"ONDO","pendle":"PENDLE","stacks":"STX",
    "kava":"KAVA","gala":"GALA","axie-infinity":"AXS","sandbox":"SAND",
    "decentraland":"MANA",
}

CATEGORIES = [
    "All","Layer 1","Layer 2","DeFi","GameFi / NFT","Meme Coins",
    "Stablecoins","AI Crypto","RWA","Liquid Staking","DEX",
]


def _cached(key: str, ttl_key: str = "quote"):
    e = _CACHE.get(key)
    ttl = _TTL.get(ttl_key, 120)
    return e["d"] if e and time.time() - e["t"] < ttl else None


def _cache(key: str, d):
    _CACHE[key] = {"d": d, "t": time.time()}
    return d


def _cg_get(path: str, params: dict = None):
    """CoinGecko API call with retry."""
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3{path}",
            params=params or {},
            headers={"Accept": "application/json",
                     "User-Agent": "Mozilla/5.0"},
            timeout=12,
        )
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            time.sleep(2)
            r2 = requests.get(f"https://api.coingecko.com/api/v3{path}",
                               params=params or {}, timeout=12)
            return r2.json() if r2.status_code == 200 else None
    except Exception as e:
        print(f"[crypto] CoinGecko error {path}: {e}")
    return None


# ── Market data ────────────────────────────────────────────────────────────────

def get_top_coins(limit: int = 100, category: str = None) -> pd.DataFrame:
    cache_key = f"top_{limit}_{category}"
    cached = _cached(cache_key, "markets")
    if cached is not None:
        return cached

    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": min(limit, 250),
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h,7d,30d",
    }
    if category and category != "All":
        cat_map = {
            "Layer 1":       "layer-1",
            "Layer 2":       "layer-2",
            "DeFi":          "decentralized-finance-defi",
            "GameFi / NFT":  "gaming",
            "Meme Coins":    "meme-token",
            "Stablecoins":   "stablecoins",
            "AI Crypto":     "artificial-intelligence",
            "RWA":           "real-world-assets-rwa",
            "Liquid Staking":"liquid-staking-tokens",
            "DEX":           "decentralized-exchange",
        }
        if category in cat_map:
            params["category"] = cat_map[category]

    data = _cg_get("/coins/markets", params)
    if not data:
        return pd.DataFrame()

    rows = []
    for coin in data:
        rows.append({
            "id":          coin.get("id",""),
            "Symbol":      str(coin.get("symbol","")).upper(),
            "Name":        coin.get("name",""),
            "Price":       coin.get("current_price"),
            "1h %":        coin.get("price_change_percentage_1h_in_currency"),
            "24h %":       coin.get("price_change_percentage_24h"),
            "7d %":        coin.get("price_change_percentage_7d_in_currency"),
            "30d %":       coin.get("price_change_percentage_30d_in_currency"),
            "Market Cap":  coin.get("market_cap"),
            "Volume 24h":  coin.get("total_volume"),
            "Circulating": coin.get("circulating_supply"),
            "ATH":         coin.get("ath"),
            "ATH %":       coin.get("ath_change_percentage"),
            "Rank":        coin.get("market_cap_rank"),
        })

    df = pd.DataFrame(rows)
    return _cache(cache_key, df)


def get_coin_detail(coin_id: str) -> dict:
    cached = _cached(f"detail_{coin_id}", "detail")
    if cached: return cached

    data = _cg_get(f"/coins/{coin_id}", {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "true",
        "developer_data": "false",
    })
    if not data:
        return {}
    return _cache(f"detail_{coin_id}", data)


def get_coin_history(coin_id: str, days: int = 365) -> pd.DataFrame:
    cache_key = f"hist_{coin_id}_{days}"
    cached = _cached(cache_key, "history")
    if cached is not None:
        return cached

    # Use market_chart for daily (more points than OHLC)
    if days > 90:
        data = _cg_get(f"/coins/{coin_id}/market_chart", {
            "vs_currency": "usd", "days": days, "interval": "daily"
        })
        if data and "prices" in data:
            prices   = data["prices"]
            volumes  = data.get("total_volumes", [])
            mkt_caps = data.get("market_caps", [])
            df = pd.DataFrame(prices, columns=["ts","close"])
            df["Date"]   = pd.to_datetime(df["ts"], unit="ms")
            df["volume"] = [v[1] for v in volumes[:len(df)]] if volumes else 0
            df["mkt_cap"]= [m[1] for m in mkt_caps[:len(df)]] if mkt_caps else 0
            df = df.drop("ts", axis=1)
            return _cache(cache_key, df)

    # OHLC for shorter periods
    data = _cg_get(f"/coins/{coin_id}/ohlc", {"vs_currency": "usd", "days": days})
    if data:
        df = pd.DataFrame(data, columns=["ts","open","high","low","close"])
        df["Date"] = pd.to_datetime(df["ts"], unit="ms")
        return _cache(cache_key, df.drop("ts", axis=1))

    return pd.DataFrame()


def get_global_stats() -> dict:
    cached = _cached("global", "global")
    if cached: return cached

    data = _cg_get("/global")
    if not data or "data" not in data:
        return {}
    return _cache("global", data["data"])


def get_trending() -> list[dict]:
    cached = _cached("trending", "trending")
    if cached: return cached

    data = _cg_get("/search/trending")
    if not data or "coins" not in data:
        return []
    trending = []
    for item in data["coins"][:10]:
        c = item.get("item", {})
        trending.append({
            "id":     c.get("id",""),
            "Symbol": str(c.get("symbol","")).upper(),
            "Name":   c.get("name",""),
            "Rank":   c.get("market_cap_rank","—"),
            "Score":  c.get("score",0),
            "thumb":  c.get("thumb",""),
        })
    return _cache("trending", trending)


def get_fear_greed(limit: int = 30) -> pd.DataFrame:
    cached = _cached("fear_greed", "fear")
    if cached is not None:
        return cached

    try:
        r = requests.get(
            f"https://api.alternative.me/fng/?limit={limit}&format=json",
            timeout=8
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            df = pd.DataFrame(data)
            if not df.empty:
                df["value"]     = pd.to_numeric(df["value"], errors="coerce")
                df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="s")
                df = df.rename(columns={"value_classification": "classification"})
                df = df[["timestamp","value","classification"]].sort_values("timestamp")
                return _cache("fear_greed", df)
    except Exception as e:
        print(f"[crypto] Fear & Greed error: {e}")
    return pd.DataFrame()


def get_defi_protocols(limit: int = 20) -> pd.DataFrame:
    cached = _cached("defi_protocols", "defi")
    if cached is not None:
        return cached

    try:
        r = requests.get("https://api.llama.fi/protocols", timeout=10)
        if r.status_code == 200:
            data = r.json()[:limit]
            rows = []
            for p in data:
                rows.append({
                    "Protocol":  p.get("name",""),
                    "Category":  p.get("category",""),
                    "Chain":     p.get("chain",""),
                    "TVL ($B)":  round(float(p.get("tvl",0)) / 1e9, 2),
                    "1d %":      round(float((p.get("change_1d") or 0)), 2),
                    "7d %":      round(float((p.get("change_7d") or 0)), 2),
                    "Symbol":    str(p.get("symbol","")).upper(),
                })
            df = pd.DataFrame(rows)
            return _cache("defi_protocols", df)
    except Exception as e:
        print(f"[crypto] DeFi Llama error: {e}")
    return pd.DataFrame()


def search_coin(query: str) -> list[dict]:
    """Search CoinGecko for a coin by name or symbol."""
    data = _cg_get("/search", {"query": query})
    if not data or "coins" not in data:
        return []
    return [
        {"id": c["id"], "Symbol": c["symbol"].upper(), "Name": c["name"],
         "Rank": c.get("market_cap_rank","—")}
        for c in data["coins"][:10]
    ]