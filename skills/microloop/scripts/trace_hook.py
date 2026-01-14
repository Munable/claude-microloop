#!/usr/bin/env python3
"""
Microloop PostToolUse Hook

在执行 Bash 命令后记录 trace 信息。

输入（stdin）: JSON 格式的工具调用结果
输出（stdout）: JSON 格式的结果
退出码: 0=成功
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime


def get_project_root() -> Path:
    """获取项目根目录"""
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"])
    return Path.cwd()


def is_dev_driver_command(command: str) -> bool:
    """检查是否是 dev_driver 相关命令"""
    keywords = ["dev_driver", "dev_driver.py", "claude-microloop"]
    return any(kw in command.lower() for kw in keywords)


def extract_action_type(command: str) -> str:
    """从命令中提取动作类型"""
    actions = ["observe", "click", "type", "inspect", "focus", "diff"]
    for action in actions:
        if action in command.lower():
            return action
    return "unknown"


def log_trace(project_root: Path, command: str, output: str, action_type: str):
    """记录 trace 到日志文件"""
    log_dir = project_root / ".claude" / "claude-microloop" / "traces"
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"trace-{date_str}.jsonl"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action_type,
        "command": command[:500],
        "output_preview": output[:200] if output else "",
        "success": "error" not in output.lower() if output else True
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"status": "ok", "message": "no input to parse"}))
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    tool_output = input_data.get("tool_output", {})
    command = tool_input.get("command", "")
    output = tool_output.get("stdout", "") or tool_output.get("content", "")

    if not is_dev_driver_command(command):
        print(json.dumps({"status": "ok", "message": "not a dev_driver command"}))
        sys.exit(0)

    project_root = get_project_root()
    action_type = extract_action_type(command)

    try:
        log_trace(project_root, command, output, action_type)
        print(json.dumps({
            "status": "ok",
            "message": f"trace logged for {action_type}",
            "action": action_type
        }))
    except Exception as e:
        print(json.dumps({
            "status": "ok",
            "message": f"trace logging failed: {e}",
            "warning": True
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
