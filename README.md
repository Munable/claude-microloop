# Claude Microloop

GUI 验证和 UI 调试的微循环工具，专为 Claude Code 设计。

## 功能

让 Claude Code 能够"看见"并"操作" GUI：
- **Observe**: 截图获取屏幕/窗口状态
- **Act**: 执行点击、输入等操作
- **Trace**: 记录每步的证据（截图）

## 目录结构

```
claude-microloop/
├── skills/
│   ├── microloop/           # 基础微循环 skill（单步模式）
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       ├── preflight_hook.py
│   │       └── trace_hook.py
│   └── microloop_loop/      # Loop 版微循环 skill（无人值守）
│       ├── SKILL.md
│       └── scripts/
│           ├── preflight_hook.py
│           └── trace_hook.py
├── driver/
│   ├── dev_driver.py        # 核心驱动程序
│   ├── poc_microloop.py     # POC 演示
│   └── README.md
├── tools/
│   ├── microloop_loop_setup.ps1
│   ├── microloop_loop_guard.ps1
│   ├── microloop_loop_tick.ps1
│   ├── microloop_loop_cancel.ps1
│   └── microloop_loop_preflight.ps1
└── traces/                  # 截图和日志（自动创建）
```

## 安装

1. 将此仓库放置在项目的 `.claude/claude-microloop` 目录下
2. 确保安装了依赖：`pip install pywin32 Pillow`
3. Claude Code 会自动识别 skills 目录中的 skill

## 使用

### 基础模式（单步）

当需要 GUI 验证时，Claude Code 会自动使用 `microloop` skill：

```
Observe → Plan → Act → Observe
```

每步只执行一个动作，便于调试和复盘。

### Loop 模式（无人值守）

用户明确要求 loop/ralph 时，使用 `microloop_loop` skill：

- 与 `ralph-loop` 插件配合使用
- 固定 prompt 反复执行直到完成
- 输出 `<promise>DONE</promise>` 标记完成

## Skill-Scoped Hooks

本仓库使用 Claude Code 的 skill-scoped hooks 特性：

- **PreToolUse**: 执行命令前自动验证环境（分辨率、窗口状态）
- **PostToolUse**: 执行后自动记录 trace 日志
- **Stop**: 智能判断任务是否完成（仅 loop 模式）

**重要**: hooks 只在 skill 激活时生效，结束后自动清理，不会影响其他会话。

## 驱动命令

### 截图
```bash
python .claude/claude-microloop/driver/dev_driver.py observe \
  --window-title "MyApp" \
  --mode client \
  --activate \
  --overlay \
  --out "trace/step-0001.png"
```

### 点击
```bash
python .claude/claude-microloop/driver/dev_driver.py click \
  --window-title "MyApp" \
  --rel-x 500 --rel-y 500 \
  --mode client \
  --activate
```

### 输入
```bash
python .claude/claude-microloop/driver/dev_driver.py type \
  --text "hello" \
  --window-title "MyApp" \
  --activate
```

### 预检
```bash
powershell -NoProfile -ExecutionPolicy Bypass \
  -File .claude/claude-microloop/tools/microloop_loop_preflight.ps1 \
  -Title "MyApp"
```

## 环境要求

- Windows 11
- 1920×1080 分辨率，100% 缩放
- Python 3.10+
- pywin32, Pillow

## 许可

MIT License
