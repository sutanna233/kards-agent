#!/usr/bin/env python3
"""
KARDS 简体中文卡图批量下载脚本
下载全部卡牌图片到当前目录，生成 index.json
"""

import json
import os
import sys
import time
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------- 配置 ----------
METADATA_PATH = Path(r"J:\dev\测试\233\kards-agent\cards\kards_api_cards.json")
OUTPUT_DIR = Path(r"J:\dev\测试\233\kards-agent\templates\cards_full")
BASE_URL = "https://www.kards.com"
CONCURRENCY = 10          # 并发数
MAX_RETRIES = 3           # 单张卡最大重试次数
RETRY_DELAY = 2           # 重试间隔(秒)
REQUEST_TIMEOUT = 30      # 请求超时(秒)
SEMAPHORE_SIZE = CONCURRENCY

# ---------- 建立 Session ----------
def make_session():
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_DELAY,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=CONCURRENCY, pool_maxsize=CONCURRENCY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://www.kards.com/",
    })
    return session

# ---------- 并发下载 ----------
import threading
import queue

def download_card(session, card_id, img_url, output_dir, results):
    """下载单张卡图"""
    full_url = BASE_URL + img_url
    out_path = output_dir / card_id

    # 保持原始扩展名
    if not out_path.suffix:
        out_path = out_path.with_suffix(".avif")

    if out_path.exists() and out_path.stat().st_size > 0:
        results["skip"].append(card_id)
        return

    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(full_url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                out_path.write_bytes(resp.content)
                results["success"].append((card_id, out_path.name, resp.headers.get("content-type", "")))
                return
            elif resp.status_code == 404:
                results["not_found"].append((card_id, f"HTTP {resp.status_code}"))
                return  # 404 不再重试
            else:
                results["pending"].append((card_id, full_url, resp.status_code, attempt + 1))
        except Exception as e:
            results["pending"].append((card_id, full_url, str(e), attempt + 1))

        time.sleep(RETRY_DELAY * (attempt + 1))

    results["failed"].append((card_id, full_url, f"重试 {MAX_RETRIES} 次失败"))

def worker(session, q, output_dir, results):
    while True:
        try:
            card_id, img_url = q.get_nowait()
        except:
            return
        download_card(session, card_id, img_url, output_dir, results)
        q.task_done()

def main():
    # 加载元数据
    print(f"[*] 加载元数据: {METADATA_PATH}")
    with open(METADATA_PATH, encoding="utf-8") as f:
        cards = json.load(f)
    total = len(cards)
    print(f"[*] 共 {total} 张卡")

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 准备任务队列
    task_queue = queue.Queue()
    for card_id, card_info in cards.items():
        img_url = card_info.get("imgUrl", "")
        if img_url:
            task_queue.put((card_id, img_url))

    print(f"[*] 任务队列: {task_queue.qsize()} 个任务")

    # 初始化结果容器
    results = {
        "success": [],
        "failed": [],
        "not_found": [],
        "skip": [],
        "pending": [],
    }

    # 创建 Session
    session = make_session()

    # 启动线程池
    print(f"[*] 启动 {CONCURRENCY} 个并发线程...")
    threads = []
    for _ in range(CONCURRENCY):
        t = threading.Thread(target=worker, args=(session, task_queue, OUTPUT_DIR, results), daemon=True)
        t.start()
        threads.append(t)

    # 等待所有任务完成
    task_queue.join()
    print("[*] 所有任务完成，等待线程退出...")
    for t in threads:
        t.join(timeout=10)

    # 处理剩余 pending
    for card_id, url, code, attempt in results.pop("pending", []):
        results["failed"].append((card_id, url, f"剩余 pending (code={code})"))

    # 统计
    n_success = len(results["success"])
    n_failed = len(results["failed"])
    n_not_found = len(results["not_found"])
    n_skip = len(results["skip"])

    print(f"\n{'='*60}")
    print(f"下载完成!")
    print(f"  成功: {n_success}")
    print(f"  跳过(已存在): {n_skip}")
    print(f"  失败: {n_failed}")
    print(f"  未找到(404): {n_not_found}")
    print(f"{'='*60}")

    # 打印失败详情
    if results["failed"]:
        print("\n[!] 失败详情:")
        for card_id, url, reason in results["failed"][:20]:
            print(f"  {card_id}: {reason}")
        if len(results["failed"]) > 20:
            print(f"  ... 共 {len(results['failed'])} 个失败")

    if results["not_found"]:
        print(f"\n[!] 404 未找到: {len(results['not_found'])} 张")
        for card_id, reason in results["not_found"][:10]:
            print(f"  {card_id}")

    # 生成 index.json
    index = []
    for card_id, filename, _ in results["success"]:
        card_info = cards.get(card_id, {})
        index.append({
            "cardId": card_id,
            "title_zh": card_info.get("title_zh", ""),
            "kredits": card_info.get("kredits", 0),
            "type": card_info.get("type", ""),
            "faction": card_info.get("faction", ""),
            "filename": filename,
        })

    index_path = OUTPUT_DIR / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"\n[*] index.json 已生成: {index_path} ({len(index)} 条)")

    # 保存失败列表以便后续重试
    if results["failed"] or results["not_found"]:
        fail_list = []
        for card_id, url, reason in results["failed"]:
            fail_list.append({"cardId": card_id, "url": url, "reason": reason})
        for card_id, reason in results["not_found"]:
            fail_list.append({"cardId": card_id, "reason": reason})
        fail_path = OUTPUT_DIR / "failed_list.json"
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(fail_list, f, ensure_ascii=False, indent=2)
        print(f"[*] 失败列表已保存: {fail_path}")

if __name__ == "__main__":
    main()
