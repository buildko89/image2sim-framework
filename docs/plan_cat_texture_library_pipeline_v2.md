# Cat Palette Driven Vertex Bake Pipeline Plan

## 位置づけ

この再プランは `docs/review_cat_texture_library_pipeline_v2.md` の再レビュー結果を反映した実装計画である。

前版 `docs/plan_cat_texture_library_pipeline.md` の方向性は維持するが、初期実装の主経路を明確に変更する。

- 採用する: 写真から色パレットを抽出する。
- 採用する: `get_calico_color()` を拡張した vertex color bake を主経路にする。
- 採用する: bake 済み baseColor texture を GLB に入れる。
- 後回しにする: Blender shader node の複雑な自動構築。
- 後回しにする: 写真から直接 tileable fur texture を生成する方式。

## 結論

初期実装は **palette driven vertex color bake** とする。

Blender の shader node を Python で20から30個自動生成する実装は、Blender バージョン差、ソケット名、ノードリンク、デバッグ負荷のリスクが高い。既に `blender/apply_calico_texture.py` で `vertex color -> Cycles Emit bake -> GLB export` の経路が成立しているため、これを拡張する。

## 全体フロー

```text
input/masks/*_cutout.png
  -> scripts/080_extract_cat_color_palette.py
  -> config/cat_color_palette.yaml
  -> output/reports/task80_cat_color_palette_preview.png

config/cat_color_palette.yaml
  + blender/cat_palette_vertex_bake.py
  -> palette driven get_procedural_calico_color()
  -> vertex color assignment
  -> Cycles Emit bake
  -> baked baseColor PNG
  -> GLB / FBX export
  -> Godot staging
```

## 既存コード再利用

| 既存ファイル | 再利用する内容 |
|---|---|
| `blender/apply_calico_texture.py` | `get_calico_color()`、Smart UV Project、Color Attribute 作成、Cycles Emit bake、final material、GLB/FBX export |
| `scripts/072_apply_calico_texture.py` | Windows Blender 呼び出し、出力パス、Godot staging |
| `blender/cat_texture_experiment_pass.py` | skinned mesh / armature 検出、UV確認、選択 export の考え方 |
| `blender/render_glb_preview.py` | front / side preview render |

既存ファイルは原則変更しない。新規ファイルを作り、既存実装を参照または派生する。

## Task 80: Cat Color Palette Extraction

### 目的

`input/masks/*_cutout.png` から、三毛猫カラー関数の入力に使う色パレットを抽出する。

Task 80 はテクスチャ画像を生成しない。責務は色パレット生成、preview、report に限定する。

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
3. alpha 境界付近、極端な暗部、白飛び、背景混入候補を除外する。
4. NumPy 実装の軽量 K-means または量子化で 5 から 8 色を抽出する。
5. 明度、彩度、色相から候補ラベルを付ける。
6. 不足ラベルは fallback palette で補完する。
7. YAML、JSON report、preview image を出力する。

### Fallback Palette

入力画像が不足した場合、またはクラスタリング結果に必要色が出ない場合は次の値を使う。

この値は `blender/apply_calico_texture.py` の既存固定色に意図的に近づける。既存結果との A/B 比較をしやすくするため。

```yaml
palette:
  - name: white
    rgb: [0.95, 0.94, 0.91]
    usage: chest, belly, paws, nose_bridge
  - name: cream
    rgb: [0.86, 0.77, 0.66]
    usage: body_base, soft_shadow
  - name: warm_brown
    rgb: [0.68, 0.32, 0.08]
    usage: calico_patch, ears, back, face_side
  - name: dark
    rgb: [0.09, 0.07, 0.06]
    usage: calico_patch, tail_stripe, face_side
  - name: accent
    rgb: [0.45, 0.22, 0.10]
    usage: patch_edge, subtle_variation
```

### YAML出力例

```yaml
palette:
  - name: white
    rgb: [0.95, 0.94, 0.91]
    usage: chest, belly, paws, nose_bridge
    source: extracted
  - name: cream
    rgb: [0.86, 0.77, 0.66]
    usage: body_base, soft_shadow
    source: fallback
  - name: warm_brown
    rgb: [0.68, 0.32, 0.08]
    usage: calico_patch, ears, back, face_side
    source: extracted
  - name: dark
    rgb: [0.09, 0.07, 0.06]
    usage: calico_patch, tail_stripe, face_side
    source: extracted
  - name: accent
    rgb: [0.45, 0.22, 0.10]
    usage: patch_edge, subtle_variation
    source: fallback
source_images:
  - input/masks/reference_side_right_body_1698975320501_cutout.png
num_colors: 6
seed: 0
```

### 実装メモ

- `PyYAML`, `Pillow`, `numpy` は既に `requirements.txt` にある。
- scikit-learn は追加しない。
- preview image は、入力画像サムネイル、抽出クラスタ、最終paletteを並べる。
- report には除外ピクセル数、採用ピクセル数、fallback 使用有無を記録する。

### 完了条件

- `config/cat_color_palette.yaml` が生成される。
- `white`, `cream`, `warm_brown`, `dark`, `accent` が必ず存在する。
- 各色に `source: extracted` または `source: fallback` が記録される。
- preview で写真由来の色として妥当か確認できる。
- 同じ入力と seed で再現可能。

## Task 81: Palette Driven Vertex Color Bake

### 目的

Task 80 のパレットを使って、`get_calico_color()` をパレット駆動に拡張し、毛流れノイズを加えた vertex color を作成する。これを Cycles Emit bake で baseColor texture に焼き込み、GLB/FBX として出力する。

### 追加ファイル

```text
scripts/081_apply_palette_vertex_bake.py
blender/cat_palette_vertex_bake.py
```

### 入力

```text
config/cat_color_palette.yaml
output/rigged/cat_animated.blend
```

実際の最新リグ付き cat blend が別名の場合は CLI で指定する。

### 出力

```text
output/textures/cat_palette_vertex_bake/
  cat_body_basecolor.png
  cat_fur_shell_basecolor.png
  bake_manifest.json

output/rigged/cat_palette_vertex_bake_pass.blend
output/clean_3d/cat_palette_vertex_bake_pass.glb
output/clean_3d/cat_palette_vertex_bake_pass.fbx
output/reports/task81_palette_vertex_bake_pass.json
output/reports/task81_palette_vertex_bake_front_preview.png
output/reports/task81_palette_vertex_bake_side_preview.png

godot/Godot3dcat/cat_palette_vertex_bake_pass.glb
```

### 主経路

初期実装では shader node 自動構築を行わない。

主経路:

1. 入力 blend / GLB を Blender で開く。
2. 対象 mesh と armature を検出する。
3. UV がなければ Smart UV Project を実行する。
4. `config/cat_color_palette.yaml` を読む。
5. mesh bounding box を取得する。
6. 各 vertex の world 座標を bounding box 正規化座標へ変換する。
7. `get_procedural_calico_color()` で色を決める。
8. Color Attribute に vertex color として設定する。
9. Emit material で vertex color を baseColor image へ bake する。
10. bake 済み image texture を final material の Base Color へ接続する。
11. body と fur shell は別 texture または別補正で扱う。
12. Blend、GLB、FBX、report を出力する。
13. Godot project へ GLB を配置する。

### get_procedural_calico_color

既存 `get_calico_color()` をベースに、以下を変更する。

- 色は固定値ではなく palette から取得する。
- 座標閾値は絶対座標ではなく、bounding box 正規化座標を使う。
- 毛流れ方向の決定的ノイズを追加する。
- fur shell では明度を上げ、コントラストを下げる。

擬似コード:

```python
def get_procedural_calico_color(u, v, w, palette, is_shell=False, seed=0):
    white = palette["white"]
    cream = palette["cream"]
    warm = palette["warm_brown"]
    dark = palette["dark"]
    accent = palette["accent"]

    # u: left/right, v: back/front, w: bottom/top
    base_color = cream

    # chest / belly / paws
    if w < 0.38 or (0.42 < v < 0.72 and abs(u - 0.5) < 0.18):
        base_color = white

    # face split near front/top
    if v > 0.72 and w > 0.55:
        if abs(u - 0.5) < 0.08:
            base_color = white
        elif u > 0.5:
            base_color = warm
        else:
            base_color = dark

    # back / hip patches
    patch_noise = smooth_hash_noise(u, v, w, scale=5.0, seed=seed)
    if w > 0.48 and patch_noise > 0.62:
        base_color = warm if patch_noise < 0.82 else dark

    # tail stripes, if target profile marks tail area
    # initial implementation may use v < 0.18 and w > 0.35 as a rough fallback
    if v < 0.18 and w > 0.35:
        stripe = int(v * 18.0 + smooth_hash_noise(u, v, w, 3.0, seed) * 2.0) % 2
        base_color = warm if stripe == 0 else dark

    color = add_fur_direction_noise(base_color, u, v, w, seed=seed)

    if is_shell:
        color = soften_shell_color(color)

    return color
```

### 座標正規化

モデル差を吸収するため、色判定は絶対座標ではなく bounding box 正規化座標で行う。

```text
u = (x - min_x) / (max_x - min_x)
v = (y - min_y) / (max_y - min_y)
w = (z - min_z) / (max_z - min_z)
```

初期profile:

- 現在のリグ付き猫モデル: `Y = front/back`, `Z = up`, `X = left/right`
- `koha9_cat`: Task 82 で bounding box と軸を確認してから適用する

CLIでは将来のために次を受け取れるようにする。

```text
--axis-left-right X
--axis-front-back Y
--axis-up Z
--front-positive true
```

### 毛流れノイズ

Blender shader node の Wave / Noise の代わりに、初期実装では Python の決定的ノイズを使う。

要件:

- 同じ seed と座標で同じ色になる。
- ランダム粒ではなく、少し方向性がある。
- 強すぎない。色差は 0.03 から 0.08 程度に抑える。

実装候補:

```python
def fur_direction_noise(u, v, w, strength=0.05, seed=0):
    wave = math.sin(u * 42.0 + v * 9.0 + seed) * math.sin(w * 35.0 + seed * 0.37)
    return wave * strength
```

斑模様の配置には `smooth_hash_noise()` を使う。これは完全な Perlin noise ではなく、正規化座標と seed から決定的に値を返す軽量な疑似ノイズでよい。

```python
def smooth_hash_noise(u, v, w, scale=5.0, seed=0):
    su, sv, sw = u * scale, v * scale, w * scale
    value = (
        math.sin(su * 12.9898 + sv * 78.233 + seed)
        * math.cos(sv * 43.758 + sw * 15.432 + seed * 1.7)
        * math.sin(sw * 27.616 + su * 51.329 + seed * 2.3)
    )
    return math.sin(value * 43758.5453) * 0.5 + 0.5
```

`scale` は斑の大きさに直結する。初期値は `5.0` とし、斑が大きすぎれば上げ、小さすぎれば下げる。

### Fur Shell 方針

fur shell は本体と同じ濃い模様を貼ると不自然になりやすい。

初期実装:

- shell は body texture とは別 bake にする。
- shell は明度を上げる。
- shell はコントラストを落とす。
- shell は斑模様を弱くする。

bake は2回に分ける。

```text
body mesh だけを select
  -> cat_body_basecolor.png に bake

fur shell mesh だけを select
  -> cat_fur_shell_basecolor.png に bake
```

既存 `apply_calico_texture.py` は全meshを同時に1枚へ bake しているが、このTaskでは body と shell の見た目を分けるため、選択対象と出力画像を分離する。

補正式:

```python
def soften_shell_color(color):
    r, g, b = color
    return (
        min(1.0, r * 0.60 + 0.40),
        min(1.0, g * 0.60 + 0.40),
        min(1.0, b * 0.60 + 0.40),
    )
```

### Shader Node は後続改善

後続改善として、Blender shader node 自動構築を検討する。

ただし、初期実装では次を行わない。

- 20個以上のノード自動生成。
- Object Info / Separate XYZ / Math Compare / ColorRamp を大量に接続する構成。
- shader node と vertex color bake の二重経路サポート。

Task 81 の成功後、必要になった場合だけ `Task 84: Shader Node Material Prototype` として切り出す。

### CLI目標

```powershell
python scripts/081_apply_palette_vertex_bake.py `
  --input output/rigged/cat_animated.blend `
  --palette config/cat_color_palette.yaml `
  --texture-dir output/textures/cat_palette_vertex_bake `
  --output-blend output/rigged/cat_palette_vertex_bake_pass.blend `
  --output-glb output/clean_3d/cat_palette_vertex_bake_pass.glb `
  --output-fbx output/clean_3d/cat_palette_vertex_bake_pass.fbx `
  --resolution 2048 `
  --seed 0
```

### 完了条件

- palette の色が vertex color に反映される。
- 2048x2048 の bake 済み baseColor texture が生成される。
- body と fur shell が適切に分離または補正される。
- GLB/FBX 出力後も animation clip が残る。
- Godot で `force_cat_materials = false` のまま表示される。
- front / side preview で三毛猫として読める。
- report に palette、fallback使用有無、bbox、axis設定、bake解像度、対象mesh、material、animation数が記録される。

## Task 82: Koha9 Reference Check

### 位置づけ

Task 82 は独立した大型実装ではなく、Task 81 の汎用性チェックである。

ただし、`koha9_cat` は座標系とスケールが現在のリグ付き猫モデルと異なる可能性が高いため、いきなり同じ閾値で塗らない。

### 前提作業

1. `input/cat2/koha9_cat/scene.gltf` を Blender で import する。
2. mesh bounding box を取得する。
3. 座標軸、front/back/up の向きを report に記録する。
4. 正規化座標 `(u, v, w)` で `get_procedural_calico_color()` を適用する。
5. 元ファイルは変更せず、別出力だけ作る。

### 入力

```text
input/cat2/koha9_cat/scene.gltf
config/cat_color_palette.yaml
```

### 出力

```text
output/clean_3d/koha9_palette_vertex_bake_pass.glb
output/reports/task82_koha9_palette_vertex_bake_pass.json
output/reports/task82_koha9_palette_vertex_bake_preview.png
```

### 完了条件

- 元の `input/cat2/koha9_cat/` 配下を変更しない。
- bounding box、座標軸、スケールが report に残る。
- `get_procedural_calico_color()` が正規化座標で動く。
- 既存2マテリアル構成を破壊せず、別出力として確認できる。
- 元テクスチャを素材として直接再利用していないことが report に残る。

## Task 83: Godot Review

### 位置づけ

Task 83 は Task 81 の完了条件に含める。Godot確認で問題が出た場合だけ、後続修正タスクとして切り出す。

### 確認項目

- `godot/Godot3dcat/cat_palette_vertex_bake_pass.glb` が読み込める。
- `force_cat_materials = false` で GLB 内 material が見える。
- Idle / Walk / Jump / lie-down 代替 animation が再生できる。
- texture が黒つぶれ、白飛び、過剰ノイズになっていない。
- fur shell が濃すぎない。
- 動いたときに三毛柄がちらついたり破綻したりしない。

## Preview 方針

Task 80 と Task 81 では preview 生成手段を分ける。

| Preview | 生成手段 |
|---|---|
| `task80_cat_color_palette_preview.png` | Pillow で入力サムネイル、抽出クラスタ、最終paletteを並べる |
| `task81_palette_vertex_bake_front_preview.png` | Blender render。`blender/render_glb_preview.py` を再利用する |
| `task81_palette_vertex_bake_side_preview.png` | Blender render。`blender/render_glb_preview.py` を再利用する |

Task 80 preview は Blender 外で完結させる。Task 81 preview は GLB 出力後の確認として扱う。

## 実装順序

1. `scripts/080_extract_cat_color_palette.py` を実装する。
2. `config/cat_color_palette.yaml`、JSON report、palette preview を確認する。
3. `blender/cat_palette_vertex_bake.py` を `apply_calico_texture.py` から派生して作る。
4. `get_procedural_calico_color()` を正規化座標、palette、noise、shell補正つきで実装する。
5. `scripts/081_apply_palette_vertex_bake.py` を作り、Blender background 実行を包む。
6. 現在のリグ付き猫モデルで bake / export / preview / Godot staging まで通す。
7. `koha9_cat` の bbox と軸を調査し、同じ関数を正規化座標で適用する。
8. レポートを見て、色、斑の大きさ、毛流れ強度、fur shell 明度を調整する。

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
python scripts/081_apply_palette_vertex_bake.py `
  --input output/rigged/cat_animated.blend `
  --palette config/cat_color_palette.yaml `
  --resolution 2048 `
  --seed 0
```

## 技術判断

### Vertex color bake を主経路にする

初期実装では shader node 自動構築をしない。既存の `apply_calico_texture.py` と同じ構造で進めることで、Blender Python のノード構築リスクを避ける。

### 写真からは色だけを取る

写真から直接 texture を作ると、背景混入、姿勢差、毛流れ方向、解像度の問題が残る。写真は palette source に限定する。

### 正規化座標でモデル差を吸収する

現在のリグ付き猫モデルと `koha9_cat` では座標系・スケールが違う可能性がある。絶対座標ではなく bounding box 正規化座標で色判定する。

### bake 済み baseColor を最終成果物にする

Godot / GLB での安定性を優先し、final material は bake 済み image texture を Base Color に接続する。

### PBR拡張は後回し

`koha9_cat` も baseColor のみで成立しているため、normal / roughness / AO は MVP 後に検討する。

## リスクと対策

### パレット抽出が写真の影に引っ張られる

対策:

- alpha 境界と極端な暗部を除外する。
- previewで確認する。
- fallback palette を必ず補完する。
- report に fallback 使用有無を記録する。

### vertex color が低密度メッシュで粗くなる

対策:

- 最終出力は vertex color そのものではなく bake texture にする。
- 必要に応じて bake 前に UV 解像度と margin を上げる。
- ノイズ強度を控えめにする。

### 別モデルで模様位置が合わない

対策:

- bounding box 正規化座標を使う。
- axis 設定を CLI で指定できるようにする。
- `koha9_cat` の bbox と axis を report に記録する。

### fur shell が不自然に濃くなる

対策:

- shell 用補正で明度を上げ、コントラストを落とす。
- shell texture は body とは別 bake にする。
- 必要なら shell は模様を弱くする。

### shader node 化したくなる

対策:

- Task 81 ではやらない。
- 必要になったら `Task 84: Shader Node Material Prototype` として切り出す。

## MVP完了条件

- `config/cat_color_palette.yaml` が写真から生成される。
- fallback palette の具体値が定義され、必要時に補完される。
- 現在のリグ付き猫モデルへ palette driven vertex bake texture が適用される。
- GLB/FBX 出力後も animation が維持される。
- Godot で texture 付きモデルを表示し、主要 animation を再生できる。
- `koha9_cat` でも bbox / axis 調査後、別出力として同じ関数を適用できる。
- report に入力、palette、fallback、bbox、axis、bake設定、出力、既知の制約が残る。

## 後回しにすること

- Blender shader node の複雑な自動構築。
- vertex color bake と shader node bake の二重経路サポート。
- 写真から直接 tileable fur texture を生成する方式。
- 固定7カテゴリの texture library 方式。
- 完全自動の顔・胴体・脚・尻尾セグメンテーション。
- 写真とモデルの厳密なカメラキャリブレーション。
- 物理ベースの毛皮 normal map 生成。
- roughness / ambient occlusion / subsurface などの PBR 拡張。
- 既存 `koha9_cat` テクスチャの素材としての直接再利用。
