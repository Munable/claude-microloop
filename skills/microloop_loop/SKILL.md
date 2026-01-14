---
name: microloop_loop
description: |
  GUI 视觉验证工具（循环模式）。配合 ralph-loop 插件实现无人值守的 GUI 验证循环。

  触发条件：
  - 用户明确说「loop」「ralph」「无人值守」「自动循环」
  - 需要反复修改代码 → 验证 GUI → 继续修改，直到完美

  工作模式：
  - ralph-loop 负责循环回灌初始任务
  - microloop_loop 负责 GUI 截图和操作
  - 两者结合 = 自动化 GUI 验证修复循环
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python .claude/claude-microloop/skills/microloop_loop/scripts/preflight_hook.py"
  PostToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python .claude/claude-microloop/skills/microloop_loop/scripts/trace_hook.py"
  Stop:
    - hooks:
        - type: prompt
          prompt: |
            检查微循环 GUI 任务是否完成。

            判断标准：
            1. 用户指定的 GUI 验证目标是否已达成
            2. 最后的截图是否显示了预期的 UI 状态
            3. 是否输出了 <promise>DONE</promise> 标记

            如果任务完成，返回 JSON: {"ok": true}
            如果需要继续迭代，返回 JSON: {"ok": false, "reason": "描述还需要做什么"}
---

# 微循环（Loop 版 / v2）

## 定位
- 面向"固定 prompt + 多轮迭代"的自循环版本（Ralph 风格）
- 默认无人值守运行，与 ralph-loop 插件协作
- 仍坚持 Observe → Act → Trace，单步单动作

## 触发条件
- 用户明确要求 loop / ralph / 无人值守
- 需要固定 prompt 反复执行直到完成或达到 max_iterations
- 其他场景使用 v1 `microloop`

## Hooks 自动化（Claude Code 特性）
本 skill 激活时：
- **PreToolUse**: 执行 dev_driver 命令前自动验证环境
- **PostToolUse**: 执行后自动记录 trace 和更新迭代计数
- **Stop**: 智能判断任务是否完成（替代手动 completion promise 检查）

## 与 ralph-loop 插件协作
本 skill 可与 `ralph-loop` 插件配合使用：
- ralph-loop 负责循环控制和 prompt 回灌
- microloop_loop 负责 GUI 操作和验证
- 使用 `/ralph-loop` 启动，`/cancel-ralph` 取消

## Ralph 约束（必须遵守）
- Prompt 固定，不扩写、不改写、不重排完成条件
- 只关注**下一步最小动作**，不要写计划
- 若设置 completion promise，只有在**完全真实**时才输出 `<promise>...</promise>`
- 接近 max_iterations 时优先收敛

## 输出格式（严格 JSON）
```json
{
  "observation": "关键 UI 状态",
  "action": {"type": "click", "rel_x": 500, "rel_y": 500},
  "expect": "本步后应看到的变化",
  "evidence": {
    "trace": ".claude/claude-microloop/trace/<session>/step-0001.png"
  }
}
```

约束：
- 字段顺序固定，不添加额外段落
- Evidence 只写路径，不写解释
- 每轮只输出**一个动作**
- 不追加建议/问题

## 完成与停止条件
- 完成：输出 `<promise>DONE</promise>`
- Stop hook 会自动检测完成状态
- 不使用 `<promise>BLOCKED</promise>` 结束循环

## 驱动命令

### 预检与聚焦（每轮开始前）
```bash
python .claude/claude-microloop/driver/dev_driver.py focus --title "<title>" --client-size 1280x720 --x 0 --y 0
python .claude/claude-microloop/driver/dev_driver.py inspect --title "<title>" --strict --expect-foreground --expect-scale 100 --expect-client-size 1280x720
python .claude/claude-microloop/driver/dev_driver.py observe --window-title "<title>" --mode client --activate --out "<trace>" --overlay --overlay-ms 600
```

### 一键预检脚本
```bash
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/claude-microloop/tools/microloop_loop_preflight.ps1 -Title "<title>"
```

### 点击
```bash
python .claude/claude-microloop/driver/dev_driver.py click --window-title "<title>" --rel-x 500 --rel-y 500 --mode client --activate
```

### 输入
```bash
python .claude/claude-microloop/driver/dev_driver.py type --text "hello" --window-title "<title>" --activate
```

### 截图对比（Diff）
```bash
python .claude/claude-microloop/driver/dev_driver.py diff --a "<prev.png>" --b "<curr.png>" --out "<diff.png>" --threshold 20
```

## 异常分层
- **L1 可恢复**: 失焦/尺寸漂移 → `focus` + `inspect` + `observe` 再继续
- **L2 需清障**: 弹窗/权限提示 → 先关闭/确认/退回
- **L3 阻塞**: 网络/权限缺失 → 写入 observation 并继续迭代

## 环境要求
- Win11，1920×1080，无缩放
- 固定窗口大小/位置
- 坐标优先使用 0..1000 相对坐标或 `--mode client`
