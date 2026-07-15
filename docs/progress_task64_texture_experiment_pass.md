# Task 6.4: Texture Experiment Pass 進捗

## 実施日

2026-06-30

## 目的

Task 6.3の調査で、フラットマテリアル色の微調整ではGodot上の見た目差分がほぼ出ないことが分かった。

そこで、次の段階として、既存可動モデルにUVとbase color textureを追加し、texture系の処理が見た目改善に効くかを検証する。

このTaskは、本格的なTripo texture transferではない。まず、Frameworkで「UV追加、texture生成、GLB埋め込み、Godot表示」まで通るかを確認する実験。

## 入力

- `output/rigged/cat_tripo_reference_visual_pass.blend`

## 実装ファイル

- `blender/cat_texture_experiment_pass.py`
- `scripts/064_cat_texture_experiment_pass.py`

## 生成テクスチャ

Pillowで毛流れ風のPNG textureを生成した。

- `output/textures/task64_cat_texture_experiment/white_fur.png`
- `output/textures/task64_cat_texture_experiment/warm_calico_fur.png`
- `output/textures/task64_cat_texture_experiment/dark_calico_fur.png`
- `output/textures/task64_cat_texture_experiment/cream_shadow_fur.png`

## 出力

- `output/rigged/cat_texture_experiment_pass.blend`
- `output/clean_3d/cat_texture_experiment_pass.glb`
- `output/clean_3d/cat_texture_experiment_pass.fbx`
- `output/godot/cat_texture_experiment_pass.glb`
- `godot/Godot3dcat/cat_texture_experiment_pass.glb`
- `output/reports/task64_cat_texture_experiment_pass.json`
- `output/reports/task64_cat_texture_experiment_pass_plan.json`
- `output/reports/task64_cat_texture_experiment_glb_inspection.json`
- `output/reports/task64_cat_texture_experiment_animation_validation.json`
- `output/reports/task64_cat_texture_experiment_side_preview.png`
- `output/reports/task64_cat_texture_experiment_front_preview.png`
- `output/reports/task64_vs_fluffy_side_diff_x5.png`

Godot review scene:

- `godot/Godot3dcat/MainAppearance.tscn` を `res://cat_texture_experiment_pass.glb` 参照へ変更。
- UID固定による取り違えを避けるため、`ext_resource` はpath指定にした。
- `force_cat_materials = false` を維持。

## 実施内容

1. skinned meshとfur shellに `TextureUV` を追加した。
2. Blender `smart_project` でUVを自動生成した。
3. 4つの主要マテリアルへbase color textureを接続した。
4. GLBにtextureを埋め込んでexportした。
5. skin、animation、armatureが維持されているか検証した。

## 検証結果

`output/clean_3d/cat_texture_experiment_pass.glb`:

- material数: 4
- mesh数: 2
- skin数: 1
- animation数: 12
- 全4 materialで `has_base_color_texture = true`
- main mesh / fur shell の全primitiveに `TEXCOORD_0` あり
- `Idle`: available
- `Walk`: available
- `Jump_ToIdle`: available

## 目視結果

Task 6.3より明確に色と質感が変わった。

ただし、今回のtextureは自動生成した汎用毛流れ風PNGであり、実猫写真やTripo textureを直接投影したものではない。そのため、毛流れ方向や柄の自然さには限界がある。

## 判断

Texture系の経路は成立した。

今回分かったこと:

- UV追加とbase color texture埋め込みは可能。
- GLB export後もskin/animationを維持できる。
- Godotで見た目差分を出すには、フラットマテリアルではなくtextureが必要。

次の課題:

- Smart UV + 汎用fur textureでは、実猫らしい毛流れにはまだ届かない。
- 次に進むなら、実画像またはTripo v2.5 textureを使ったprojection / bake / retextureを検討する。

## 次の確認

Godotで `MainAppearance.tscn` を開き、以下を確認する。

- 新GLBが読み込まれているか。
- textureの毛流れ風パターンが表示されるか。
- `Walk` でtextureやfur shellが破綻しないか。
- 今回のtexture実験が、前版より見た目改善として意味があるか。
