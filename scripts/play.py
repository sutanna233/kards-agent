"""启动:导航进训练模式对局,用指定卡组skill+卡组约束的Agent打。
自带 WebUI:http://127.0.0.1:8399 实时看画面+思维链。"""
import sys
sys.path.insert(0, ".")
from kards_agent import nav, webview
from kards_agent.agent_full import Agent

SKILL = "skills/deying_kongding.md"
DECK = "decklists/deying_kongding.txt"

port = webview.start_server(8399)
print(f"WebUI 已启动: http://127.0.0.1:{port}")

print("导航进对局...")
ok = nav.navigate_to_battle()
print("导航结果:", ok)
if ok:
    agent = Agent(SKILL, DECK)
    result = agent.play_match(max_steps=50)
    print("本局结果:", result)
