"""test_templates.py - 船舶YAMLテンプレートの継承解決およびバリデーションテスト。"""
from __future__ import annotations

import copy
from pathlib import Path
import pytest
import yaml

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "config" / "ship_templates"


def resolve_template(yaml_path: Path) -> dict:
    """template_file が指定されていれば親テンプレートを再帰的にマージして解決する。"""
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if "template_file" in data:
        parent_path = yaml_path.parent / data["template_file"]
        parent_data = resolve_template(parent_path)
        # 再帰的ディープマージ
        merged = copy.deepcopy(parent_data)
        _deep_merge(merged, data)
        return merged
    return data


def _deep_merge(base: dict, update: dict) -> None:
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_merge(base[k], v)
        else:
            base[k] = copy.deepcopy(v)


def test_base_template_exists():
    base_file = TEMPLATES_DIR / "vessel_base.yaml"
    assert base_file.exists()
    data = yaml.safe_load(base_file.read_text(encoding="utf-8"))
    assert data["template_id"] == "vessel_base"
    assert data["vehicle_type"] == "vessel"
    assert data["coordinate_system"]["front_axis"] == "+Y"
    assert data["coordinate_system"]["right_axis"] == "+X"
    assert data["coordinate_system"]["up_axis"] == "+Z"


@pytest.mark.parametrize("ship_file, expected_id, expected_lpp, expected_beam, expected_ais", [
    ("container_749gt.yaml", "container_749gt", 90.0, 14.0, True),
    ("container_700teu.yaml", "container_700teu", 124.0, 21.0, True),
    ("ferry_seto.yaml", "ferry_seto", 60.0, 14.0, True),
    ("fishing_boat.yaml", "fishing_boat", 10.5, 3.2, False),
])
def test_ship_templates_resolution(ship_file, expected_id, expected_lpp, expected_beam, expected_ais):
    p = TEMPLATES_DIR / ship_file
    assert p.exists()
    resolved = resolve_template(p)

    assert resolved["template_id"] == expected_id
    assert resolved["vehicle_type"] == "vessel"

    # 主要目の確認
    dim = resolved["dimensions"]
    assert dim["length_pp_m"] == expected_lpp
    assert dim["beam_m"] == expected_beam
    assert dim["draft_m"] > 0
    assert dim["block_coefficient"] > 0

    # 署名・AIS属性の確認
    sig = resolved["signatures"]
    assert sig["has_ais"] == expected_ais
    assert sig["radar_cross_section_m2"] > 0

    # アクチュエータの確認
    act = resolved["actuators"]
    assert len(act["propellers"]) >= 1
    assert len(act["rudders"]) >= 1

    # 40点浮力計算サイト設定の継承確認
    assert resolved["buoyancy"]["total_sites"] == 40
    assert resolved["buoyancy"]["stations_count"] == 20

    # 航海灯設定の確認
    assert len(resolved["nav_lights"]) >= 4
