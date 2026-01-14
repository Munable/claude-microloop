"""
dev_driver/dev_driver.py

Stateless, atomic CLI tool for Agentic Workflow:
- observe: capture full-screen or window PNG (lossless)
- click: send a left-click to a screen coordinate via Win32 messages
- type: send text to the foreground window via Win32 messages
- inspect: report screen/window geometry for preflight checks
- focus: bring a window to foreground (optional maximize)
- diff: highlight visual changes between two PNGs

No sessions, no tracing, no waits. The caller owns any loop/state.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
from typing import Any, Optional


SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
REL_MAX = 1000.0
OVERLAY_DEFAULT_MS = 600
OVERLAY_DEFAULT_HEIGHT = 36
OVERLAY_DEFAULT_BG = (255, 92, 0)
OVERLAY_DEFAULT_TEXT = "CAPTURE ACTIVE - PLEASE DON'T TOUCH"
OVERLAY_DEFAULT_ALPHA = 220


class _Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


_OVERLAY_CLASS = "SFA_CAPTURE_OVERLAY"
_OVERLAY_TEXT = OVERLAY_DEFAULT_TEXT
_OVERLAY_BG = OVERLAY_DEFAULT_BG
_OVERLAY_TEXT_RGB = (255, 255, 255)


def _overlay_wnd_proc(hwnd: int, msg: int, wparam: int, lparam: int) -> int:
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32api  # type: ignore

    if msg == win32con.WM_PAINT:
        hdc, paint_struct = win32gui.BeginPaint(hwnd)
        try:
            rect = win32gui.GetClientRect(hwnd)
            brush = win32gui.CreateSolidBrush(win32api.RGB(*_OVERLAY_BG))
            win32gui.FillRect(hdc, rect, brush)
            win32gui.DeleteObject(brush)
            win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
            win32gui.SetTextColor(hdc, win32api.RGB(*_OVERLAY_TEXT_RGB))
            win32gui.DrawText(
                hdc,
                _OVERLAY_TEXT,
                -1,
                rect,
                win32con.DT_CENTER | win32con.DT_VCENTER | win32con.DT_SINGLELINE,
            )
        finally:
            win32gui.EndPaint(hwnd, paint_struct)
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _ok(action: str, **extra: Any) -> None:
    payload: dict[str, Any] = {"status": "ok", "action": action}
    payload.update(extra)
    _print_json(payload)


def _error(action: str, message: str) -> int:
    _print_json({"status": "error", "action": action, "message": message})
    return 1


def _enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # type: ignore[attr-defined]
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
    except Exception:
        pass


def _screen_size() -> tuple[int, int]:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


def _dpi_scale() -> tuple[int, float]:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    dpi = 96
    try:
        dpi = int(user32.GetDpiForSystem())
    except Exception:
        try:
            hdc = user32.GetDC(0)
            dpi = int(ctypes.windll.gdi32.GetDeviceCaps(hdc, 88))  # LOGPIXELSX
            user32.ReleaseDC(0, hdc)
        except Exception:
            dpi = 96
    scale = float(dpi) / 96.0 * 100.0
    return dpi, scale


def _ensure_screen_size() -> None:
    w, h = _screen_size()
    if (w, h) != (SCREEN_WIDTH, SCREEN_HEIGHT):
        raise RuntimeError(f"screen size mismatch: {w}x{h}, expected {SCREEN_WIDTH}x{SCREEN_HEIGHT}")


def _safe_mkdir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def _capture_fullscreen_image():
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32ui  # type: ignore
    from PIL import Image  # type: ignore

    _ensure_screen_size()

    hwnd = win32gui.GetDesktopWindow()
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    mem_dc = src_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()

    try:
        bmp.CreateCompatibleBitmap(src_dc, SCREEN_WIDTH, SCREEN_HEIGHT)
        mem_dc.SelectObject(bmp)
        capture_blt = getattr(win32con, "CAPTUREBLT", 0x40000000)
        blt_flags = win32con.SRCCOPY | capture_blt
        mem_dc.BitBlt(
            (0, 0),
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            src_dc,
            (0, 0),
            blt_flags,
        )
        bmp_info = bmp.GetInfo()
        bmp_bytes = bmp.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_bytes,
            "raw",
            "BGRX",
            0,
            1,
        )
        return image
    finally:
        try:
            win32gui.ReleaseDC(hwnd, hwnd_dc)
        except Exception:
            pass
        try:
            mem_dc.DeleteDC()
            src_dc.DeleteDC()
        except Exception:
            pass
        try:
            win32gui.DeleteObject(bmp.GetHandle())
        except Exception:
            pass


def _dwm_window_rect(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    try:
        dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
    except Exception:
        return None

    rect = _Rect()
    DWMWA_EXTENDED_FRAME_BOUNDS = 9
    try:
        res = dwmapi.DwmGetWindowAttribute(
            int(hwnd),
            DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect),
            ctypes.sizeof(rect),
        )
    except Exception:
        return None
    if int(res) != 0:
        return None
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def _ensure_overlay_class_registered() -> None:
    import win32gui  # type: ignore
    import win32api  # type: ignore

    try:
        win32gui.GetClassInfo(win32api.GetModuleHandle(None), _OVERLAY_CLASS)
        return
    except Exception:
        pass

    wndclass = win32gui.WNDCLASS()
    wndclass.hInstance = win32api.GetModuleHandle(None)
    wndclass.lpszClassName = _OVERLAY_CLASS
    wndclass.lpfnWndProc = _overlay_wnd_proc
    wndclass.hCursor = win32api.LoadCursor(0, 32512)  # IDC_ARROW
    wndclass.hbrBackground = win32gui.GetStockObject(0)  # NULL_BRUSH
    try:
        win32gui.RegisterClass(wndclass)
    except Exception as exc:
        # Ignore "class already exists" to allow repeated overlay calls.
        if getattr(exc, "winerror", None) == 1410:
            return
        raise


def _set_display_affinity(hwnd: int) -> bool:
    # WDA_EXCLUDEFROMCAPTURE (0x11) requires Win10 1903+.
    WDA_EXCLUDEFROMCAPTURE = 0x11
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        res = user32.SetWindowDisplayAffinity(int(hwnd), WDA_EXCLUDEFROMCAPTURE)
        return bool(res)
    except Exception:
        return False


def _create_overlay_window(text: str, height: int, alpha: int) -> Optional[int]:
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32api  # type: ignore

    global _OVERLAY_TEXT
    _OVERLAY_TEXT = text

    _ensure_overlay_class_registered()
    ex_style = (
        win32con.WS_EX_TOPMOST
        | win32con.WS_EX_TOOLWINDOW
        | win32con.WS_EX_LAYERED
        | win32con.WS_EX_TRANSPARENT
    )
    style = win32con.WS_POPUP
    hwnd = win32gui.CreateWindowEx(
        ex_style,
        _OVERLAY_CLASS,
        "",
        style,
        0,
        0,
        SCREEN_WIDTH,
        int(height),
        0,
        0,
        win32api.GetModuleHandle(None),
        None,
    )
    if not hwnd:
        return None

    _set_display_affinity(hwnd)

    win32gui.SetLayeredWindowAttributes(hwnd, 0, int(alpha), win32con.LWA_ALPHA)
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
    win32gui.UpdateWindow(hwnd)
    win32gui.PumpWaitingMessages()
    return int(hwnd)


def _destroy_overlay_window(hwnd: Optional[int]) -> None:
    if not hwnd:
        return
    try:
        import win32gui  # type: ignore

        win32gui.DestroyWindow(int(hwnd))
    except Exception:
        pass


def _sleep_ms(ms: int) -> None:
    if ms <= 0:
        return
    import time

    time.sleep(float(ms) / 1000.0)


def _capture_fullscreen_png(
    out_path: str,
    *,
    overlay: bool,
    overlay_ms: int,
    overlay_text: str,
) -> bool:
    from PIL import Image  # type: ignore

    _safe_mkdir(os.path.dirname(out_path))
    overlay_hwnd = None
    overlay_shown = False
    if overlay:
        overlay_hwnd = _create_overlay_window(overlay_text, OVERLAY_DEFAULT_HEIGHT, OVERLAY_DEFAULT_ALPHA)
        if overlay_hwnd:
            overlay_shown = True
            _sleep_ms(int(overlay_ms))
        _destroy_overlay_window(overlay_hwnd)
        overlay_hwnd = None
    image = _capture_fullscreen_image()
    if not isinstance(image, Image.Image):
        _destroy_overlay_window(overlay_hwnd)
        raise RuntimeError("failed to capture image")
    image.save(out_path, format="PNG")
    if overlay:
        overlay_hwnd = _create_overlay_window(overlay_text, OVERLAY_DEFAULT_HEIGHT, OVERLAY_DEFAULT_ALPHA)
        if overlay_hwnd:
            overlay_shown = True
            _sleep_ms(int(overlay_ms))
        _destroy_overlay_window(overlay_hwnd)
    return overlay_shown


def _validate_xy(x: int, y: int) -> None:
    if not (0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT):
        raise ValueError(f"coordinate out of bounds: x={x}, y={y}")


def _lparam_from_client_xy(x: int, y: int) -> int:
    return (int(y) << 16) | (int(x) & 0xFFFF)


def _root_hwnd(hwnd: int) -> int:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    try:
        return int(win32gui.GetAncestor(hwnd, win32con.GA_ROOT))
    except Exception:
        current = int(hwnd)
        while True:
            parent = win32gui.GetParent(current)
            if not parent:
                return int(current)
            current = int(parent)


def _window_at_point(x: int, y: int) -> int:
    import win32gui  # type: ignore

    hwnd = win32gui.WindowFromPoint((int(x), int(y)))
    if not hwnd:
        raise RuntimeError("no window found at target point")
    return int(hwnd)


def _post_click(hwnd: int, client_x: int, client_y: int) -> None:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    lparam = _lparam_from_client_xy(client_x, client_y)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)


def _click_at(x: int, y: int) -> None:
    import win32gui  # type: ignore

    _ensure_screen_size()
    _validate_xy(x, y)
    hwnd = _window_at_point(int(x), int(y))
    cx, cy = win32gui.ScreenToClient(hwnd, (int(x), int(y)))
    _post_click(hwnd, int(cx), int(cy))


def _enum_windows() -> list[tuple[int, str]]:
    import win32gui  # type: ignore

    windows: list[tuple[int, str]] = []

    def _cb(hwnd: int, _ctx: Any) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title:
            windows.append((hwnd, title))

    win32gui.EnumWindows(_cb, None)
    return windows


def _find_window_by_title(title: str) -> tuple[int, str]:
    needle = title.strip().lower()
    if not needle:
        raise RuntimeError("empty window title")
    matches = [(hwnd, t) for hwnd, t in _enum_windows() if needle in t.lower()]
    if not matches:
        raise RuntimeError(f"no window title contains: {title}")
    if len(matches) > 1:
        titles = ", ".join([t for _hwnd, t in matches[:5]])
        raise RuntimeError(f"multiple windows matched: {titles}")
    return matches[0]


def _window_rect(hwnd: int, mode: str) -> tuple[int, int, int, int]:
    import win32gui  # type: ignore

    mode = mode.lower().strip()
    if mode not in ("window", "client"):
        raise RuntimeError(f"unknown mode: {mode}")
    if mode == "window":
        rect = _dwm_window_rect(hwnd)
        if rect is None:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            return int(left), int(top), int(right), int(bottom)
        return rect
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    x0, y0 = win32gui.ClientToScreen(hwnd, (left, top))
    x1, y1 = win32gui.ClientToScreen(hwnd, (right, bottom))
    return int(x0), int(y0), int(x1), int(y1)


def _rect_dict(rect: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = rect
    return {
        "left": int(left),
        "top": int(top),
        "right": int(right),
        "bottom": int(bottom),
        "width": int(right - left),
        "height": int(bottom - top),
    }


def _parse_size(value: str) -> tuple[int, int]:
    raw = str(value or "").strip().lower()
    if "x" not in raw:
        raise ValueError(f"invalid size format: {value}")
    parts = raw.split("x")
    if len(parts) != 2:
        raise ValueError(f"invalid size format: {value}")
    w = int(parts[0])
    h = int(parts[1])
    if w <= 0 or h <= 0:
        raise ValueError(f"invalid size format: {value}")
    return w, h


def _adjust_window_size_for_client(hwnd: int, client_w: int, client_h: int) -> tuple[int, int]:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    rect = _Rect()
    rect.left = 0
    rect.top = 0
    rect.right = int(client_w)
    rect.bottom = int(client_h)
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        if hasattr(user32, "AdjustWindowRectExForDpi"):
            dpi = 96
            if hasattr(user32, "GetDpiForWindow"):
                try:
                    dpi = int(user32.GetDpiForWindow(int(hwnd)))
                except Exception:
                    dpi = 96
            res = user32.AdjustWindowRectExForDpi(
                ctypes.byref(rect),
                int(style),
                False,
                int(ex_style),
                int(dpi),
            )
        else:
            res = user32.AdjustWindowRectEx(
                ctypes.byref(rect),
                int(style),
                False,
                int(ex_style),
            )
        if not res:
            raise RuntimeError("AdjustWindowRectEx failed")
    except Exception as exc:
        if hasattr(win32gui, "AdjustWindowRectEx"):
            win32gui.AdjustWindowRectEx(rect, style, False, ex_style)
        else:
            raise RuntimeError(f"failed to compute window size from client size: {exc}") from exc
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    if width <= 0 or height <= 0:
        raise RuntimeError("failed to compute window size from client size")
    return width, height


def _set_window_pos(hwnd: int, x: Optional[int], y: Optional[int], width: Optional[int], height: Optional[int]) -> None:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    flags = win32con.SWP_NOZORDER
    if x is None or y is None:
        flags |= win32con.SWP_NOMOVE
        x = 0
        y = 0
    if width is None or height is None:
        flags |= win32con.SWP_NOSIZE
        width = 0
        height = 0
    win32gui.SetWindowPos(hwnd, 0, int(x), int(y), int(width), int(height), flags)


def _focus_window(hwnd: int, maximize: bool) -> None:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    if maximize:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)


def _is_window_foreground(hwnd: int) -> bool:
    import win32gui  # type: ignore

    fg = win32gui.GetForegroundWindow()
    return int(fg) == int(hwnd)


def _is_window_maximized(hwnd: int) -> bool:
    import win32con  # type: ignore
    import win32gui  # type: ignore

    placement = win32gui.GetWindowPlacement(hwnd)
    return int(placement[1]) == int(win32con.SW_SHOWMAXIMIZED)


def _validate_rel(rel: float) -> None:
    if not (0.0 <= rel <= REL_MAX):
        raise ValueError(f"relative coordinate out of bounds: {rel} (0..{int(REL_MAX)})")


def _rel_to_abs(rel_x: float, rel_y: float, rect: tuple[int, int, int, int]) -> tuple[int, int]:
    _validate_rel(rel_x)
    _validate_rel(rel_y)
    left, top, right, bottom = rect
    width = int(right - left)
    height = int(bottom - top)
    if width <= 0 or height <= 0:
        raise RuntimeError(f"invalid rect size: {width}x{height}")
    x = left + int(round((rel_x / REL_MAX) * max(width - 1, 0)))
    y = top + int(round((rel_y / REL_MAX) * max(height - 1, 0)))
    return int(x), int(y)


def _capture_window_png(
    out_path: str,
    hwnd: int,
    mode: str,
    *,
    overlay: bool,
    overlay_ms: int,
    overlay_text: str,
) -> tuple[tuple[int, int, int, int], bool]:
    from PIL import Image  # type: ignore

    _safe_mkdir(os.path.dirname(out_path))
    overlay_hwnd = None
    overlay_shown = False
    if overlay:
        overlay_hwnd = _create_overlay_window(overlay_text, OVERLAY_DEFAULT_HEIGHT, OVERLAY_DEFAULT_ALPHA)
        if overlay_hwnd:
            overlay_shown = True
            _sleep_ms(int(overlay_ms))
        _destroy_overlay_window(overlay_hwnd)
        overlay_hwnd = None
    image = _capture_fullscreen_image()
    if not isinstance(image, Image.Image):
        _destroy_overlay_window(overlay_hwnd)
        raise RuntimeError("failed to capture image")
    rect = _window_rect(hwnd, mode)
    left, top, right, bottom = rect
    if left < 0 or top < 0 or right > SCREEN_WIDTH or bottom > SCREEN_HEIGHT:
        _destroy_overlay_window(overlay_hwnd)
        raise RuntimeError(f"window rect out of bounds: {rect}")
    cropped = image.crop((left, top, right, bottom))
    cropped.save(out_path, format="PNG")
    if overlay:
        overlay_hwnd = _create_overlay_window(overlay_text, OVERLAY_DEFAULT_HEIGHT, OVERLAY_DEFAULT_ALPHA)
        if overlay_hwnd:
            overlay_shown = True
            _sleep_ms(int(overlay_ms))
        _destroy_overlay_window(overlay_hwnd)
    return rect, overlay_shown


def _type_text(text: str) -> None:
    import win32api  # type: ignore
    import win32con  # type: ignore
    import win32gui  # type: ignore

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("no foreground window to receive text")
    for ch in text:
        if ch == "\n":
            code = 13
        else:
            code = ord(ch)
        win32api.PostMessage(hwnd, win32con.WM_CHAR, code, 0)


def cmd_observe(args: argparse.Namespace) -> int:
    out_path = str(args.out or "").strip()
    if not out_path:
        return _error("observe", "--out is required")
    overlay = bool(getattr(args, "overlay", False)) or bool(str(os.getenv("SFA_CAPTURE_OVERLAY", "")).strip())
    overlay_ms = int(getattr(args, "overlay_ms", OVERLAY_DEFAULT_MS) or OVERLAY_DEFAULT_MS)
    overlay_text = str(getattr(args, "overlay_text", "") or "").strip() or OVERLAY_DEFAULT_TEXT
    window_title = str(getattr(args, "window_title", "") or "").strip()
    if window_title:
        hwnd, title = _find_window_by_title(window_title)
        if bool(getattr(args, "activate", False)):
            _focus_window(hwnd, bool(getattr(args, "maximize", False)))
        mode = str(getattr(args, "mode", "window") or "window")
        rect, overlay_shown = _capture_window_png(
            out_path,
            hwnd,
            mode,
            overlay=overlay,
            overlay_ms=overlay_ms,
            overlay_text=overlay_text,
        )
        _ok(
            "observe",
            file=out_path,
            window={"title": title, "mode": mode, "rect": _rect_dict(rect)},
            screen={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
            overlay={"enabled": bool(overlay), "shown": bool(overlay_shown)},
        )
        return 0
    overlay_shown = _capture_fullscreen_png(
        out_path,
        overlay=overlay,
        overlay_ms=overlay_ms,
        overlay_text=overlay_text,
    )
    _ok(
        "observe",
        file=out_path,
        screen={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
        overlay={"enabled": bool(overlay), "shown": bool(overlay_shown)},
    )
    return 0


def cmd_click(args: argparse.Namespace) -> int:
    window_title = str(getattr(args, "window_title", "") or "").strip()
    rel_x = getattr(args, "rel_x", None)
    rel_y = getattr(args, "rel_y", None)
    x = getattr(args, "x", None)
    y = getattr(args, "y", None)

    if rel_x is not None or rel_y is not None:
        if rel_x is None or rel_y is None:
            return _error("click", "--rel-x and --rel-y must be provided together")
        if not window_title:
            return _error("click", "--window-title is required for relative coordinates")
        hwnd, title = _find_window_by_title(window_title)
        if bool(getattr(args, "activate", False)):
            _focus_window(hwnd, bool(getattr(args, "maximize", False)))
        mode = str(getattr(args, "mode", "window") or "window")
        rect = _window_rect(hwnd, mode)
        abs_x, abs_y = _rel_to_abs(float(rel_x), float(rel_y), rect)
        import win32gui  # type: ignore

        hit_hwnd = _window_at_point(abs_x, abs_y)
        if _root_hwnd(hit_hwnd) != int(hwnd):
            return _error(
                "click",
                "target window mismatch at point (window may be unfocused or covered)",
            )
        cx, cy = win32gui.ScreenToClient(hit_hwnd, (int(abs_x), int(abs_y)))
        _post_click(hit_hwnd, int(cx), int(cy))
        _ok(
            "click",
            x=abs_x,
            y=abs_y,
            window={"title": title, "mode": mode, "rect": _rect_dict(rect)},
            hit_window={"hwnd": int(hit_hwnd)},
        )
        return 0

    if x is None or y is None:
        return _error("click", "--x and --y are required when not using relative coordinates")
    if window_title:
        hwnd, _title = _find_window_by_title(window_title)
        if bool(getattr(args, "activate", False)):
            _focus_window(hwnd, bool(getattr(args, "maximize", False)))
        if bool(getattr(args, "verify_window", False)):
            hit_hwnd = _window_at_point(int(x), int(y))
            if _root_hwnd(hit_hwnd) != int(hwnd):
                return _error("click", "target window mismatch at point")
    _click_at(int(x), int(y))
    _ok("click", x=int(x), y=int(y))
    return 0


def cmd_type(args: argparse.Namespace) -> int:
    text = str(args.text or "")
    if text == "":
        return _error("type", "--text is required")
    window_title = str(getattr(args, "window_title", "") or "").strip()
    if window_title and bool(getattr(args, "activate", False)):
        hwnd, _title = _find_window_by_title(window_title)
        _focus_window(hwnd, bool(getattr(args, "maximize", False)))
    _type_text(text)
    _ok("type")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    w, h = _screen_size()
    dpi, scale = _dpi_scale()
    info: dict[str, Any] = {
        "screen": {"width": int(w), "height": int(h)},
        "dpi": {"value": int(dpi), "scale_percent": float(scale)},
    }

    window_title = str(getattr(args, "title", "") or "").strip()
    if window_title:
        hwnd, title = _find_window_by_title(window_title)
        rect = _window_rect(hwnd, "window")
        client_rect = _window_rect(hwnd, "client")
        info["window"] = {
            "title": title,
            "rect": _rect_dict(rect),
            "client_rect": _rect_dict(client_rect),
            "is_foreground": _is_window_foreground(hwnd),
            "is_maximized": _is_window_maximized(hwnd),
        }

    expect_scale = getattr(args, "expect_scale", None)
    if expect_scale is not None:
        expected = float(expect_scale)
        if abs(float(scale) - expected) > 0.5:
            return _error("inspect", f"dpi scale mismatch: {scale:.1f}, expected {expected:.1f}")

    expect_window_size = str(getattr(args, "expect_window_size", "") or "").strip()
    if expect_window_size:
        if "window" not in info:
            return _error("inspect", "window not found for size check")
        exp_w, exp_h = _parse_size(expect_window_size)
        rect_info = info["window"]["rect"]
        if rect_info["width"] != exp_w or rect_info["height"] != exp_h:
            return _error(
                "inspect",
                f"window size mismatch: {rect_info['width']}x{rect_info['height']}, expected {exp_w}x{exp_h}",
            )

    expect_client_size = str(getattr(args, "expect_client_size", "") or "").strip()
    if expect_client_size:
        if "window" not in info:
            return _error("inspect", "window not found for client size check")
        exp_w, exp_h = _parse_size(expect_client_size)
        rect_info = info["window"]["client_rect"]
        if rect_info["width"] != exp_w or rect_info["height"] != exp_h:
            return _error(
                "inspect",
                f"client size mismatch: {rect_info['width']}x{rect_info['height']}, expected {exp_w}x{exp_h}",
            )

    if bool(getattr(args, "expect_maximized", False)):
        if "window" not in info:
            return _error("inspect", "window not found for maximize check")
        if not bool(info.get("window", {}).get("is_maximized")):
            return _error("inspect", "window is not maximized")

    if bool(getattr(args, "strict", False)):
        if (w, h) != (SCREEN_WIDTH, SCREEN_HEIGHT):
            return _error("inspect", f"screen size mismatch: {w}x{h}, expected {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
        if window_title and "window" not in info:
            return _error("inspect", f"window not found: {window_title}")
        if window_title and bool(getattr(args, "expect_foreground", False)):
            if not bool(info.get("window", {}).get("is_foreground")):
                return _error("inspect", "window is not foreground")

    _ok("inspect", **info)
    return 0


def cmd_focus(args: argparse.Namespace) -> int:
    title = str(getattr(args, "title", "") or "").strip()
    if not title:
        return _error("focus", "--title is required")
    hwnd, win_title = _find_window_by_title(title)
    maximize = bool(getattr(args, "maximize", False))
    window_size = str(getattr(args, "window_size", "") or "").strip()
    client_size = str(getattr(args, "client_size", "") or "").strip()
    pos_x = getattr(args, "x", None)
    pos_y = getattr(args, "y", None)

    if not maximize:
        # Restore first so size/position adjustments stick.
        _focus_window(hwnd, False)
        width = height = None
        if window_size:
            width, height = _parse_size(window_size)
        elif client_size:
            cw, ch = _parse_size(client_size)
            width, height = _adjust_window_size_for_client(hwnd, cw, ch)
        if window_size or client_size or pos_x is not None or pos_y is not None:
            _set_window_pos(hwnd, pos_x, pos_y, width, height)
        try:
            import win32gui  # type: ignore

            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    else:
        _focus_window(hwnd, True)
    rect = _window_rect(hwnd, "window")
    client_rect = _window_rect(hwnd, "client")
    _ok(
        "focus",
        window={
            "title": win_title,
            "rect": _rect_dict(rect),
            "client_rect": _rect_dict(client_rect),
            "is_foreground": _is_window_foreground(hwnd),
        },
    )
    return 0


def _write_diff_image(
    a_path: str,
    b_path: str,
    out_path: str,
    *,
    threshold: int,
    alpha: float,
) -> tuple[int, float, tuple[int, int]]:
    from PIL import Image, ImageChops  # type: ignore

    if threshold < 0 or threshold > 255:
        raise ValueError("threshold must be in 0..255")
    if alpha < 0.0 or alpha > 1.0:
        raise ValueError("alpha must be in 0..1")

    img_a = Image.open(a_path).convert("RGB")
    img_b = Image.open(b_path).convert("RGB")
    if img_a.size != img_b.size:
        raise RuntimeError(f"image size mismatch: {img_a.size} vs {img_b.size}")

    diff = ImageChops.difference(img_a, img_b).convert("L")
    mask = diff.point(lambda p: 255 if p > threshold else 0)
    hist = mask.histogram()
    diff_pixels = int(hist[255]) if len(hist) > 255 else 0
    total_pixels = int(mask.size[0] * mask.size[1])
    ratio = (float(diff_pixels) / float(total_pixels)) if total_pixels else 0.0

    overlay = Image.new("RGB", img_b.size, (255, 0, 0))
    blended = Image.blend(img_b, overlay, float(alpha))
    out_img = Image.composite(blended, img_b, mask)
    _safe_mkdir(os.path.dirname(out_path))
    out_img.save(out_path, format="PNG")
    return diff_pixels, ratio, img_b.size


def cmd_diff(args: argparse.Namespace) -> int:
    a_path = str(getattr(args, "a", "") or "").strip()
    b_path = str(getattr(args, "b", "") or "").strip()
    out_path = str(getattr(args, "out", "") or "").strip()
    if not a_path:
        return _error("diff", "--a is required")
    if not b_path:
        return _error("diff", "--b is required")
    if not out_path:
        return _error("diff", "--out is required")
    threshold = int(getattr(args, "threshold", 20) or 20)
    alpha = float(getattr(args, "alpha", 0.6) or 0.6)
    try:
        diff_pixels, ratio, size = _write_diff_image(
            a_path,
            b_path,
            out_path,
            threshold=threshold,
            alpha=alpha,
        )
    except Exception as exc:
        return _error("diff", str(exc))
    _ok(
        "diff",
        file=out_path,
        diff_pixels=diff_pixels,
        diff_ratio=ratio,
        size={"width": int(size[0]), "height": int(size[1])},
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="dev_driver", description="Stateless Windows GUI driver")
    sub = ap.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("observe", help="capture full-screen PNG (1920x1080)")
    sp.add_argument("--out", required=True, help="output PNG path")
    sp.add_argument("--window-title", default="", help="capture window by title substring")
    sp.add_argument("--mode", default="window", choices=["window", "client"], help="window rect mode")
    sp.add_argument("--activate", action="store_true", help="bring window to foreground before observe")
    sp.add_argument("--maximize", action="store_true", help="maximize window before observe")
    sp.add_argument("--overlay", action="store_true", help="show capture overlay (excluded from screenshot)")
    sp.add_argument("--overlay-ms", type=int, default=OVERLAY_DEFAULT_MS, help="overlay duration before/after capture")
    sp.add_argument("--overlay-text", default=OVERLAY_DEFAULT_TEXT, help="overlay text")
    sp.set_defaults(func=cmd_observe)

    sp = sub.add_parser("click", help="left-click at screen coordinates")
    sp.add_argument("--x", type=int, help="screen x (0..1919)")
    sp.add_argument("--y", type=int, help="screen y (0..1079)")
    sp.add_argument("--window-title", default="", help="target window title substring")
    sp.add_argument("--rel-x", type=float, help="relative x (0..1000)")
    sp.add_argument("--rel-y", type=float, help="relative y (0..1000)")
    sp.add_argument("--mode", default="window", choices=["window", "client"], help="window rect mode")
    sp.add_argument("--activate", action="store_true", help="bring window to foreground before click")
    sp.add_argument("--maximize", action="store_true", help="maximize window before click")
    sp.add_argument("--verify-window", action="store_true", help="fail if click point is outside target window")
    sp.set_defaults(func=cmd_click)

    sp = sub.add_parser("type", help="type text into foreground window")
    sp.add_argument("--text", required=True, help="text to type")
    sp.add_argument("--window-title", default="", help="target window title substring")
    sp.add_argument("--activate", action="store_true", help="bring window to foreground before type")
    sp.add_argument("--maximize", action="store_true", help="maximize window before type")
    sp.set_defaults(func=cmd_type)

    sp = sub.add_parser("inspect", help="report screen/window geometry for preflight")
    sp.add_argument("--title", default="", help="window title substring")
    sp.add_argument("--strict", action="store_true", help="fail if screen/window checks fail")
    sp.add_argument("--expect-foreground", action="store_true", help="require window to be foreground (strict only)")
    sp.add_argument("--expect-scale", type=float, help="expected dpi scale percent (e.g. 100)")
    sp.add_argument("--expect-window-size", help="expected window size WxH (e.g. 1280x720)")
    sp.add_argument("--expect-client-size", help="expected client size WxH (e.g. 1280x688)")
    sp.add_argument("--expect-maximized", action="store_true", help="require window to be maximized")
    sp.set_defaults(func=cmd_inspect)

    sp = sub.add_parser("focus", help="bring a window to foreground")
    sp.add_argument("--title", required=True, help="window title substring")
    sp.add_argument("--maximize", action="store_true", help="maximize window before focus")
    sp.add_argument("--x", type=int, help="optional window x position")
    sp.add_argument("--y", type=int, help="optional window y position")
    sp.add_argument("--window-size", help="optional window size WxH (e.g. 1280x720)")
    sp.add_argument("--client-size", help="optional client size WxH (e.g. 1280x720)")
    sp.set_defaults(func=cmd_focus)

    sp = sub.add_parser("diff", help="highlight changes between two PNGs")
    sp.add_argument("--a", required=True, help="path to first PNG")
    sp.add_argument("--b", required=True, help="path to second PNG")
    sp.add_argument("--out", required=True, help="output PNG path")
    sp.add_argument("--threshold", type=int, default=20, help="diff threshold (0..255)")
    sp.add_argument("--alpha", type=float, default=0.6, help="overlay alpha (0..1)")
    sp.set_defaults(func=cmd_diff)

    return ap


def main() -> int:
    _enable_dpi_awareness()
    ap = build_parser()
    args = ap.parse_args()
    action = str(getattr(args, "command", "") or "unknown")
    try:
        return int(args.func(args))
    except Exception as exc:
        return _error(action, str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
