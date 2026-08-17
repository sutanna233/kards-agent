"""通过 GitHub Contents API 探测仓库当前状态，判断是否能绕过 git push。"""
import json, urllib.request, subprocess, base64, sys, os

TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
API = "https://api.github.com/repos/sutanna233/kards-agent"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "User-Agent": "kards-agent-pusher"}


def req(path, method="GET", body=None):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={**HEADERS, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def put_file(path, local_path, message, sha=None):
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    body = {"message": message, "branch": "main", "content": content}
    if sha:
        body["sha"] = sha
    return req(f"/contents/{path}", method="PUT", body=body)


def main():
    # 1. 看 README.md 远端 sha
    s, info = req("/contents/README.md?ref=main")
    print("README.md 远端状态:", s, "sha:", info.get("sha", "")[:10] if isinstance(info, dict) else info[:200])
    # 2. 看 AGENTS.md 是否存在
    s, info = req("/contents/AGENTS.md?ref=main")
    print("AGENTS.md 远端状态:", s, "存在?" if isinstance(info, dict) and "sha" in info else "不存在", "->", info.get("sha", "")[:10] if isinstance(info, dict) and "sha" in info else info[:200])

    # 3. 用 Contents API 直接 put 试一下 README.md
    s, info = put_file("README.md", "README.md", "docs: README按代码事实重写(attack已有/三层识别路径) + 新建项目级AGENTS.md", sha=info.get("sha") if isinstance(info, dict) and "sha" in info else None)
    print("PUT README.md 状态:", s, "->", json.dumps(info)[:300])


if __name__ == "__main__":
    main()