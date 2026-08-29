import os
import time
import json
import math
import requests
import pandas as pd
from datetime import datetime, timezone

# ============================================================
# CONFIG
# ============================================================

API_KEY = os.environ["COINGECKO_API_KEY"]

BASE_URL = "https://api.coingecko.com/api/v3"
ONCHAIN_URL = "https://api.coingecko.com/api/v3/onchain"

HEADERS = {
    "x-cg-demo-api-key": API_KEY,
    "accept": "application/json",
}

NETWORK = "base"

MAX_POOLS = 100
OHLCV_LIMIT = 100

REQUEST_DELAY = 0.7

# ============================================================
# HTTP
# ============================================================

def get(url, params=None):
    r = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    if r.status_code == 429:
        print("Rate limit reached. Waiting...")
        time.sleep(10)
        r = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30
        )

    r.raise_for_status()
    return r.json()


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        value = float(value)

        if math.isnan(value) or math.isinf(value):
            return None

        return value

    except Exception:
        return None


def pct_change(a, b):
    if a is None or b is None or b == 0:
        return None

    return ((a / b) - 1.0) * 100.0


# ============================================================
# BASE POOLS
# ============================================================

def get_base_pools():
    """
    Retrieves active pools on Base.
    """

    url = f"{ONCHAIN_URL}/networks/{NETWORK}/pools"

    params = {
        "page": 1,
        "include": "base_token,quote_token",
        "sort": "h24_volume_usd_desc"
    }

    data = get(url, params)

    return data.get("data", [])


# ============================================================
# POOL PARSER
# ============================================================

def parse_pool(pool):
    attrs = pool.get("attributes", {})

    return {
        "pool_id": pool.get("id"),

        "name": attrs.get("name"),

        "address": attrs.get("address"),

        "base_token_price_usd":
            safe_float(attrs.get("base_token_price_usd")),

        "quote_token_price_usd":
            safe_float(attrs.get("quote_token_price_usd")),

        "fdv_usd":
            safe_float(attrs.get("fdv_usd")),

        "market_cap_usd":
            safe_float(attrs.get("market_cap_usd")),

        "reserve_usd":
            safe_float(attrs.get("reserve_in_usd")),

        "volume_5m":
            safe_float(
                attrs.get("volume_usd", {}).get("m5")
            ),

        "volume_1h":
            safe_float(
                attrs.get("volume_usd", {}).get("h1")
            ),

        "volume_6h":
            safe_float(
                attrs.get("volume_usd", {}).get("h6")
            ),

        "volume_24h":
            safe_float(
                attrs.get("volume_usd", {}).get("h24")
            ),

        "price_change_5m":
            safe_float(
                attrs.get("price_change_percentage", {}).get("m5")
            ),

        "price_change_1h":
            safe_float(
                attrs.get("price_change_percentage", {}).get("h1")
            ),

        "price_change_6h":
            safe_float(
                attrs.get("price_change_percentage", {}).get("h6")
            ),

        "price_change_24h":
            safe_float(
                attrs.get("price_change_percentage", {}).get("h24")
            ),

        "tx_5m":
            safe_float(
                attrs.get("transactions", {})
                .get("m5", {})
                .get("buys", 0)
            ) or 0
            +
            safe_float(
                attrs.get("transactions", {})
                .get("m5", {})
                .get("sells", 0)
            ) or 0,

        "tx_1h":
            safe_float(
                attrs.get("transactions", {})
                .get("h1", {})
                .get("buys", 0)
            ) or 0
            +
            safe_float(
                attrs.get("transactions", {})
                .get("h1", {})
                .get("sells", 0)
            ) or 0,

        "buys_5m":
            safe_float(
                attrs.get("transactions", {})
                .get("m5", {})
                .get("buys", 0)
            ) or 0,

        "sells_5m":
            safe_float(
                attrs.get("transactions", {})
                .get("m5", {})
                .get("sells", 0)
            ) or 0,

        "buys_1h":
            safe_float(
                attrs.get("transactions", {})
                .get("h1", {})
                .get("buys", 0)
            ) or 0,

        "sells_1h":
            safe_float(
                attrs.get("transactions", {})
                .get("h1", {})
                .get("sells", 0)
            ) or 0,
    }


# ============================================================
# DERIVED VOLUME FEATURES
# ============================================================

def add_volume_features(row):

    mc = row.get("market_cap_usd")
    liquidity = row.get("reserve_usd")

    v5 = row.get("volume_5m")
    v1 = row.get("volume_1h")
    v6 = row.get("volume_6h")
    v24 = row.get("volume_24h")

    # Volume / Market Cap
    if mc and mc > 0:
        row["volume_mc_5m"] = v5 / mc if v5 else None
        row["volume_mc_1h"] = v1 / mc if v1 else None
        row["volume_mc_24h"] = v24 / mc if v24 else None
    else:
        row["volume_mc_5m"] = None
        row["volume_mc_1h"] = None
        row["volume_mc_24h"] = None

    # Volume / Liquidity
    if liquidity and liquidity > 0:
        row["volume_liquidity_1h"] = (
            v1 / liquidity if v1 else None
        )

        row["volume_liquidity_24h"] = (
            v24 / liquidity if v24 else None
        )
    else:
        row["volume_liquidity_1h"] = None
        row["volume_liquidity_24h"] = None

    # Approximate volume acceleration
    if v1 and v6 and v6 > 0:
        expected_1h = v6 / 6.0

        row["volume_acceleration"] = (
            v1 / expected_1h
        )

    else:
        row["volume_acceleration"] = None

    # Buy / Sell imbalance
    buys = row.get("buys_5m", 0)
    sells = row.get("sells_5m", 0)

    total = buys + sells

    if total > 0:
        row["buy_ratio_5m"] = buys / total
        row["sell_ratio_5m"] = sells / total
        row["buy_sell_ratio_5m"] = buys / max(sells, 1)
    else:
        row["buy_ratio_5m"] = None
        row["sell_ratio_5m"] = None
        row["buy_sell_ratio_5m"] = None

    return row


# ============================================================
# OHLCV
# ============================================================

def get_ohlcv(pool_address):

    url = (
        f"{ONCHAIN_URL}/networks/"
        f"{NETWORK}/pools/"
        f"{pool_address}/ohlcv/minute"
    )

    params = {
        "aggregate": 5,
        "limit": OHLCV_LIMIT
    }

    try:
        data = get(url, params)

        rows = (
            data
            .get("data", {})
            .get("attributes", {})
            .get("ohlcv_list", [])
        )

        if not rows:
            return None

        df = pd.DataFrame(
            rows,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        )

        df = df.sort_values("timestamp")

        for col in [
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        return df.dropna()

    except Exception as e:

        print(
            f"OHLCV failed for {pool_address}: {e}"
        )

        return None


# ============================================================
# BOLLINGER
# ============================================================

def bollinger(df, period=20):

    close = df["close"]

    df["bb_mid"] = (
        close
        .rolling(period)
        .mean()
    )

    std = (
        close
        .rolling(period)
        .std()
    )

    df["bb_upper"] = (
        df["bb_mid"] + 2 * std
    )

    df["bb_lower"] = (
        df["bb_mid"] - 2 * std
    )

    df["bb_width"] = (
        (df["bb_upper"] - df["bb_lower"])
        / df["bb_mid"]
    )

    df["bb_percent_b"] = (
        (close - df["bb_lower"])
        /
        (df["bb_upper"] - df["bb_lower"])
    )

    return df


# ============================================================
# ICHIMOKU
# ============================================================

def ichimoku(df):

    high = df["high"]
    low = df["low"]

    conversion_high = (
        high.rolling(9).max()
    )

    conversion_low = (
        low.rolling(9).min()
    )

    df["tenkan"] = (
        conversion_high +
        conversion_low
    ) / 2

    base_high = (
        high.rolling(26).max()
    )

    base_low = (
        low.rolling(26).min()
    )

    df["kijun"] = (
        base_high +
        base_low
    ) / 2

    df["senkou_a"] = (
        (df["tenkan"] + df["kijun"]) / 2
    )

    span_b_high = (
        high.rolling(52).max()
    )

    span_b_low = (
        low.rolling(52).min()
    )

    df["senkou_b"] = (
        span_b_high +
        span_b_low
    ) / 2

    return df


# ============================================================
# CANDLE STRUCTURE
# ============================================================

def candle_features(df):

    df["body"] = (
        df["close"] - df["open"]
    ).abs()

    df["range"] = (
        df["high"] - df["low"]
    )

    df["upper_wick"] = (
        df["high"]
        -
        df[["open", "close"]].max(axis=1)
    )

    df["lower_wick"] = (
        df[["open", "close"]].min(axis=1)
        -
        df["low"]
    )

    df["body_ratio"] = (
        df["body"] /
        df["range"].replace(0, pd.NA)
    )

    df["green"] = (
        df["close"] > df["open"]
    )

    return df


# ============================================================
# RESEARCH FEATURES
# ============================================================

def extract_latest_features(df):

    if df is None or len(df) < 55:
        return {}

    df = bollinger(df)
    df = ichimoku(df)
    df = candle_features(df)

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    result = {}

    result["close"] = safe_float(
        latest["close"]
    )

    result["bb_width"] = safe_float(
        latest["bb_width"]
    )

    result["bb_percent_b"] = safe_float(
        latest["bb_percent_b"]
    )

    result["bb_squeeze"] = (
        latest["bb_width"] <
        df["bb_width"].rolling(50).quantile(
            0.20
        ).iloc[-1]
    )

    result["above_kijun"] = (
        latest["close"] >
        latest["kijun"]
    )

    result["above_cloud"] = (
        latest["close"] >
        max(
            latest["senkou_a"],
            latest["senkou_b"]
        )
    )

    result["tenkan_above_kijun"] = (
        latest["tenkan"] >
        latest["kijun"]
    )

    result["candle_body_ratio"] = safe_float(
        latest["body_ratio"]
    )

    result["green_candle"] = bool(
        latest["green"]
    )

    result["range_expansion"] = (
        latest["range"] >
        df["range"].rolling(20).mean().iloc[-1]
    )

    result["volume_expansion"] = (
        latest["volume"] >
        df["volume"].rolling(20).mean().iloc[-1] * 2
    )

    result["price_change_5c"] = safe_float(
        pct_change(
            latest["close"],
            df["close"].iloc[-6]
        )
    )

    return result


# ============================================================
# RESEARCH SCORE
# ============================================================

def research_score(row):

    score = 0
    reasons = []

    # IMPORTANT:
    # This is NOT a trading signal.
    # It is only a research ranking.

    if (
        row.get("volume_mc_1h") is not None
        and row["volume_mc_1h"] > 0.05
    ):
        score += 1
        reasons.append("high_volume_mc")

    if (
        row.get("volume_acceleration") is not None
        and row["volume_acceleration"] > 2
    ):
        score += 1
        reasons.append("volume_acceleration")

    if (
        row.get("buy_ratio_5m") is not None
        and row["buy_ratio_5m"] > 0.60
    ):
        score += 1
        reasons.append("buy_pressure")

    if (
        row.get("price_change_1h") is not None
        and 0 < row["price_change_1h"] < 15
    ):
        score += 1
        reasons.append("controlled_momentum")

    if row.get("bb_squeeze"):
        score += 1
        reasons.append("bb_squeeze")

    if row.get("above_kijun"):
        score += 1
        reasons.append("above_kijun")

    if row.get("above_cloud"):
        score += 1
        reasons.append("above_cloud")

    if row.get("range_expansion"):
        score += 1
        reasons.append("range_expansion")

    row["research_score"] = score
    row["research_reasons"] = reasons

    return row


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("BASE PUMP LAB SCANNER")
    print("=" * 60)

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    pools = get_base_pools()

    print(
        f"Pools received: {len(pools)}"
    )

    records = []

    for i, pool in enumerate(
        pools[:MAX_POOLS],
        start=1
    ):

        try:

            row = parse_pool(pool)

            row = add_volume_features(row)

            pool_address = row["address"]

            if pool_address:

                print(
                    f"[{i}] {row.get('name')}"
                )

                df = get_ohlcv(
                    pool_address
                )

                technical = (
                    extract_latest_features(df)
                    if df is not None
                    else {}
                )

                row.update(technical)

                row = research_score(row)

                records.append(row)

            time.sleep(
                REQUEST_DELAY
            )

        except Exception as e:

            print(
                f"Pool failed: {e}"
            )

    os.makedirs(
        "data",
        exist_ok=True
    )

    # JSON
    output_json = (
        "data/base_research.json"
    )

    with open(
        output_json,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "timestamp": timestamp,
                "network": NETWORK,
                "count": len(records),
                "records": records
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    # CSV
    output_csv = (
        "data/base_research.csv"
    )

    pd.DataFrame(
        records
    ).to_csv(
        output_csv,
        index=False
    )

    print("=" * 60)
    print(
        f"Saved {len(records)} records"
    )

    print(output_json)
    print(output_csv)

    # Top research candidates
    if records:

        df = pd.DataFrame(records)

        columns = [
            "name",
            "market_cap_usd",
            "reserve_usd",
            "volume_24h",
            "volume_mc_1h",
            "volume_acceleration",
            "buy_ratio_5m",
            "price_change_1h",
            "research_score"
        ]

        available = [
            c for c in columns
            if c in df.columns
        ]

        print("\nTOP RESEARCH CANDIDATES")

        print(
            df.sort_values(
                "research_score",
                ascending=False
            )[available]
            .head(20)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
