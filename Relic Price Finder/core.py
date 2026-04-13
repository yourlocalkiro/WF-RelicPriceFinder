import aiohttp
import asyncio
import requests

import time

CACHE = {
    "data": None,
    "timestamp": 0
}

CACHE_DURATION = 300  # 5 minutes

# ---------------------------
# CONFIG
# ---------------------------
DATA_URL = "https://drops.warframestat.us/data/all.json"
MARKET_BASE = "https://api.warframe.market/v1/items"


# ---------------------------
# HELPERS
# ---------------------------
def normalize(item):
    return item.lower().replace(" ", "_")


# ---------------------------
# GET DATA
# ---------------------------
def get_data():
    return requests.get(DATA_URL).json()


# ---------------------------
# GET UNVAULTED RELICS
# ---------------------------
def get_unvaulted_relics():
    return {
        # Lith
        "Lith C14", "Lith C7", "Lith E2", "Lith G14",
        "Lith K12", "Lith N18", "Lith N19", "Lith Q2",

        # Meso
        "Meso A10", "Meso A9", "Meso D8", "Meso E7",
        "Meso L4", "Meso N11", "Meso V13", "Meso V15", "Meso X1",

        # Neo
        "Neo C7", "Neo K9", "Neo N24", "Neo P10",
        "Neo S20", "Neo T10", "Neo V11", "Neo V9",

        # Axi
        "Axi C11", "Axi D6", "Axi S20", "Axi S8",
        "Axi T13", "Axi V10", "Axi V14", "Axi Y1", "Axi Y3",
    }

# ---------------------------
# BUILD RELIC → ITEMS MAP
# ---------------------------
def build_relic_map(data, active_relics):
    relic_map = {}

    relics = data["relics"]

    for relic in relics:
        # Skip anything weird
        if not isinstance(relic, dict):
            continue

        # Only intact
        if relic.get("state") != "Intact":
            continue

        # ✅ Try multiple possible key names
        tier = relic.get("tier")
        name = (
            relic.get("relicName")
            or relic.get("relic_name")
            or relic.get("name")
        )

        # Skip if missing data
        if not tier or not name:
            continue

        full_name = f"{tier} {name}"

        # Only keep active (unvaulted)
        if full_name not in active_relics:
            continue

        rewards = relic.get("rewards", [])

        items = []
        for r in rewards:
            if not isinstance(r, dict):
                continue

            item = r.get("itemName") or r.get("item") or ""

            if "Forma" in item:
                continue

            if item:
                items.append(item)

        if items:
            relic_map[full_name] = items

    print(f"Filtered relics: {len(relic_map)}")
    return relic_map


# ---------------------------
# BUILD ITEM → RELICS MAP
# ---------------------------
def build_item_map(relic_map):
    item_to_relics = {}

    for relic, items in relic_map.items():
        for item in items:
            item_to_relics.setdefault(item, []).append(relic)

    print(f"Total items: {len(item_to_relics)}")
    return item_to_relics


# ---------------------------
# ASYNC PRICE FETCHING
# ---------------------------
async def fetch_price(session, item):
    url_name = normalize(item)

    url = f"https://api.warframe.market/v1/items/{url_name}/statistics"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return item, 0

            data = await resp.json()

            stats_48 = data["payload"]["statistics_closed"]["48hours"]
            stats_90 = data["payload"]["statistics_closed"]["90days"]

            # ✅ Try 48h first
            if stats_48:
                prices = [entry["avg_price"] for entry in stats_48]
                return item, round(sum(prices) / len(prices))

            # ✅ Fallback to 90 days
            if stats_90:
                prices = [entry["avg_price"] for entry in stats_90]
                return item, round(sum(prices) / len(prices))

            # ✅ Final fallback
            return item, 0

    except:
        return item, 0
    

async def fetch_all_prices(items):
    connector = aiohttp.TCPConnector(limit=5)  # 🔥 LIMIT REQUESTS

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_price(session, item) for item in items]
        return await asyncio.gather(*tasks)
# ---------------------------
# MAIN FUNCTION
# ---------------------------

def calculate_best_relic(relic_map, item_prices):
    relic_values = {}

    for relic, items in relic_map.items():
        total = 0
        count = 0

        for item in items:
            price = item_prices.get(item, 0)
            total += price
            count += 1

        if count > 0:
            relic_values[relic] = total / count

    best = sorted(relic_values.items(), key=lambda x: x[1], reverse=True)

    return best[:5]

def get_top_items():
    now = time.time()

    # ✅ USE CACHE if still valid
    if CACHE["data"] and now - CACHE["timestamp"] < CACHE_DURATION:
        print("Using cached data")
        return CACHE["data"]

    print("Fetching fresh data...")

    # ---- YOUR EXISTING LOGIC ----
    data = get_data()

    active_relics = get_unvaulted_relics()
    relic_map = build_relic_map(data, active_relics)
    item_map = build_item_map(relic_map)

    items = list(item_map.keys())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(fetch_all_prices(items))

    item_prices = dict(results)

    sorted_items = sorted(
        item_prices.items(),
        key=lambda x: x[1],
        reverse=True
    )

    output = []
    for item, price in sorted_items:
        output.append({
            "item": item,
            "price": price,
            "relics": item_map[item]
        })

    best_relics = calculate_best_relic(relic_map, item_prices)

    result = {
        "items": output,
        "best_relics": best_relics
    }

    if len(output) < 80:
        print("Bad data, not caching")
    else:
        CACHE["data"] = result
        CACHE["timestamp"] = time.time()

    return result


# ---------------------------
# CLI MODE
# ---------------------------
if __name__ == "__main__":
    data = get_top_items()

    print("\nAll Relic Drops (Sorted by Platinum):\n")

    for i, entry in enumerate(data, 1):
        relics = ", ".join(entry["relics"])
        print(f"{i}. {entry['item']} ({entry['price']}p)")
        print(f"   Relics: {relics}\n")