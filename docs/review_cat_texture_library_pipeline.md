# Cat Texture Library Pipeline Plan — レビューと代替案

## 1. レビュー総評

[plan_cat_texture_library_pipeline.md](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/plan_cat_texture_library_pipeline.md) は、これまでの試行錯誤（Fox → Cat ベースモデル移行、写真投影 bake の限界、手続き的テクスチャ実験）を踏まえた上で、**よく構造化されたプラン**です。

ただし、いくつかの構造的な問題と、より効果的な代替アプローチがあります。

---

## 2. 良い点 ✅

| 項目 | 評価 |
|------|------|
| 2段階分離（生成 → 適用） | テクスチャ生成とモデル適用を分離した設計は正しい |
| baseColor 優先 | koha9_cat も baseColor のみで成立しており、PBR を後回しにする判断は妥当 |
| 再現性（seed 固定） | 再実行で同等の結果が出せる設計は重要 |
| リスク認識 | 写真抽出の不安定さ、UV差、fur shell の問題を事前に認識している |
| MVP 完了条件 | 明確で検証可能 |
| koha9_cat を参考（非素材）として扱う | ライセンスリスクを回避した正しい判断 |

---

## 3. 問題点と懸念 ⚠️

### 3.1 Task 64 との重複が大きい

> [!WARNING]
> Task 64 で既に「Pillow で毛流れ風テクスチャを生成 → UV に適用 → GLB 埋め込み → Godot 表示」の経路全体が検証済みです。

[Task 64 の成果物](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output/textures/task64_cat_texture_experiment):
- `white_fur.png`, `warm_calico_fur.png`, `dark_calico_fur.png`, `cream_shadow_fur.png`

Task 80 で作ろうとしている 7 つの baseColor テクスチャは、Task 64 の 4 枚を**名前と色を変えて増やしただけ**になるリスクがあります。

写真からの色抽出を加えても、最終的に Pillow + NumPy で tileable テクスチャを生成するという根本的アプローチは同じです。

### 3.2 「写真から毛色を抽出して tileable テクスチャを作る」のギャップが大きい

プランでは以下のステップを列挙しています：

```
色クラスタを作る → 代表色を抽出 → 毛並みノイズを抽出 → tileable 風テクスチャを生成
```

しかし、**色クラスタの代表色 + ノイズ = 平均色に粒状ノイズが乗ったテクスチャ**にしかなりません。実際の猫の毛並みが持つ以下の特徴は再現できません：

- 毛の一本一本の方向性（毛流れ）
- 色の境界のグラデーション（三毛の斑模様の輪郭）
- 密度感・光沢の変化

### 3.3 座標ベースの部位分けは既に [apply_calico_texture.py](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py) で実装済み

Task 81 の「座標ベースで大まかに部位を分ける」は、[apply_calico_texture.py](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py#L22-L78) の `get_calico_color()` 関数で**ほぼ同じことが既にできています**。この関数は：

- 3D座標で顔の左右分け（茶 / 黒）
- 尻尾の縞模様
- 体のスポット（球体で定義）
- Smoothstep によるブレンド

Task 81 は、この既存実装の「テクスチャソース」を差し替えるだけの変更に過ぎません。

### 3.4 7つの固定テクスチャカテゴリは硬直的

```
white_fur / cream_fur / warm_brown_fur / dark_fur / calico_patch / mixed_body / tail_stripe
```

これらのカテゴリは **この猫専用の設計** であり、「複数モデルに再利用できる texture library」という目標と矛盾します。別の猫（例：黒猫、サビ猫、キジトラ）には全く使えません。

### 3.5 4つのタスク（80–83）に分割する必要性が薄い

Task 80–83 は、実質的に以下の 2 ステップです：

1. テクスチャを生成する（Task 80）
2. モデルに貼って確認する（Task 81–83）

Task 82（koha9 検証）と Task 83（Godot 確認）は独立タスクにするほどの作業量ではなく、Task 81 の完了条件に含めるべきです。

---

## 4. 代替プラン提案

### 方針の違い

| | 現プラン | 代替プラン |
|---|---------|----------|
| テクスチャ生成 | 写真色抽出 → Pillow で tileable 生成 | **Blender シェーダノードで手続き的に生成 → UV に bake** |
| 色の決定 | K-means クラスタリング | **写真からパレット抽出 → シェーダの入力パラメータ** |
| 部位分け | 外部スクリプトで座標分割 | **既存 `get_calico_color` を拡張、シェーダノード内で Object 座標による分割** |
| 毛流れ | ノイズテクスチャ加算 | **Blender の Wave / Musgrave / Noise ノードで方向性あるパターン** |
| 依存関係 | Pillow + NumPy（Blender 外） | **Blender のみ（追加依存なし）** |

### 代替プラン概要: Blender Procedural Shader → Bake 方式

```text
input/masks/*_cutout.png
  -> Python: カラーパレット抽出 (5〜8色、RGB値のみ)
  -> config/cat_color_palette.yaml

config/cat_color_palette.yaml
  + blender/cat_procedural_texture.py
  -> Blender: プロシージャルシェーダ構築
  -> Blender: UV bake (2048x2048)
  -> output/textures/cat_procedural_bake/

output/textures/cat_procedural_bake/
  -> blender/apply_cat_texture_library.py
  -> output/rigged/ + output/clean_3d/
  -> godot/Godot3dcat/
```

---

### Task 80-alt: カラーパレット抽出

**目的**: 写真から「テクスチャ」ではなく「色パレット」だけを抽出する。

**追加ファイル**:
```
scripts/080_extract_cat_color_palette.py
```

**処理内容**:
1. `input/masks/*_cutout.png` を走査する
2. Alpha 有効ピクセルだけを収集
3. K-means で 5〜8 色のクラスタを抽出
4. 各クラスタに意味ラベルを付与（明度順: darkest → lightest）
5. `config/cat_color_palette.yaml` に出力

**出力例**:
```yaml
palette:
  - name: white
    rgb: [0.95, 0.94, 0.91]
    usage: belly, chest, paws
  - name: cream
    rgb: [0.88, 0.78, 0.65]
    usage: body base, shadow areas
  - name: warm_brown
    rgb: [0.68, 0.32, 0.08]
    usage: calico patches, ears, back
  - name: dark
    rgb: [0.09, 0.07, 0.06]
    usage: calico patches, tail stripes
source_images:
  - input/masks/reference_side_right_body_1698975320501_cutout.png
  - input/masks/front_P_20260326_195241_cutout.png
```

> [!TIP]
> テクスチャ画像を生成するのではなく、色情報だけを抽出します。テクスチャの「見た目」は Blender のプロシージャルノードが担当します。

**完了条件**:
- `config/cat_color_palette.yaml` に 5 色以上のパレットが出力される
- preview シートで代表色と元画像の対応が確認できる
- 同じ入力と seed で再現可能

---

### Task 81-alt: Blender プロシージャルテクスチャ生成 + モデル適用

**目的**: Blender のシェーダノードで猫の毛並みテクスチャをプロシージャルに構築し、UV に bake してモデルに適用する。

**追加ファイル**:
```
blender/cat_procedural_texture.py
scripts/081_apply_procedural_cat_texture.py
```

**処理内容**:

1. `config/cat_color_palette.yaml` を読み込む
2. 入力モデル（blend / GLB）を Blender で開く
3. **プロシージャルシェーダを構築**:

```
Object Info (座標)
  → Separate XYZ
  → 部位判定（顔左右、背中/腹、尻尾）
    → ColorRamp で色を割り当て
    → Noise Texture / Wave Texture で毛流れ方向ノイズを追加
    → MixRGB で三毛斑パターンをブレンド
  → Principled BSDF → Base Color
```

4. **UV が無ければ Smart UV Project で作成**（既存処理を再利用）
5. **Cycles Emit Bake で 2048x2048 に焼き込み**（[apply_calico_texture.py](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py#L178-L196) の手法を再利用）
6. bake 済みテクスチャを GLB に埋め込んでエクスポート
7. Godot 用に `godot/Godot3dcat/` へ配置

**既存コードの再利用**:

| 既存コード | 再利用する部分 |
|-----------|--------------|
| [apply_calico_texture.py](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py) | Smart UV Project、Cycles bake 手順、マテリアル構築、GLB/FBX エクスポート |
| [get_calico_color()](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py#L22-L78) | 座標ベースの部位分けロジック（改良のベース） |
| [cat_texture_experiment_pass.py](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/cat_texture_experiment_pass.py) | UV 追加 + テクスチャ接続の経路 |

**プロシージャルシェーダの利点**:

1. **毛流れ方向**: Blender の `Wave Texture` + `Noise Texture` で、座標に沿った方向性のあるパターンを生成できる（Pillow のランダムノイズより自然）
2. **無限解像度**: bake 前はプロシージャルなので、1024 でも 4096 でも同一シェーダから生成可能
3. **リアルタイムプレビュー**: Blender の viewport shading (Material Preview) で即座に確認できる。Pillow のように「生成 → 貼る → 確認」の往復が不要
4. **パラメータ調整が容易**: 色、斑の大きさ、毛流れの強さ、コントラストをスライダーで調整可能
5. **既存パイプラインとの統合**: 既に Blender Python スクリプトが 21 本あり、Cycles bake の経路も検証済み

**出力**:
```
output/textures/cat_procedural_bake/
  cat_body_basecolor.png         (2048x2048)
  cat_fur_shell_basecolor.png    (2048x2048)
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

**完了条件**:
- プロシージャルシェーダで三毛猫パターンが生成される
- 2048x2048 に bake された baseColor テクスチャがある
- GLB/FBX 出力後もアニメーションが維持される
- Godot で `force_cat_materials = false` で表示される
- koha9_cat にも同一シェーダを適用して出力できる（別 GLB として）
- report にパレット、bake 解像度、マテリアル構成が記録される

---

## 5. 比較まとめ

| 観点 | 現プラン (Pillow texture library) | 代替プラン (Blender procedural bake) |
|------|----------------------------------|--------------------------------------|
| **新規依存** | なし（Pillow/NumPy 既存） | なし（Blender 既存） |
| **タスク数** | 4 (Task 80–83) | 2 (Task 80-alt, 81-alt) |
| **新規スクリプト** | 2 Python + 1 Blender | 1 Python + 1 Blender |
| **既存コード再利用** | 少ない | `apply_calico_texture.py` を大幅再利用 |
| **Task 64 との差分** | 小さい（色数が増えるだけ） | 大きい（アプローチが根本的に異なる） |
| **毛流れの表現** | ランダムノイズ | 方向性のある Wave/Noise テクスチャ |
| **解像度の柔軟性** | 生成時に固定 | bake 時に自由に選択 |
| **リアルタイムプレビュー** | 不可 | Blender Material Preview で即確認 |
| **パラメータ調整** | スクリプト修正＋再実行 | Blender UI でスライダー操作 |
| **他の猫種への汎用性** | 7固定カテゴリ → 再設計が必要 | パレット YAML を差し替えるだけ |
| **koha9_cat 対応** | 別タスク (Task 82) | 同じシェーダを適用するだけ |

---

## 6. 推奨

> [!IMPORTANT]
> **代替プランを推奨します。** 理由は以下の 3 点です：
>
> 1. **既存コード資産を最大限活用できる**（`apply_calico_texture.py` の vertex color → bake フローが検証済み）
> 2. **Task 64 の繰り返しを避けられる**（Pillow テクスチャ生成はもう十分に試した）
> 3. **Blender 内で完結するため、生成→確認のイテレーションが速い**

### 着手順序

```
1. scripts/080_extract_cat_color_palette.py を実装する
   → config/cat_color_palette.yaml を生成する
   → preview で色が妥当か確認する

2. blender/cat_procedural_texture.py を実装する
   → apply_calico_texture.py の bake 処理をベースにする
   → get_calico_color() の座標分割を Wave/Noise ノードに置き換える
   → パレットの色をシェーダに接続する
   → Blender Material Preview で確認する

3. scripts/081_apply_procedural_cat_texture.py を実装する
   → bake → GLB/FBX エクスポート → Godot 配置
   → koha9_cat にも適用して汎用性を確認する
```

### 最初のコマンド目標

```powershell
python scripts/080_extract_cat_color_palette.py `
  --input-dir input/masks `
  --output config/cat_color_palette.yaml `
  --num-colors 6 `
  --seed 0
```
