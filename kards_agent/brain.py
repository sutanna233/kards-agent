"""
LLM 决策大脑:把紧凑的对局文本状态喂给 Qwen3.6-35B,让它输出本回合打法。
关键设计(控制上下文):
  - 输入是 CV 压缩出的短文本(几十~两百 token),不喂大图;
  - 无状态调用:每次独立,不带历史对话;
  - 输出结构化 JSON,agent 解析后执行。
系统提示里注入 KARDS 打法知识 = "教它打"的主要载体。
"""
from __future__ import annotations
import re, json, urllib.request, urllib.error, os

CRED = os.environ.get("DSH_CRED", r"C:\Users\User\.dsh\.credentials.yaml")
BASE = os.environ.get("KARDS_LLM_BASE", "http://ai.sunjun3773.top:62222/v1")
MODEL = os.environ.get("KARDS_LLM_MODEL", "Qwen3.6-35B-A3B.gguf")
_key_cache = None


def _key() -> str:
    global _key_cache
    if _key_cache:
        return _key_cache
    txt = open(CRED, encoding="utf-8", errors="ignore").read()
    m = re.search(r"SUNJUN3773_API_KEY['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]+)", txt)
    if not m:
        raise RuntimeError("未找到 SUNJUN3773_API_KEY")
    _key_cache = m.group(1)
    return _key_cache


# KARDS 打法知识(基础规则,卡组特化打法通过 skill 注入)
BASE_SYSTEM = """你是 KARDS(二战卡牌)顶级玩家,替我方(LK021)做每回合决策。

【核心规则】
- 目标:摧毁敌方总部(HQ)。双方初始 HQ 20 血。
- 指挥点(Kredits)每回合+1,出牌/行动都耗费。
- 手牌上限 9 张:手牌 ≥8 张时严禁过牌/抽牌(如 HX 175 护航队),抽了也爆掉纯浪费。
- 三条战线:防御线(单位部署点)→前线(地面单位推进到这才能攻击)→敌方。
- 步兵/坦克:需推进到前线才能攻击;炮兵/轰炸机/战斗机:远程,可在防御线直接攻击。
- 单位被攻击只减防御不减攻击;攻击敌方单位会被反击。
- 关键词:闪袭(部署当回合即可行动)/奋战(一回合行动两次)/守护/烟幕。
- 指令卡:一次性效果;反制措施:隐藏,敌方回合触发。

【通用决策优先级】
1. 能斩杀敌方HQ就斩杀。
2. 【铁律】只能出"费用 <= 我方当前费用"的卡!
3. 地面单位需推进到前线才能攻击;炮兵/战斗机/轰炸机可在防御线远程攻击。
4. 用我方单位换掉敌方高威胁单位。
5. 有费就出单位站场,保持场面压力。
6. 费用不够出任何卡、或没有能攻击的单位,果断结束回合。
"""


def _system_with_skill(skill: str) -> str:
    if skill:
        return BASE_SYSTEM + "\n\n【我方卡组的专属打法(务必遵循)】\n" + skill
    return BASE_SYSTEM


def _decide_prompt():
    return """\n\n【输出格式】严格只输出一个 JSON,不要任何多余文字:
{"action":"play|attack|move|end","hand_index":第几张手牌(0起),"attacker":"场上单位描述","target":"敌方单位描述或hq","line":"defense|front","reason":"一句话理由","say":"一句对战解说(中文,简短)"}
换牌阶段输出:{"action":"mulligan","replace":[要换的手牌index],"reason":"...","say":"..."}"""


def chat(user_text: str, max_tokens: int = 400, temperature: float = 0.0, skill: str = "") -> str:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": _system_with_skill(skill)},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": max_tokens, "temperature": temperature,
    }
    req = urllib.request.Request(BASE + "/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + _key()})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    return resp["choices"][0]["message"]["content"]


def decide_with_skill(state_json: str, skill: str = "") -> dict:
    """带卡组 skill 的决策。输入局面 JSON,输出决策 dict(含 say 解说)。"""
    out = chat(state_json + _decide_prompt(), max_tokens=600, skill=skill)
    return _parse_json_action(out)


def chat_free(question: str, state_json: str, skill: str = "") -> str:
    """自由对话:基于当前局面回答用户问题,或接受用户指挥。"""
    prompt = (f"当前对局局面(JSON):\n{state_json}\n\n"
              f"玩家对你说:{question}\n"
              f"请用中文简洁回答(如果你是决策请求,给出建议动作;如果是询问,解释局势或你的理由)。")
    return chat(prompt, max_tokens=400, skill=skill)


def _parse_json_action(out: str) -> dict:
    """从 LLM 输出解析决策 JSON(容忍截断/噪声)。"""
    m = re.search(r"\{.*", out, re.S)  # 从第一个 { 起到结尾
    if not m:
        return {"action": "end", "reason": "LLM输出无法解析", "raw": out[:200]}
    js = m.group(0)
    # 截断修复:若 JSON 不完整,尝试补齐
    if js.count("{") > js.count("}"):
        js += "}" * (js.count("{") - js.count("}"))
    try:
        return json.loads(js)
    except Exception:
        last = js.rfind("}")
        if last > 0:
            try:
                return json.loads(js[:last + 1])
            except Exception:
                pass
    # 兜底:从文本里抽 action 关键词
    for act in ("play", "attack", "move", "mulligan", "end"):
        if f'"{act}"' in out or f'action": "{act}"' in out or f'"action":"{act}"' in out:
            hi = re.search(r"hand_index\"?\s*[:=]\s*(\d+)", out)
            return {"action": act, "hand_index": int(hi.group(1)) if hi else 0,
                    "line": "defense", "reason": "容错解析"}
    return {"action": "end", "reason": "JSON解析失败", "raw": out[:200]}


def decide(state_text: str) -> dict:
    """向后兼容:不带 skill 的决策。"""
    out = chat(state_text, max_tokens=600)
    return _parse_json_action(out)
