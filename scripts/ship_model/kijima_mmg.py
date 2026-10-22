"""kijima_mmg.py - 貴島（Kijima 1990）推定式による船舶初期MMG流体微係数自動推算モジュール。

主要目 (L_pp, B, d, C_b, 舵面積, プロペラ直径) から、
無次元流体微係数・付加質量・プロペラ・舵干渉係数を自動算出し、
箱庭船舶物理プラグイン (ShipHydroPlugin) が読み込む hydro_mmg.json を生成する。
"""
from __future__ import annotations

import math
from typing import Any, Dict


def estimate_mmg_coefficients(
    length_pp_m: float,
    beam_m: float,
    draft_m: float,
    block_coefficient: float,
    rudder_area_m2: float,
    propeller_dia_m: float,
    water_density_kg_m3: float = 1025.0,
    trim_m: float = 0.0,
) -> Dict[str, Any]:
    """主要目から貴島 (1990) 推定式に基づき MMG 操縦運動パラメータを算出する。

    無次元化基準:
      長さ: L_pp
      速度: U
      質量基準: 0.5 * rho * L_pp^2 * d
      力: 0.5 * rho * L_pp * d * U^2
      モーメント: 0.5 * rho * L_pp^2 * d * U^2
    """
    L = float(length_pp_m)
    B = float(beam_m)
    d = float(draft_m)
    Cb = float(block_coefficient)
    Ar = float(rudder_area_m2)
    Dp = float(propeller_dia_m)
    rho = float(water_density_kg_m3)

    # 排水量 Δ [kg]
    mass_kg = rho * Cb * L * B * d
    # 無次元質量 m' = mass / (0.5 * rho * L^2 * d) = 2 * Cb * (B / L)
    mass_prime = mass_kg / (0.5 * rho * (L ** 2) * d)

    # アスペクト比パラメータ k = 2 * d / L
    k = 2.0 * d / L
    B_L = B / L
    d_B = d / B

    # 慣性モーメント I_zz [kg*m^2]
    # 一般に内航貨物船の旋回半径 k_zz ≈ 0.25 * Lpp
    k_zz = 0.25 * L
    Izz = mass_kg * (k_zz ** 2)
    Izz_prime = Izz / (0.5 * rho * (L ** 4) * d)

    # 付加質量 (Added Mass) 推算 (加藤・元良の推定式)
    # 前後付加質量 mx ≈ 0.05 * m
    mx_kg = 0.05 * mass_kg
    mx_prime = 0.05 * mass_prime

    # 横付加質量 my: 元良式による付加質量比 ky = my / mass ≈ (pi/2) * (d/B) * (1 / Cb) * [1 + 0.14 * Cb * (B/L)]
    # 実船の代表値: ky ≈ 0.50 ~ 0.85
    ky = (math.pi / 2.0) * d_B * (1.0 / max(0.1, Cb)) * (1.0 + 0.14 * Cb * B_L)
    # 現実的な範囲 [0.45, 0.95] にクランプ
    ky = max(0.45, min(0.95, ky))
    my_kg = ky * mass_kg
    my_prime = ky * mass_prime

    # 付加慣性モーメント Jzz: Jzz ≈ (0.25 * L)^2 * my
    Jzz_kg = (0.25 * L) ** 2 * my_kg
    Jzz_prime = Jzz_kg / (0.5 * rho * (L ** 4) * d)

    # 船体流体力微係数 (Hull Derivatives) - 貴島 (1990) 標準推定式
    # 偶数次 (X方向: 前進抵抗・連成減衰)
    X_vv_prime = -0.0014 - 0.1975 * (1.0 - Cb) * (B / d) + 0.0191 * B_L
    X_vr_prime = -0.0033 + 0.0888 * (1.0 - Cb) * (B / d) + 0.0028 * B_L
    X_rr_prime = 0.0028 - 0.0450 * (1.0 - Cb) * (B / d) - 0.0008 * B_L
    X_vvvv_prime = 0.0

    # 奇数次 (Y方向: 横力)
    Y_v_prime = -(0.5 * math.pi * k + 1.4 * Cb * B_L)
    Y_r_prime = 0.25 * math.pi * k
    Y_vvv_prime = -(2.5 * (1.0 - Cb) * (B / d) + 0.5)
    Y_vvr_prime = -(1.5 * (1.0 - Cb) * (B / d) + 0.2)
    Y_vrr_prime = -(0.35 * (1.0 - Cb) * (B / d) + 0.05)
    Y_rrr_prime = -(0.015 * (1.0 - Cb) * (B / d) + 0.005)

    # 奇数次 (N方向: 回頭モーメント)
    N_v_prime = -k
    N_r_prime = -0.54 * k + (k ** 2)
    N_vvv_prime = -(0.56 * Cb * (B / d) - 0.09)
    N_vvr_prime = -(0.35 * Cb * (B / d) - 0.05)
    N_vrr_prime = -(0.08 * Cb * (B / d) - 0.01)
    N_rrr_prime = -(0.038 * Cb * (B / d) - 0.005)

    # プロペラ・舵相互干渉係数 (Propeller & Rudder Interaction)
    # プロペラ推力減損率 t_P
    t_P = 0.22 * Cb - 0.05
    # プロペラ有効伴流率 w_P0
    w_P0 = 0.50 * Cb - 0.05

    # 舵力減損率 (1 - t_R)
    t_R = 1.0 - (0.28 * Cb + 0.55)
    # 船体誘導横力係数 a_H
    a_H = 0.678 * (1.0 - Cb) + 0.156
    # 船体誘導モーメントレバー x_H'
    x_H_prime = -0.450

    # 舵面積比
    rudder_area_ratio = Ar / (L * d)

    # 推進器単独特性 (Wageningen B-Series 近似係数)
    # K_T(J) = a_0 + a_1 * J + a_2 * J^2
    kt_a0 = 0.38
    kt_a1 = -0.32
    kt_a2 = -0.12

    return {
        "metadata": {
            "model_type": "MMG_3DOF_Hybrid",
            "estimation_source": "Kijima 1990 & Kato-Motora",
            "units": "SI_metric",
        },
        "dimensions": {
            "length_pp_m": L,
            "beam_m": B,
            "draft_m": d,
            "block_coefficient": Cb,
            "displacement_kg": mass_kg,
            "rudder_area_m2": Ar,
            "propeller_dia_m": Dp,
            "water_density_kg_m3": rho,
        },
        "mass_and_inertia": {
            "mass_kg": mass_kg,
            "mass_prime": mass_prime,
            "Izz_kgm2": Izz,
            "Izz_prime": Izz_prime,
            "added_mass_x_kg": mx_kg,
            "added_mass_x_prime": mx_prime,
            "added_mass_y_kg": my_kg,
            "added_mass_y_prime": my_prime,
            "added_inertia_zz_kgm2": Jzz_kg,
            "added_inertia_zz_prime": Jzz_prime,
        },
        "hull_derivatives_prime": {
            "X_vv": X_vv_prime,
            "X_vr": X_vr_prime,
            "X_rr": X_rr_prime,
            "X_vvvv": X_vvvv_prime,
            "Y_v": Y_v_prime,
            "Y_r": Y_r_prime,
            "Y_vvv": Y_vvv_prime,
            "Y_vvr": Y_vvr_prime,
            "Y_vrr": Y_vrr_prime,
            "Y_rrr": Y_rrr_prime,
            "N_v": N_v_prime,
            "N_r": N_r_prime,
            "N_vvv": N_vvv_prime,
            "N_vvr": N_vvr_prime,
            "N_vrr": N_vrr_prime,
            "N_rrr": N_rrr_prime,
        },
        "propeller_and_rudder": {
            "thrust_deduction_t_P": t_P,
            "wake_fraction_w_P0": w_P0,
            "rudder_force_deduction_t_R": t_R,
            "induced_lateral_force_a_H": a_H,
            "induced_moment_lever_x_H_prime": x_H_prime,
            "rudder_area_ratio": rudder_area_ratio,
            "propeller_kt_coefficients": [kt_a0, kt_a1, kt_a2],
        },
        "low_speed_cross_flow": {
            "cross_flow_drag_coefficient_cd": 1.15,
            "blending_speed_threshold_m_s": 1.5,
        },
    }
