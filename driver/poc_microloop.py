"""
dev_driver/poc_microloop.py

Minimal demo for the stateless driver: Observe -> Click -> Observe.
The caller manages trace paths and step numbering.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime


def _now_session_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _step_name(idx: int) -> str:
    return f"step-{idx:04d}.png"


def run(cmd: list[str]) -> int:
    p = subprocess.run(cmd, check=False)
    return int(p.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="", help="session id (optional)")
    ap.add_argument("--out-root", default=os.path.join("dev_driver", "trace"), help="trace root dir")
    ap.add_argument("--x", type=int, required=True, help="screen x (0..1919)")
    ap.add_argument("--y", type=int, required=True, help="screen y (0..1079)")
    args = ap.parse_args()

    session = str(args.session or "").strip() or _now_session_id()
    out_dir = os.path.join(str(args.out_root), session)
    os.makedirs(out_dir, exist_ok=True)

    py = sys.executable
    driver = os.path.join("dev_driver", "dev_driver.py")

    rc = run([py, driver, "observe", "--out", os.path.join(out_dir, _step_name(1))])
    if rc != 0:
        return rc

    rc = run([py, driver, "click", "--x", str(args.x), "--y", str(args.y)])
    if rc != 0:
        return rc

    rc = run([py, driver, "observe", "--out", os.path.join(out_dir, _step_name(2))])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
