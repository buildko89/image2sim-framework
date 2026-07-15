# Cat Procedural Texture Pipeline Plan

## レビュー反映方針

`docs/review_cat_texture_library_pipeline.md` の指摘を受けて、当初の「写真から複数の tileable baseColor 画像を生成する texture library」計画は撤回する。

撤回理由:

- Task 64 で、Pillow による毛並み風テクスチャ生成、UV適用、GLB埋め込み、Godot表示まで検証済み。
- 固定カテゴリのテクスチャを増やしても、Task 64 の繰り返しになりやすい。
- 写真の色クラスタとランダムノイズだけでは、毛流れ、三毛柄の境界、密度感を表現しにくい。
- 座標ベースの三毛柄配置は `blender/apply_calico_texture.py` の `get_calico_color()` で既に実装済み。

改訂後は、写真から抽出するものを「テクスチャ画像」ではなく「色パレット」に絞る。見た目の生成は Blender の procedural shader と bake で行う。

## 改訂後の目的

猫写真から抽出した色パレットを入力にして、Blender 内で三毛猫向け procedural material を構築し、UVへ bake した baseColor texture を生成する。

重視すること:

- 既存コード資産を再利用する。
- 写真由来の色を反映する。
- 毛流れ方向、斑模様、尻尾縞を procedural に調整できるようにする。
- 現在のリグ付き猫モデルと `koha9_cat` 参考モデルの両方に適用できるようにする。
- Godot で `force_cat_materials = false` のまま表示できる GLB を出力する。

## 全体フロー

```text
input/masks/*_cutout.png
  -> scripts/080_extract_cat_color_palette.py
  -> config/cat_color_palette.yaml
  -> output/reports/task80_cat_color_palette_preview.png

config/cat_color_palette.yaml
  + blender/cat_procedural_texture.py
  -> procedural material
  -> UV bake
  -> output/textures/cat_procedural_bake/
  -> output/rigged/
  -> output/clean_3d/
  -> godot/Godot3dcat/
```

## 参考モデル調査結果

`input/cat2/koha9_cat/` は次の構成になっている。

```text
input/cat2/koha9_cat/
  scene.gltf
  scene.bin
  license.txt
  textures/
    Koha9Tail_baseColor.png
    Koha9Body_baseColor.png
```

確認した特徴:

- glTF は2マテリアル構成。
- 画像は baseColor 2枚。
- テクスチャ解像度は 4096x4096。
- normal map、roughness map、metallic map は使っていない。

このため、初期実装では procedural material を最終的に baseColor texture へ bake する。PBR一式は後回しにする。

## 既存コード再利用

| 既存ファイル | 再利用する内容 |
|---|---|
| `blender/apply_calico_texture.py` | `get_calico_color()` の座標ベース部位分け、Smart UV Project、Cycles Emit bake、GLB/FBX export |
| `blender/cat_texture_experiment_pass.py` | UV追加、テクスチャ接続、skinned mesh / armature の選択 export |
| `scripts/072_apply_calico_texture.py` | Windows Blender 呼び出し、出力パス設計、Godot staging |
| `blender/render_glb_preview.py` | front / side preview render |

## Task 80: Cat Color Palette Extraction

### 目的

`input/masks/*_cutout.png` から、三毛猫 procedural shader の入力に使う色パレットを抽出する。

テクスチャ画像は生成しない。Task 80 の責務は「色を決めること」だけに限定する。

### 追加ファイル

```text
scripts/080_extract_cat_color_palette.py
```

### 入力

```text
input/masks/*_cutout.png
```

### 出力

```text
config/cat_color_palette.yaml
output/reports/task80_cat_color_palette.json
output/reports/task80_cat_color_palette_preview.png
```

### 処理内容

1. `input/masks/*_cutout.png` を走査する。
2. alpha が有効なピクセルだけを収集する。
3. alpha 境界付近、極端な影、白飛び、低彩度の背景混入候補を除外する。
4. K-means または同等の軽量クラスタリングで 5 から 8 色を抽出する。
5. 明度と彩度で `dark`, `warm_brown`, `cream`, `white`, `accent` などの候補ラベルを付ける。
6. YAML、JSON report、preview image を出力する。

### YAML例

```yaml
palette:
  - name: white
    rgb: [0.95, 0.94, 0.91]
    usage: chest, belly, paws
  - name: cream
    rgb: [0.86, 0.77, 0.66]
    usage: body_base, shadow
  - name: warm_brown
    rgb: [0.68, 0.32, 0.08]
    usage: calico_patch, ears, back
  - name: dark
    rgb: [0.09, 0.07, 0.06]
    usage: calico_patch, tail_stripe
source_images:
  - input/masks/reference_side_right_body_1698975320501_cutout.png
num_colors: 6
seed: 0
```

### 実装メモ

- `PyYAML`, `Pillow`, `numpy` は既に `requirements.txt` にある。
- scikit-learn は追加しない。K-means が必要なら NumPy で小さく実装する。
- preview は、元画像サムネイル、抽出色スウォッチ、使用候補ラベルを並べる。
- 固定色 fallback を持つ。入力画像が足りない場合でも Task 81 を動かせるようにする。

### 完了条件

- `config/cat_color_palette.yaml` が生成される。
- 5色以上の有効な色候補がある。
- preview で写真由来の色として妥当か確認できる。
- 同じ入力と seed で再現可能。

## Task 81: Procedural Cat Texture Bake and Application

### 目的

Task 80 のパレットを使い、Blender 内で procedural material を構築して、現在のリグ付き猫モデルへ適用する。最終的には bake 済み baseColor texture を GLB に含める。

### 追加ファイル

```text
scripts/081_apply_procedural_cat_texture.py
blender/cat_procedural_texture.py
```

### 入力

```text
config/cat_color_palette.yaml
output/rigged/cat_animated.blend
```

既存の最新リグ付き cat blend が別名の場合は CLI 引数で指定する。

### 出力

```text
output/textures/cat_procedural_bake/
  cat_body_basecolor.png
  cat_fur_shell_basecolor.png
  bake_manifest.json
  shader_preview.png

output/rigged/cat_procedural_texture_pass.blend
output/clean_3d/cat_procedural_texture_pass.glb
output/clean_3d/cat_procedural_texture_pass.fbx
output/reports/task81_procedural_texture_pass.json
output/reports/task81_procedural_texture_front_preview.png
output/reports/task81_procedural_texture_side_preview.png

godot/Godot3dcat/cat_procedural_texture_pass.glb
```

### Blender処理内容

1. 入力モデルを開く。
2. skinned mesh と armature を検出する。
3. 既存UVを確認する。UVがない場合だけ Smart UV Project を実行する。
4. `config/cat_color_palette.yaml` を読む。
5. procedural material を構築する。
6. Object 座標または Generated 座標で、背中、腹、顔左右、尻尾を大まかに分ける。
7. Noise / Wave / ColorRamp / Mix 系ノードで毛流れと三毛斑を作る。
8. Fur shell は本体より明るく、低コントラストにする。
9. Cycles Emit bake で baseColor texture を出力する。
10. bake 済み画像を最終 material の Base Color へ接続する。
11. Blend、GLB、FBX を出力する。
12. Godot project へ GLB を配置する。

### Procedural material の設計

初期実装では、完全なノード自動生成にこだわりすぎない。安定性を優先し、必要なら CPU 側で vertex color / image bake を併用する。

推奨構成:

- `white`: 胸、腹、足先。
- `cream`: 体のベース、白毛の影。
- `warm_brown`: 背中、耳、腰、顔片側。
- `dark`: 黒斑、顔片側、尻尾縞。
- `accent`: 必要に応じて境界や影に使用。

パターン:

- 顔は左右で `warm_brown` と `dark` を分け、鼻筋は `white` を残す。
- 背中と腰は大きめの三毛斑にする。
- 腹側は `white` または `cream` を優先する。
- 尻尾は座標方向に沿った縞を入れる。
- 毛流れは Wave texture 相当の方向性ノイズを使う。

### 既存実装からの差分

`apply_calico_texture.py` は固定色をコード内に持っている。Task 81 では以下を変更する。

- 固定色を `config/cat_color_palette.yaml` から読み込む。
- 色配置パラメータを report に保存する。
- bake texture を body と fur shell で分ける。
- procedural shader または vertex color bake を再利用可能な関数に分ける。
- `koha9_cat` など別モデルにも同じ shader 設計を適用できるよう CLI 化する。

### CLI目標

```powershell
python scripts/081_apply_procedural_cat_texture.py `
  --input output/rigged/cat_animated.blend `
  --palette config/cat_color_palette.yaml `
  --texture-dir output/textures/cat_procedural_bake `
  --output-blend output/rigged/cat_procedural_texture_pass.blend `
  --output-glb output/clean_3d/cat_procedural_texture_pass.glb `
  --output-fbx output/clean_3d/cat_procedural_texture_pass.fbx `
  --resolution 2048
```

### 完了条件

- palette の色が procedural material に反映される。
- 2048x2048 の bake 済み baseColor texture が生成される。
- GLB/FBX 出力後も animation clip が残る。
- Godot で `force_cat_materials = false` のまま表示される。
- front / side preview で、三毛猫として読める。
- report に palette、bake解像度、対象mesh、material、animation数が記録される。

## Task 82: Koha9 Reference Check

### 位置づけ

独立した大きな実装タスクにはしない。Task 81 の汎用性チェックとして扱う。

### 目的

`input/cat2/koha9_cat/scene.gltf` にも同じ procedural bake 方針を適用できるか確認する。

### 入力

```text
input/cat2/koha9_cat/scene.gltf
config/cat_color_palette.yaml
```

### 出力

```text
output/clean_3d/koha9_procedural_texture_pass.glb
output/reports/task82_koha9_procedural_texture_pass.json
output/reports/task82_koha9_procedural_texture_preview.png
```

### 完了条件

- 元の `input/cat2/koha9_cat/` 配下を変更しない。
- 既存2マテリアル構成を破壊せず、別出力として確認できる。
- ライセンス上、元テクスチャを素材として直接再利用していないことが report に残る。

## Task 83: Godot Review

### 位置づけ

独立タスクではなく Task 81 の完了条件に含める。ただし、Godot確認で問題が出た場合は後続の修正タスクとして切り出す。

### 確認項目

- `godot/Godot3dcat/cat_procedural_texture_pass.glb` が読み込める。
- `force_cat_materials = false` で GLB 内 material が見える。
- Idle / Walk / Jump / lie-down 代替 animation が再生できる。
- texture が黒つぶれ、白飛び、過剰ノイズになっていない。
- fur shell が濃すぎない。

## 実装順序

1. `scripts/080_extract_cat_color_palette.py` を実装する。
2. `config/cat_color_palette.yaml` と palette preview を確認する。
3. `blender/cat_procedural_texture.py` を、`apply_calico_texture.py` から派生して作る。
4. `scripts/081_apply_procedural_cat_texture.py` を作り、Blender background 実行を包む。
5. 現在のリグ付き猫モデルで bake / export / preview / Godot staging まで通す。
6. `koha9_cat` へ同じ処理を適用し、別GLBとして出力する。
7. レポートを見て、色、斑の大きさ、毛流れ強度、fur shell 明度を調整する。

## 最初のコマンド目標

```powershell
python scripts/080_extract_cat_color_palette.py `
  --input-dir input/masks `
  --output config/cat_color_palette.yaml `
  --num-colors 6 `
  --seed 0
```

その後:

```powershell
python scripts/081_apply_procedural_cat_texture.py `
  --input output/rigged/cat_animated.blend `
  --palette config/cat_color_palette.yaml `
  --resolution 2048
```

## 技術判断

### 写真からは色だけを取る

写真から直接 texture を作ろうとすると、背景混入、解像度、姿勢、毛流れ方向の問題が残る。初期実装では写真は palette source に限定する。

### 見た目は Blender procedural で作る

毛流れや斑模様は、Blender の Noise / Wave / ColorRamp / Mix 系の処理で作る。これにより、解像度やモデルごとの bake に柔軟に対応できる。

### bake 済み baseColor を最終成果物にする

Godot / GLB での安定性を優先し、最終 material は bake 済み image texture を Base Color に接続する。Blender procedural node tree をそのまま runtime に持ち込むことは主目的にしない。

### PBR拡張は後回し

`koha9_cat` も baseColor のみで成立しているため、normal / roughness / AO は MVP 後に検討する。

## リスクと対策

### パレット抽出が写真の影に引っ張られる

対策:

- alpha 境界と極端な暗部を除外する。
- previewで確認する。
- fallback palette を用意する。

### Blender node 自動生成が複雑になりすぎる

対策:

- 最初は `get_calico_color()` ベースの CPU color attribute bake を残す。
- shader node 化は段階的に進める。
- report に使用モードを記録する。

### 別モデルで座標軸が合わない

対策:

- CLI で front/up/body axis を指定できるようにする。
- `koha9_cat` で検証する。
- 将来 `config/cat_texture_profiles/*.yaml` を導入する。

### fur shell が不自然に濃くなる

対策:

- shell 用 palette は body より明るく、低彩度に補正する。
- shell texture は低コントラストにする。
- 必要なら shell には模様を入れず body texture の薄い版だけを使う。

## MVP完了条件

- `config/cat_color_palette.yaml` が写真から生成される。
- 現在のリグ付き猫モデルへ procedural bake texture が適用される。
- GLB/FBX 出力後も animation が維持される。
- Godot で texture 付きモデルを表示し、主要 animation を再生できる。
- `koha9_cat` にも別出力として同じ palette / bake 方針を適用できる。
- report に入力、palette、bake設定、出力、既知の制約が残る。

## 後回しにすること

- 写真から直接 tileable fur texture を生成する方式。
- 固定7カテゴリの texture library 方式。
- 完全自動の顔・胴体・脚・尻尾セグメンテーション。
- 写真とモデルの厳密なカメラキャリブレーション。
- 物理ベースの毛皮 normal map 生成。
- roughness / ambient occlusion / subsurface などの PBR 拡張。
- 既存 `koha9_cat` テクスチャの素材としての直接再利用。
