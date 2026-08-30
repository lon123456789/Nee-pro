import os
import json
import time
import requests
from datetime import datetime, timezone

API_KEY = os.environ["COINGECKO_API_KEY"]

ONCHAIN_URL = "https://api.coingecko.com/api/v3/onchain"

NETWORK = "base"

# هدف: جمع‌آوری 100 Pool
MAX_POOLS = 100

# هر صفحه حداکثر 20 Pool دارد
# 5 صفحه = حداکثر 100 Pool
MAX_PAGES = 5

REQUEST_DELAY = 0.7

HEADERS = {
    "x-cg-demo-api-key": API_KEY,
    "accept": "application/json",
}


# ============================================================
# EXCLUDED ASSETS
# ============================================================

EXCLUDED = (
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
    "BTC",
)


# ============================================================
# HTTP
# ============================================================

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


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value):

    try:

        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):

        return None


# ============================================================
# GET BASE POOLS
# ============================================================

def get_base_pools():

    url = (
        f"{ONCHAIN_URL}/networks/"
        f"{NETWORK}/pools"
    )

    pools = []

    seen = set()

    pages_used = 0

    for page in range(
        1,
        MAX_PAGES + 1
    ):

        print(
            f"Requesting Base pools page {page}..."
        )

        params = {
            "page": page,
            "include": "base_token,quote_token",
            "sort": "h24_volume_usd_desc"
        }

        data = get(
            url,
            params
        )

        batch = data.get(
            "data",
            []
        )

        pages_used += 1

        print(
            f"Page {page}: {len(batch)} pools"
        )

        if not batch:
            break

        for pool in batch:

            pool_id = pool.get(
                "id"
            )

            if (
                pool_id
                and pool_id not in seen
            ):

                seen.add(
                    pool_id
                )

                pools.append(
                    pool
                )

                if len(pools) >= MAX_POOLS:

                    return (
                        pools,
                        pages_used
                    )

        # اگر کمتر از 20 آمد،
        # یعنی صفحه آخر است.

        if len(batch) < 20:

            break

        time.sleep(
            REQUEST_DELAY
        )

    return (
        pools,
        pages_used
    )


# ============================================================
# PARSE POOL
# ============================================================

def parse_pool(pool):

    attrs = pool.get(
        "attributes",
        {}
    )

    return {

        "pool_id":
            pool.get("id"),

        "name":
            attrs.get("name"),

        "address":
            attrs.get("address"),

        "market_cap_usd":
            safe_float(
                attrs.get(
                    "market_cap_usd"
                )
            ),

        "fdv_usd":
            safe_float(
                attrs.get(
                    "fdv_usd"
                )
            ),

        "reserve_usd":
            safe_float(
                attrs.get(
                    "reserve_in_usd"
                )
            ),

        "volume_24h":
            safe_float(
                attrs.get(
                    "volume_usd",
                    {}
                ).get(
                    "h24"
                )
            ),

        "price_change_24h":
            safe_float(
                attrs.get(
                    "price_change_percentage",
                    {}
                ).get(
                    "h24"
                )
            )
    }


# ============================================================
# RESEARCH FILTER
# ============================================================

def passes_research_filter(row):

    mc = row.get(
        "market_cap_usd"
    )

    liquidity = row.get(
        "reserve_usd"
    )

    name = str(
        row.get("name") or ""
    ).upper()


    # --------------------------------------------------------
    # Market Cap must be VERIFIED
    # --------------------------------------------------------

    if mc is None:

        return False


    # --------------------------------------------------------
    # Market Cap: $1M - $100M
    # --------------------------------------------------------

    if mc < 1_000_000:

        return False

    if mc > 100_000_000:

        return False


    # --------------------------------------------------------
    # Minimum Liquidity: $100K
    # --------------------------------------------------------

    if liquidity is None:

        return False

    if liquidity < 100_000:

        return False


    # --------------------------------------------------------
    # Excluded assets
    # --------------------------------------------------------

    if any(
        symbol in name
        for symbol in EXCLUDED
    ):

        return False


    return True


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


    # --------------------------------------------------------
    # GET POOLS
    # --------------------------------------------------------

    pools, pages_used = get_base_pools()


    print("=" * 60)

    print(
        f"Source pools collected: {len(pools)}"
    )

    print(
        f"Pages used: {pages_used}"
    )

    print("=" * 60)


    # --------------------------------------------------------
    # PARSE
    # --------------------------------------------------------

    parsed = []

    for pool in pools:

        try:

            parsed.append(
                parse_pool(pool)
            )

        except Exception as error:

            print(
                f"Parse failed: {error}"
            )


    # --------------------------------------------------------
    # FILTER
    # --------------------------------------------------------

    filtered = []

    for row in parsed:

        if passes_research_filter(row):

            filtered.append(
                row
            )


    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    os.makedirs(
        "data",
        exist_ok=True
    )


    output = {

        "timestamp":
            timestamp,

        "network":
            NETWORK,

        "source_pool_count":
            len(pools),

        "parsed_pool_count":
            len(parsed),

        "pages_used":
            pages_used,

        "count":
            len(filtered),

        "research_filter": {

            "market_cap_min_usd":
                1_000_000,

            "market_cap_max_usd":
                100_000_000,

            "liquidity_min_usd":
                100_000,

            "excluded_assets":
                list(EXCLUDED),

            "max_pools":
                MAX_POOLS,

            "max_pages":
                MAX_PAGES
        },

        "records":
            filtered
    }


    output_path = (
        "data/base_research.json"
    )


    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
            allow_nan=False
        )


    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print("=" * 60)
    print("RESEARCH FILTER RESULT")
    print("=" * 60)

    print(
        f"Source pools: {len(pools)}"
    )

    print(
        f"Parsed pools: {len(parsed)}"
    )

    print(
        f"Filtered pools: {len(filtered)}"
    )

    print(
        f"Pages used: {pages_used}"
    )

    print(
        "Market Cap: $1M - $100M"
    )

    print(
        "Minimum Liquidity: $100K"
    )

    print(
        "Verified Market Cap required: YES"
    )

    print("=" * 60)


    # --------------------------------------------------------
    # SHOW CANDIDATES
    # --------------------------------------------------------

    if filtered:

        print(
            "QUALIFIED POOLS"
        )

        print("-" * 60)

        for row in filtered:

            print(
                f"{row.get('name')} | "
                f"MC=${row.get('market_cap_usd')} | "
                f"Liquidity=${row.get('reserve_usd')}"
            )

    else:

        print(
            "NO POOLS PASSED THE RESEARCH FILTER"
        )


    print("=" * 60)

    print(
        f"Saved: {output_path}"
    )

    print("=" * 60)


if __name__ == "__main__":

    main()
