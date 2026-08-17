"""Download zh-Hans card faces for cards.json ids from the official KARDS CDN.

Matches cards.json (English name) to the official API card index (kards_api_cards.json),
downloads the Simplified-Chinese (zh-Hans) card face AVIF, converts to PNG, and writes
templates/cards/<id>.png plus templates/cards/index.json.
"""
import json, os, re, sys, time
from urllib.request import Request, urlopen
from PIL import Image
from io import BytesIO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # kards-agent/
CARDS = os.path.join(ROOT, "cards", "cards.json")
API_INDEX = os.path.join(ROOT, "cards", "kards_api_cards.json")
OUT_DIR = os.path.join(ROOT, "templates", "cards")

CDN = "https://www.kards.com/images/card/v52/zh-Hans/"

def norm(s):
    if not s:
        return ""
    s = s.upper()
    s = re.sub(r"[\u00b7\u2019'\".,\-/()\u0301\u0308\u00b4`]", "", s)
    s = re.sub(r"\s+", "", s)
    return s

def fetch_bytes(url, retries=3):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/144.0.0.0",
        "Referer": "https://www.kards.com/",
    })
    last = None
    for _ in range(retries):
        try:
            with urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.0)
    raise last

def main():
    with open(CARDS, encoding="utf-8-sig") as f:
        cards = json.load(f)
    with open(API_INDEX, encoding="utf-8") as f:
        index = json.load(f)

    # Manual cardId overrides for wiki names that don't exactly match API title_en
    OVERRIDES = {
        "Light Infantry (Old)": "light_infantry",
        'BL 4.5" Medium Gun': "bl_4_5_medium_gun",
    }

    # Build lookup: normalized name -> list of api records (prefer sorted by title len)
    by_name = {}
    for rec in index.values():
        k = norm(rec.get("title_en"))
        if k:
            by_name.setdefault(k, []).append(rec)
    by_id = {rec["cardId"]: rec for rec in index.values()}

    os.makedirs(OUT_DIR, exist_ok=True)
    entries = []
    matched = miss = downloaded = 0
    for card in cards:
        cid = card["id"]
        want_en = norm(card.get("name"))
        match = None
        override_cid = OVERRIDES.get(card.get("name"))
        if override_cid and override_cid in by_id:
            match = by_id[override_cid]
        elif want_en in by_name:
            cands = by_name[want_en]
            for cand in cands:
                if norm(cand.get("faction")) == norm(card.get("nation")):
                    match = cand
                    break
            if match is None:
                match = cands[0]
        if match is None:
            print(f"MISS  {cid}  {card.get('name')!r}")
            miss += 1
            entries.append({
                "id": cid, "name": card.get("name"), "cardId": None,
                "image": None, "zhTitle": None, "downloaded": False,
            })
            continue
        matched += 1
        cardid = match["cardId"]
        imgname = match.get("image") or (cardid + ".avif")
        url = CDN + imgname
        dst = os.path.join(OUT_DIR, cid + ".png")
        success = False
        try:
            data = fetch_bytes(url)
            im = Image.open(BytesIO(data)).convert("RGB")
            im.save(dst, "PNG")
            success = True
            downloaded += 1
            print(f"OK    {cid} <- {cardid} {match.get('title_zh')}")
        except Exception as e:
            print(f"DLERR {cid} {cardid}: {e}")
        entries.append({
            "id": cid, "name": card.get("name"), "cardId": cardid,
            "image": imgname, "zhTitle": match.get("title_zh"),
            "unitType": card.get("unitType"), "type": card.get("type"),
            "nation": card.get("nation"), "cost": card.get("cost"),
            "downloaded": success,
        })

    idx = {"total": len(entries), "downloaded": downloaded,
           "source": CDN, "cards": entries}
    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"DONE: total={len(cards)} matched={matched} miss={miss} downloaded={downloaded}")

if __name__ == "__main__":
    main()
