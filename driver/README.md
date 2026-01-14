# 微循环驱动（Stateless CLI）

`dev_driver` 是 Agentic Workflow 的**底层扳手**：只做原子动作、无状态、瞬时响应。  
循环、规划、trace 管理全部由上层（Skills / 脚本）负责。

## 能力
- **Observe**：全屏或窗口截图（PNG，无损，固定 1920×1080）
- **Act**：`click` / `type`（通过 Win32 消息发送，不移动物理鼠标）
- **Inspect**：输出屏幕/窗口几何信息，用于环境预检
- **Focus**：把目标窗口拉到前台（可选最大化）
- **Diff**：对比两张截图并高亮变化区域

> 已移除：输入锁定、虚拟桌面切换、Alt-Tab 焦点争夺、拟人化等待。

## 运行前提
- Windows 11（固定 1920×1080、无缩放）
- Python 3.10+
- 依赖：`pywin32`、`Pillow`

## 使用方式

### 一键预检脚本（长流程推荐）
```bash
powershell -NoProfile -ExecutionPolicy Bypass -File tools/microloop_preflight.ps1
```
可选参数：
```bash
powershell -NoProfile -ExecutionPolicy Bypass -File tools/microloop_preflight.ps1 -WindowWidth 1280 -WindowHeight 720 -X 0 -Y 0 -Mode client
```

### 1) Observe（全屏截图）
```bash
python dev_driver/dev_driver.py observe --out "dev_driver/trace/step-0001.png"
```

输出示例：
```json
{"status":"ok","action":"observe","file":"dev_driver/trace/step-0001.png"}
```

### 2) Observe（窗口截图）
```bash
python dev_driver/dev_driver.py observe --window-title "ShowForAi" --mode window --activate --out "dev_driver/trace/step-0001.png"
```

输出示例：
```json
{"status":"ok","action":"observe","file":"dev_driver/trace/step-0001.png","window":{"title":"ShowForAi - Visual RPA","mode":"window","rect":{"left":0,"top":0,"right":1280,"bottom":720,"width":1280,"height":720}},"screen":{"width":1920,"height":1080}}
```

可选提示特效（不会被截图捕获）：
```bash
python dev_driver/dev_driver.py observe --overlay --overlay-ms 600 --out "dev_driver/trace/step-0001.png"
```
说明：特效显示在截图前后，并在实际截图瞬间隐藏，因此不会进入截图；同时会尝试设置 `WDA_EXCLUDEFROMCAPTURE` 作为额外保险。

### 3) Click（屏幕绝对坐标）
```bash
python dev_driver/dev_driver.py click --x 500 --y 300
```

输出示例：
```json
{"status":"ok","action":"click","x":500,"y":300}
```

可选校验（若提供 window-title）：
```bash
python dev_driver/dev_driver.py click --x 500 --y 300 --window-title "ShowForAi" --verify-window
```

### 4) Click（窗口相对坐标 0..1000）
```bash
python dev_driver/dev_driver.py click --window-title "ShowForAi" --mode client --rel-x 500 --rel-y 500 --activate
```

输出示例：
```json
{"status":"ok","action":"click","x":640,"y":360,"window":{"title":"ShowForAi - Visual RPA","mode":"client","rect":{"left":0,"top":32,"right":1280,"bottom":720,"width":1280,"height":688}}}
```

### 5) Type（前台窗口）
```bash
python dev_driver/dev_driver.py type --text "hello"
```

输出示例：
```json
{"status":"ok","action":"type"}
```

### 6) Inspect（环境预检）
```bash
python dev_driver/dev_driver.py inspect --title "ShowForAi" --strict --expect-foreground --expect-scale 100 --expect-window-size 1280x720
```

输出示例：
```json
{"status":"ok","action":"inspect","screen":{"width":1920,"height":1080},"dpi":{"value":96,"scale_percent":100.0},"window":{"title":"ShowForAi - Visual RPA","rect":{"left":0,"top":0,"right":1280,"bottom":720,"width":1280,"height":720},"client_rect":{"left":0,"top":32,"right":1280,"bottom":720,"width":1280,"height":688},"is_foreground":true,"is_maximized":false}}
```

### 7) Focus（拉前台/最大化）
```bash
python dev_driver/dev_driver.py focus --title "ShowForAi" --maximize
```

输出示例：
```json
{"status":"ok","action":"focus","window":{"title":"ShowForAi - Visual RPA","rect":{"left":-8,"top":-8,"right":1936,"bottom":1048,"width":1944,"height":1056},"client_rect":{"left":0,"top":0,"right":1920,"bottom":1040,"width":1920,"height":1040},"is_foreground":true}}
```

固定窗口尺寸/位置（长流程建议）：
```bash
python dev_driver/dev_driver.py focus --title "ShowForAi" --window-size 1280x720 --x 0 --y 0
```

如需固定“客户区”尺寸：
```bash
python dev_driver/dev_driver.py focus --title "ShowForAi" --client-size 1280x720 --x 0 --y 0
```

### 8) Diff（截图差异标注）
```bash
python dev_driver/dev_driver.py diff --a "dev_driver/trace/step-0001.png" --b "dev_driver/trace/step-0002.png" --out "dev_driver/trace/diff-0002.png"
```

可选参数：
- `--threshold`：差异阈值（0..255，默认 20）
- `--alpha`：红色叠层透明度（0..1，默认 0.6）

输出示例：
```json
{"status":"ok","action":"diff","file":"dev_driver/trace/diff-0002.png","diff_pixels":1234,"diff_ratio":0.0123,"size":{"width":1280,"height":720}}
```

## 坐标体系
- **屏幕绝对坐标**：`x ∈ [0,1919]`，`y ∈ [0,1079]`
- **窗口相对坐标**：`x,y ∈ [0,1000]`，配合 `--window-title --rel-x --rel-y` 自动换算
- 如需使用窗口客户区坐标，使用 `--mode client`

## Trace（由上层管理）
`dev_driver` 本身不创建 session/step。  
如需 trace，请由上层决定输出路径，例如：
```
dev_driver/trace/<session>/step-0001.png
```
命名建议：
- `<session>`：`YYYYMMDD-HHMMSS_<short-tag>`
- step：`step-0001.png`、`step-0002.png`

## 旧版说明
如需查看历史功能/命令示例，请参考归档：
`archive/microloop-driver-backup-20251222-170155/`
