"""继续打当前这局(不重新导航),直到 game_over。用于观察整局流程与结算画面。"""
import sys, time, json
sys.path.insert(0, ".")
from kards_agent.loop import GameLoop, state_to_text
from kards_agent import brain

g = GameLoop()
g.turn = 0
for step in range(40):
    img = g.capture(f"cont{step}")
    try:
        st = g.recognize_state(img)
    except Exception as e:
        print("识别出错:", e); time.sleep(2); continue
    ph = st.get("phase")
    print(f"[步{step}] phase={ph} 费{st.get('my_kredits')}/{st.get('my_kredits_max')} HQ{st.get('my_hq')}v{st.get('enemy_hq')} 手牌{len(st.get('my_hand') or [])}")
    if ph == "game_over":
        print("对局结束! my_hq=", st.get("my_hq"), " enemy_hq=", st.get("enemy_hq"))
        g.capture("gameover")
        break
    if ph in ("my_turn", "mulligan"):
        g._last_hand_count = len(st.get("my_hand") or [])
        try:
            a = brain.decide(state_to_text(st))
        except Exception as e:
            print("决策出错:", e); a = {"action": "end"}
        print("  决策", json.dumps(a, ensure_ascii=False)[:130])
        g.execute(a)
    else:
        time.sleep(2)
    time.sleep(2)
print("循环结束")
