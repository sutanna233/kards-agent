import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, ".")
from kards_agent import card_effects as ce

txt = open("decklists/deying_kongding.txt", encoding="utf-8").read()
cards = re.findall(r"(\d+)x\s*\((\d+)K\)\s*(.+)", txt)
print("德英控顶 卡组:", len(cards), "种卡")
ok = miss = 0
for cnt, fee, name in cards:
    name = name.strip()
    c = ce.find(name)
    if c:
        ok += 1
        eff = (c.get("text_zh") or "")
        print(f"[OK] {cnt}x {name} ({fee}费) -> {c.get('title_zh')} | {c.get('type')} | {c.get('faction')} | 效果:{eff}")
    else:
        miss += 1
        print(f"[MISS] {cnt}x {name} ({fee}费)")
print(f"\n匹配 {ok}/{len(cards)}, 未匹配 {miss}")
