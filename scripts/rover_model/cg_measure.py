"""公式 CG からローバの寸法を測る（カメラ合わせ）。

透視の強い CG では「既知長 × 画素比」（newplan2/01_写真採寸とパラメータ仕様.md §6.1）が使えないので、
**同じ半径の円（車輪の外側の面）が同じ平面に一直線に並ぶ**ことを拘束にして、
画像ごとにカメラ（焦点距離・向き・位置）と軸の位置を最小二乗で解く。長さの単位は車輪半径 r。

  画像 02・03：カメラ＋軸の位置（前↔中・中↔後）。側面の点・地面の点・鉛直の点を r 単位で測る
  画像 04    ：正面。同じ奥行きどうしの横方向の比（トレッド幅・車輪間隔・車体幅）
  物差し      ：宇宙飛行士の身長・全長・全高・全幅（anchors）から r [m] を出し、ばらつきも示す

使い方（リポジトリ直下で）:
  python scripts/rover_model/cg_measure.py config/rover_measurements/lunar_cruiser_cg.json \
      --out output/rover_measure/lunar_cruiser [--overlay]

出力: <out>/measurements.json（数値）と、--overlay のとき <out>/overlay_<画像>.jpg（当てはめの確認用。
CG を含むので git 管理外。再配布しない）。
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares
from scipy.spatial.transform import Rotation

THETA = np.linspace(0.0, 2.0 * np.pi, 240, endpoint=False)


class Camera:
    """ピンホール（主点は画像中心・正方画素）。世界は X 後ろ向き・Y は側面の法線・Z 上、単位は r。"""

    def __init__(self, f: float, R: np.ndarray, t: np.ndarray, size: tuple[int, int]):
        self.f, self.R, self.t = f, R, t
        self.pp = np.array([size[0] / 2.0, size[1] / 2.0])

    def project(self, P: np.ndarray) -> np.ndarray:
        Pc = (self.R @ np.atleast_2d(P).T).T + self.t
        return np.c_[self.f * Pc[:, 0] / Pc[:, 2], self.f * Pc[:, 1] / Pc[:, 2]] + self.pp

    @property
    def center(self) -> np.ndarray:
        return -self.R.T @ self.t

    def ray(self, uv) -> np.ndarray:
        d = np.array([(uv[0] - self.pp[0]) / self.f, (uv[1] - self.pp[1]) / self.f, 1.0])
        w = self.R.T @ d
        return w / np.linalg.norm(w)


def circle(xc: float, y: float = 0.0) -> np.ndarray:
    return np.c_[xc + np.cos(THETA), np.full_like(THETA, y), np.sin(THETA)]


def fit_wheels(img: dict) -> tuple[Camera, list[float], float]:
    """車輪 3 つからカメラと軸の位置（前軸 = 0、後ろ向き正）を解く。戻り値の最後は残差 RMS [px]。"""
    size = tuple(img["size"])
    pp = np.array([size[0] / 2.0, size[1] / 2.0])
    obs = img["wheels_front_to_rear"]

    def unpack(p):
        cam = Camera(p[0], Rotation.from_rotvec(p[1:4]).as_matrix(), p[4:7], size)
        return cam, [0.0, p[7], p[8]]

    def vp_res(cam, axis, vp):
        d = cam.R @ axis
        a = math.atan2(cam.f * d[1], cam.f * d[0]) if abs(d[2]) < 1e-12 else \
            math.atan2(cam.f * d[1] / d[2], cam.f * d[0] / d[2])
        b = math.atan2(vp[1] - pp[1], vp[0] - pp[0])
        return (a - b + math.pi / 2) % math.pi - math.pi / 2   # 向きは ±180° を同一視

    def res(p):
        cam, xs = unpack(p)
        out = []
        for o, xc in zip(obs, xs):
            uv = cam.project(circle(xc))
            out += [uv[:, 0].min() - o["l"], uv[:, 0].max() - o["r"], uv[:, 1].min() - o["t"], uv[:, 1].max() - o["b"]]
            out += list((cam.project(np.array([xc, 0.0, 0.0]))[0] - o["hub"]) * 0.5)
        out.append(vp_res(cam, np.array([1.0, 0, 0]), img["vp_x"]) * 3000.0)
        out.append(vp_res(cam, np.array([0, 0, 1.0]), img["vp_z"]) * 3000.0)
        # 鏡像の解を除く：世界の上（+Z）は画像でも上、カメラは地面（Z = −1）より上
        hub = cam.project(np.array([xs[1], 0.0, 0.0]))[0]
        up = cam.project(np.array([xs[1], 0.0, 1.0]))[0]
        out.append(max(0.0, up[1] - hub[1]) * 10.0)
        out.append(max(0.0, -1.0 - cam.center[2]) * 1000.0)
        return np.array(out)

    base = Rotation.from_euler("x", -90, degrees=True)
    best = None
    for f0 in (4000, 7000, 10000, 15000, 22000):
        for yaw0 in range(0, 360, 20):
            for pitch0 in (-10, 0, 10):
                rot = Rotation.from_euler("x", pitch0, degrees=True) * base * Rotation.from_euler("z", yaw0, degrees=True)
                Rm = rot.as_matrix()
                target = np.array([3.0, 0.0, 0.0])
                cam_pos = target - Rm.T @ np.array([0, 0, 1.0]) * (f0 * 2.0 / 700.0)
                p0 = np.r_[f0, rot.as_rotvec(), -Rm @ cam_pos, 3.2, 6.4]
                try:
                    s = least_squares(res, p0, max_nfev=3000)
                except (ValueError, FloatingPointError):
                    continue
                cam, _ = unpack(s.x)
                if cam.f <= 0 or s.x[6] <= 0:
                    continue
                if best is None or s.cost < best.cost:
                    best = s
    cam, xs = unpack(best.x)
    r = res(best.x)[:-4]
    return cam, xs, float(np.sqrt(np.mean(r ** 2)))


def on_side_plane(cam: Camera, uv) -> np.ndarray:
    """側面（Y = 0、車輪の外側の面と同じ平面）上の点として 3D を求める。"""
    c, d = cam.center, cam.ray(uv)
    s = -c[1] / d[1]
    return c + s * d


def on_ground(cam: Camera, uv) -> np.ndarray:
    """地面（Z = −1）上の点として 3D を求める。"""
    c, d = cam.center, cam.ray(uv)
    s = (-1.0 - c[2]) / d[2]
    return c + s * d


def vertical_height(cam: Camera, base: np.ndarray, uv_top) -> float:
    """地面の点 base の真上で、画像の v が uv_top に一致する高さ（地面から、r 単位）。"""
    g = lambda z: cam.project(np.array([base[0], base[1], z]))[0][1] - uv_top[1]
    z = brentq(g, base[2], base[2] + 50.0)
    return z - base[2]


def tread_width(cam: Camera, x_wheel: float, extreme_x: float) -> float:
    """タイヤの内側の縁（外側の面からカメラと反対側へ w だけ奥）の右端が extreme_x に来る w。"""
    away = -math.copysign(1.0, cam.center[1])
    g = lambda w: cam.project(circle(x_wheel, away * w))[:, 0].max() - extreme_x
    return brentq(g, 1e-3, 3.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("config")
    ap.add_argument("--out", default="output/rover_measure/lunar_cruiser")
    ap.add_argument("--overlay", action="store_true", help="当てはめを CG に重ねた確認画像を出す")
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    imgs = cfg["images"]
    result: dict = {"subject": cfg["subject"], "unit": "車輪半径 r（anchors で m に換算）", "images": {}}

    # --- 画像 02・03：カメラと軸 -------------------------------------------------
    cams = {}
    for key in ("02", "03"):
        cam, xs, rms = fit_wheels(imgs[key])
        cams[key] = (cam, xs)
        hfov = math.degrees(2 * math.atan(imgs[key]["size"][0] / 2.0 / cam.f))
        result["images"][key] = {
            "rms_px": round(rms, 2), "focal_px": round(cam.f), "hfov_deg": round(hfov, 1),
            "camera_r": [round(v, 2) for v in cam.center],
            "axle_x_r": [round(abs(v), 3) for v in xs],
            "spacing_front_mid_r": round(abs(xs[1] - xs[0]), 3),
            "spacing_mid_rear_r": round(abs(xs[2] - xs[1]), 3),
        }

    sp_fm = np.mean([result["images"][k]["spacing_front_mid_r"] for k in ("02", "03")])
    sp_mr = np.mean([result["images"][k]["spacing_mid_rear_r"] for k in ("02", "03")])

    # --- 02：側面の点（前軸からの前後位置・地面からの高さ）------------------------
    cam02, xs02 = cams["02"]
    sgn = 1.0 if xs02[2] > xs02[0] else -1.0          # 後ろ向きを正にそろえる
    side = {}
    for name, uv in imgs["02"]["side_points"].items():
        if name.startswith("_"):
            continue
        P = on_side_plane(cam02, uv)
        side[name] = {"x_back_r": round(sgn * P[0], 3), "height_r": round(P[2] + 1.0, 3)}
    result["images"]["02"]["side_points"] = side
    front_end = side["front_corner_mid"]["x_back_r"]
    rear_end = max(side["rear_lower_end"]["x_back_r"], side["rear_box_mid"]["x_back_r"])
    body_len_r = rear_end - front_end
    body_h_r = side["rear_box_top"]["height_r"]

    # --- 03：宇宙飛行士の身長・タイヤ幅 --------------------------------------------
    cam03, xs03 = cams["03"]
    feet = on_ground(cam03, imgs["03"]["ground_points"]["astronaut_feet"])
    astro_r = vertical_height(cam03, feet, imgs["03"]["vertical_tops"]["astronaut_head"]["uv"])
    tread_r = tread_width(cam03, xs03[2], imgs["03"]["tread_inner_extreme_x_rear"])
    result["images"]["03"]["astronaut_height_r"] = round(astro_r, 3)
    result["images"]["03"]["astronaut_distance_r"] = round(float(np.linalg.norm(feet - cam03.center)), 1)
    result["images"]["03"]["tire_width_r"] = round(tread_r, 3)

    # --- 04：正面の横方向の比（同じ奥行き）→ r 単位へ（タイヤ幅で換算）---------------
    i4 = imgs["04"]
    tw_px = np.mean([i4["front_tread_x"]["right_wheel"][1] - i4["front_tread_x"]["right_wheel"][0],
                     i4["front_tread_x"]["left_wheel"][1] - i4["front_tread_x"]["left_wheel"][0]])
    track_px = np.mean(i4["front_tread_x"]["left_wheel"]) - np.mean(i4["front_tread_x"]["right_wheel"])
    outer_px = i4["front_tread_x"]["left_wheel"][1] - i4["front_tread_x"]["right_wheel"][0]
    cabin_px = i4["cabin_width_x"][1] - i4["cabin_width_x"][0]
    k = tread_r / tw_px
    result["images"]["04"] = {
        "tire_width_px": round(float(tw_px), 1),
        "track_center_r": round(float(track_px * k), 3),
        "wheel_outer_width_r": round(float(outer_px * k), 3),
        "cabin_width_r": round(float(cabin_px * k), 3),
    }

    # --- 物差し → r [m] ---------------------------------------------------------
    an = cfg["anchors"]
    r_by = {
        "astronaut": an["astronaut_height_m"]["value"] / astro_r,
        "body_length": an["body_length_m"]["value"] / body_len_r,
        "body_height": an["body_height_m"]["value"] / body_h_r,
        "body_width": an["body_width_m"]["value"] / result["images"]["04"]["cabin_width_r"],
    }
    r_vals = np.array(list(r_by.values()))
    # 基準の物差し（baseline_anchors）の平均を採る。ほかは確認用（偏りの理由は採寸シートに書く）
    base_keys = cfg.get("baseline_anchors", list(r_by))
    r_m = float(np.mean([r_by[k] for k in base_keys]))
    summary_r = {
        "axle_spacing_front_mid_r": round(float(sp_fm), 3),
        "axle_spacing_mid_rear_r": round(float(sp_mr), 3),
        "front_overhang_r": round(-front_end, 3),
        "rear_overhang_r": round(rear_end - abs(xs02[2] - xs02[0]), 3),
        "body_length_r": round(body_len_r, 3),
        "body_height_r": round(body_h_r, 3),
        "panel_top_height_r": side["panel_top_rear"]["height_r"],
        "panel_bottom_height_r": side["panel_bottom_rear"]["height_r"],
        "tire_width_r": round(tread_r, 3),
        "track_center_r": result["images"]["04"]["track_center_r"],
        "cabin_width_r": result["images"]["04"]["cabin_width_r"],
    }
    result["wheel_radius_m_by_anchor"] = {k: round(v, 4) for k, v in r_by.items()}
    result["wheel_radius_m"] = {"baseline": round(r_m, 4), "baseline_anchors": base_keys, "min": round(float(r_vals.min()), 4),
                                "max": round(float(r_vals.max()), 4)}
    result["summary_r"] = summary_r
    result["summary_m"] = {k[:-2] + "_m": round(v * r_m, 3) for k, v in summary_r.items()}   # 末尾の _r → _m
    result["summary_m"]["wheel_diameter_m"] = round(2 * r_m, 3)

    (out / "measurements.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if a.overlay:
        from PIL import Image, ImageDraw
        root = Path(cfg["images_dir"])
        for key, (cam, xs) in cams.items():
            im = Image.open(root / imgs[key]["file"]).convert("RGB")
            d = ImageDraw.Draw(im)
            for xc in xs:
                d.line([tuple(p) for p in cam.project(circle(xc))] + [tuple(cam.project(circle(xc))[0])],
                       fill=(255, 0, 255), width=8)
            for o in imgs[key]["wheels_front_to_rear"]:
                d.rectangle([o["l"], o["t"], o["r"], o["b"]], outline=(0, 255, 0), width=5)
            if key == "03":
                away = -math.copysign(1.0, cam.center[1])
                pts = cam.project(circle(xs[2], away * tread_r))
                d.line([tuple(p) for p in pts], fill=(0, 200, 255), width=6)
                top = feet + np.array([0, 0, astro_r])
                d.line([tuple(cam.project(feet)[0]), tuple(cam.project(top)[0])], fill=(255, 255, 0), width=8)
            if key == "02":
                for uv in imgs["02"]["side_points"].values():
                    if isinstance(uv, list):
                        d.ellipse([uv[0] - 25, uv[1] - 25, uv[0] + 25, uv[1] + 25], outline=(255, 255, 0), width=6)
            im.thumbnail((2400, 2400))
            im.save(out / f"overlay_{key}.jpg", quality=88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
