"""用 adb 截屏,原始字节写盘,绕过 PowerShell 文本重定向对二进制的破坏。"""
import subprocess
import sys
import os

ADB = r"D:\leidian\LDPlayer9\adb.exe"
SERIAL = "emulator-5554"
OUT = sys.argv[1] if len(sys.argv) > 1 else r"J:\dev\测试\233\kards-agent\logs\cap.png"

os.makedirs(os.path.dirname(OUT), exist_ok=True)
cmd = [ADB, "-s", SERIAL, "exec-out", "screencap", "-p"]
raw = subprocess.run(cmd, capture_output=True).stdout
# exec-out 直通二进制流,不做任何字节转换
with open(OUT, "wb") as f:
    f.write(raw)
print(f"saved {len(raw)} bytes -> {OUT}")
