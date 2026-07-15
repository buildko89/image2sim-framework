# 改訂版 Cat Procedural Texture Pipeline Plan — レビュー

## 1. 総評

改訂版プランは、前回レビューの指摘を**的確に反映**しています。

| 前回の指摘 | 改訂での対応 | 評価 |
|-----------|-------------|------|
| Task 64 との重複 | Pillow テクスチャ生成を撤回、「色を決める」ことに限定 | ✅ 解消 |
| 7固定カテゴリの硬直性 | YAML パレットに変更、カテゴリ数は可変 | ✅ 解消 |
| 4タスク分割の過剰さ | Task 82/83 を「独立タスクではなく確認項目」に格下げ | ✅ 解消 |
| 既存コードの未活用 | 再利用テーブルを明示（apply_calico_texture.py 等） | ✅ 解消 |
| Blender procedural の提案 | 採用、Wave/Noise/ColorRamp を設計に含める | ✅ 採用 |

**プランの方向性は正しく、このまま実装に入れる水準**です。

以下では、実装段階で問題になりそうな **3つの残リスク** と、それに対する **具体的な対処案** を示します。

---

## 2. 残リスク ⚠️

### 2.1 Shader Node 自動構築の複雑さ

プランの [Task 81 処理内容 ステップ 5–8](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/plan_cat_texture_library_pipeline.md#L199-L203) では：

```
procedural material を構築する。
Object 座標で部位を分ける。
Noise / Wave / ColorRamp / Mix 系ノードで毛流れと三毛斑を作る。
Fur shell は本体より明るく、低コントラストにする。
```

これを Blender Python でゼロから組むと、ノード数が **20〜30個**、リンク数が **30〜50本** になります。具体的には：

```
Object Info → Separate XYZ → (顔判定) Math Compare → Mix
                             → (背腹判定) Math Compare → Mix
                             → (尻尾判定) Math Compare → Mix
各判定 → ColorRamp (パレット色)
Noise Texture → (毛流れ用) → Mix (強度調整)
Wave Texture → (縞模様用) → Mix
全体 Mix → Principled BSDF → Output
```

**問題**: Blender Python でのノード配置・接続コードは**冗長で壊れやすい**。ノード座標の手動指定、ソケット名のバージョン依存（Blender 3.x vs 4.x で `Base Color` のソケットインデックスが異なる場合がある）など、デバッグが重くなります。

### 2.2 Vertex Color Fallback との二重経路

プランでは「安定性を優先し、必要なら CPU 側で vertex color / image bake を併用する」と書かれています。これは正しい判断ですが、**2つの経路を両方サポートする設計になると、テスト対象が倍増**します。

### 2.3 koha9_cat の座標系

[get_calico_color()](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py#L22-L78) は現在のリグ付き猫モデルの座標系（Y=前方、Z=上）にハードコードされています。koha9_cat は 70MB の高密度メッシュで、座標系・スケールが全く異なる可能性が高いです。

---

## 3. 推奨: Vertex Color Bake を主経路に固定する

> [!IMPORTANT]
> shader node 自動構築は**初期実装では避け**、既存の `get_calico_color()` を拡張する vertex color bake を主経路にすることを推奨します。

### 理由

1. [apply_calico_texture.py](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py) が既に **vertex color → Cycles Emit bake → GLB export** の完全な経路を持っている
2. Vertex color bake は **Blender バージョン依存が少なく**、デバッグしやすい
3. 毛流れの方向性ノイズは、Python 側の `get_calico_color()` に **Perlin noise を加算するだけ**で実現できる（Blender の shader node を使わなくても可能）
4. shader node 化は「見た目が固まった後」の最適化ステップとして後からやれる

### 具体的な実装構造

```python
# blender/cat_procedural_texture.py（apply_calico_texture.py からの派生）

import yaml
import math
import random

def load_palette(yaml_path: str) -> dict:
    """YAML からパレットを読み込む"""
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    palette = {}
    for entry in data['palette']:
        palette[entry['name']] = tuple(entry['rgb'])
    return palette

def simple_noise(x, y, z, scale=20.0, seed=42):
    """座標ベースの決定的な擬似ノイズ (0.0〜1.0)"""
    # hash-based noise — Perlin の代わりに十分
    val = math.sin(x * scale + seed) * math.cos(y * scale * 1.3 + seed * 2) * math.sin(z * scale * 0.7 + seed * 3)
    return (val * 0.5 + 0.5)  # 0〜1 に正規化

def fur_direction_noise(x, y, z, strength=0.06):
    """毛流れ方向のノイズ（Y軸方向に伸びるパターン）"""
    # Y方向に引き伸ばすことで毛流れ感を出す
    wave = math.sin(x * 40.0 + y * 8.0) * math.sin(z * 35.0)
    return wave * strength

def get_procedural_calico_color(x, y, z, palette, is_shell=False):
    """
    パレット駆動の三毛猫カラー関数
    apply_calico_texture.py の get_calico_color() を拡張
    """
    white = palette.get('white', (0.95, 0.94, 0.91))
    cream = palette.get('cream', (0.86, 0.77, 0.66))
    warm = palette.get('warm_brown', (0.68, 0.32, 0.08))
    dark = palette.get('dark', (0.09, 0.07, 0.06))

    # --- 既存ロジック（顔、尻尾、スポット）をここに配置 ---
    # get_calico_color() と同じ構造、色だけ palette から

    # --- 毛流れノイズを加算 ---
    r, g, b = base_color  # 上で決定した色
    noise = fur_direction_noise(x, y, z)
    r = max(0.0, min(1.0, r + noise))
    g = max(0.0, min(1.0, g + noise))
    b = max(0.0, min(1.0, b + noise))

    # --- fur shell 用の補正 ---
    if is_shell:
        # 明度を上げ、コントラストを下げる
        r = r * 0.6 + 0.4
        g = g * 0.6 + 0.4
        b = b * 0.6 + 0.4

    return (r, g, b)
```

### 既存コードからの変更量

| ファイル | 変更内容 | 変更量 |
|---------|---------|--------|
| [apply_calico_texture.py](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py) | **変更なし**（参照のみ） | 0行 |
| `blender/cat_procedural_texture.py` (新規) | apply_calico_texture.py をベースに、palette 読み込み + ノイズ追加 + shell 分離 | ~250行 |
| `scripts/081_apply_procedural_cat_texture.py` (新規) | scripts/072_apply_calico_texture.py をベースに、CLI 引数拡張 | ~80行 |
| `scripts/080_extract_cat_color_palette.py` (新規) | K-means + YAML 出力 | ~120行 |

**合計: 新規 ~450行、既存ファイル変更 0行**

---

## 4. プランへの修正提案

現プランに対して、以下の 3 点だけ修正を推奨します：

### 4.1 Task 81 の処理内容を明確にする

現状の記述：
> 5\. procedural material を構築する。

推奨する修正：
```
5a. [初期実装] get_calico_color() をパレット駆動に拡張し、
    毛流れノイズを追加した vertex color bake で baseColor を生成する。
5b. [後続改善] 必要に応じて Blender shader node で置き換える。
```

### 4.2 koha9_cat 対応の前提条件を追加する

現状では koha9_cat への適用が暗黙的に想定されていますが、座標系が異なる可能性があります。

```
Task 82 の前提:
- koha9_cat のメッシュ bounding box を調査し、
  座標軸とスケールを report に記録する。
- get_procedural_calico_color() の座標閾値を
  bounding box に対する正規化座標で指定する。
```

### 4.3 fallback palette の具体値を書く

プランに「固定色 fallback を持つ」とあるが、具体的な値がないと実装時に迷います。

```yaml
# fallback palette（入力画像が不足した場合）
palette:
  - name: white
    rgb: [0.95, 0.94, 0.91]
  - name: cream
    rgb: [0.86, 0.77, 0.66]
  - name: warm_brown
    rgb: [0.68, 0.32, 0.08]
  - name: dark
    rgb: [0.09, 0.07, 0.06]
  - name: accent
    rgb: [0.45, 0.22, 0.10]
```

> [!TIP]
> この fallback 値は、既存 [get_calico_color()](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/blender/apply_calico_texture.py#L23-L26) のハードコード値（`base_white`, `orange_brown`, `dark_black`）と**意図的に揃える**と、A/B 比較がしやすくなります。

---

## 5. まとめ

| 観点 | 評価 |
|------|------|
| 前回レビューの反映 | ✅ 全指摘に対応済み |
| 方向性 | ✅ 正しい。実装に進める |
| タスク分割 | ✅ 適切（2主タスク + 2確認項目） |
| 既存コード再利用 | ✅ 明示的に設計されている |
| リスク | ⚠️ shader node 自動構築の複雑さに注意 |
| 推奨修正 | 3 点のみ（vertex color 主経路化、koha9 座標正規化、fallback palette 具体値） |

**結論: このプランで実装を開始して問題ありません。** 上記 3 点の修正を加えれば、さらに安定した実装になります。
