"""hull_form.py - パラメトリック船体形状（Blender 非依存。build_ship.py とテストが使う）。

座標系は build_ship.py と同じ（+X 右舷, +Y 船首, +Z 上, 原点 = 船体中央の計画水線）。

船体は u ∈ [-1, 1]（-1: 船尾トランサム, 0: 船体中央, +1: 船首材）の断面列で表す。
  - 水線半幅 b_wl(u) と甲板半幅 b_deck(u)（甲板の方が肥えているので船首でフレアになる）
  - 水線下の断面は超楕円 |y/b|^n + |z/T|^n = 1（n が大きいほど平底・角ばったビルジ、n = 2 で楕円）。
    船体中央の n は中央横断面係数 C_m（大型船 0.985、Cb 0.42 の小型 V 形船 0.70）から決める
  - 肥瘠度 s（水線の船首尾の絞りと断面が V 形へ細る速さを同時に変える）を「水線下の体積 = 排水容積」に
    なるよう二分法で決める（物理の浮力と見た目の喫水を一致させる）
  - 船尾は竜骨線がプロペラの前で切り上がり（カウンター）、トランサム下端はプロペラ円の上端より上
  - 前後位置は高さで変わる: 船首材は水線上で前傾（レーキ）、水線下で丸く後退（フォアフット）、
    船尾は水線上でトランサムまで張り出す
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

Point3 = Tuple[float, float, float]


@dataclass
class HullParams:
    Lpp: float
    B: float
    D: float
    d: float
    Cb: float
    loa: float
    transom_width_ratio: float = 0.75
    sheer_fore: float = 1.8
    sheer_aft: float = 0.6
    bulb: bool = False
    # 導出値
    bow_rake: float = 0.0          # 甲板位置での船首材の FP からの張り出し [m]
    stern_overhang: float = 0.0    # トランサムの AP からの張り出し [m]
    forefoot: float = 0.0          # 竜骨位置での船首材の FP からの後退 [m]
    transom_z: float = 0.0         # トランサム下端（カウンター）の高さ [m]（負: 水線下）
    run_start_u: float = -0.55     # 竜骨線が切り上がり始める u
    counter_u: float = -0.9        # カウンター高さに達する u（プロペラの前縁）
    n_mid: float = 6.0             # 船体中央断面の超楕円指数（C_m から）
    n_end: float = 1.4             # 船首尾の超楕円指数（V 形）
    fullness: float = 1.0          # 肥瘠度 s（solve_fullness で決める。大きいほど肥大）
    target_volume: float = 0.0     # 排水容積 [m^3]
    props: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, 直径)

    @property
    def freeboard(self) -> float:
        return self.D - self.d


def params_from_cfg(cfg: dict) -> HullParams:
    dim = cfg["dimensions"]
    hull = cfg.get("hull", {})
    Lpp = float(dim["length_pp_m"])
    B = float(dim["beam_m"])
    D = float(dim["depth_m"])
    d = float(dim["draft_m"])
    Cb = float(dim["block_coefficient"])
    loa = float(dim.get("length_oa_m", Lpp * 1.06))
    rho = float(dim.get("water_density_kg_m3", 1025.0))
    disp_t = dim.get("displacement_tonnes")
    target = float(disp_t) * 1000.0 / rho if disp_t else Cb * Lpp * B * d

    bulb = bool(hull.get("bulbous_bow", {}).get("enabled", False))
    over = max(0.0, loa - Lpp)
    p = HullParams(
        Lpp=Lpp, B=B, D=D, d=d, Cb=Cb, loa=loa,
        transom_width_ratio=float(hull.get("transom_width_ratio", 0.75)),
        sheer_fore=float(hull.get("sheer_fore_m", hull.get("sections", {}).get("sheer_fore_m", 1.8))),
        sheer_aft=float(hull.get("sheer_aft_m", hull.get("sections", {}).get("sheer_aft_m", 0.6))),
        bulb=bulb,
        bow_rake=0.65 * over,
        stern_overhang=0.35 * over,
        forefoot=(0.03 if bulb else 0.07) * Lpp,
        target_volume=target,
    )
    # プロペラ（船尾形状をプロペラ位置に合わせる）
    for pr in cfg.get("actuators", {}).get("propellers", []):
        x, y, z = (float(v) for v in pr.get("shaft_pos_m", [0.0, -0.45 * Lpp, -0.6 * d]))
        p.props.append((y, z, float(pr.get("diameter_m", 0.35 * d))))
    if p.props:
        # カウンター（トランサム下端）はプロペラ円の上端より 12 % D 上。竜骨線はプロペラ前縁の手前で上がり切る
        tops = [z + 0.5 * dia for _, z, dia in p.props]
        dia = max(dia for _, _, dia in p.props)
        p.transom_z = min(-0.02 * d, max(tops) + 0.12 * dia)
        y_front = max(y for y, _, _ in p.props) + 0.45 * dia
        p.counter_u = max(-0.97, min(-0.6, y_front / stern_x(p)))
    else:
        p.transom_z = -0.15 * d
        p.counter_u = -0.9
    p.run_start_u = min(p.counter_u + 0.3, -0.35)
    solve_fullness(p)
    return p


# --- 基本形状 ------------------------------------------------------------------

def stern_x(p: HullParams) -> float:
    return p.Lpp / 2.0 + p.stern_overhang


def bow_x(p: HullParams, z: float) -> float:
    """高さ z での船首材の前後位置（FP からのレーキ・フォアフット）"""
    if z >= 0.0:
        return p.Lpp / 2.0 + p.bow_rake * min(1.0, z / max(0.1, p.freeboard + p.sheer_fore)) ** 0.9
    return p.Lpp / 2.0 - p.forefoot * min(1.0, -z / p.d) ** 2


def x_of(p: HullParams, u: float, z: float) -> float:
    return u * bow_x(p, z) if u >= 0.0 else u * stern_x(p)


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def keel_z(p: HullParams, u: float) -> float:
    """船体中心線の船底高さ（負）。船尾はカウンターへ切り上がる"""
    if u >= p.run_start_u:
        return -p.d
    t = (p.run_start_u - u) / max(1e-6, p.run_start_u - p.counter_u)
    return -p.d + (p.d + p.transom_z) * _smoothstep(t)


def deck_z(p: HullParams, u: float) -> float:
    return p.freeboard + (p.sheer_fore if u > 0.0 else p.sheer_aft) * u * u


def b_wl(p: HullParams, u: float) -> float:
    """水線半幅"""
    return b_wl_s(p, u, p.fullness)


def b_wl_s(p: HullParams, u: float, s: float) -> float:
    if u >= 0.0:
        e = max(1.0, (2.0 + 4.0 * p.Cb) * s)
        return 0.5 * p.B * max(0.0, 1.0 - u ** e) ** 0.5
    # 没水部のトランサム幅は肥えた船ほど広い（痩せた船は船尾の水線が細る）
    tw = p.transom_width_ratio * max(0.3, min(1.0, p.Cb / 0.65) ** 2)
    e = max(1.0, 2.5 * s)
    return 0.5 * p.B * (tw + (1.0 - tw) * (1.0 - (-u) ** e))


def b_deck(p: HullParams, u: float) -> float:
    """甲板半幅（水線より肥えている → 船首フレア）"""
    if u >= 0.0:
        e = 1.6 * (2.0 + 4.0 * p.Cb)
        return 0.5 * p.B * max(0.0, 1.0 - u ** e) ** 0.5
    tw = min(0.98, p.transom_width_ratio + 0.08)
    return 0.5 * p.B * (tw + (1.0 - tw) * (1.0 - (-u) ** 3.0))


def midship_coefficient(Cb: float) -> float:
    return 0.70 + (0.985 - 0.70) * max(0.0, min(1.0, (Cb - 0.42) / 0.18))


def superellipse_fill(n: float) -> float:
    """四分円型超楕円の面積 / (b T)"""
    return math.gamma(1.0 + 1.0 / n) ** 2 / math.gamma(1.0 + 2.0 / n)


def n_for_fill(c: float) -> float:
    lo, hi = 1.01, 200.0
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if superellipse_fill(mid) < c:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def section_n(p: HullParams, u: float, s: float = None) -> float:
    """断面の超楕円指数。船体中央 n_mid から船首尾の n_end（V 形）へ"""
    s = p.fullness if s is None else s
    w = 1.0 - abs(u) ** max(0.3, 3.0 * s)
    return p.n_end + (p.n_mid - p.n_end) * w


def section_half(p: HullParams, u: float, n_below: int = 14, n_above: int = 5,
                 s: float = None) -> List[Tuple[float, float]]:
    """断面の半分（右舷側）を竜骨中心 (0, z_keel) から甲板端 (b_deck, z_deck) まで"""
    T = -keel_z(p, u)
    b = b_wl_s(p, u, p.fullness if s is None else s)
    n = section_n(p, u, s)
    pts = []
    for k in range(n_below + 1):
        phi = (math.pi / 2.0) * (1.0 - k / n_below)      # π/2: 竜骨, 0: 水線
        c, s = math.cos(phi), math.sin(phi)
        y = b * (c ** (2.0 / n) if c > 0 else 0.0)
        z = -T * (s ** (2.0 / n) if s > 0 else 0.0)
        pts.append((y, z))
    zd = deck_z(p, u)
    bd = b_deck(p, u)
    for k in range(1, n_above + 1):
        t = k / n_above
        pts.append((b + (bd - b) * t ** 1.5, zd * t))
    return pts


def section_area_below(p: HullParams, u: float, s: float = None) -> float:
    pts = [pt for pt in section_half(p, u, 24, 1, s) if pt[1] <= 1e-9]
    area = 0.0
    for (y0, z0), (y1, z1) in zip(pts[:-1], pts[1:]):
        area += 0.5 * (y0 + y1) * (z1 - z0)
    return 2.0 * area


def underwater_volume(p: HullParams, s: float = None, n_u: int = 200) -> float:
    vol = 0.0
    for i in range(n_u):
        u0 = -1.0 + 2.0 * i / n_u
        u1 = -1.0 + 2.0 * (i + 1) / n_u
        um = 0.5 * (u0 + u1)
        zm = 0.5 * keel_z(p, um)
        dx = x_of(p, u1, zm) - x_of(p, u0, zm)
        vol += section_area_below(p, um, s) * dx
    return vol


def solve_fullness(p: HullParams) -> None:
    """船体中央断面を C_m から決め、水線下の体積が排水容積になる肥瘠度 s を二分法で決める（0.1〜20）"""
    p.n_mid = n_for_fill(midship_coefficient(p.Cb))
    p.n_end = min(p.n_mid, 1.4)
    lo, hi = 0.1, 20.0
    if underwater_volume(p, hi) < p.target_volume:
        p.fullness = hi
        return
    if underwater_volume(p, lo) > p.target_volume:
        p.fullness = lo
        return
    for _ in range(40):
        mid = math.sqrt(lo * hi)
        if underwater_volume(p, mid) < p.target_volume:
            lo = mid
        else:
            hi = mid
    p.fullness = math.sqrt(lo * hi)


def stations(n: int = 41) -> List[float]:
    """船首尾で細かい u の列（-1..1）"""
    return [math.sin(0.5 * math.pi * (-1.0 + 2.0 * i / (n - 1))) for i in range(n)]


def rings(p: HullParams, n_stations: int = 41, n_below: int = 14, n_above: int = 5) -> List[List[Point3]]:
    """断面リング（左舷甲板端 → 竜骨 → 右舷甲板端）の列。船首端のリングは幅 0 に潰れる"""
    out = []
    for u in stations(n_stations):
        half = section_half(p, u, n_below, n_above)
        port = [(-y, x_of(p, u, z), z) for y, z in reversed(half[1:])]
        keel = [(0.0, x_of(p, u, half[0][1]), half[0][1])]
        stbd = [(y, x_of(p, u, z), z) for y, z in half[1:]]
        out.append(port + keel + stbd)
    return out


def hull_bottom_z_at(p: HullParams, y_long: float, x_lat: float) -> float:
    """前後位置 y_long・横位置 x_lat での船底の高さ（プロペラ・舵との干渉確認用。断面の外なら +inf）"""
    u = y_long / stern_x(p) if y_long < 0 else y_long / bow_x(p, -0.5 * p.d)
    u = max(-1.0, min(1.0, u))
    half = section_half(p, u, 48, 1)
    below = [pt for pt in half if pt[1] <= 0.0]
    ax = abs(x_lat)
    if ax > below[-1][0]:
        return math.inf
    for (y0, z0), (y1, z1) in zip(below[:-1], below[1:]):
        if y0 <= ax <= y1 and y1 > y0:
            return z0 + (z1 - z0) * (ax - y0) / (y1 - y0)
    return below[0][1]
