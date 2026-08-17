"""批量下载全部 KARDS 简体中文卡图(并发,带重试)。"""
import sys, os, json, urllib.request, concurrent.futures
sys.path.insert(0, ".")

DB = "cards/kards_api_cards.json"
OUT = "templates/cards_full"
os.makedirs(OUT, exist_ok=True)

cards = json.load(open(DB, encoding="utf-8-sig"))
print("总卡数:", len(cards))


def fetch(item):
    cid, c = item
    img = c.get("image")
    if not img:
        return cid, False, "no image"
    url = "https://www.kards.com/images/card/v52/zh-Hans/" + img
    fn = os.path.join(OUT, cid + ".avif")
    if os.path.exists(fn) and os.path.getsize(fn) > 1000:
        return cid, True, "exists"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if len(data) > 1000:
                with open(fn, "wb") as f:
                    f.write(data)
                return cid, True, "ok"
        except Exception as e:
            err = str(e)
    return cid, False, err


ok = fail = 0
items = list(cards.items())
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    for i, (cid, success, msg) in enumerate(ex.map(fetch, items)):
        if success:
            ok += 1
        else:
            fail += 1
        if (i + 1) % 100 == 0:
            print(f"  进度 {i+1}/{len(items)}  ok={ok} fail={fail}", flush=True)
print(f"完成: 成功 {ok}, 失败 {fail}")

# 生成 index.json
idx = [{"cardId": c["cardId"], "title_zh": c.get("title_zh"), "title_en": c.get("title_en"),
        "kredits": c.get("kredits"), "type": c.get("type"), "faction": c.get("faction"),
        "text_zh": c.get("text_zh"), "file": cid + ".avif",
        "downloaded": os.path.exists(os.path.join(OUT, cid + ".avif"))}
       for cid, c in cards.items()]
json.dump({"total": len(idx), "cards": idx}, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("index.json 已生成")
