"""test_nc_machine_templates.py - 加工機テンプレートの継承・形の計算・MJCF・QA の回帰試験（Blender 不要）。"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "nc_machine"))

import forge_nc_machine as forge  # noqa: E402
import nc_geometry as ncg  # noqa: E402
import qa_nc  # noqa: E402

TEMPLATES = forge.list_templates()


def resolved(tid):
    return forge.resolve_yaml(forge.TEMPLATES_DIR / f"{tid}.yaml")


def test_templates_found():
    assert {"turning_h_k1", "turning_h_k2", "turning_h_k2s", "cart_large", "cart_mobile", "pallet_M",
            "pallet_L"} <= set(TEMPLATES)
    assert "turning_h_base" not in TEMPLATES


def test_inheritance_k2_overrides_and_keeps_base():
    k2 = resolved("turning_h_k2")
    assert k2["template_id"] == "turning_h_k2"
    assert k2["envelope"]["width_m"] == 4.175        # 公開仕様の外形
    assert k2["envelope"]["wall_m"] == 0.04          # 基礎テンプレートの値が残る
    assert [s["id"] for s in k2["spindles"]] == ["spindle1"]
    assert k2["tailstock"]["thrust_n"] == 10000
    assert "template_file" not in k2


def test_k2_has_tailstock_and_k2s_has_second_spindle():
    names = [b["name"] for b in ncg.describe(resolved("turning_h_k2"))["bodies"]]
    assert "tailstock" in names and "spindle2" not in names
    k2s = resolved("turning_h_k2s")                  # 2 段の継承（k2s → k2 → base）
    assert k2s["envelope"]["width_m"] == 4.175 and k2s["tailstock"] is None
    names = [b["name"] for b in ncg.describe(k2s)["bodies"]]
    assert {"spindle1", "spindle2"} <= set(names) and "tailstock" not in names


def test_mobile_cart_drops_front_anchor():
    iface = ncg.describe(resolved("cart_mobile"))["interface"]
    assert set(iface["pallet_anchors"]) == {"left", "right"}
    assert iface["footprint_m"] == [0.810, 1.345]


def test_k1_geometry():
    desc = ncg.describe(resolved("turning_h_k1"))
    names = [b["name"] for b in desc["bodies"]]
    assert names[0] == "machine_root"
    assert {"door", "spindle1", "headstock_spindle1", "turret"} <= set(names)
    jaws = [b for b in desc["bodies"] if b["parent"] == "spindle1" and "_jaw" in b["name"]]
    assert len(jaws) == 3
    load = desc["interface"]["spindles"]["spindle1"]["load_m"]
    assert load == pytest.approx([-0.19, 0.50, 1.10])


def test_jaws_are_on_chuck_face_and_symmetric():
    """爪は主軸の子のボディ。面から +X に半分だけ出て、内面の半径＝生爪の径/2＋すき間で 120° おき。"""
    cfg = resolved("turning_h_k1")
    jaw = cfg["spindles"][0]["chuck"]["jaw"]
    desc = ncg.describe(cfg)
    jaws = [b for b in desc["bodies"] if b["parent"] == "spindle1" and "_jaw" in b["name"]]
    for b in jaws:
        g = b["geoms"][0]
        assert b["pos"][0] == pytest.approx(g["size"][0])
        inner = (b["pos"][1] ** 2 + b["pos"][2] ** 2) ** 0.5 - g["size"][1]
        assert inner == pytest.approx(jaw["grip_dia_m"] / 2 + jaw["open_clearance_m"])


def test_lod1_joints_actuators_and_plant_interface():
    """N2：LOD1 は扉・主軸・爪・心押台に関節とアクチュエータを持ち、プラント用の名前一覧を出す。"""
    cfg = resolved("turning_h_k2")
    assert cfg["lod"] == 1
    desc = ncg.describe(cfg)
    joints = {b["joint"]["name"]: b["joint"] for b in desc["bodies"] if b["joint"]}
    assert set(joints) == {"door", "spindle1", "spindle1_jaw1", "spindle1_jaw2", "spindle1_jaw3", "tailstock"}
    stroke_r = cfg["spindles"][0]["chuck"]["stroke_dia_m"] / 2
    assert joints["spindle1_jaw1"]["range"] == pytest.approx([-stroke_r, 0.0])
    assert joints["door"]["range"] == pytest.approx([0.0, cfg["door"]["stroke_m"]])
    acts = {a["name"]: a for a in desc["actuators"]}
    assert acts["spindle1_vel"]["kind"] == "velocity" and acts["door_act"]["kind"] == "position"
    assert acts["spindle1_jaw1_act"]["forcerange"][1] == pytest.approx(cfg["spindles"][0]["chuck"]["force_n"] / 3)
    pl = desc["plant"]
    assert pl["door"]["open_q"] == cfg["door"]["stroke_m"] and pl["door"]["time_s"] == cfg["door"]["time_s"]
    sp = pl["spindles"][0]
    assert sp["grip_dia_m"] == pytest.approx(0.200) and len(sp["jaws"]) == 3 and sp["close_q"] == -stroke_r
    assert pl["tailstock"]["travel_m"] == cfg["tailstock"]["travel_m"]
    # LOD0 にすると関節・アクチュエータ・プラント情報は無い（扉は開いた位置）
    cfg0 = dict(cfg, lod=0)
    d0 = ncg.describe(cfg0)
    assert not [b for b in d0["bodies"] if b["joint"]] and not d0["actuators"] and d0["plant"] is None


def test_mujoco_lod1_is_stable_and_moves(tmp_path):
    mujoco = pytest.importorskip("mujoco")
    import numpy as np
    forge.forge("turning_h_k2", skip_blender=True, out_root=tmp_path)
    m = mujoco.MjModel.from_xml_path(str(tmp_path / "turning_h_k2" / "turning_h_k2.xml"))
    d = mujoco.MjData(m)
    for _ in range(2000):                      # 指令なしで 2 s：その場にとどまる
        mujoco.mj_step(m, d)
    assert np.max(np.abs(d.qpos)) < 1e-4
    jaw = m.actuator("spindle1_jaw1_act").id
    d.ctrl[jaw] = m.actuator_ctrlrange[jaw, 0]
    d.ctrl[m.actuator("door_act").id] = m.actuator_ctrlrange[m.actuator("door_act").id, 1]
    for _ in range(2000):
        mujoco.mj_step(m, d)
    assert d.qpos[m.jnt_qposadr[m.joint("spindle1_jaw1").id]] < 0.9 * m.actuator_ctrlrange[jaw, 0]
    assert d.qpos[m.jnt_qposadr[m.joint("door").id]] > 0.95 * m.jnt_range[m.joint("door").id, 1]


def test_pallet_slots():
    desc = ncg.describe(resolved("pallet_M"))
    slots = desc["interface"]["slots"]
    assert len(slots) == 20
    assert all(abs(s["pos_m"][0]) < 0.42 and abs(s["pos_m"][1]) < 0.37 for s in slots)
    assert len(ncg.describe(resolved("pallet_L"))["interface"]["slots"]) == 12


def test_bad_opening_is_rejected():
    cfg = resolved("turning_h_k1")
    cfg["door"]["opening_w_m"] = 5.0
    with pytest.raises(ValueError):
        ncg.describe(cfg)


@pytest.mark.parametrize("tid", TEMPLATES)
def test_build_without_blender_passes_qa(tid, tmp_path):
    r = forge.forge(tid, skip_blender=True, out_root=tmp_path)
    assert r["passed"], (tmp_path / tid / "qa_report.json").read_text(encoding="utf-8")
    root = ET.parse(tmp_path / tid / f"{tid}.xml").getroot()
    assert root.tag == "mujoco" and root.get("model") == tid
    assert (tmp_path / tid / "BUILD_REPORT.md").is_file()


def test_qa_detects_door_blocking_opening(tmp_path):
    cfg = resolved("turning_h_k1")
    cfg["door"]["stroke_m"] = 0.5
    out = tmp_path / "k1"
    out.mkdir()
    rep = qa_nc.run_qa(cfg, out)
    assert not rep["passed"]
    assert [c for c in rep["checks"] if c["id"] == "QA-4"][0]["result"] == "fail"


def test_mujoco_loads_if_available(tmp_path):
    mujoco = pytest.importorskip("mujoco")
    forge.forge("turning_h_k1", skip_blender=True, out_root=tmp_path)
    m = mujoco.MjModel.from_xml_path(str(tmp_path / "turning_h_k1" / "turning_h_k1.xml"))
    assert m.nbody >= 6
