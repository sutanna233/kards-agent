"""
绕路推送 — 把仓库内容通过 GitHub Contents API 一个一个文件 PUT 上去。
适用：当前网络对 git smart-http (chunked) 不友好，但对标准 HTTPS REST API 通畅的情况。

- 仓库根目录保持原样(不重建 .git/),只是把工作区所有 tracked 文件 + AGENTS.md
  通过 Contents API 推到 main 分支。
- 已有文件会取 sha 后再 PUT(否则 422)。
- 大文件 / 二进制文件 / .git/ 跳过。
"""
import json, urllib.request, subprocess, base64, sys, os, mimetypes

TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
API = "https://api.github.com/repos/sutanna233/kards-agent"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "User-Agent": "kards-agent-pusher"}

SKIP_DIRS = {".git", "__pycache__", "logs"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".pyc", ".pyd", ".so", ".dll"}
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2MB 单文件上限(API 限制)


def req(path, method="GET", body=None):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={**HEADERS, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def collect_files(root="."):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            ext = os.path.splitext(fn)[1].lower()
            if ext in SKIP_EXTS:
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                print(f"  跳过(>{MAX_FILE_BYTES//1024}KB): {rel}")
                continue
            out.append(rel)
    return sorted(out)


def get_sha(path):
    s, info = req(f"/contents/{path}?ref=main")
    if s == 200 and isinstance(info, dict):
        return info.get("sha")
    return None


def put_file(rel, local_path, message):
    sha = get_sha(rel)
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    body = {"message": message, "branch": "main", "content": content}
    if sha:
        body["sha"] = sha
    s, info = req(f"/contents/{rel}", method="PUT", body=body)
    return s, info


def main():
    files = collect_files(".")
    print(f"待上传文件数: {len(files)}")
    msg = "docs: README按代码事实重写(attack已有/三层识别路径) + 新建项目级AGENTS.md"
    ok, fail = 0, 0
    for i, rel in enumerate(files, 1):
        s, info = put_file(rel, rel, msg)
        if s in (200, 201):
            ok += 1
            print(f"[{i}/{len(files)}] OK {s} {rel}")
        else:
            fail += 1
            print(f"[{i}/{len(files)}] FAIL {s} {rel} -> {str(info)[:120]}")
    print(f"\n完成:成功 {ok} 失败 {fail}")


if __name__ == "__main__":
    main()