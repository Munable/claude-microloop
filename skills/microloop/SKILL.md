---
name: microloop
description: |
  GUI 视觉验证工具。当 Claude 需要像人一样「真正看到屏幕画面」并「操作窗口」时使用。

  自动触发场景：
  - 用户说「看看界面」「截个图」「检查 UI」「验证显示效果」
  - 开发 GUI 应用后需要验证实际渲染结果
  - 调试 UI bug 需要看到真实画面
  - 需要点击按钮、输入文本等窗口操作
  - 需要截图作为证据

  关键词：GUI、界面、UI、窗口、截图、看到、显示效果、点击、视觉验证
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

## 这是什么？

让 Claude Code 获得「眼睛」和「手」：
- **眼睛**：通过截图看到真实的屏幕/窗口画面
- **手**：通过模拟点击、输入来操作 GUI

## 什么时候用？

当你需要 Claude 像人一样**真正看到并操作界面**时：
- ✅ 开发了 GUI 功能，需要验证实际显示效果
- ✅ UI 有 bug，需要看到真实画面来调试
- ✅ 需要自动化操作某个窗口（点击、输入）
- ✅ 需要截图作为证据

**不需要用的场景**：
- ❌ 只是读写代码文件
- ❌ 运行命令行程序
- ❌ 不涉及 GUI 的任务

## 单步 vs Loop

- **microloop（本 skill）**：每次一个动作，便于调试和观察
- **microloop_loop**：配合 ralph-loop 插件，无人值守循环直到完成

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
