"""author_camera_usd.py - カメラの USD（Isaac Sim 用）を組み立てる。

pxr だけを使う（Blender 同梱の Python で動かす: blender --background --python <this> -- ...）。
Isaac Sim の Python（omni.usd.libs の pxr）でも動く。

    blender --background --factory-startup --python scripts/camera_model/author_camera_usd.py -- \
        --config-json output/camera_model/irvision_2d/resolved_config.json

出力: <id>.usda（ルート = <root_prim>、defaultPrim、Z 上、1 m）
    /<root>                 Xform（kind=component）。本体の座標（原点 = 光学中心、+x = 光軸、+z = 上）
    /<root>/Visual          <id>_visual.usdc を参照（Blender の見た目）
    /<root>/Collision       外形の箱（purpose=guide、CollisionAPI・MassAPI 0.6 kg）
    /<root>/OpticalFrame    原点・本体と同じ向きの Xform（取り付け位置を決めるときの基準）
    /<root>/OpticalFrame/Camera   UsdGeom.Camera（-Z を見る規約に合わせて回転。焦点距離・撮像の大きさは mm）
    /<root>/OpticalFrame/LED      UsdLux.DiskLight（+x へ向けた赤色のスポット、ShapingAPI）
カメラの画像サイズ・形式などは Camera の属性（irvision:*）に書く（Isaac Sim の Camera は描画時に解像度を決めるため）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdLux, UsdPhysics, UsdShade, Vt  # noqa: F401

# 本体の座標から見たカメラ（USD の規約: -Z を見る、+Y が上）の軸。行 = カメラの X・Y・Z 軸（Gf は行ベクトル）
#   画像の右 = -y、画像の上 = +z、見る向き(-Z) = +x → Z = -x
CAMERA_ROWS = ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0))
# DiskLight も -Z に光る。光る向きを +x、上を +z にする（カメラと同じ回転）
LIGHT_ROWS = CAMERA_ROWS


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser(prog="author_camera_usd.py")
    p.add_argument("--config-json", required=True)
    return p.parse_args(argv)


def rows_to_quat(rows) -> Gf.Quatf:
    m = Gf.Matrix3d(*[v for r in rows for v in r])
    q = m.ExtractRotation().GetQuat()
    return Gf.Quatf(q.GetReal(), Gf.Vec3f(q.GetImaginary()))


def set_orient(prim: Usd.Prim, rows) -> None:
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddOrientOp(UsdGeom.XformOp.PrecisionFloat).Set(rows_to_quat(rows))


def author(cfg: dict, out_dir: Path) -> Path:
    tid, root_name = cfg["template_id"], cfg["root_prim"]
    optics, usd_cfg = cfg["optics"], cfg["usd"]
    path = out_dir / f"{tid}.usda"
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdPhysics.SetStageKilogramsPerUnit(stage, 1.0)

    root = UsdGeom.Xform.Define(stage, f"/{root_name}").GetPrim()
    stage.SetDefaultPrim(root)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    root.SetCustomData({
        "model": cfg["model"],
        "template_id": tid,
        "generator": "image2sim-framework scripts/camera_model",
        "source_sensor_config": Path(cfg["sensor_config"]).name,
        "frame": "origin = optical centre (front window centre), +x = optical axis, +y = left, +z = up, m",
        "provenance": json.dumps(cfg["provenance"], ensure_ascii=False),
    })

    # 見た目（Blender の書き出しを参照）
    visual = stage.DefinePrim(f"/{root_name}/Visual", "Xform")
    visual.GetReferences().AddReference(f"./{tid}_visual.usdc", f"/{root_name}_Visual")

    # 衝突・質量（外形の箱 1 つ）
    h = cfg["housing_mm"]
    L, W, H = h["length"] / 1000, h["width"] / 1000, h["height"] / 1000
    col = UsdGeom.Cube.Define(stage, f"/{root_name}/Collision")
    col.CreateSizeAttr(1.0)
    col.CreatePurposeAttr(UsdGeom.Tokens.guide)
    xf = UsdGeom.Xformable(col)
    xf.AddTranslateOp().Set(Gf.Vec3d(-L / 2, 0.0, 0.0))
    xf.AddScaleOp().Set(Gf.Vec3f(L, W, H))
    col.CreateExtentAttr([(-0.5, -0.5, -0.5), (0.5, 0.5, 0.5)])
    UsdPhysics.CollisionAPI.Apply(col.GetPrim())
    mass = UsdPhysics.MassAPI.Apply(col.GetPrim())
    mass.CreateMassAttr(float(cfg["mass_kg"]))

    # 光学中心
    optical = UsdGeom.Xform.Define(stage, f"/{root_name}/OpticalFrame")
    optical.GetPrim().SetCustomDataByKey("frame_id", optics["frame_id"])
    oc = optics.get("optical_center_m") or [0.0, 0.0, 0.0]
    if any(abs(v) > 0 for v in oc):                # RealSense：深度・RGB の原点は左の撮像素子
        optical.AddTranslateOp().Set(Gf.Vec3d(*oc))

    cam = UsdGeom.Camera.Define(stage, f"/{root_name}/OpticalFrame/Camera")
    set_orient(cam.GetPrim(), CAMERA_ROWS)
    sw, sh = optics["sensor_size_mm"]
    cam.CreateProjectionAttr(UsdGeom.Tokens.perspective)
    cam.CreateFocalLengthAttr(float(optics["focal_length_mm"]))
    cam.CreateHorizontalApertureAttr(float(sw))
    cam.CreateVerticalApertureAttr(float(sh))
    cam.CreateClippingRangeAttr(Gf.Vec2f(*optics["clip_m"]))
    cam.CreateFocusDistanceAttr(float(usd_cfg["camera"]["focus_distance_m"]))
    cam.CreateFStopAttr(0.0)
    p = cam.GetPrim()
    w, hpx = optics["image_size"]
    p.CreateAttribute("irvision:resolution", Sdf.ValueTypeNames.Int2, custom=True).Set(Gf.Vec2i(w, hpx))
    p.CreateAttribute("irvision:imageFormat", Sdf.ValueTypeNames.Token, custom=True).Set(optics["image_format"])
    p.CreateAttribute("irvision:updateRateHz", Sdf.ValueTypeNames.Double, custom=True).Set(optics["update_rate_hz"])
    p.CreateAttribute("irvision:horizontalFovRad", Sdf.ValueTypeNames.Double, custom=True).Set(
        optics["horizontal_fov_rad"])
    p.CreateAttribute("irvision:verticalFovRad", Sdf.ValueTypeNames.Double, custom=True).Set(optics["vertical_fov_rad"])
    intr = optics.get("intrinsics") or {}
    if intr:
        p.CreateAttribute("irvision:intrinsics", Sdf.ValueTypeNames.Double4, custom=True).Set(
            Gf.Vec4d(intr["fx"], intr["fy"], intr["cx"], intr["cy"]))
    p.CreateAttribute("irvision:mujocoCameraName", Sdf.ValueTypeNames.String, custom=True).Set(optics["camera_name"])

    led_cfg = usd_cfg["led_light"]
    if optics["led_color"] != "none":
        led = UsdLux.DiskLight.Define(stage, f"/{root_name}/OpticalFrame/LED")
        set_orient(led.GetPrim(), LIGHT_ROWS)
        led.CreateRadiusAttr(float(led_cfg["radius_m"]))
        led.CreateIntensityAttr(float(led_cfg["intensity"]))
        led.CreateExposureAttr(float(led_cfg["exposure"]))
        led.CreateColorAttr(Gf.Vec3f(*optics["led_rgb"]))
        shaping = UsdLux.ShapingAPI.Apply(led.GetPrim())
        shaping.CreateShapingConeAngleAttr(float(led_cfg["cone_angle_deg"]))
        shaping.CreateShapingConeSoftnessAttr(float(led_cfg["cone_softness"]))

    ds = optics.get("depth_sensor")
    if ds:
        # Isaac Sim 5.0 の SingleViewDepthSensorAsset が見つけるひな形（D455 アセットと同じ作り）
        rp = stage.DefinePrim(f"/{root_name}/TemplateRenderProducts/Camera_render_product", "RenderProduct")
        rp.SetMetadata("apiSchemas", Sdf.TokenListOp.CreateExplicit(["OmniSensorDepthSensorSingleViewAPI"]))
        rp.CreateRelationship("camera").SetTargets([cam.GetPath()])
        rp.CreateAttribute("resolution", Sdf.ValueTypeNames.Int2).Set(Gf.Vec2i(*optics["image_size"]))
        pre = "omni:rtx:post:depthSensor:"
        for name, typ, val in (("enabled", Sdf.ValueTypeNames.Bool, True),
                               ("baselineMM", Sdf.ValueTypeNames.Float, ds["baseline_mm"]),
                               ("focalLengthPixel", Sdf.ValueTypeNames.Float, ds["focal_length_pixel"]),
                               ("sensorSizePixel", Sdf.ValueTypeNames.Float, ds["sensor_size_pixel"]),
                               ("maxDisparityPixel", Sdf.ValueTypeNames.Float, ds["max_disparity_pixel"]),
                               ("minDistance", Sdf.ValueTypeNames.Float, ds["min_distance_m"]),
                               ("maxDistance", Sdf.ValueTypeNames.Float, ds["max_distance_m"]),
                               ("noiseSigma", Sdf.ValueTypeNames.Float, ds["noise_sigma_px"]),
                               ("noiseMean", Sdf.ValueTypeNames.Float, ds["noise_mean_px"]),
                               ("confidenceThreshold", Sdf.ValueTypeNames.Float, ds["confidence_threshold"])):
            rp.CreateAttribute(pre + name, typ, custom=False).Set(val)

    stage.GetRootLayer().documentation = (
        f"{cfg['display_name']} — generated by image2sim-framework scripts/camera_model from "
        f"{Path(cfg['sensor_config']).name}")
    stage.Save()
    return path


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config_json)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    path = author(cfg, cfg_path.parent)
    print(f"[author_camera_usd] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
