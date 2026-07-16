# -*- coding: utf-8 -*-
"""P5: アニメ時の顔・胸の破綻対策（ウェイト整理）。

診断（2026-07-16）で判明した根因:
  - この rig は顔上半分= neck1 支配（眉 0.83）、顎〜前胸= head 支配（0.75-0.82）で、
    目・マズルの高さが 50/50 の遷移帯。head と neck1 の回転がずれる姿勢
    （Idle1 の見下ろし・Walkback の首振り）で顔がねじれて潰れる。
  - 眉に bip01_r_clavicle / 両 upperarm のウェイトが少量・非対称に混入しており、
    歩行で顔が左右非対称に歪む（Walkback）。
  - 前胸（Z<0.13 の前面帯）は head 0.75-0.82 で頭に追従するため、
    伸び上がり（Idle2）で胸が膨らむ/折れる。

対処（すべて座標フィールドベース = body と毛シェルに同一変換 → 毛は浮かない）:
  A) 顔領域（y < FACE_Y1, z > FACE_Z0, ランプ帯 FACE_Y0..FACE_Y1）の全頂点を
     「neck1/head の均一混合」に統一（領域実測の平均比を使用）。他ボーン
     （neck, clavicle, arm 等）の混入は 0 に。顔全体が1つの剛体のように動き、
     ねじれ・非対称が消える。Whiskers も同じ処理（顔から剥離させない）。
  B) 前胸領域（y < CHEST_Y, z < CHEST_Z1, ランプ）で head+neck1 ウェイトの
     一部を首の付け根（bip01_neck, z>=CHEST_SPLIT）と胴（koha_belly_front,
     z<CHEST_SPLIT）へ移譲。胸が頭でなく胴に付いて動くようになる。

検証済み（2026-07-16 テストコピー）: ゲート2本 PASS、Idle1 顔つぶれ解消・
Idle2 胸の膨らみ軽減・Walkback 顔非対称解消を strips 目視で確認。
"""
import argparse
import sys
from pathlib import Path

import bpy

# ---- 領域パラメータ（Blender world: Y=前(-), Z=上, X=左右）----
FACE_Y1 = -0.165   # ここより前は顔（t=1）
FACE_Y0 = -0.145   # ここより後ろは無変更（t=0）。間は線形ランプ
FACE_Z0 = 0.14     # 顎下より上だけ（胸は B で扱う）

CHEST_Y = -0.105     # 肩ラインより前
CHEST_Z1 = 0.13      # ここより上は無変更（顎・喉は顔側）
CHEST_Z_FULL = 0.07  # ここ以下で移譲率が最大
CHEST_MAX_SHIFT = 0.7  # head+neck1 のうち移譲する最大割合
CHEST_SPLIT = 0.09   # 移譲先: これ以上 z → bip01_neck / 未満 → koha_belly_front
CHEST_X = 0.09

SRC_FACE = ("bip01_neck1", "bip01_head")
NECK_BONE = "bip01_neck"
BELLY_BONE = "koha_belly_front"

FACE_MESHES = ("Koha9", "Whiskers")
CHEST_MESHES = ("Koha9", "FurShell1", "FurShell2", "FurShell3", "FurShell4")


def log(msg: str) -> None:
    print("[P5fw] " + msg, flush=True)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    return p.parse_args(argv)


def get_weights(v, gnames):
    return {gnames[g.group]: g.weight for g in v.groups if g.weight > 0.0}


def set_weight(ob, name, idx, value):
    vg = ob.vertex_groups.get(name)
    if vg is None:
        vg = ob.vertex_groups.new(name=name)
    if value <= 0.0:
        try:
            vg.remove([idx])
        except RuntimeError:
            pass
    else:
        vg.add([idx], value, "REPLACE")


def face_target_mix(body):
    """顔領域（t=1 の帯）の neck1/head 実測平均 → 均一混合比。"""
    gnames = [g.name for g in body.vertex_groups]
    mw = body.matrix_world
    s1 = sh = 0.0
    n = 0
    for v in body.data.vertices:
        c = mw @ v.co
        if c.y < FACE_Y1 and c.z > FACE_Z0:
            ws = get_weights(v, gnames)
            s1 += ws.get(SRC_FACE[0], 0.0)
            sh += ws.get(SRC_FACE[1], 0.0)
            n += 1
    tot = s1 + sh
    if n == 0 or tot <= 0.0:
        raise RuntimeError("face region empty")
    mix = (s1 / tot, sh / tot)
    log(f"face region verts={n} target mix neck1={mix[0]:.3f} head={mix[1]:.3f}")
    return mix


def fix_face(ob, mix):
    gnames = [g.name for g in ob.vertex_groups]
    mw = ob.matrix_world
    touched = 0
    for v in ob.data.vertices:
        c = mw @ v.co
        if c.z <= FACE_Z0 or c.y >= FACE_Y0:
            continue
        t = min(1.0, (FACE_Y0 - c.y) / (FACE_Y0 - FACE_Y1))
        ws = get_weights(v, gnames)
        total = sum(ws.values())
        if total <= 0.0:
            continue
        # 目標: neck1/head の均一混合（合計は元の総和を保存）
        tgt = {SRC_FACE[0]: mix[0] * total, SRC_FACE[1]: mix[1] * total}
        names = set(ws) | set(tgt)
        for name in names:
            new = (1.0 - t) * ws.get(name, 0.0) + t * tgt.get(name, 0.0)
            if abs(new - ws.get(name, 0.0)) > 1e-6:
                set_weight(ob, name, v.index, new)
        touched += 1
    log(f"{ob.name}: face verts adjusted {touched}")


def fix_chest(ob):
    gnames = [g.name for g in ob.vertex_groups]
    mw = ob.matrix_world
    touched = 0
    for v in ob.data.vertices:
        c = mw @ v.co
        if not (c.y < CHEST_Y and 0.0 <= c.z < CHEST_Z1 and abs(c.x) < CHEST_X):
            continue
        f = CHEST_MAX_SHIFT * min(
            1.0, max(0.0, (CHEST_Z1 - c.z) / (CHEST_Z1 - CHEST_Z_FULL)))
        if f <= 0.0:
            continue
        ws = get_weights(v, gnames)
        pool = ws.get(SRC_FACE[0], 0.0) + ws.get(SRC_FACE[1], 0.0)
        if pool <= 0.0:
            continue
        moved = pool * f
        dst = NECK_BONE if c.z >= CHEST_SPLIT else BELLY_BONE
        for name in SRC_FACE:
            w0 = ws.get(name, 0.0)
            if w0 > 0.0:
                set_weight(ob, name, v.index, w0 * (1.0 - f))
        set_weight(ob, dst, v.index, ws.get(dst, 0.0) + moved)
        touched += 1
    log(f"{ob.name}: chest verts adjusted {touched}")


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)
    log(f"face window y<{FACE_Y1}(ramp {FACE_Y0}) z>{FACE_Z0} / "
        f"chest y<{CHEST_Y} z<{CHEST_Z1} shift{CHEST_MAX_SHIFT}")

    body = bpy.data.objects.get("Koha9")
    if body is None:
        raise RuntimeError("body mesh 'Koha9' not found")
    mix = face_target_mix(body)

    for name in FACE_MESHES:
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.vertex_groups:
            fix_face(ob, mix)
        else:
            log(f"{name}: skipped (missing or no groups)")
    for name in CHEST_MESHES:
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.vertex_groups:
            fix_chest(ob)
        else:
            log(f"{name}: skipped (missing or no groups)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
