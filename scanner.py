import os
import json
import time
import math
import requests
from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

API_KEY = os.environ["COINGECKO_API_KEY"]

ONCHAIN_URL = "https://api.coingecko.com/api/v3/onchain"
NETWORK = "base"

MAX_POOLS = 100
MAX_PAGES = 5
REQUEST_DELAY = 0.7

MIN_VALUATION_USD = 1_000_000
MAX_VALUATION_USD = 100_000_000
MIN_LIQUIDITY_USD = 100_000

HEADERS = {
    "x-cg-demo-api-key": API_KEY,
    "accept": "application/json",
}

# فقط برای BASE TOKEN استفاده می‌شود
EXCLUDED_BASE_TOKENS = {
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
}


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

        print("Rate limit reached. Waiting 10 seconds...")

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
# HELPERS
# ============================================================

def safe_float(value):

    try:

        if value is None:
            return None

        number = float(value)

        if math.isnan(number) or math.isinf(number):
            return None

        return number

    except (TypeError, ValueError):

        return None


def get_base_symbol(pool):

    """
    نام Pool معمولاً به شکل:
    TOKEN / USDC
    است.

    فقط TOKEN اول را بررسی می‌کنیم تا وجود USDC یا WETH
    در سمت Quote باعث حذف Pool نشود.
    """

    attrs = pool.get("attributes", {})

    name = str(
        attrs.get("name") or ""
    )

    if " / " in name:

        return (
            name.split(" / ", 1)[0]
            .strip()
            .upper()
        )

    return name.strip().upper()


# ============================================================
# GET POOLS WITH PAGINATION
# ============================================================

def get_base_pools():

    url = (
        f"{ONCHAIN_URL}/networks/"
        f"{NETWORK}/pools"
    )

    pools = []
    seen_ids = set()
    pages_used = 0

    for page in range(
        1,
        MAX_PAGES + 1
    ):

        print(
            f"Requesting page {page}..."
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

            pool_id = pool.get("id")

            if (
                pool_id
                and pool_id not in seen_ids
            ):

                seen_ids.add(pool_id)

                pools.append(pool)

                if len(pools) >= MAX_POOLS:

                    return (
                        pools,
                        pages_used
                    )

        if len(batch) < 20:
            break

        time.sleep(REQUEST_DELAY)

    return pools, pages_used


# ============================================================
# PARSE POOL
# ============================================================

def parse_pool(pool):

    attrs = pool.get(
        "attributes",
        {}
    )

    market_cap = safe_float(
        attrs.get("market_cap_usd")
    )

    fdv = safe_float(
        attrs.get("fdv_usd")
    )

    # Market Cap واقعی اولویت دارد.
    # اگر موجود نباشد، FDV به‌عنوان valuation proxy استفاده می‌شود.
    if market_cap is not None:

        valuation = market_cap
        valuation_source = "market_cap"

    elif fdv is not None:

        valuation = fdv
        valuation_source = "fdv_proxy"

    else:

        valuation = None
        valuation_source = None

    return {

        "pool_id":
            pool.get("id"),

        "name":
            attrs.get("name"),

        "base_symbol":
            get_base_symbol(pool),

        "address":
            attrs.get("address"),

        "market_cap_usd":
            market_cap,

        "fdv_usd":
            fdv,

        "valuation_usd":
            valuation,

        "valuation_source":
            valuation_source,

        "reserve_usd":
            safe_float(
                attrs.get("reserve_in_usd")
            ),

        "volume_24h":
            safe_float(
                attrs.get(
                    "volume_usd",
                    {}
                ).get("h24")
            ),

        "price_change_24h":
            safe_float(
                attrs.get(
                    "price_change_percentage",
                    {}
                ).get("h24")
            )
    }


# ============================================================
# FILTER WITH REJECTION REASON
# ============================================================

def filter_reason(row):

    base_symbol = row.get(
        "base_symbol"
    )

    valuation = row.get(
        "valuation_usd"
    )

    liquidity = row.get(
        "reserve_usd"
    )

    # فقط خود Base Token حذف می‌شود
    if base_symbol in EXCLUDED_BASE_TOKENS:

        return "excluded_base_asset"

    if valuation is None:

        return "valuation_missing"

    if valuation < MIN_VALUATION_USD:

        return "valuation_too_small"

    if valuation > MAX_VALUATION_USD:

        return "valuation_too_large"

    if liquidity is None:

        return "liquidity_missing"

    if liquidity < MIN_LIQUIDITY_USD:

        return "liquidity_too_low"

    return None


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
    # GET 100 POOLS
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
    # PARSE + FILTER
    # --------------------------------------------------------

    parsed = []
    qualified = []

    rejection_stats = {
        "excluded_base_asset": 0,
        "valuation_missing": 0,
        "valuation_too_small": 0,
        "valuation_too_large": 0,
        "liquidity_missing": 0,
        "liquidity_too_low": 0,
    }

    for pool in pools:

        try:

            row = parse_pool(pool)

            parsed.append(row)

            reason = filter_reason(row)

            if reason is None:

                qualified.append(row)

            else:

                rejection_stats[reason] += 1

        except Exception as error:

            print(
                f"Pool processing failed: {error}"
            )


    # --------------------------------------------------------
    # SAVE
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
            len(qualified),

        "rejection_stats":
            rejection_stats,

        "research_filter": {

            "valuation_min_usd":
                MIN_VALUATION_USD,

            "valuation_max_usd":
                MAX_VALUATION_USD,

            "liquidity_min_usd":
                MIN_LIQUIDITY_USD,

            "valuation_policy":
                "market_cap_first_fdv_proxy_when_market_cap_missing",

            "excluded_base_tokens":
                sorted(
                    EXCLUDED_BASE_TOKENS
                ),

            "max_pools":
                MAX_POOLS
        },

        "records":
            qualified
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
    print("SCAN RESULT")
    print("=" * 60)

    print(
        f"Source pools: {len(pools)}"
    )

    print(
        f"Parsed pools: {len(parsed)}"
    )

    print(
        f"Qualified pools: {len(qualified)}"
    )

    print("-" * 60)

    print("REJECTION STATS")

    for reason, count in rejection_stats.items():

        print(
            f"{reason}: {count}"
        )

    print("=" * 60)

    if qualified:

        print("QUALIFIED POOLS")

        for row in qualified:

            print(
                f"{row.get('name')} | "
                f"Base={row.get('base_symbol')} | "
                f"Valuation=${row.get('valuation_usd')} "
                f"({row.get('valuation_source')}) | "
                f"Liquidity=${row.get('reserve_usd')}"
            )

    else:

        print(
            "No pools passed all filters."
        )

    print("=" * 60)

    print(
        f"Saved: {output_path}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()
