# XPS_UPS.py (启动入口)
# ============================================================
# UPS IBW Processor v3.1 - 启动 GUI
# 功能已拆分到：reader.py, plots.py, export_csv.py, app.py
# 首次运行若缺库会自动用 pip 安装
# ============================================================

import sys
import subprocess
import traceback

# 本程序必须的库（包名与 pip 名一致）
_REQUIRED = ["numpy", "matplotlib", "igor2", "pandas"]


def _ensure_deps():
    """若缺少依赖则自动 pip 安装，然后返回是否就绪。"""
    missing = []
    for pkg in _REQUIRED:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return True
    print("正在自动安装缺少的库:", ", ".join(missing))
    print("请稍候…")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            check=True,
        )
        print("安装完成，正在启动程序…")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("自动安装失败，请手动在命令行执行：")
        print("  pip install numpy matplotlib igor2 pandas")
        print("然后重新运行本程序。")
        if getattr(e, "returncode", None) is not None:
            input("按回车键退出…")
        return False


if __name__ == "__main__":
    if not _ensure_deps():
        sys.exit(1)
    try:
        from app import UPSApp
        UPSApp().mainloop()
    except Exception:
        print(traceback.format_exc())
        sys.exit(1)
