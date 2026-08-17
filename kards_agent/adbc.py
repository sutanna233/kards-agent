"""
ADB 封装:雷电模拟器(LDPlayer9)读屏与注入触摸。

接口由 MASTER 定义,不要改动函数签名。关键点:
  - Windows 下不能用文本重定向('<')收二进制,必须用 subprocess 直接捕获原始字节写盘,
    否则 screencap 的 PNG 会被破坏(0x00 转成换行、行尾回车等)。
  - 默认序列 127.0.0.1:5555(雷电),可用 KARDS_ADB 环境变量覆盖 adb 路径。
"""
from __future__ import annotations
import os
import subprocess
from typing import List, Optional, Tuple

ADB_PATH = os.environ.get("KARDS_ADB", r"D:\leidian\LDPlayer9\adb.exe")
DEFAULT_SERIAL = os.environ.get("KARDS_SERIAL", "127.0.0.1:5555")


def _run(args: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run([ADB_PATH] + args, capture_output=True, timeout=timeout)


def _opts(serial: str) -> List[str]:
    return ["-s", serial] if serial else []


def devices() -> List[str]:
    """运行 `adb devices`,解析出状态为 device 的 serial 列表。"""
    try:
        out = _run(["devices"]).stdout.decode(errors="ignore")
    except Exception:
        return []
    res = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2 and parts[1] == "device":
            res.append(parts[0])
    return res


def connect(serial: str = DEFAULT_SERIAL) -> bool:
    """运行 `adb connect <serial>`,返回是否真正可用(出现在 devices 且在线)。"""
    try:
        _run(["connect", serial])
    except Exception:
        return False
    return serial in devices()


def screenshot(serial: str = DEFAULT_SERIAL, out_path: str = "logs/cap.png") -> bool:
    """
    运行 `adb -s <serial> exec-out screencap -p` 并把原始 PNG 字节写入 <out_path>。
    用 subprocess 捕获字节直接写盘,不用 > 文本重定向。
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    try:
        raw = _run(_opts(serial) + ["exec-out", "screencap", "-p"], timeout=30).stdout
    except Exception:
        return False
    if not raw.startswith(b"\x89PNG"):
        return False
    try:
        with open(out_path, "wb") as f:
            f.write(raw)
    except OSError:
        return False
    return True


def screenshot_bytes(serial: str = DEFAULT_SERIAL) -> Optional[bytes]:
    """返回原始 PNG 字节(读屏用),非 PNG 返回 None。"""
    try:
        raw = _run(_opts(serial) + ["exec-out", "screencap", "-p"], timeout=30).stdout
    except Exception:
        return None
    return raw if raw.startswith(b"\x89PNG") else None


def screenshot_cv(serial: str = DEFAULT_SERIAL):
    """raw screencap(不编码 PNG,比 -p 快约2倍)直接返回 cv2 BGR 图像。
    设备返回 RGBA 原始字节+小头(12或16字节),自动探测头长。"""
    try:
        import numpy as np, cv2
        raw = _run(_opts(serial) + ["exec-out", "screencap"], timeout=30).stdout
    except Exception:
        return None
    if len(raw) < 32:
        return None
    import struct
    w, h = struct.unpack("<II", raw[:8])
    if w <= 0 or h <= 0 or w > 4096 or h > 4096:
        return None
    px = w * h * 4
    hdr = len(raw) - px
    if hdr not in (0, 12, 16):
        return None
    arr = np.frombuffer(raw[hdr:hdr + px], dtype=np.uint8).reshape(h, w, 4)
    return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)


def wm_size(serial: str = DEFAULT_SERIAL) -> Optional[Tuple[int, int]]:
    """解析 `adb -s <serial> shell wm size` 的 "Physical size: WxH"。"""
    try:
        out = _run(_opts(serial) + ["shell", "wm", "size"]).stdout.decode(errors="ignore")
    except Exception:
        return None
    try:
        part = out.split("Physical size:")[-1].strip()     # "1280x720"
        w, h = part.lower().split("x")
        return int(w), int(h)
    except (ValueError, IndexError):
        return None


def tap(serial: str, x: int, y: int) -> bool:
    """`adb -s <serial> shell input tap x y`。"""
    try:
        return _run(_opts(serial) + ["shell", "input", "tap",
                                     str(int(x)), str(int(y))]).returncode == 0
    except Exception:
        return False


def swipe(serial: str, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> bool:
    """`adb -s <serial> shell input swipe x1 y1 x2 y2 <ms>`。"""
    try:
        return _run(_opts(serial) + ["shell", "input", "swipe",
                                     str(int(x1)), str(int(y1)),
                                     str(int(x2)), str(int(y2)),
                                     str(int(ms))]).returncode == 0
    except Exception:
        return False


def key(serial: str, keycode: str) -> bool:
    """`adb -s <serial> shell input keyevent <keycode>`。"""
    try:
        return _run(_opts(serial) + ["shell", "input", "keyevent",
                                     keycode]).returncode == 0
    except Exception:
        return False


def uiautomator_dump(serial: str = DEFAULT_SERIAL, out_path: str = "logs/ui.xml") -> bool:
    """
    `adb -s <serial> shell uiautomator dump` 得到 UI 层级 XML,拉到 <out_path>。
    返回是否成功(有些设备 XML 输出到 /sdcard/window_dump.xml)。
    """
    try:
        out = _run(_opts(serial) + ["shell", "uiautomator", "dump"]).stdout.decode(errors="ignore")
    except Exception:
        return False
    # 设备端回显 dump 结果路径,如 "UI hierchary dumped to: /sdcard/window_dump.xml"
    path = "/sdcard/window_dump.xml"
    for token in out.strip().split():
        if token.endswith(".xml"):
            path = token
            break
    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        if path.startswith("/sdcard"):
            data = _run(_opts(serial) + ["exec-out", "cat", path]).stdout
        else:  # 某些版本输出到 /data/local/tmp
            data = _run(_opts(serial) + ["shell", "cat", path]).stdout
        with open(out_path, "wb") as f:
            f.write(data)
        return data.strip().startswith(b"<?xml") or b"<hierarchy" in data[:200]
    except Exception:
        return False


def is_ready(serial: str = DEFAULT_SERIAL) -> bool:
    """系统是否启动完成(sys.boot_completed == 1)。"""
    try:
        out = _run(_opts(serial) + ["shell", "getprop", "sys.boot_completed"], timeout=10)
        return out.stdout.decode(errors="ignore").strip() == "1"
    except Exception:
        return False
