"""run_build.py - カメラモデル自動生成パイプライン（forge_camera のエントリポイント）。

使用法:
    python scripts/camera_model/run_build.py irvision_2d
    python scripts/camera_model/run_build.py irvision_2d --publish <コピー先>
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from forge_camera import main

if __name__ == "__main__":
    main()
