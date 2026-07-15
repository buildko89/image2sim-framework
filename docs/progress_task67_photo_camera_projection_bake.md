# Task 6.7: Photo Camera Projection Bake

## 目的

実写真からのcamera projection bakeを試し、Textureだけで毛並み、やわらかさ、ポリゴン感の軽減がどこまで可能かを確認する。

## 実施内容

Blender内で既存リグ付き猫メッシュにUVを作成し、3D座標を写真へ投影してtextureを生成した。

使用した投影元:

- side: `input/masks/reference_side_standing_pattern_1713434749448_cutout.png`
- front: `input/masks/reference_front_face_1763363798733_cutout.png`
- back: `input/masks/reference_back_top_tail_1755598074234_cutout.png`

追加で比較用として、ユーザー提供の`input/raw_photos/横.png`をside投影に使うraw side版も作成した。

## 追加ファイル

- `blender/cat_photo_camera_projection_bake_pass.py`
- `scripts/067_cat_photo_camera_projection_bake_pass.py`
- `output/rigged/cat_photo_camera_projection_bake_pass.blend`
- `output/clean_3d/cat_photo_camera_projection_bake_pass.glb`
- `output/clean_3d/cat_photo_camera_projection_bake_pass.fbx`
- `output/textures/task67_cat_photo_camera_projection_bake/Fox_photo_camera_projection.png`
- `output/textures/task67_cat_photo_camera_projection_bake/PhotoCat_Fur_Shell_photo_camera_projection.png`
- `output/reports/task67_cat_photo_camera_projection_bake_side_preview.png`
- `output/reports/task67_cat_photo_camera_projection_bake_front_preview.png`
- `output/reports/task67_cat_photo_camera_projection_bake_pass.json`

比較用raw side版:

- `output/clean_3d/cat_photo_camera_projection_bake_raw_side_pass.glb`
- `output/reports/task67b_cat_photo_camera_projection_bake_raw_side_side_preview.png`
- `output/reports/task67b_cat_photo_camera_projection_bake_raw_side_front_preview.png`
- `output/reports/task67b_cat_photo_camera_projection_bake_raw_side_pass.json`

## 検証結果

通常版:

- mesh: 2
- material: 2
- skin: 1
- animation: 12
- base color texture: あり
- `TEXCOORD_0`: あり
- animation validation:
  - animations: 12
  - available motions: 3
  - fallback motions: 1
  - missing motions: 0

raw side版も同様に、GLB構造とアニメーションは維持できた。

## 見た目評価

結論として、camera projection bake単体では今回の目的には届かなかった。

確認できたこと:

- 実写真からtextureを生成してGLBへ入れる経路は作れた。
- Godotで確認できる形のGLBとして出力できた。
- animation / skin は維持できた。

届かなかったこと:

- 毛並みのやわらかさは出ない。
- ポリゴン面の硬さは残る。
- 三毛柄の大きな色配置は弱い。
- 写真の毛流れは、低ポリメッシュの面単位表示に分断される。

主因:

- 現在の猫モデルは低ポリで、面の形状がはっきり見える。
- UV islandが細かく分かれるため、写真の連続した毛流れが切れる。
- 実写真の猫姿勢と既存リグ付きメッシュの形状が一致していない。
- textureだけでは、毛量・輪郭のふわっとしたシルエット・毛束の立体感は表現できない。

## Godot確認対象

`godot/Godot3dcat/MainAppearance.tscn`は以下を参照するように更新済み。

```text
res://cat_photo_camera_projection_bake_pass.glb
```

## 結論

今回の検証で、texture projection系は「色を貼る」ことはできるが、「ふわふわ感」「自然な毛並み」「低ポリ感の解消」には不十分だと判断する。

次は別の手立てを検討するのが妥当。

候補:

1. Hunyuan3Dなどで、より高密度・毛並み込みの見た目を生成する。
2. Blender側でfur shell / hair card / particle hair相当を作り、シルエットと毛流れを足す。
3. 既存リグを維持する場合は、低ポリ本体に頼らず、外側に毛並み用の追加メッシュを載せる。

現実的には、次の検証は「AI生成メッシュまたはAI生成texture + 追加fur表現」に進むべき。
