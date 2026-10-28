"""qa_nc.py - 加工機・台車・パレットの生成物の機械ゲート（devai_automation/02 §2.9.4 の QA-1〜6）。

形の検査は nc_geometry の結果で行い、生成物（MJCF・GLB）には必須ノードの有無だけを確かめる。
GLB が無い（Blender を使わずに生成した）ときは GLB の検査を「skip」にする。
"""
from __future__ import annotations

import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

import nc_geometry as ncg

TOL_DIM = 0.001


def glb_node_names(path: Path) -> List[str]:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise ValueError(f"GLB ではない: {path}")
    length, ctype = struct.unpack_from("<I4s", data, 12)
    if ctype != b"JSON":
        raise ValueError("GLB の先頭チャンクが JSON でない")
    gltf = json.loads(data[20:20 + length].decode("utf-8"))
    return [n.get("name", "") for n in gltf.get("nodes", [])]


def mjcf_names(path: Path) -> Dict[str, List[str]]:
    root = ET.parse(path).getroot()
    return {tag: [e.get("name") for e in root.iter(tag)] for tag in ("body", "geom", "site", "joint")}


def bounds(geoms: List[Dict[str, Any]]):
    lo, hi = [1e9] * 3, [-1e9] * 3
    for g in geoms:
        if g["type"] == "box" and g["quat"] == ncg.Q_ID:
            ext = g["size"]
        else:
            r = max(g["size"])
            ext = [r, r, r]
        for i in range(3):
            lo[i] = min(lo[i], g["pos"][i] - ext[i])
            hi[i] = max(hi[i], g["pos"][i] + ext[i])
    return lo, hi


def check(cid: str, title: str, ok: Optional[bool], detail: str) -> Dict[str, Any]:
    return {"id": cid, "title": title, "result": "skip" if ok is None else ("pass" if ok else "fail"), "detail": detail}


def required_nodes(desc: Dict[str, Any]) -> List[str]:
    return [bd["name"] for bd in desc["bodies"]]


def qa_machine(cfg, desc, geoms) -> List[Dict[str, Any]]:
    out = []
    b = ncg.machine_bounds(cfg)
    body = [g for g in geoms if g["collide"] and g["body"] == "machine_root"]
    lo, hi = bounds(body)
    env = cfg["envelope"]
    got = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]]
    want = [env["width_m"], env["depth_m"], env["height_m"]]
    out.append(check("QA-1", "外形寸法がテンプレートと一致", all(abs(a - c) <= TOL_DIM for a, c in zip(got, want)),
                     f"生成 {got} / テンプレート {want} [m]"))

    door = cfg["door"]
    ow = door["opening_w_m"]
    dg = [g for g in geoms if g["name"] == "door_panel"][0]
    dlo, dhi = dg["pos"][0] - dg["size"][0], dg["pos"][0] + dg["size"][0]
    if cfg.get("lod", 0) == 0:
        clear = dlo >= ow / 2 if dg["pos"][0] > 0 else dhi <= -ow / 2
        out.append(check("QA-4", "扉を全開にしたとき開口をふさがない", clear,
                         f"扉 X {dlo:.3f}〜{dhi:.3f} / 開口 X ±{ow / 2:.3f} [m]"))

    jaws = [g for g in geoms if "_jaw" in g["name"]]
    min_d = 1e9
    for i in range(len(jaws)):
        for j in range(i + 1, len(jaws)):
            if jaws[i]["body"] != jaws[j]["body"]:
                continue
            d = sum((a - c) ** 2 for a, c in zip(jaws[i]["pos"], jaws[j]["pos"])) ** 0.5
            min_d = min(min_d, d - (jaws[i]["size"][2] + jaws[j]["size"][2]) - (jaws[i]["size"][1] + jaws[j]["size"][1]))
    out.append(check("QA-5", "チャックの爪どうしが重ならない", min_d > 0.0, f"爪の最小すき間（概算）{min_d:.4f} m"))

    t = b["t"]
    wz = cfg["work_zone_m"]
    inside = (b["xmin"] + t <= wz["min"][0] and wz["max"][0] <= b["xmax"] - t and t <= wz["min"][1]
              and wz["max"][1] <= b["ymax"] - t and b["bed_top"] <= wz["min"][2] and wz["max"][2] <= b["zmax"] - t)
    ri = cfg["robot_interface"]
    ap, dp = ri["approach_m"], ri["door_pass_m"]
    sill, oh = door["sill_h_m"], door["opening_h_m"]
    in_open = lambda p: -ow / 2 < p[0] < ow / 2 and sill < p[2] < sill + oh  # noqa: E731
    ok6 = inside and ap[1] < 0 and in_open(ap) and dp[1] > t and in_open(dp)
    marks_ok = all(m["pos_m"][1] <= 0.0 and not in_open(m["pos_m"]) for m in cfg.get("markers", []))
    out.append(check("QA-6", "work_zone・進入点・マークの位置が正しい側にある", ok6 and marks_ok,
                     f"work_zone 機内={inside}, approach 機外かつ開口内={ap[1] < 0 and in_open(ap)}, "
                     f"door_pass 機内かつ開口内={dp[1] > t and in_open(dp)}, マーク前面かつ開口外={marks_ok}"))
    return out


def qa_cart(cfg, desc, geoms) -> List[Dict[str, Any]]:
    c = cfg["cart"]
    lo, hi = bounds([g for g in geoms if g["collide"]])
    got = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]]
    want = [c["width_m"], c["depth_m"], c["height_m"]]
    out = [check("QA-1", "外形寸法がテンプレートと一致", all(abs(a - b) <= TOL_DIM for a, b in zip(got, want)),
                 f"生成 {got} / テンプレート {want} [m]")]
    m = c["robot_mount_m"]
    out.append(check("QA-6", "ロボットの取り付け点が天板の上にある",
                     abs(m[2] - c["height_m"]) <= TOL_DIM and abs(m[0]) < c["width_m"] / 2 and abs(m[1]) < c["depth_m"] / 2,
                     f"robot_mount {m}"))
    return out


def qa_pallet(cfg, desc, geoms) -> List[Dict[str, Any]]:
    p = cfg["pallet"]
    lo, hi = bounds([g for g in geoms if g["collide"]])
    got = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]]
    want = [p["width_m"], p["depth_m"], p["stand_h_m"]]
    out = [check("QA-1", "外形寸法がテンプレートと一致", all(abs(a - b) <= TOL_DIM for a, b in zip(got, want)),
                 f"生成 {got} / テンプレート {want} [m]")]
    n = len(desc["interface"]["slots"])
    want_n = int(p["grid"][0]) * int(p["grid"][1])
    out.append(check("QA-6", "スロットの数がテンプレートと一致し、高さ 500mm 以下", n == want_n and p["stand_h_m"] <= 0.5,
                     f"スロット {n}/{want_n}、高さ {p['stand_h_m']} m"))
    return out


def run_qa(cfg: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    desc = ncg.describe(cfg)
    geoms = ncg.world_geoms(desc)
    subject = desc["template_id"]
    kind = desc["kind"]
    checks = {"machine": qa_machine, "cart": qa_cart, "pallet": qa_pallet}[kind](cfg, desc, geoms)

    need = required_nodes(desc)
    mjcf = out_dir / f"{subject}.xml"
    names = mjcf_names(mjcf) if mjcf.is_file() else {"body": []}
    miss_mjcf = [n for n in need if n not in names["body"]]
    glb = out_dir / f"{subject}.glb"
    if glb.is_file():
        nodes = glb_node_names(glb)
        miss_glb = [n for n in need if n not in nodes]
        out2 = check("QA-2", "必須ノードが MJCF と GLB の両方にある", not miss_mjcf and not miss_glb,
                     f"MJCF の欠け {miss_mjcf}、GLB の欠け {miss_glb}")
    else:
        out2 = check("QA-2", "必須ノードが MJCF にある（GLB なし）", not miss_mjcf, f"MJCF の欠け {miss_mjcf}（GLB 未生成）")
    checks.insert(1, out2)

    joints = [bd["joint"] for bd in desc["bodies"] if bd["joint"]]
    if cfg.get("lod", 0) == 0 or not joints:
        checks.insert(2, check("QA-3", "関節の範囲・軸がテンプレートと一致", None, "LOD0（関節なし）"))
    else:
        got_j = names.get("joint", [])
        checks.insert(2, check("QA-3", "関節の範囲・軸がテンプレートと一致",
                               all(j["name"] in got_j for j in joints), f"関節 {[j['name'] for j in joints]}"))

    passed = all(c["result"] != "fail" for c in checks)
    report = {"subject": subject, "kind": kind, "lod": cfg.get("lod", 0), "passed": passed,
              "glb": glb.is_file(), "checks": checks}
    (out_dir / "qa_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
