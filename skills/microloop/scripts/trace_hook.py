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
    """检查是否是 dev_driver.py 命令（不匹配其他 microloop 脚本）"""
    # 只匹配 dev_driver.py，不匹配 microloop_loop_*.ps1 等脚本
    return "dev_driver.py" in command or "dev_driver " in command


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
    log_dir = project_root / ".claude" / "microloop" / "traces"
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"trace-{date_str}.jsonl"

    # 解析 dev_driver 输出
    success = False
    trace_path = ""

    # 尝试从输出中找到 JSON 部分（dev_driver 输出是 JSON 格式）
    json_output = output.strip()

    # 如果输出包含多行，尝试找到 JSON 行
    if json_output:
        for line in json_output.split('\n'):
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                json_output = line
                break

    try:
        result = json.loads(json_output)
        success = result.get("status") == "ok"
        trace_path = result.get("file", "")
    except (json.JSONDecodeError, TypeError, ValueError):
        # 无法解析 JSON，使用启发式判断
        success = "error" not in output.lower() if output else False
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
    # PostToolUse 的输出在 tool_response 字段（不是 tool_result）
    tool_response = input_data.get("tool_response", {})
    command = tool_input.get("command", "")

    # 提取实际输出：tool_response.stdout 是主要输出
    if isinstance(tool_response, str):
        output = tool_response.strip()
    elif isinstance(tool_response, dict):
        # Claude Code 使用 tool_response.stdout
        output = (
            tool_response.get("stdout", "") or
            tool_response.get("content", "") or
            tool_response.get("output", "") or
            ""
        ).strip()
    else:
        output = str(tool_response).strip() if tool_response else ""

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
