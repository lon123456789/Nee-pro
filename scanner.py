import os
import json
import time
import requests
from datetime import datetime, timezone

API_KEY = os.environ["COINGECKO_API_KEY"]

BASE_URL = "https://api.coingecko.com/api/v3"
ONCHAIN_URL = "https://api.coingecko.com/api/v3/onchain"

HEADERS = {
    "x-cg-demo-api-key": API_KEY,
    "accept": "application/json",
}

NETWORK = "base"

# تعداد Poolهایی که از CoinGecko می‌گیریم
MAX_POOLS = 100

REQUEST_DELAY = 0.7


def get(url, params=None):
    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code == 429:
        print("Rate limit reached. Waiting...")
        time.sleep(10)

        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30
        )

    response.raise_for_status()

    return response.json()


def safe_float(value):
    try:
        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def get_base_pools():
    url = f"{ONCHAIN_URL}/networks/{NETWORK}/pools"

    params = {
        "page": 1,
        "include": "base_token,quote_token",
        "sort": "h24_volume_usd_desc"
    }

    data = get(url, params)

    return data.get("data", [])


def parse_pool(pool):
    attrs = pool.get("attributes", {})

    return {
        "pool_id": pool.get("id"),
        "name": attrs.get("name"),
        "address": attrs.get("address"),

        "market_cap_usd": safe_float(
            attrs.get("market_cap_usd")
        ),

        "fdv_usd": safe_float(
            attrs.get("fdv_usd")
        ),

        "reserve_usd": safe_float(
            attrs.get("reserve_in_usd")
        ),

        "volume_24h": safe_float(
            attrs.get("volume_usd", {}).get("h24")
        ),

        "price_change_24h": safe_float(
            attrs.get("price_change_percentage", {}).get("h24")
        )
    }


def passes_research_filter(row):
    mc = row.get("market_cap_usd")
    liquidity = row.get("reserve_usd")
    name = str(row.get("name") or "").upper()

    if mc is None:
        return False

    if liquidity is None:
        return False

    # Market Cap
    if mc < 1_000_000:
        return False

    if mc > 100_000_000:
        return False

    # Liquidity
    if liquidity < 100_000:
        return False

    # دارایی‌ها / Poolهای نامطلوب
    excluded = (
        "USDC",
        "USDBC",
        "DAI",
        "USDT",
        "USDS",
        "USDE",
        "WETH",
        "ETH",
        "CBBTC",
        "CBTC",
        "WBTC",
        "BTC"
    )

    if any(symbol in name for symbol in excluded):
        return False

    return True


def main():
    print("=" * 60)
    print("BASE PUMP LAB SCANNER")
    print("=" * 60)

    timestamp = datetime.now(timezone.utc).isoformat()

    pools = get_base_pools()

    source_count = min(
        len(pools),
        MAX_POOLS
    )

    print(f"Source pools received: {len(pools)}")
    print(f"Scanning first: {source_count}")

    filtered = []

    for index, pool in enumerate(
        pools[:MAX_POOLS],
        start=1
    ):
        try:
            row = parse_pool(pool)

            name = row.get("name")

            print(
                f"[{index}/{source_count}] {name}"
            )

            if passes_research_filter(row):
                filtered.append(row)

            time.sleep(REQUEST_DELAY)

        except Exception as error:
            print(
                f"Pool failed: {error}"
            )

    os.makedirs(
        "data",
        exist_ok=True
    )

    output = {
        "timestamp": timestamp,
        "network": NETWORK,
        "source_pool_count": source_count,
        "count": len(filtered),
        "research_filter": {
            "market_cap_min_usd": 1_000_000,
            "market_cap_max_usd": 100_000_000,
            "liquidity_min_usd": 100_000,
            "source_pool_limit": MAX_POOLS
        },
        "records": filtered
    }

    output_path = "data/base_research.json"

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("=" * 60)
    print("RESEARCH FILTER RESULT")
    print("=" * 60)
    print(f"Source pools: {source_count}")
    print(f"Filtered pools: {len(filtered)}")
    print("Market Cap: $1M - $100M")
    print("Minimum Liquidity: $100K")
    print("=" * 60)

    for row in filtered:
        print(
            f"{row.get('name')} | "
            f"MC=${row.get('market_cap_usd')} | "
            f"Liquidity=${row.get('reserve_usd')}"
        )

    print("=" * 60)
    print(f"Saved: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
