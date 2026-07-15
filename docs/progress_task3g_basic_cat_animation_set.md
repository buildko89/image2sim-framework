# Task 3G: 基本猫アニメーションセット 進捗

## 実施日

2026-06-22

## 目的

Task 3Eで準備したリグ付きベースモデルに含まれるアニメーションを確認し、MVPで必要な基本動作へ割り当てる。

必要動作:

- Idle / stand
- Walk
- Jump または飛ぶような上下移動
- Sleep または lie-down

## 実施内容

1. `output/rigged/cat_base_rigged.glb` を検査対象にした。
2. GLB内のanimation、skin、meshを読み取る検査スクリプトを追加した。
3. 既存クリップをMVPの必要動作へ割り当てた。
4. sleep / lie-down の不足を確認し、一時代替候補を定義した。

## 成果物

- `scripts/03g_validate_basic_animation_set.py`
- `output/reports/task3g_basic_animation_set.json`
- `docs/progress_task3g_basic_cat_animation_set.md`

## 検査結果

- 入力: `output/rigged/cat_base_rigged.glb`
- animation数: 12
- skin数: 1
- mesh数: 1

検出したアニメーション:

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

## MVP動作への割り当て

| 必要動作 | 採用クリップ | 状態 |
| --- | --- | --- |
| Idle / stand | `Idle` | 利用可能 |
| Walk | `Walk` | 利用可能 |
| Jump | `Jump_ToIdle` | 利用可能 |
| Sleep / lie-down | `Eating` または `Idle_2_HeadLow` | 一時代替 |

## 判断

Task 3Gは、既存アニメーションセットの検査とMVP用の割り当てとして完了とする。

ただし、本物のsleep / lie-downアニメーションは未収録。MVPでは `Eating` または `Idle_2_HeadLow` を休憩風のプレースホルダーとして使い、後続でlie-down専用クリップを作るか、別途CC0/自作の動作を追加する。

## 次のTask

Task 4: Blender Rig Cleanup and Animation Export

次は、リグとアニメーションを保持したまま、ゲームエンジン向けにGLB/FBXを書き出す方針を整理し、Godot確認へ渡せる形にする。
