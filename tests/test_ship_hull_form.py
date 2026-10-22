"""test_ship_hull_form.py - 船体形状（blender/ship_model/hull_form.py）の検証。Blender 不要。

見た目の船体が物理モデルと矛盾しないこと（排水容積・主要目・プロペラの収まり）を確認する。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "blender" / "ship_model"))
import hull_form as hf  # noqa: E402

SHIPS = ["container_749gt", "container_700teu", "ferry_seto", "fishing_boat"]


def load(subject: str) -> dict:
    with (REPO / "output" / subject / "resolved_config.json").open(encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("subject", SHIPS)
def test_underwater_volume_matches_displacement(subject):
    p = hf.params_from_cfg(load(subject))
    vol = hf.underwater_volume(p)
    # 小型漁船は肥瘠度の下限に当たるため 2 % まで許容（他は二分法で一致）
    assert abs(vol / p.target_volume - 1.0) < 0.02, f"{subject}: {vol:.1f} m^3 vs {p.target_volume:.1f} m^3"


@pytest.mark.parametrize("subject", SHIPS)
def test_principal_dimensions(subject):
    cfg = load(subject)
    dim = cfg["dimensions"]
    p = hf.params_from_cfg(cfg)
    pts = [pt for ring in hf.rings(p) for pt in ring]
    xs = [pt[1] for pt in pts]
    assert abs((max(xs) - min(xs)) / float(dim["length_oa_m"]) - 1.0) < 0.01, "LOA"
    half_b = max(hf.b_wl(p, u) for u in hf.stations(81))
    assert 0.98 * p.B / 2 <= half_b <= p.B / 2 + 1e-9, "waterline beam"
    assert max(abs(pt[0]) for pt in pts) <= p.B / 2 + 1e-9, "no point outside the beam"
    assert hf.keel_z(p, 0.0) == pytest.approx(-p.d), "keel at design draft amidships"
    assert hf.deck_z(p, 0.0) == pytest.approx(p.D - p.d), "deck at depth amidships"


@pytest.mark.parametrize("subject", SHIPS)
def test_propellers_fit_under_the_counter(subject):
    cfg = load(subject)
    p = hf.params_from_cfg(cfg)
    for pr in cfg["actuators"]["propellers"]:
        x, y, z = pr["shaft_pos_m"]
        dia = float(pr["diameter_m"])
        bottom = hf.hull_bottom_z_at(p, y, x)
        assert bottom - (z + dia / 2) > 0.05 * dia, f"{pr['id']}: hull bottom {bottom:.2f} m vs blade tip {z + dia / 2:.2f} m"


def test_sections_are_fuller_amidships_than_at_the_ends():
    p = hf.params_from_cfg(load("container_749gt"))
    assert hf.midship_coefficient(p.Cb) > 0.98
    assert hf.section_n(p, 0.0) > 3 * hf.section_n(p, 0.9)
