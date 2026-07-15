# Task 4: Blender Rig Cleanup and Animation Export 進捗

## 実施日

2026-06-22

## 目的

Task 3Eで準備したリグ付きベースモデルを、ゲームエンジン向けに正規化し、アニメーション付きGLB/FBXとして出力する。

## 実施内容

1. 静的メッシュ用ではなく、リグ付きモデル専用のBlender cleanup/exportスクリプトを追加した。
2. `output/rigged/cat_base_rigged.glb` を入力にした。
3. Armatureとmeshの関係を壊さないよう、ルートオブジェクト単位で保守的にスケール・原点調整を行った。
4. 高さ1.0に正規化し、床面をZ=0に合わせた。
5. `.blend`、`.glb`、`.fbx` を出力した。
6. 出力GLB内にanimation、skin、meshが残っていることを確認した。
7. Task 3Gの検査スクリプトで、clean済みGLBの基本アニメーションセットを再検査した。

## 追加したスクリプト

- `blender/rig_cleanup_export.py`
- `scripts/04_blender_rig_cleanup_export.py`

## 実行コマンド

```powershell
python scripts/04_blender_rig_cleanup_export.py
```

## 入力

- `output/rigged/cat_base_rigged.glb`

## 出力

- `output/clean_3d/cat_rigged_clean.blend`
- `output/clean_3d/cat_rigged_clean.glb`
- `output/clean_3d/cat_rigged_clean.fbx`
- `output/reports/task4_blender_rig_cleanup_export.json`
- `output/reports/task4_clean_animation_set_validation.json`

## 正規化結果

- target_height: 1.0
- scale_factor: 0.27615980026283976
- after_bbox_min: `[-0.2626439332962036, -0.7714062929153442, 0.0]`
- after_bbox_max: `[0.2626439332962036, 0.7714062929153442, 1.0]`
- after_size: `[0.5252878665924072, 1.5428125858306885, 1.0]`

## 検査結果

出力GLB:

- animation数: 12
- skin数: 1
- mesh数: 1

維持されたアニメーション:

- Attack
- Death
- Eating
- Gallop
- Gallop_Jump
- Idle
- Idle_2
- Idle_2_HeadLow
- Idle_HitReact1
- Idle_HitReact2
- Jump_ToIdle
- Walk

MVP動作への割り当て:

| 必要動作 | 採用クリップ | 状態 |
| --- | --- | --- |
| Idle / stand | `Idle` | 利用可能 |
| Walk | `Walk` | 利用可能 |
| Jump | `Jump_ToIdle` | 利用可能 |
| Sleep / lie-down | `Eating` または `Idle_2_HeadLow` | 一時代替 |

## 注意点

- 本物のsleep / lie-downアニメーションはまだない。
- `Eating` または `Idle_2_HeadLow` は休憩風の一時代替であり、最終的なsleepではない。
- 見た目はまだFoxベースで、猫らしい外観反映は未実施。
- Blender上の補助的な `Icosphere` はレポート上では残っているが、出力GLBのmesh数は1で、ゲームエンジン向けGLBには主メッシュのみが入っている。

## 判断

Task 4は完了とする。

リグ、skin、animationを保持したまま、ゲームエンジン向けのGLB/FBXを出力できた。次はGodotで `output/clean_3d/cat_rigged_clean.glb` を読み込み、表示とアニメーション再生を確認する。

## 次のTask

Task 5: Godot Animated Import Check
