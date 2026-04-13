import aiohttp
import asyncio
import requests

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
def get_unvaulted_relics(data):
    active = set()

    missions = data["missionRewards"]

    for planet in missions.values():
        for mission in planet.values():
            for rotation in mission.values():
                if not isinstance(rotation, list):
                    continue

                for reward in rotation:

                    # Handle dict or string
                    if isinstance(reward, dict):
                        item = reward.get("itemName", "")
                    else:
                        item = reward

                    if "Relic" in item:
                        relic_name = item.replace(" Relic", "").strip()
                        active.add(relic_name)

    print(f"Active relics: {len(active)}")
    return active

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
def get_top_items():
    data = get_data()

    active_relics = get_unvaulted_relics(data)
    relic_map = build_relic_map(data, active_relics)
    item_map = build_item_map(relic_map)

    items = list(item_map.keys())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(fetch_all_prices(items))

    item_prices = dict(results)

    # ✅ SORT ALL ITEMS (not just top 5)
    sorted_items = sorted(
        item_prices.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # ✅ BUILD OUTPUT CLEANLY
    output = []
    for item, price in sorted_items:
        output.append({
            "item": item,
            "price": price,
            "relics": item_map[item]
        })

    return output


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