"""qa_camera.py - 生成したカメラの USD を検査する（pxr が要る。Blender 同梱の Python か Isaac Sim の Python で動かす）。

    blender --background --factory-startup --python scripts/camera_model/qa_camera.py -- \
        --config-json output/camera_model/irvision_2d/resolved_config.json

検査（すべて resolved_config.json の値＝センサーの設定 JSON と比べる）:
    Q1 ステージ: Z 上・1 m・defaultPrim
    Q2 見た目の外形: 本体の箱の大きさ（80 × 74 × 131.8 mm）と位置（前面 = 原点、後ろへ伸びる）、±0.5 mm
    Q3 衝突の箱: 外形と同じ大きさ・位置、質量 0.6 kg
    Q4 カメラの向き: 見る向き = +x、画像の上 = +z、画像の右 = -y（光学中心 = 原点）
    Q5 カメラの光学: 焦点距離・撮像の大きさ・横と縦の画角がセンサーの設定と一致
    Q6 LED: 色・光る向き（+x）・円錐の角度（LED ありの場合）
    Q7 照明: LED 以外の光源が無い（Blender の背景が DomeLight として紛れ込まない）
結果: qa_report.json（同じフォルダ）。終了コード 0 = 全合格。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from pxr import Gf, Usd, UsdGeom, UsdLux, UsdPhysics

TOL_M = 0.0005


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser(prog="qa_camera.py")
    p.add_argument("--config-json", required=True)
    p.add_argument("--usd", help="検査する USD（既定は <id>.usda）")
    return p.parse_args(argv)


def _dir(xf: Gf.Matrix4d, v) -> Gf.Vec3d:
    return xf.TransformDir(Gf.Vec3d(*v)).GetNormalized()


def _close_vec(a, b, tol) -> bool:
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def run(cfg: dict, usd_path: Path) -> dict:
    checks = []

    def check(cid: str, name: str, ok: bool, got, want) -> None:
        checks.append({"id": cid, "name": name, "ok": bool(ok), "got": got, "want": want})

    stage = Usd.Stage.Open(str(usd_path))
    root_name = cfg["root_prim"]
    root = stage.GetPrimAtPath(f"/{root_name}")
    check("Q1", "up axis Z", UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z, UsdGeom.GetStageUpAxis(stage), "Z")
    check("Q1", "meters per unit 1.0", UsdGeom.GetStageMetersPerUnit(stage) == 1.0,
          UsdGeom.GetStageMetersPerUnit(stage), 1.0)
    check("Q1", "defaultPrim", stage.GetDefaultPrim() == root, str(stage.GetDefaultPrim().GetPath()), f"/{root_name}")

    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
    h = cfg["housing_mm"]
    L, W, H = h["length"] / 1000, h["width"] / 1000, h["height"] / 1000
    env = cfg["envelope_body"]
    vis = cache.ComputeWorldBound(stage.GetPrimAtPath(f"/{root_name}/Visual")).ComputeAlignedRange()
    # 銘板・コネクタは外へ出るので、本体の外形は envelope_body（本体＋前面の層）で比べる
    body_min = list(env["min"])
    body_max = list(env["max"])
    vis_min, vis_max = list(vis.GetMin()), list(vis.GetMax())
    want_vis_min, want_vis_max = cfg["envelope_all"]["min"], cfg["envelope_all"]["max"]
    check("Q2", "visual bounds (all parts)", _close_vec(vis_min, want_vis_min, TOL_M)
          and _close_vec(vis_max, want_vis_max, TOL_M), [vis_min, vis_max], [want_vis_min, want_vis_max])
    check("Q2", "body size = housing 131.8 x 80 x 74 mm", _close_vec(env["size"], [L, W, H], TOL_M), env["size"],
          [L, W, H])
    check("Q2", "front face at the optical centre (x max = 0)", abs(body_max[0]) <= TOL_M, body_max[0], 0.0)

    col_prim = stage.GetPrimAtPath(f"/{root_name}/Collision")
    col = cache.ComputeWorldBound(col_prim).ComputeAlignedRange() if col_prim else None
    if col is not None:
        # guide は既定の BBoxCache に入らないので、purpose guide を含めて計算し直す
        gcache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.guide])
        col = gcache.ComputeWorldBound(col_prim).ComputeAlignedRange()
        cmin, cmax = list(col.GetMin()), list(col.GetMax())
        check("Q3", "collision box = housing", _close_vec(cmin, [-L, -W / 2, -H / 2], TOL_M)
              and _close_vec(cmax, [0.0, W / 2, H / 2], TOL_M), [cmin, cmax], [[-L, -W / 2, -H / 2], [0, W / 2, H / 2]])
        check("Q3", "CollisionAPI", col_prim.HasAPI(UsdPhysics.CollisionAPI), col_prim.HasAPI(UsdPhysics.CollisionAPI),
              True)
        m = UsdPhysics.MassAPI(col_prim).GetMassAttr().Get()
        check("Q3", "mass", m is not None and abs(m - cfg["mass_kg"]) < 1e-6, m, cfg["mass_kg"])
    else:
        check("Q3", "collision prim exists", False, None, f"/{root_name}/Collision")

    cam_prim = stage.GetPrimAtPath(f"/{root_name}/OpticalFrame/Camera")
    cam = UsdGeom.Camera(cam_prim)
    xf = UsdGeom.Xformable(cam_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    fwd, up, right = _dir(xf, (0, 0, -1)), _dir(xf, (0, 1, 0)), _dir(xf, (1, 0, 0))
    org = xf.Transform(Gf.Vec3d(0, 0, 0))
    check("Q4", "camera looks +x", _close_vec(fwd, (1, 0, 0), 1e-6), list(fwd), [1, 0, 0])
    check("Q4", "image up = +z", _close_vec(up, (0, 0, 1), 1e-6), list(up), [0, 0, 1])
    check("Q4", "image right = -y", _close_vec(right, (0, -1, 0), 1e-6), list(right), [0, -1, 0])
    oc = cfg["optics"].get("optical_center_m") or [0.0, 0.0, 0.0]
    check("Q4", "optical centre (origin, or the left imager for RealSense)", _close_vec(org, oc, 1e-9), list(org), oc)

    o = cfg["optics"]
    f = cam.GetFocalLengthAttr().Get()
    ha, va = cam.GetHorizontalApertureAttr().Get(), cam.GetVerticalApertureAttr().Get()
    hfov, vfov = 2 * math.atan(ha / (2 * f)), 2 * math.atan(va / (2 * f))
    check("Q5", "focal length [mm]", abs(f - o["focal_length_mm"]) < 1e-5, f, o["focal_length_mm"])
    check("Q5", "aperture [mm]", abs(ha - o["sensor_size_mm"][0]) < 1e-5 and abs(va - o["sensor_size_mm"][1]) < 1e-5,
          [ha, va], o["sensor_size_mm"])
    check("Q5", "horizontal FOV [deg]", abs(hfov - o["horizontal_fov_rad"]) < 1e-6, math.degrees(hfov),
          math.degrees(o["horizontal_fov_rad"]))
    check("Q5", "vertical FOV [deg]", abs(vfov - o["vertical_fov_rad"]) < 1e-6, math.degrees(vfov),
          math.degrees(o["vertical_fov_rad"]))
    res = cam_prim.GetAttribute("irvision:resolution").Get()
    check("Q5", "resolution attribute", res is not None and tuple(res) == tuple(o["image_size"]),
          list(res) if res is not None else None, o["image_size"])
    clip = cam.GetClippingRangeAttr().Get()
    check("Q5", "clipping range [m]", abs(clip[0] - o["clip_m"][0]) < 1e-6 and abs(clip[1] - o["clip_m"][1]) < 1e-6,
          list(clip), o["clip_m"])

    led_prim = stage.GetPrimAtPath(f"/{root_name}/OpticalFrame/LED")
    if o["led_color"] == "none":
        check("Q6", "no LED light", not led_prim, bool(led_prim), False)
    else:
        led = UsdLux.DiskLight(led_prim)
        lxf = UsdGeom.Xformable(led_prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        ldir = _dir(lxf, (0, 0, -1))
        color = led.GetColorAttr().Get()
        cone = UsdLux.ShapingAPI(led_prim).GetShapingConeAngleAttr().Get()
        check("Q6", "LED shines +x", _close_vec(ldir, (1, 0, 0), 1e-6), list(ldir), [1, 0, 0])
        check("Q6", "LED colour", _close_vec(color, o["led_rgb"], 1e-6), list(color), o["led_rgb"])
        check("Q6", "LED cone angle [deg]", abs(cone - cfg["usd"]["led_light"]["cone_angle_deg"]) < 1e-6, cone,
              cfg["usd"]["led_light"]["cone_angle_deg"])

    ds = o.get("depth_sensor")
    if ds:
        tp = stage.GetPrimAtPath(f"/{root_name}/TemplateRenderProducts/Camera_render_product")
        api = tp.GetMetadata("apiSchemas") if tp else None
        has_api = bool(api) and "OmniSensorDepthSensorSingleViewAPI" in list(api.explicitItems) + list(api.prependedItems)
        tgt = tp.GetRelationship("camera").GetTargets() if tp else []
        check("Q8", "depth sensor template (RenderProduct + OmniSensorDepthSensorSingleViewAPI -> Camera)",
              has_api and len(tgt) == 1 and tgt[0] == cam_prim.GetPath(), [has_api, [str(x) for x in tgt]],
              [True, [str(cam_prim.GetPath())]])
        bl = tp.GetAttribute("omni:rtx:post:depthSensor:baselineMM").Get() if tp else None
        md = tp.GetAttribute("omni:rtx:post:depthSensor:minDistance").Get() if tp else None
        check("Q8", "depth sensor baseline / min distance", bl is not None and abs(bl - ds["baseline_mm"]) < 1e-4
              and md is not None and abs(md - ds["min_distance_m"]) < 1e-6, [bl, md], [ds["baseline_mm"], ds["min_distance_m"]])
    lights = [str(p.GetPath()) for p in stage.Traverse() if p.HasAPI(UsdLux.LightAPI) or "Light" in p.GetTypeName()]
    want_lights = [] if o["led_color"] == "none" else [f"/{root_name}/OpticalFrame/LED"]
    check("Q7", "no lights other than the LED (no dome light from Blender's world)", lights == want_lights, lights,
          want_lights)
    ok = all(c["ok"] for c in checks)
    return {"template_id": cfg["template_id"], "usd": str(usd_path), "usd_version": list(Usd.GetVersion()),
            "passed": ok, "n_checks": len(checks), "n_failed": sum(not c["ok"] for c in checks), "checks": checks}


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config_json)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    usd_path = Path(args.usd) if args.usd else cfg_path.parent / f"{cfg['template_id']}.usda"
    report = run(cfg, usd_path)
    out = cfg_path.parent / "qa_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    for c in report["checks"]:
        print(f"  [{'ok' if c['ok'] else 'FAIL'}] {c['id']} {c['name']}")
    print(f"[qa_camera] {report['n_checks'] - report['n_failed']}/{report['n_checks']} passed -> {out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
