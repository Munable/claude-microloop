#!/usr/bin/env python3
"""
Microloop PreToolUse Hook

在执行 Bash 命令前检查是否涉及 dev_driver，
如果是则验证环境状态（窗口焦点、分辨率等）。

输入（stdin）: JSON 格式的工具调用信息
输出（stdout）: JSON 格式的结果
退出码: 0=允许, 2=阻止
"""

import json
import sys
import subprocess
import os
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录"""
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"])
    return Path.cwd()


def get_driver_path(project_root: Path) -> Path:
    """获取 dev_driver.py 路径"""
    return project_root / ".claude" / "claude-microloop" / "driver" / "dev_driver.py"


def is_dev_driver_command(command: str) -> bool:
    """检查是否是 dev_driver 相关命令"""
    keywords = ["dev_driver", "dev_driver.py", "claude-microloop"]
    return any(kw in command.lower() for kw in keywords)


def run_preflight_check(project_root: Path) -> tuple[bool, str]:
    """运行预检"""
    driver = get_driver_path(project_root)

    if not driver.exists():
        return True, f"dev_driver not found at {driver}, skipping preflight"

    try:
        result = subprocess.run(
            ["python", str(driver), "inspect"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(project_root)
        )

        if result.returncode != 0:
            return False, f"inspect failed: {result.stderr or result.stdout}"

        try:
            info = json.loads(result.stdout)
            screen = info.get("screen", {})
            if screen.get("width") != 1920 or screen.get("height") != 1080:
                return False, f"screen size mismatch: {screen.get('width')}x{screen.get('height')}, expected 1920x1080"
        except json.JSONDecodeError:
            pass

        return True, "preflight check passed"
    except subprocess.TimeoutExpired:
        return True, "preflight timeout, allowing command"
    except Exception as e:
        return True, f"preflight error: {e}, allowing command"


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"status": "ok", "message": "no input to parse"}))
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if not is_dev_driver_command(command):
        print(json.dumps({"status": "ok", "message": "not a dev_driver command"}))
        sys.exit(0)

    project_root = get_project_root()
    passed, message = run_preflight_check(project_root)

    if passed:
        print(json.dumps({"status": "ok", "message": message}))
        sys.exit(0)
    else:
        print(json.dumps({
            "status": "error",
            "message": f"Preflight check failed: {message}",
            "action": "blocked"
        }))
        sys.exit(2)


if __name__ == "__main__":
    main()
