"""ADB 冒烟测试:确认雷电模拟器连接、分辨率、截图链路。

用法:python scripts/smoke_adb.py [serial]
若模拟器未运行/未连接,会打印清晰错误提示。
"""
import os
import sys

# Windows 控制台默认 GBK,强制以 UTF-8 输出中文提示
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kards_agent import adbc  # noqa: E402


def main() -> int:
    serial = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KARDS_SERIAL", adbc.DEFAULT_SERIAL)

    print(f"[1] adb path      : {adbc.ADB_PATH}")
    print(f"[2] 目标 serial    : {serial}")

    devs = adbc.devices()
    print(f"[3] 已连接设备     : {devs}")
    if serial not in devs:
        print()
        print("=====================================================")
        print(" 错误:未检测到雷电模拟器连接!")
        print(" 请先启动雷电模拟器(LDPlayer9),并确认其 ADB 端口已开启。")
        print(" (可用 adb connect 127.0.0.1:5555 手动连接;端口为 5555 时为默认)")
        print("=====================================================")
        return 1

    print(f"[4] 系统就绪       : {adbc.is_ready(serial)}")

    size = adbc.wm_size(serial)
    print(f"[5] 分辨率(wm size): {size}")
    if size is None:
        print(" 未能解析 wm size,截图与坐标映射可能不可用。")

    out = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "logs", "smoke.png"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ok = adbc.screenshot(serial, out)
    print(f"[6] screenshot     : {ok}")
    if ok:
        print(f"    已保存 {out} ({os.path.getsize(out)} bytes),尺寸 {size}")
        print()
        print("冒烟测试通过 ✓")
        return 0

    print()
    print("=====================================================")
    print(" 截图失败:请确认雷电模拟器已启动、KARDS 在前台,且串口连接正常。")
    print("=====================================================")
    return 1


if __name__ == "__main__":
    sys.exit(main())
