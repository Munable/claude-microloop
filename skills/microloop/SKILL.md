---
name: microloop
description: GUI verification and UI debugging via observe/act/trace micro-loops. Use when tasks require seeing the screen, manipulating UI, validating visual results, or debugging UI flows. 当涉及"需要看到画面/调试界面/操作界面/GUI 验证"时使用。
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python .claude/claude-microloop/skills/microloop/scripts/preflight_hook.py"
  PostToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python .claude/claude-microloop/skills/microloop/scripts/trace_hook.py"
---

# 微循环（Microloop）

## 定位
- microloop = **微循环**（记忆映射）
- 只做 Observe / Act / Trace；规划与改代码仍在 Claude Code 完成。

## 触发条件
- 需要看到画面 / 调试界面 / 操作 GUI / 验证 UI 行为时。
- 若用户明确要求 loop/ralph/无人值守，改用 `microloop_loop`。

## 核心流程（严格单步）
1) Observe：截图 + trace
2) Plan：在 Claude Code 决定下一步
3) Act：执行**单个动作**
4) Observe：再次截图验证结果

## Hooks 自动化（Claude Code 特性）
本 skill 激活时，以下操作自动执行：
- **PreToolUse**: 执行 dev_driver 命令前自动验证环境
- **PostToolUse**: 执行后自动记录 trace 日志

## 驱动命令

### 截图（Observe）
```bash
python .claude/claude-microloop/driver/dev_driver.py observe --out ".claude/claude-microloop/trace/<session>/step-XXXX.png" --window-title "<title>" --mode client --activate --overlay --overlay-ms 600
```

### 点击（Act）
```bash
# 窗口相对坐标（推荐）
python .claude/claude-microloop/driver/dev_driver.py click --window-title "<title>" --rel-x 500 --rel-y 500 --mode client --activate

# 屏幕绝对坐标（需要 --verify-window）
python .claude/claude-microloop/driver/dev_driver.py click --x 640 --y 360 --window-title "<title>" --verify-window
```

### 输入文本
```bash
python .claude/claude-microloop/driver/dev_driver.py type --text "hello" --window-title "<title>" --activate
```

### 预检与聚焦
```bash
python .claude/claude-microloop/driver/dev_driver.py focus --title "<title>" --client-size 1280x720 --x 0 --y 0
python .claude/claude-microloop/driver/dev_driver.py inspect --title "<title>" --strict --expect-foreground --expect-scale 100 --expect-client-size 1280x720
```

### 一键预检脚本
```bash
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/claude-microloop/tools/microloop_loop_preflight.ps1 -Title "<title>"
```

## 固定输出格式
```
Observation: 关键 UI 状态（1-2 句）
Action: 单条动作（JSON）
Expect: 本步后应看到的变化
Evidence: trace 路径（png 必须）
```

## 动作与坐标
- 动作使用结构化 JSON（兼容 Open-AutoGLM 风格）
- 坐标优先使用 0..1000 相对坐标
- 内容区点击优先 `--mode client`，减少标题栏/边框影响
- 每次只执行一个动作

## 异常处理（必须优先）
- 白屏/卡死/不一致 → 立即插入"修复/排查"任务
- 修复后再回到微循环验证

## 环境要求
- Win11，1920×1080，无缩放
- 固定窗口大小/位置，避免坐标漂移

## Trace 证据
- 每步必须产出 trace（截图 png）
- 关键结论必须引用 trace
- 位置：`.claude/claude-microloop/trace/<session>/step-XXXX.png`
- 命名建议：
  - session：`YYYYMMDD-HHMMSS_<short-tag>`
  - step：`step-0001.png`、`step-0002.png`

## 结论要求
- 每次 GUI 验证完成，结论末尾写：**GUI 验证 via 微循环**
