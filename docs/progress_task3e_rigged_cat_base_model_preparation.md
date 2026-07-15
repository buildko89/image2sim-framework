# Task 3E: リグ付き猫ベースモデル準備 進捗

## 実施日

2026-06-22

## 目的

静的な3Dメッシュではなく、歩く、ジャンプする、寝るなどの動作を持たせられるリグ付きモデルの土台を準備する。

## 実施内容

1. Quaternius Ultimate Animated Animal Pack を取得した。
2. 配布ライセンスが CC0 1.0 Universal であることを確認した。
3. 猫そのものではないが、猫に近い四足動物の検証用ベースとして `Fox.gltf` を選択した。
4. Blender 5.0 CLI で `Fox.gltf` を読み込んだ。
5. Armature、mesh、animation clip を検査した。
6. `.blend`、`.glb`、`.fbx` を出力した。
7. 出力GLB内に skin と animation が残っていることを確認した。

## 成果物

- `output/rigged/cat_base_rigged.blend`
- `output/rigged/cat_base_rigged.glb`
- `output/rigged/cat_base_rigged.fbx`
- `output/reports/rigged_cat_base_model.json`
- `blender/prepare_rigged_base_model.py`

## 検査結果

- ベースモデル: Quaternius Ultimate Animated Animal Pack / Fox
- ライセンス: CC0 1.0 Universal
- mesh数: 2
- armature数: 1
- bone数: 51
- action数: 12
- GLB内のskin数: 1
- GLB内のanimation数: 12

確認できたアニメーション:

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

## 判断

Task 3E は完了とする。

このモデルは最終的な猫の見た目ではない。ただし、Blenderでリグ付き四足動物を読み込み、アニメーション付きGLB/FBXとして再出力できることを確認できたため、可動モデル化の土台としては成立した。

## 制約

- sleep / lie-down そのもののアニメーションは含まれていない。
- Foxベースのため、猫らしい体型や毛色は未反映。
- 本格的な原点、スケール、向きの正規化は Task 4 側で扱う。
- 猫らしい見た目への寄せ方は Task 3F で計画する。

## 次のTask

Task 3F: Appearance / Shape Transfer Planning

次は、実写真、マスク、Hunyuan3D生成メッシュを参照し、リグを壊さずに猫らしい見た目や体型へ近づける方法を計画する。
