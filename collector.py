import os
import requests
import json
from datetime import datetime, timezone

API_KEY = os.environ["COINGECKO_API_KEY"]

BASE_URL = "https://api.coingecko.com/api/v3"

headers = {
    "x-cg-demo-api-key": API_KEY,
    "accept": "application/json"
}

def get_markets():
    url = f"{BASE_URL}/coins/markets"

    params = {
        "vs_currency": "usd",
        "category": "base-ecosystem",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": "false"
    }

    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()

    return r.json()


def main():

    print("Scanning Base tokens...")

    data = get_markets()

    timestamp = datetime.now(timezone.utc).isoformat()

    result = {
        "timestamp": timestamp,
        "network": "base",
        "count": len(data),
        "tokens": data
    }

    os.makedirs("data", exist_ok=True)

    filename = "data/base_snapshot.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(data)} tokens.")
    print(filename)


if __name__ == "__main__":
    main()
