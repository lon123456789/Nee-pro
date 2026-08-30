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

# Scan a larger universe BEFORE applying filters

MAX_POOLS = 100

OHLCV_LIMIT = 50
REQUEST_DELAY = 0.7

# Research universe filters

MIN_MARKET_CAP = 1_000_000
MAX_MARKET_CAP = 100_000_000
MIN_LIQUIDITY = 100_000

EXCLUDED_SYMBOLS = (
"USDC",
"USDBC",
"DAI",
"USDT",
"USDS",
"USDE",
"WETH",
"ETH",
"CBBTC",
"WBTC",
"BTC",
)

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

```
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
```

# ============================================================

# HELPERS

# ============================================================

def safe_float(value):

```
try:
    if value is None:
        return None

    value = float(value)

    if math.isnan(value) or math.isinf(value):
        return None

    return value

except Exception:
    return None
```

def pct_change(a, b):

```
if a is None or b is None or b == 0:
    return None

return ((a / b) - 1.0) * 100.0
```

# ============================================================

# GET BASE POOLS

# ============================================================

def get_base_pools():

```
url = f"{ONCHAIN_URL}/networks/{NETWORK}/pools"

params = {
    "page": 1,
    "include": "base_token,quote_token",
    "sort": "h24_volume_usd_desc"
}

data = get(url, params)

return data.get("data", [])
```

# ============================================================

# PARSE POOL

# ============================================================

def parse_pool(pool):

```
attrs = pool.get("attributes", {})

transactions = attrs.get("transactions", {})

m5 = transactions.get("m5", {})
h1 = transactions.get("h1", {})

buys_5m = safe_float(m5.get("buys", 0)) or 0
sells_5m = safe_float(m5.get("sells", 0)) or 0

buys_1h = safe_float(h1.get("buys", 0)) or 0
sells_1h = safe_float(h1.get("sells", 0)) or 0

return {

    "pool_id":
        pool.get("id"),

    "name":
        attrs.get("name"),

    "address":
        attrs.get("address"),

    "base_token_price_usd":
        safe_float(
            attrs.get("base_token_price_usd")
        ),

    "quote_token_price_usd":
        safe_float(
            attrs.get("quote_token_price_usd")
        ),

    "fdv_usd":
        safe_float(
            attrs.get("fdv_usd")
        ),

    "market_cap_usd":
        safe_float(
            attrs.get("market_cap_usd")
        ),

    "reserve_usd":
        safe_float(
            attrs.get("reserve_in_usd")
        ),

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
            attrs.get(
                "price_change_percentage", {}
            ).get("m5")
        ),

    "price_change_1h":
        safe_float(
            attrs.get(
                "price_change_percentage", {}
            ).get("h1")
        ),

    "price_change_6h":
        safe_float(
            attrs.get(
                "price_change_percentage", {}
            ).get("h6")
        ),

    "price_change_24h":
        safe_float(
            attrs.get(
                "price_change_percentage", {}
            ).get("h24")
        ),

    "tx_5m":
        buys_5m + sells_5m,

    "tx_1h":
        buys_1h + sells_1h,

    "buys_5m":
        buys_5m,

    "sells_5m":
        sells_5m,

    "buys_1h":
        buys_1h,

    "sells_1h":
        sells_1h,
}
```

# ============================================================

# UNIVERSE FILTER

# ============================================================

def passes_research_filter(row):

```
mc = row.get("market_cap_usd")
liquidity = row.get("reserve_usd")
name = str(row.get("name") or "").upper()

if mc is None:
    return False

if liquidity is None:
    return False

if mc < MIN_MARKET_CAP:
    return False

if mc > MAX_MARKET_CAP:
    return False

if liquidity < MIN_LIQUIDITY:
    return False

if any(symbol in name for symbol in EXCLUDED_SYMBOLS):
    return False

return True
```

# ============================================================

# DERIVED VOLUME FEATURES

# ============================================================

def add_volume_features(row):

```
mc = row.get("market_cap_usd")
liquidity = row.get("reserve_usd")

v5 = row.get("volume_5m")
v1 = row.get("volume_1h")
v6 = row.get("volume_6h")
v24 = row.get("volume_24h")

if mc and mc > 0:

    row["volume_mc_5m"] = (
        v5 / mc if v5 else None
    )

    row["volume_mc_1h"] = (
        v1 / mc if v1 else None
    )

    row["volume_mc_24h"] = (
        v24 / mc if v24 else None
    )

else:

    row["volume_mc_5m"] = None
    row["volume_mc_1h"] = None
    row["volume_mc_24h"] = None

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

if v1 and v6 and v6 > 0:

    expected_1h = v6 / 6.0

    row["volume_acceleration"] = (
        v1 / expected_1h
    )

else:

    row["volume_acceleration"] = None

buys = row.get("buys_5m", 0)
sells = row.get("sells_5m", 0)

total = buys + sells

if total > 0:

    row["buy_ratio_5m"] = buys / total

    row["sell_ratio_5m"] = sells / total

    row["buy_sell_ratio_5m"] = (
        buys / max(sells, 1)
    )

else:

    row["buy_ratio_5m"] = None
    row["sell_ratio_5m"] = None
    row["buy_sell_ratio_5m"] = None

return row
```

# ============================================================

# OHLCV

# ============================================================

def get_ohlcv(pool_address):

```
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
```

# ============================================================

# BOLLINGER

# ============================================================

def bollinger(df, period=20):

```
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

denominator = (
    df["bb_upper"] - df["bb_lower"]
)

df["bb_percent_b"] = (
    (close - df["bb_lower"])
    / denominator.replace(0, pd.NA)
)

return df
```

# ============================================================

# ICHIMOKU

# ============================================================

def ichimoku(df):

```
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
)

return df
```

# ============================================================

# CANDLE FEATURES

# ============================================================

def candle_features(df):

```
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
    df["body"]
    /
    df["range"].replace(0, pd.NA)
)

df["green"] = (
    df["close"] > df["open"]
)

return df
```

# ============================================================

# TECHNICAL FEATURES

# ============================================================

def extract_latest_features(df):

```
if df is None or len(df) < 55:
    return {}

df = bollinger(df)

df = ichimoku(df)

df = candle_features(df)

latest = df.iloc[-1]

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

squeeze_level = (
    df["bb_width"]
    .rolling(50)
    .quantile(0.20)
    .iloc[-1]
)

result["bb_squeeze"] = bool(
    pd.notna(squeeze_level)
    and
    pd.notna(latest["bb_width"])
    and
    latest["bb_width"] < squeeze_level
)

result["above_kijun"] = bool(
    pd.notna(latest["kijun"])
    and
    latest["close"] > latest["kijun"]
)

cloud_values = [
    latest["senkou_a"],
    latest["senkou_b"]
]

cloud_values = [
    x for x in cloud_values
    if pd.notna(x)
]

result["above_cloud"] = bool(
    cloud_values
    and
    latest["close"] > max(cloud_values)
)

result["tenkan_above_kijun"] = bool(
    pd.notna(latest["tenkan"])
    and
    pd.notna(latest["kijun"])
    and
    latest["tenkan"] > latest["kijun"]
)

result["candle_body_ratio"] = safe_float(
    latest["body_ratio"]
)

result["green_candle"] = bool(
    latest["green"]
)

range_average = (
    df["range"]
    .rolling(20)
    .mean()
    .iloc[-1]
)

result["range_expansion"] = bool(
    pd.notna(range_average)
    and
    latest["range"] > range_average
)

volume_average = (
    df["volume"]
    .rolling(20)
    .mean()
    .iloc[-1]
)

result["volume_expansion"] = bool(
    pd.notna(volume_average)
    and
    latest["volume"] > volume_average * 2
)

result["price_change_5c"] = safe_float(
    pct_change(
        latest["close"],
        df["close"].iloc[-6]
    )
)

return result
```

# ============================================================

# RESEARCH SCORE

# ============================================================

def research_score(row):

```
score = 0

reasons = []

if (
    row.get("volume_mc_1h") is not None
    and
    row["volume_mc_1h"] > 0.05
):

    score += 1

    reasons.append(
        "high_volume_mc"
    )

if (
    row.get("volume_acceleration") is not None
    and
    row["volume_acceleration"] > 2
):

    score += 1

    reasons.append(
        "volume_acceleration"
    )

if (
    row.get("buy_ratio_5m") is not None
    and
    row["buy_ratio_5m"] > 0.60
):

    score += 1

    reasons.append(
        "buy_pressure"
    )

if (
    row.get("price_change_1h") is not None
    and
    0 < row["price_change_1h"] < 15
):

    score += 1

    reasons.append(
        "controlled_momentum"
    )

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
```

# ============================================================

# MAIN

# ============================================================

def main():

```
print("=" * 60)
print("BASE PUMP LAB SCANNER")
print("=" * 60)

timestamp = datetime.now(
    timezone.utc
).isoformat()

pools = get_base_pools()

source_count = len(pools)

print(
    f"Pools received from CoinGecko: {source_count}"
)

# --------------------------------------------------------
# FIRST FILTER
# --------------------------------------------------------

universe = []

for pool in pools[:MAX_POOLS]:

    try:

        row = parse_pool(pool)

        if passes_research_filter(row):

            universe.append(row)

    except Exception as e:

        print(
            f"Filter failed: {e}"
        )

print("=" * 60)
print("RESEARCH UNIVERSE FILTER")
print("=" * 60)

print(
    f"Source pools scanned: {min(source_count, MAX_POOLS)}"
)

print(
    f"Pools after MC/Liquidity filters: {len(universe)}"
)

print(
    f"Market Cap: ${MIN_MARKET_CAP:,} - ${MAX_MARKET_CAP:,}"
)

print(
    f"Minimum Liquidity: ${MIN_LIQUIDITY:,}"
)

print("=" * 60)

# --------------------------------------------------------
# TECHNICAL ANALYSIS ONLY ON FILTERED UNIVERSE
# --------------------------------------------------------

records = []

for i, row in enumerate(
    universe,
    start=1
):

    try:

        row = add_volume_features(row)

        pool_address = row.get("address")

        if not pool_address:
            continue

        print(
            f"[{i}/{len(universe)}] "
            f"{row.get('name')}"
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

# --------------------------------------------------------
# OUTPUT
# --------------------------------------------------------

os.makedirs(
    "data",
    exist_ok=True
)

output = {
    "timestamp": timestamp,
    "network": NETWORK,
    "count": len(records),
    "source_pool_count": min(
        source_count,
        MAX_POOLS
    ),
    "records": records,
    "research_filter": {
        "market_cap_min_usd":
            MIN_MARKET_CAP,

        "market_cap_max_usd":
            MAX_MARKET_CAP,

        "liquidity_min_usd":
            MIN_LIQUIDITY,

        "excluded_assets":
            list(EXCLUDED_SYMBOLS)
    }
}

output_json = (
    "data/base_research.json"
)

with open(
    output_json,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        output,
        f,
        ensure_ascii=False,
        indent=2,
        allow_nan=False
    )

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
    f"Saved {len(records)} filtered records"
)

print(output_json)

print(output_csv)

# --------------------------------------------------------
# TOP CANDIDATES
# --------------------------------------------------------

if records:

    df = pd.DataFrame(
        records
    )

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

    print(
        "\nTOP RESEARCH CANDIDATES"
    )

    print(
        df.sort_values(
            "research_score",
            ascending=False
        )[available]
        .head(20)
        .to_string(index=False)
    )
```

if **name** == "**main**":
main()
