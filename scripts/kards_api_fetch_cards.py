"""Fetch ALL KARDS cards via official GraphQL API (single-stream pagination), cache to JSON."""
import json, time, sys, requests

API_URL = "https://herokuapi.kards.com/graphql"
QUERY = """query getCards($language: String, $offset: Int, $nationIds: [Int], $kredits: [Int], $q: String, $type: [String], $rarity: [String], $set: [String], $showSpawnables: Boolean, $showExiles: Boolean, $showReserved: Boolean) {
  cards(language: $language, first: 20, offset: $offset, nationIds: $nationIds, kredits: $kredits, q: $q, type: $type, set: $set, rarity: $rarity, showSpawnables: $showSpawnables, showExiles: $showExiles, showReserved: $showReserved) {
    pageInfo { count hasNextPage }
    edges { node { cardId json image(language: $language) } }
  }
}"""

HEADERS = {
    "content-type": "application/json", "origin": "https://www.kards.com",
    "referer": "https://www.kards.com/", "accept": "*/*", "cache-control": "no-cache",
    "pragma": "no-cache",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36",
}

OUT = sys.argv[1] if len(sys.argv) > 1 else "kards_api_cards.json"

seen = {}
offset = 0
while True:
    body = {"operationName": "getCards",
            "variables": {"language": "zh", "offset": offset, "nationIds": None,
                          "kredits": None, "q": None, "type": None, "rarity": None,
                          "set": None, "showSpawnables": True, "showExiles": True,
                          "showReserved": True},
            "query": QUERY}
    ok = False
    for _ in range(3):
        try:
            r = requests.post(API_URL, headers=HEADERS, json=body, timeout=30)
            if r.status_code == 200:
                ok = True
                break
        except Exception as e:
            print("req err", e, file=sys.stderr)
        time.sleep(1.0)
    if not ok:
        print("FAILED offset", offset, file=sys.stderr)
        break
    cards = (r.json().get("data") or {}).get("cards")
    if not cards:
        break
    for e in cards.get("edges", []):
        node = e.get("node", {})
        cid = node.get("cardId")
        js = node.get("json") or {}
        if cid and cid not in seen:
            seen[cid] = {
                "cardId": cid, "image": js.get("image"), "imgUrl": node.get("image"),
                "title_en": (js.get("title") or {}).get("en-EN"),
                "title_zh": (js.get("title") or {}).get("zh-Hans"),
                "faction": js.get("faction"), "kredits": js.get("kredits"),
                "type": js.get("type"), "rarity": js.get("rarity"), "set": js.get("set"),
                "text_zh": (js.get("text") or {}).get("zh-Hans"),
            }
    has_next = (cards.get("pageInfo") or {}).get("hasNextPage", False)
    print(f"offset={offset} total={len(seen)} hasNext={has_next}", file=sys.stderr)
    if not has_next:
        break
    offset += 20
    time.sleep(0.15)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(seen, f, ensure_ascii=False, indent=1)
print(f"TOTAL: {len(seen)} -> {OUT}")
