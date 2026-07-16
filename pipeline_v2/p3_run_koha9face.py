"""koha9face（顔改善版）を1コマンドで通す。p3_run_koha9.py の face 変種。

    python pipeline_v2/p3_run_koha9face.py [--skip-capture]

p3_koha9.* / p3_koha9_* テクスチャは正典として触らず、p3_koha9face_* だけを出力する
（ユーザー指示のリスク回避。2026-07-12）。
koha9 との差分: 目（縮小・伏し目・青磁グリーン）と髭（白く細く・眉髭控えめ）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")

ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IN_BLEND = REPO / "output_v2/base/p2_koha.blend"
RGB = REPO / "output_v2/textures/p3_koha9face_basecolor.png"
RGBA = REPO / "output_v2/textures/p3_koha9face_basecolor_alpha.png"
FUR = REPO / "output_v2/textures/p3_koha9face_fur_shell.png"
OUT_BLEND = REPO / "output_v2/base/p3_koha9face.blend"
OUT_GLB = REPO / "output_v2/base/p3_koha9face.glb"

# face の髭: 実物（顔検討.png）は白く細く、眉の髭は控えめ
# 第2段階: 「もう少し細く」の指摘で 0.00055 -> 0.0004 (2026-07-15)
WHISKER_RADIUS = "0.0004"
WHISKER_COLOR = "0.95,0.94,0.92"
BROW_SCALE = "0.7"
# P4-尻尾: 「太い」の指摘で径 0.85 倍（実測 0.215×体長 -> 0.183。写真仕様 0.18）(2026-07-15)
TAIL_RADIUS_SCALE = "0.85"
# P4-尻尾: 長さ 1.3 倍（鎖 0.186 -> 0.242m = 0.69×体長。ユーザー承認 2026-07-15、見た目判断中）
TAIL_LENGTH_SCALE = "1.3"
# P4-胸: jump_left.gif で「顎下〜前脚間の胸が丸く張り出す」指摘。肩ライン(Y=-0.11)基準で
# 前胸の突出を半分に凹ませる（apex Y-0.204 -> -0.157。喉のくびれも生まれる）(2026-07-16)
CHEST_PULL = "0.5"
# P5: 胸を凹ませた分マズルが長く見える指摘（ユーザー 2026-07-16「1/3 くらい短く」）。
# 目の面(Y=-0.185)〜鼻先を一様圧縮（0.33 = 鼻先 14.4mm 後退）。頂点のみ移動・髭追従。
MUZZLE_PULL = "0.33"
# P4-1: Jump は 581f の複合シーケンス。跳躍コアだけ切り出す（ビート実測 2026-07-15）
JUMP_TRIM = ("397", "489")
# P4-2: ネコパンチ化（2026-07-16）。素の Atk は弱い「持ち上げ」なので前脚の振りをオーサリング
# （p4_punch_author）。前方へ突くとアッパーになる（ユーザー指摘）ため、猫本来の振り方に:
# Atk1=左手の上から下の振り下ろし、Atk2=右手の横フック（右→左）。手も振り方も変えて差別化
# （ユーザー決定 2026-07-16）。左右は --side、振り方は --mode で切替可。
ATK1_DOWN = ("-170", "-12", "-20", "1.4")   # raise_deg, strike_deg, fore_deg, speed
ATK2_HOOK = ("-92", "55", "-20", "1.5")     # lift_deg, sweep_deg, fore_deg, speed
# P4-3: Walk の尻尾を「?」形に（ユーザー要望 2026-07-15、適用 2026-07-16）。上半分(017-020)を
# 前方へ緩くアーチさせ先端を約100mm前へ出す（先端だけ強く巻くと軸線へ戻り読めない）。Walk のみ。
# 再生速度は「現状のままでOK」（ユーザー 2026-07-16）なので速度リタイムは無し。
TAIL_HOOK = ("20", "30", "34", "28")        # curl017, 018, 019, 020 (度, 前方)


def sh(cmd: list[str], label: str, keys: tuple[str, ...] = ()) -> None:
    print(f"\n=== {label} ===", flush=True)
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV)
    lines = p.stdout.splitlines()
    if keys:
        lines = [ln for ln in lines if any(k in ln for k in keys)]
    print("\n".join(lines[-24:]))
    if p.returncode != 0:
        print(p.stdout[-2500:])
        print(p.stderr[-2500:])
        raise SystemExit(f"{label} failed ({p.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-capture", action="store_true")
    a = ap.parse_args()

    sh([PY, str(REPO / "pipeline_v2/p3_paint_texture_koha9face.py")], "1/6 テクスチャ (face)",
       keys=("目", "->", "塗り替えた"))

    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3_apply_texture_blender.py"), "--",
        "--input", str(IN_BLEND), "--rgb", str(RGB), "--rgba", str(RGBA),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "2/6 モデルへ適用", keys=("[P3]", "Saved:", "Exported:", "rror"))

    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3c_add_whiskers_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--root-radius", WHISKER_RADIUS, "--color", WHISKER_COLOR, "--brow-scale", BROW_SCALE],
       "3/6 髭（白く細く）", keys=("[P3c]", "Saved:", "Exported:", "rror"))

    sh([PY, str(REPO / "pipeline_v2/p3_make_fur_alpha.py"),
        "--src", str(RGB), "--out", str(FUR)], "4/6 毛シェルのアルファ", keys=("cutoff", "->"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3d_fur_shells_blender.py"), "--",
        "--input", str(OUT_BLEND), "--fur", str(FUR),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "4.5/6 毛シェル生成", keys=("[P3d]", "FurShell", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3e_tail_densify_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "4.8/6 尻尾の高密度化", keys=("[P3e]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_tail_slim_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--radius-scale", TAIL_RADIUS_SCALE],
       "4.9/6 尻尾の細身化", keys=("[P4t]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_tail_lengthen_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--length-scale", TAIL_LENGTH_SCALE],
       "4.95/6 尻尾の伸長", keys=("[P4l]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_chest_dent_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--pull-frac", CHEST_PULL],
       "4.96/6 胸の凹ませ", keys=("[P4c]", "Saved:", "Exported:", "rror"))
    # P5: マズル短縮（胸凹ませ後の「口が長い」指摘対応）と、アニメ時の顔・胸の破綻対策
    # （顔=neck1/head 均一混合化・腕ウェイト除去、前胸=head 支配を首根・胴へ移譲）。
    # どちらも座標フィールドベースで body/髭/毛シェルに同一変換（2026-07-16）。
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p5_muzzle_shorten_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--pull-frac", MUZZLE_PULL],
       "4.962/6 マズル短縮", keys=("[P5mz]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p5_face_weight_fix_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "4.965/6 顔・胸ウェイト整理", keys=("[P5fw]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4a_trim_action_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--action", "Armature|Jump", "--start", JUMP_TRIM[0], "--end", JUMP_TRIM[1]],
       "4.97/6 Jump 切り出し", keys=("[P4a]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_punch_author_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--action", "Armature|Atk1", "--side", "l", "--mode", "downward",
        "--raise-deg", ATK1_DOWN[0], "--strike-deg", ATK1_DOWN[1],
        "--fore-deg", ATK1_DOWN[2], "--speed", ATK1_DOWN[3]],
       "4.98/6 ネコパンチ Atk1（振り下ろし）", keys=("[P4pa]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_punch_author_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--action", "Armature|Atk2", "--side", "r", "--mode", "hook",
        "--lift-deg", ATK2_HOOK[0], "--sweep-deg", ATK2_HOOK[1],
        "--fore-deg", ATK2_HOOK[2], "--speed", ATK2_HOOK[3]],
       "4.99/6 ネコパンチ Atk2（右手・横フック）", keys=("[P4pa]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_tail_hook_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--action", "Armature|Walk", "--curl017", TAIL_HOOK[0], "--curl018", TAIL_HOOK[1],
        "--curl019", TAIL_HOOK[2], "--curl020", TAIL_HOOK[3]],
       "4.995/6 Walk 尻尾の?フック", keys=("[P4th]", "Saved:", "Exported:", "rror"))
    # P4-4: 新規アクション 香箱座り(Loaf)・お座り(Sit)。レストから骨を回してポーズ化し呼吸で
    # ループ。ポーズは JSON。※rig 制約（前脚が首の子＋短い）で背筋を立てた座りは前足が浮くため、
    # Sit は頭を上げたコンパクト座り（前足接地は簡略。ユーザー承認 2026-07-16）。
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_pose_action_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--pose-json", str(REPO / "pipeline_v2/p4_pose_loaf.json"), "--action", "Armature|Loaf"],
       "4.996/6 香箱座り(Loaf)", keys=("[P4po]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_pose_action_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--pose-json", str(REPO / "pipeline_v2/p4_pose_sit.json"), "--action", "Armature|Sit"],
       "4.997/6 お座り(Sit)", keys=("[P4po]", "Saved:", "Exported:", "rror"))

    print("\n=== 5/6 機械ゲート ===", flush=True)
    rc = subprocess.run([PY, str(REPO / "pipeline_v2/qa_skin_stretch.py"),
                         "--glb", str(OUT_GLB),
                         "--json", str(REPO / "output_v2/reports/qa_skin_p3_koha9face.json")],
                        cwd=REPO, text=True).returncode
    rc2 = subprocess.run([PY, str(REPO / "pipeline_v2/qa_belly_bind.py"),
                          "--glb", str(OUT_GLB)],
                         cwd=REPO, text=True).returncode

    if not a.skip_capture:
        sh([PY, str(REPO / "pipeline_v2/p1_capture.py"), "--glb", str(OUT_GLB),
            "--prefix", "p3k9f", "--res", "1440"],
           "6/6 コンタクトシート (1440px)", keys=("SHOTS", "HEADSHOTS", "->"))
    return rc or rc2


if __name__ == "__main__":
    raise SystemExit(main())
