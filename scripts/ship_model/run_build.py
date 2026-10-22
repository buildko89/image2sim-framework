"""run_build.py - パラメトリック船舶モデル自動生成パイプライン (forge_ship エントリポイント)

使用法:
    python scripts/ship_model/run_build.py container_749gt
    python scripts/ship_model/run_build.py fishing_boat
    python scripts/ship_model/run_build.py all
"""
from __future__ import annotations

import sys
from pathlib import Path

# 同一ディレクトリの forge_ship をインポートして実行
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from forge_ship import main

if __name__ == "__main__":
    main()
