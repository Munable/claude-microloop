#!/usr/bin/env python3
"""
Microloop PostToolUse Hook (Claude Code)

在执行 Bash 命令后记录 trace 信息。

输入（stdin）: Claude Code hook JSON 格式（包含 tool_input 和 tool_result）
输出（stdout）: JSON 格式的结果（可包含 additionalContext 反馈给 Claude）
退出码: 0=成功
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime


def get_project_root() -> Path:
    """获取项目根目录"""
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


def extract_trace_path(command: str) -> str:
    """从命令中提取截图路径"""
    # 查找 --out 参数后的路径
    parts = command.split()
    for i, part in enumerate(parts):
        if part == "--out" and i + 1 < len(parts):
            return parts[i + 1].strip('"\'')
    return ""


def log_trace(project_root: Path, command: str, output: str, action_type: str) -> str:
    """记录 trace 到日志文件，返回日志路径"""
    log_dir = project_root / ".claude" / "claude-microloop" / "traces"
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"trace-{date_str}.jsonl"

    # 解析 dev_driver 输出
    success = True
    trace_path = ""
    try:
        result = json.loads(output)
        success = result.get("status") == "ok"
        trace_path = result.get("file", "")
    except (json.JSONDecodeError, TypeError):
        success = "error" not in output.lower() if output else True
        trace_path = extract_trace_path(command)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action_type,
        "command": command[:500],
        "trace_path": trace_path,
        "success": success
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return str(log_file)


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    # PostToolUse 的输出在 tool_result 字段
    tool_result = input_data.get("tool_result", {})
    command = tool_input.get("command", "")

    # tool_result 可能是字符串或对象
    if isinstance(tool_result, str):
        output = tool_result
    else:
        output = tool_result.get("stdout", "") or tool_result.get("content", "") or str(tool_result)

    # 非 dev_driver 命令直接跳过
    if not is_dev_driver_command(command):
        sys.exit(0)

    project_root = get_project_root()
    action_type = extract_action_type(command)

    try:
        log_file = log_trace(project_root, command, output, action_type)
        # 返回额外上下文信息给 Claude
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[microloop] {action_type} traced to {log_file}"
            }
        }))
    except Exception as e:
        # 记录失败不阻止流程
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"[microloop] trace logging failed: {e}"
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
