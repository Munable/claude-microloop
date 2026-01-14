#!/usr/bin/env python3
"""
Microloop PreToolUse Hook (Claude Code)

在执行 Bash 命令前检查是否涉及 dev_driver，
如果是则验证环境状态（窗口焦点、分辨率等）。

输入（stdin）: Claude Code hook JSON 格式
输出（stdout）: JSON 格式的决策结果
退出码: 0=成功（配合 JSON decision 字段）
"""

import json
import sys
import subprocess
import os
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录"""
    # Claude Code 通过 cwd 字段传递项目目录
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
        # 无输入时允许通过
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # 非 dev_driver 命令直接允许
    if not is_dev_driver_command(command):
        sys.exit(0)

    project_root = get_project_root()
    passed, message = run_preflight_check(project_root)

    if passed:
        # 允许执行
        print(json.dumps({
            "decision": "allow",
            "permissionDecisionReason": message
        }))
        sys.exit(0)
    else:
        # 阻止执行，返回原因给 Claude
        print(json.dumps({
            "decision": "deny",
            "permissionDecisionReason": f"Preflight check failed: {message}"
        }))
        sys.exit(0)


if __name__ == "__main__":
    main()
