"""run_build.py - パラメトリック加工機モデル自動生成パイプライン（forge_nc_machine のエントリポイント）。

使用法:
    python scripts/nc_machine/run_build.py turning_h_k1
    python scripts/nc_machine/run_build.py all
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from forge_nc_machine import main

if __name__ == "__main__":
    main()
