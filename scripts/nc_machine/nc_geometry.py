"""nc_geometry.py - 加工機・台車・パレットのテンプレート（resolved config）から部品の形を計算する。

Blender（見た目）と MJCF（物理）の両方がこのモジュールの結果を使うので、寸法の正本は 1 か所になる。
bpy・numpy に依存しない（Blender 同梱の Python からも読み込む）。

出力（describe() の返り値）:
    {
      "template_id", "kind",
      "bodies": [{"name", "parent", "pos", "joint", "geoms": [geom...]}],   # 親は先に並ぶ
      "sites":  [{"name", "body", "type", "pos", "size", "quat"}],
      "materials": {name: [r, g, b, a]},
      "interface": {...}                                                  # robot_interface.json の中身
    }
    geom = {"name", "type": "box"|"cylinder", "size"(MuJoCo の半寸法), "pos", "quat"(w,x,y,z),
            "material", "collide": bool}
座標はすべて親ボディの座標（LOD0 ではボディは回転しないので、ルート座標と平行）。単位 m。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

Vec = List[float]
Q_ID = [1.0, 0.0, 0.0, 0.0]
JAW_ANGLES_DEG = (90.0, 210.0, 330.0)


# --- 小さなベクトル演算 ----------------------------------------------------------

def add(a: Sequence[float], b: Sequence[float]) -> Vec:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def sub(a: Sequence[float], b: Sequence[float]) -> Vec:
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def scale(a: Sequence[float], s: float) -> Vec:
    return [a[0] * s, a[1] * s, a[2] * s]


def norm(a: Sequence[float]) -> Vec:
    n = math.sqrt(sum(x * x for x in a))
    return [x / n for x in a]


def cross(a: Sequence[float], b: Sequence[float]) -> Vec:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def mat_to_quat(cols: Sequence[Sequence[float]]) -> Vec:
    """列ベクトル（ローカル x, y, z 軸の向き）の回転行列 → クォータニオン (w, x, y, z)。"""
    r = [[cols[j][i] for j in range(3)] for i in range(3)]
    t = r[0][0] + r[1][1] + r[2][2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [0.25 * s, (r[2][1] - r[1][2]) / s, (r[0][2] - r[2][0]) / s, (r[1][0] - r[0][1]) / s]
    else:
        i = max(range(3), key=lambda k: r[k][k])
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(1.0 + r[i][i] - r[j][j] - r[k][k]) * 2
        q = [0.0] * 4
        q[0] = (r[k][j] - r[j][k]) / s
        q[1 + i] = 0.25 * s
        q[1 + j] = (r[j][i] + r[i][j]) / s
        q[1 + k] = (r[k][i] + r[i][k]) / s
    n = math.sqrt(sum(x * x for x in q))
    q = [x / n for x in q]
    return q if q[0] >= 0 else [-x for x in q]


def z_to(axis: Sequence[float]) -> Vec:
    """ローカル z を axis に向けるクォータニオン（円柱の軸合わせ）。"""
    z = norm(axis)
    ref = [0.0, 0.0, 1.0] if abs(z[2]) < 0.9 else [1.0, 0.0, 0.0]
    x = norm(cross(ref, z))
    y = cross(z, x)
    return mat_to_quat([x, y, z])


def box_from_bounds(name: str, lo: Sequence[float], hi: Sequence[float], material: str,
                    collide: bool = True) -> Dict[str, Any]:
    return {"name": name, "type": "box", "size": scale(sub(hi, lo), 0.5), "pos": scale(add(lo, hi), 0.5),
            "quat": list(Q_ID), "material": material, "collide": collide}


def rgba(c: Sequence[float]) -> Vec:
    return [float(c[0]), float(c[1]), float(c[2]), float(c[3]) if len(c) > 3 else 1.0]


# --- 加工機 ----------------------------------------------------------------------

def machine_bounds(cfg: Dict[str, Any]) -> Dict[str, float]:
    env = cfg["envelope"]
    ox, w, d, h = env.get("offset_x_m", 0.0), env["width_m"], env["depth_m"], env["height_m"]
    t = env.get("wall_m", 0.04)
    return {"xmin": ox - w / 2, "xmax": ox + w / 2, "ymin": 0.0, "ymax": d, "zmin": 0.0, "zmax": h, "t": t,
            "bed_top": env["bed_top_m"]}


def describe_machine(cfg: Dict[str, Any]) -> Dict[str, Any]:
    b = machine_bounds(cfg)
    t = b["t"]
    door = cfg["door"]
    ow, oh, sill = door["opening_w_m"], door["opening_h_m"], door["sill_h_m"]
    top = sill + oh
    if not (b["xmin"] + t < -ow / 2 and ow / 2 < b["xmax"] - t):
        raise ValueError("扉開口が外形の左右からはみ出す（offset_x_m・opening_w_m を確認）")
    if not (b["bed_top"] < sill and top < b["zmax"] - t):
        raise ValueError("扉開口の高さが床・屋根と合わない（sill_h_m・opening_h_m・bed_top_m を確認）")

    paint = cfg.get("paint", {})
    mats = {k: rgba(v) for k, v in paint.items()}
    mats.setdefault("door_glass", [0.2, 0.24, 0.28, 0.6])
    mats["door_glass"][3] = 0.6

    geoms: List[Dict[str, Any]] = []
    xn, xx, yd, zh = b["xmin"], b["xmax"], b["ymax"], b["zmax"]
    # 前面カバー（開口のまわり 4 枚）
    geoms += [
        box_from_bounds("front_left", [xn, 0.0, 0.0], [-ow / 2, t, zh], "cover"),
        box_from_bounds("front_right", [ow / 2, 0.0, 0.0], [xx, t, zh], "cover"),
        box_from_bounds("front_bottom", [-ow / 2, 0.0, 0.0], [ow / 2, t, sill], "cover"),
        box_from_bounds("front_top", [-ow / 2, 0.0, top], [ow / 2, t, zh], "frame"),
    ]
    # 側面・背面・屋根・機内の床（ベッド）
    geoms += [
        box_from_bounds("side_left", [xn, t, 0.0], [xn + t, yd, zh], "frame"),
        box_from_bounds("side_right", [xx - t, t, 0.0], [xx, yd, zh], "frame"),
        box_from_bounds("back", [xn + t, yd - t, 0.0], [xx - t, yd, zh], "frame"),
        box_from_bounds("roof", [xn + t, t, zh - t], [xx - t, yd - t, zh], "frame"),
        box_from_bounds("bed", [xn + t, t, 0.0], [xx - t, yd - t, b["bed_top"]], "bed"),
    ]
    bodies: List[Dict[str, Any]] = [
        {"name": "machine_root", "parent": None, "pos": [0.0, 0.0, 0.0], "joint": None, "geoms": geoms}]

    # 扉（LOD0 は開いた位置に固定）
    dt = door.get("thickness_m", 0.03)
    sign = -1.0 if str(door.get("direction", "+x")).startswith("-") else 1.0
    stroke = door["stroke_m"] if cfg.get("lod", 0) == 0 else 0.0
    dw, dh = ow / 2 + 0.05, oh / 2 + 0.05
    door_pos = [sign * stroke, -dt / 2 - 0.005, sill + oh / 2]
    bodies.append({"name": "door", "parent": "machine_root", "pos": door_pos, "joint": None, "geoms": [
        {"name": "door_panel", "type": "box", "size": [dw, dt / 2, dh], "pos": [0.0, 0.0, 0.0], "quat": list(Q_ID),
         "material": "door", "collide": True},
        {"name": "door_window", "type": "box", "size": [dw * 0.7, dt / 2 + 0.002, dh * 0.55],
         "pos": [0.0, 0.0, dh * 0.15], "quat": list(Q_ID), "material": "door_glass", "collide": False},
    ]})

    # 主軸台・主軸（チャック・爪）
    for sp in cfg["spindles"]:
        sid = sp["id"]
        face = [float(x) for x in sp["pos_m"]]
        ax = norm(sp["axis"])
        ch = sp["chuck"]
        r, L = ch["dia_m"] / 2, ch["length_m"]
        back = sub(face, scale(ax, L))
        hs_half = max(r + 0.05, 0.16)
        if ax[0] > 0:
            hs_lo = [xn + t, face[1] - hs_half, b["bed_top"]]
            hs_hi = [back[0], face[1] + hs_half, face[2] + hs_half]
        else:
            hs_lo = [back[0], face[1] - hs_half, b["bed_top"]]
            hs_hi = [xx - t, face[1] + hs_half, face[2] + hs_half]
        bodies.append({"name": f"headstock_{sid}", "parent": "machine_root", "pos": [0.0, 0.0, 0.0], "joint": None,
                       "geoms": [box_from_bounds(f"headstock_{sid}_body", hs_lo, hs_hi, "frame")]})

        jaw = ch["jaw"]
        jh, jw, jl = jaw["h_m"], jaw["w_m"], jaw.get("l_m", 0.05)
        jr = r * 0.55
        geoms_sp = [{"name": f"{sid}_chuck", "type": "cylinder", "size": [r, L / 2], "pos": scale(ax, -L / 2),
                     "quat": z_to(ax), "material": "chuck", "collide": True}]
        ref = [0.0, 0.0, 1.0] if abs(ax[2]) < 0.9 else [0.0, 1.0, 0.0]
        e1 = norm(cross(ax, ref))
        e2 = cross(ax, e1)
        for k, deg in enumerate(JAW_ANGLES_DEG, 1):
            a = math.radians(deg)
            radial = add(scale(e1, math.cos(a)), scale(e2, math.sin(a)))
            tang = cross(ax, radial)
            geoms_sp.append({"name": f"{sid}_jaw{k}", "type": "box", "size": [jh / 2, jl / 2, jw / 2],
                             "pos": add(scale(ax, jh / 2), scale(radial, jr)),
                             "quat": mat_to_quat([ax, radial, tang]), "material": "jaw", "collide": True})
        bodies.append({"name": sid, "parent": "machine_root", "pos": face, "joint": None, "geoms": geoms_sp})

    # 刃物台・ミーリングヘッド（退避位置）
    tur = cfg["turret"]
    bodies.append({"name": "turret", "parent": "machine_root", "pos": [float(x) for x in tur["home_m"]],
                   "joint": None, "geoms": [
                       {"name": "turret_body", "type": "box", "size": [float(x) for x in tur["half_size_m"]],
                        "pos": [0.0, 0.0, 0.0], "quat": list(Q_ID), "material": "turret", "collide": True}]})

    # 心押台（任意。LOD0 は後退端に固定。pos_m はセンタ先端、axis はセンタの向き＝主軸側）
    ts = cfg.get("tailstock")
    if ts:
        tip = [float(x) for x in ts["pos_m"]]
        ax = norm(ts["axis"])
        ql, qr = ts["quill_len_m"], ts["quill_dia_m"] / 2
        hb = [float(x) for x in ts["body_half_size_m"]]
        body_c = sub(tip, scale(ax, ql + hb[0]))
        bodies.append({"name": "tailstock", "parent": "machine_root", "pos": tip, "joint": None, "geoms": [
            {"name": "tailstock_body", "type": "box", "size": hb, "pos": sub(body_c, tip), "quat": list(Q_ID),
             "material": "frame", "collide": True},
            {"name": "tailstock_quill", "type": "cylinder", "size": [qr, ql / 2], "pos": scale(ax, -ql / 2),
             "quat": z_to(ax), "material": "chuck", "collide": True},
        ]})

    # 位置補正マーク（見た目は前面カバーに貼った薄い板）
    sites: List[Dict[str, Any]] = []
    for mk in cfg.get("markers", []):
        p = [float(x) for x in mk["pos_m"]]
        s = mk.get("size_m", 0.08) / 2
        bodies[0]["geoms"].append({"name": f"marker_{mk['id']}", "type": "box", "size": [s, 0.001, s],
                                   "pos": [p[0], p[1] - 0.001, p[2]], "quat": list(Q_ID),
                                   "material": "marker", "collide": False})
        sites.append({"name": f"marker_{mk['id']}", "body": "machine_root", "type": "sphere", "pos": p,
                      "size": [0.01], "quat": list(Q_ID)})

    wz = cfg["work_zone_m"]
    sites.append({"name": "work_zone", "body": "machine_root", "type": "box",
                  "pos": scale(add(wz["min"], wz["max"]), 0.5), "size": scale(sub(wz["max"], wz["min"]), 0.5),
                  "quat": list(Q_ID)})

    ri = cfg["robot_interface"]
    loads = {}
    for sp in cfg["spindles"]:
        ax = norm(sp["axis"])
        loads[sp["id"]] = {"face_m": [float(x) for x in sp["pos_m"]], "axis": ax,
                           "load_m": add(sp["pos_m"], scale(ax, ri["load_offset_m"])),
                           "chuck_dia_m": sp["chuck"]["dia_m"]}
        sites.append({"name": f"load_{sp['id']}", "body": "machine_root", "type": "sphere",
                      "pos": loads[sp["id"]]["load_m"], "size": [0.01], "quat": list(Q_ID)})
    for key in ("approach_m", "door_pass_m"):
        sites.append({"name": key[:-2], "body": "machine_root", "type": "sphere", "pos": list(ri[key]),
                      "size": [0.01], "quat": list(Q_ID)})

    interface = {
        "schema": "hakoniwa.ncmachine.robot-interface/v1",
        "template_id": cfg["template_id"],
        "frame": "M (floor, door opening center, front face; X right, Y into machine, Z up)",
        "approach_m": list(ri["approach_m"]),
        "door_pass_m": list(ri["door_pass_m"]),
        "load_offset_m": ri["load_offset_m"],
        "spindles": loads,
        "door_opening": {"x_m": [-ow / 2, ow / 2], "z_m": [sill, top], "y_m": 0.0, "wall_m": t},
        "markers": [{"id": m["id"], "pos_m": list(m["pos_m"])} for m in cfg.get("markers", [])],
        "work_zone_m": wz,
    }
    return {"template_id": cfg["template_id"], "kind": "machine", "bodies": bodies, "sites": sites,
            "materials": mats, "interface": interface}


# --- 台車 ------------------------------------------------------------------------

def describe_cart(cfg: Dict[str, Any]) -> Dict[str, Any]:
    c = cfg["cart"]
    w, d, h = c["width_m"], c["depth_m"], c["height_m"]
    mats = {k: rgba(v) for k, v in cfg.get("paint", {}).items()}
    top_t = 0.02
    geoms = [
        box_from_bounds("cart_body", [-w / 2, -d / 2, 0.0], [w / 2, d / 2, h - top_t], "cart"),
        box_from_bounds("cart_top", [-w / 2, -d / 2, h - top_t], [w / 2, d / 2, h], "top"),
    ]
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
        geoms.append({"name": f"light_bar_{i}", "type": "box", "size": [0.015, 0.015, h * 0.4],
                      "pos": [sx * (w / 2 - 0.015), sy * (d / 2 - 0.015), h * 0.5], "quat": list(Q_ID),
                      "material": "light_bar", "collide": False})
    mount = [float(x) for x in c["robot_mount_m"]]
    sites = [{"name": "robot_mount", "body": "cart_root", "type": "sphere", "pos": mount, "size": [0.02],
              "quat": list(Q_ID)}]
    anchors = {}
    for key, a in cfg.get("pallet_anchors", {}).items():
        if a is None:            # 継承元の置き場を無効にした
            continue
        anchors[key] = {"pos_m": [float(x) for x in a["pos_m"]], "yaw_deg": float(a.get("yaw_deg", 0.0))}
        sites.append({"name": f"pallet_{key}", "body": "cart_root", "type": "sphere", "pos": anchors[key]["pos_m"],
                      "size": [0.02], "quat": list(Q_ID)})
    interface = {"schema": "hakoniwa.ncmachine.cart-interface/v1", "template_id": cfg["template_id"],
                 "frame": "C (floor, cart center; X right, Y forward, Z up)",
                 "robot_mount_m": mount, "pallet_anchors": anchors, "footprint_m": [w, d]}
    return {"template_id": cfg["template_id"], "kind": "cart",
            "bodies": [{"name": "cart_root", "parent": None, "pos": [0.0, 0.0, 0.0], "joint": None, "geoms": geoms}],
            "sites": sites, "materials": mats, "interface": interface}


# --- パレット --------------------------------------------------------------------

def pallet_slots(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    nx, ny = int(p["grid"][0]), int(p["grid"][1])
    w, d, m = p["width_m"], p["depth_m"], p["margin_m"]
    px = (w - 2 * m) / nx
    py = (d - 2 * m) / ny
    if min(px, py) < p["slot_dia_m"]:
        raise ValueError(f"スロットが重なる（ピッチ {min(px, py):.3f} m < 径 {p['slot_dia_m']} m）")
    z = p["stand_h_m"]   # 窪みの底＝パレット上面
    out = []
    for j in range(ny):
        for i in range(nx):
            out.append({"name": f"slot_{j}{i}", "pos_m": [-w / 2 + m + px * (i + 0.5), -d / 2 + m + py * (j + 0.5), z]})
    return out


def describe_pallet(cfg: Dict[str, Any]) -> Dict[str, Any]:
    p = cfg["pallet"]
    w, d, h, pt, tt = p["width_m"], p["depth_m"], p["stand_h_m"], p["plate_m"], p["template_m"]
    mats = {k: rgba(v) for k, v in cfg.get("paint", {}).items()}
    geoms = []
    leg = 0.04
    for i, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), 1):
        geoms.append(box_from_bounds(f"leg_{i}", [sx * (w / 2 - 0.05) - leg / 2, sy * (d / 2 - 0.05) - leg / 2, 0.0],
                                     [sx * (w / 2 - 0.05) + leg / 2, sy * (d / 2 - 0.05) + leg / 2, h - pt], "stand"))
    geoms.append(box_from_bounds("plate", [-w / 2, -d / 2, h - pt], [w / 2, d / 2, h], "plate"))
    slots = pallet_slots(p)
    sites = []
    for s in slots:
        geoms.append({"name": f"{s['name']}_ring", "type": "cylinder", "size": [p["slot_dia_m"] / 2 + 0.01, tt / 2],
                      "pos": [s["pos_m"][0], s["pos_m"][1], h + tt / 2], "quat": list(Q_ID),
                      "material": "template", "collide": False})
        sites.append({"name": s["name"], "body": "pallet_root", "type": "sphere", "pos": s["pos_m"], "size": [0.01],
                      "quat": list(Q_ID)})
    interface = {"schema": "hakoniwa.ncmachine.pallet-interface/v1", "template_id": cfg["template_id"],
                 "frame": "P (floor, pallet center; X right, Y forward, Z up)",
                 "slot_dia_m": p["slot_dia_m"], "grid": list(p["grid"]), "slots": slots, "top_m": h}
    return {"template_id": cfg["template_id"], "kind": "pallet",
            "bodies": [{"name": "pallet_root", "parent": None, "pos": [0.0, 0.0, 0.0], "joint": None, "geoms": geoms}],
            "sites": sites, "materials": mats, "interface": interface}


def describe(cfg: Dict[str, Any]) -> Dict[str, Any]:
    kind = cfg.get("kind", "machine")
    if kind == "machine":
        return describe_machine(cfg)
    if kind == "cart":
        return describe_cart(cfg)
    if kind == "pallet":
        return describe_pallet(cfg)
    raise ValueError(f"未対応の kind: {kind}")


def world_geoms(desc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """ルート座標での geom 一覧（LOD0 はボディが回転しないので位置の足し算だけ）。"""
    origin = {}
    for bd in desc["bodies"]:
        base = origin[bd["parent"]] if bd["parent"] else [0.0, 0.0, 0.0]
        origin[bd["name"]] = add(base, bd["pos"])
    out = []
    for bd in desc["bodies"]:
        for g in bd["geoms"]:
            out.append({**g, "body": bd["name"], "pos": add(origin[bd["name"]], g["pos"])})
    return out
