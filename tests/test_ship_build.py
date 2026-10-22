"""test_ship_build.py - 生成された船舶モデル、MJCF、MMGパラメータ、レンダリング画像の自動検証テスト。"""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

VESSEL_CASES = [
    ("container_749gt", 2500.0, True, 90.0, 14.0),
    ("container_700teu", 8000.0, True, 124.0, 21.0),
    ("ferry_seto", 1200.0, True, 60.0, 14.0),
    ("fishing_boat", 5.0, False, 10.5, 3.2),
]


@pytest.mark.parametrize("subject, expected_rcs, has_ais, expected_lpp, expected_beam", VESSEL_CASES)
def test_vessel_deliverables_exist(subject, expected_rcs, has_ais, expected_lpp, expected_beam):
    vessel_dir = OUTPUT_DIR / subject
    assert vessel_dir.is_dir(), f"Vessel directory not found: {vessel_dir}"

    # 1. Blender .blend と glTF .glb の確認
    blend_path = vessel_dir / f"{subject}.blend"
    glb_path = vessel_dir / f"{subject}.glb"
    assert blend_path.is_file(), f".blend file missing: {blend_path}"
    assert glb_path.is_file(), f".glb file missing: {glb_path}"
    assert blend_path.stat().st_size > 50_000, ".blend file size too small"
    assert glb_path.stat().st_size > 30_000, ".glb file size too small"

    # 2. MJCF XML の検証
    mjcf_path = vessel_dir / f"{subject}.xml"
    assert mjcf_path.is_file(), f"MJCF XML missing: {mjcf_path}"
    tree = ET.parse(mjcf_path)
    root = tree.getroot()
    assert root.tag == "mujoco"
    assert root.attrib.get("model") == subject

    # vessel ボディと freejoint
    worldbody = root.find("worldbody")
    assert worldbody is not None
    vessel_body = worldbody.find("./body[@name='vessel']")
    assert vessel_body is not None
    freejoint = vessel_body.find("./freejoint[@name='vessel_free']")
    assert freejoint is not None

    # 40点浮力計算サイト (buoyancy_st00_port .. buoyancy_st19_stbd)
    buoy_sites = vessel_body.findall("./site[@class='buoyancy_site']")
    assert len(buoy_sites) == 40, f"Expected 40 buoyancy sites, got {len(buoy_sites)}"

    # 船体コライダと RCS 属性 (geom user属性)
    main_geom = vessel_body.find("./geom[@name='geom_hull_main']")
    assert main_geom is not None
    assert "user" in main_geom.attrib, "RCS user attribute missing in geom"
    user_rcs = float(main_geom.attrib["user"])
    assert user_rcs > 0.0

    # センサマウントサイト
    mount_sites = vessel_body.findall("./site[@class='mount_site']")
    assert len(mount_sites) >= 2

    # 航海灯サイト
    light_sites = vessel_body.findall("./site[@class='light_site']")
    assert len(light_sites) >= 4

    # 3. hydro_mmg.json の検証
    hydro_path = vessel_dir / "hydro_mmg.json"
    assert hydro_path.is_file(), f"hydro_mmg.json missing: {hydro_path}"
    with hydro_path.open("r", encoding="utf-8") as f:
        hydro = json.load(f)
    assert hydro["dimensions"]["length_pp_m"] == expected_lpp
    assert hydro["dimensions"]["beam_m"] == expected_beam
    assert hydro["mass_and_inertia"]["mass_kg"] > 0
    assert hydro["mass_and_inertia"]["Izz_kgm2"] > 0
    assert hydro["hull_derivatives_prime"]["Y_v"] < 0
    assert hydro["hull_derivatives_prime"]["N_r"] < 0

    # 4. ship_sync.profile.json の検証
    prof_path = vessel_dir / "ship_sync.profile.json"
    assert prof_path.is_file(), f"ship_sync.profile.json missing: {prof_path}"
    with prof_path.open("r", encoding="utf-8") as f:
        prof = json.load(f)
    assert prof["robot_name"] == subject
    assert len(prof["joints"]) >= 2

    # 5. レンダリング画像の確認
    renders_dir = vessel_dir / "renders"
    assert renders_dir.is_dir()
    for view in ["front", "back", "port", "starboard", "top", "iso"]:
        img_path = renders_dir / f"{view}.png"
        assert img_path.is_file(), f"Render image missing: {img_path}"
        assert img_path.stat().st_size > 10_000, f"Render image size too small: {img_path}"


@pytest.mark.parametrize("subject, expected_rcs, has_ais, expected_lpp, expected_beam", VESSEL_CASES)
def test_visual_model_stays_within_the_ship(subject, expected_rcs, has_ais, expected_lpp, expected_beam):
    """見た目のモデルが主要目の範囲に収まり（船外に浮いた部品が無い）、水線下の体積が排水容積に一致する"""
    with (OUTPUT_DIR / subject / "build_report.json").open(encoding="utf-8") as f:
        report = json.load(f)
    with (OUTPUT_DIR / subject / "resolved_config.json").open(encoding="utf-8") as f:
        dim = json.load(f)["dimensions"]
    lo, hi = report["visual_bounds_m"]["min"], report["visual_bounds_m"]["max"]
    loa = float(dim["length_oa_m"])
    # 前後: 全長＋バルバスバウの突出（全長の 3 % まで）
    assert hi[1] - lo[1] <= loa * 1.03, f"length {hi[1] - lo[1]:.1f} m vs LOA {loa} m"
    # 左右: 船橋翼・救命艇の張り出しを 1 m まで許容
    assert max(abs(lo[0]), abs(hi[0])) <= expected_beam / 2 + 1.0
    # 上下: 竜骨（喫水）より下は舵の下端程度まで（漁船のテンプレートの舵は基線より 0.14 m 下に出る）
    assert lo[2] >= -1.15 * float(dim["draft_m"])
    hull = report["hull_form"]
    assert abs(hull["underwater_volume_m3"] / hull["target_volume_m3"] - 1.0) < 0.02
