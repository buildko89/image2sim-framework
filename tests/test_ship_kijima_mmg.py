"""test_ship_kijima_mmg.py - 貴島推定式の単体テスト。"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ship_model"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from kijima_mmg import estimate_mmg_coefficients


def test_kijima_mmg_749gt():
    # 749GT コンテナ船の主要目
    res = estimate_mmg_coefficients(
        length_pp_m=90.0,
        beam_m=14.0,
        draft_m=3.8,
        block_coefficient=0.672,
        rudder_area_m2=7.2,
        propeller_dia_m=3.2,
    )

    # 1. 排水量と質量の確認 (約 3,300 t)
    mass = res["mass_and_inertia"]["mass_kg"]
    assert 3_200_000 <= mass <= 3_400_000

    # 2. 付加質量の確認 (mx ≈ 5% mass, my ≈ 50-80% mass)
    mx = res["mass_and_inertia"]["added_mass_x_kg"]
    my = res["mass_and_inertia"]["added_mass_y_kg"]
    assert 0.04 * mass <= mx <= 0.06 * mass
    assert 0.40 * mass <= my <= 0.90 * mass

    # 3. 操縦流体微係数の物理的符号の確認
    h = res["hull_derivatives_prime"]
    assert h["Y_v"] < 0.0, "Y_v must be negative (damping/restoring lateral force)"
    assert h["Y_r"] > 0.0, "Y_r must be positive"
    assert h["N_v"] < 0.0, "N_v must be negative (static directional stability tendency)"
    assert h["N_r"] < 0.0, "N_r must be negative (yaw damping moment)"

    # 非線形3次係数の確認
    assert h["Y_vvv"] < 0.0
    assert h["N_vvv"] < 0.0
    assert h["N_rrr"] < 0.0

    # 4. プロペラ・舵干渉係数の確認
    pr = res["propeller_and_rudder"]
    assert 0.05 <= pr["thrust_deduction_t_P"] <= 0.25
    assert 0.20 <= pr["wake_fraction_w_P0"] <= 0.35
