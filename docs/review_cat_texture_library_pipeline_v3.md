# Cat Palette Driven Vertex Bake Pipeline Plan — レビュー (v2)

## 1. 総評

**実装に進めてよいプランです。** 代替プランの提案は不要と判断しました。

前回・前々回のレビュー指摘がすべて反映されており、既存コードベースとの整合性も取れています。

---

## 2. 指摘の反映状況

| # | 初回レビューの指摘 | v1 での対応 | v2 での対応 | 評価 |
|---|------------------|------------|------------|------|
| 1 | Task 64 との重複 | Pillow 撤回、色パレットに限定 | 維持 | ✅ |
| 2 | 7固定カテゴリの硬直性 | YAML パレットに変更 | 維持 | ✅ |
| 3 | 4タスク分割の過剰さ | Task 82/83 を確認項目に格下げ | 維持 | ✅ |
| 4 | 既存コードの未活用 | 再利用テーブル追加 | 維持 | ✅ |
| 5 | Shader node 自動構築の複雑さ | 「段階的に」と記述 | **vertex color bake を主経路に固定、shader node は Task 84 に分離** | ✅ 改善 |
| 6 | 二重経路のリスク | 未対応 | **「二重経路サポートを後回しにする」と明記** | ✅ 解消 |
| 7 | koha9_cat の座標系差異 | 未対応 | **bounding box 正規化座標の導入、前提作業として bbox/axis 調査を追加** | ✅ 解消 |
| 8 | Fallback palette の具体値 | 未記載 | **apply_calico_texture.py の既存固定色に揃えた fallback 値を明記** | ✅ 解消 |

---

## 3. 良い点

### 3.1 明確な主経路の選択

> 初期実装は **palette driven vertex color bake** とする。

この宣言が冒頭にあることで、実装者が迷わなくなっています。shader node を「やらない」と明記した上で、必要なら Task 84 として切り出す判断も正しいです。

### 3.2 擬似コードの充実

`get_procedural_calico_color()` の擬似コードは、正規化座標 `(u, v, w)` を使った部位判定と、パレット駆動の色選択が具体的に書かれています。実装との距離が近く、そのままコードに落とせます。

### 3.3 Fallback palette の A/B 比較設計

> この値は `blender/apply_calico_texture.py` の既存固定色に意図的に近づける。既存結果との A/B 比較をしやすくするため。

これにより、palette 抽出が成功した場合と fallback の場合の差分を比較でき、palette 抽出の価値を定量的に評価できます。

### 3.4 `source: extracted | fallback` の記録

各色が写真由来か fallback かを YAML に記録する設計は、再実行やデバッグ時に非常に有用です。

### 3.5 座標正規化の CLI 対応

```
--axis-left-right X
--axis-front-back Y
--axis-up Z
--front-positive true
```

将来の拡張に備えつつ、初期実装では現在のモデルの軸をデフォルトにすることで、複雑さを最小限にしています。

---

## 4. 小さな改善提案

プランの方向性を変える必要はありませんが、実装時に迷いそうな **3 点** を補足します。

### 4.1 `smooth_hash_noise` の実装方針を明記する

擬似コード内で `smooth_hash_noise()` と `add_fur_direction_noise()` が呼ばれていますが、具体的な実装は `fur_direction_noise` だけが定義されています。

`smooth_hash_noise` は斑模様のランダム配置に使われる重要な関数です。実装時の参考として：

```python
def smooth_hash_noise(u, v, w, scale=5.0, seed=0):
    """bounding box 正規化座標に対する決定的な擬似ノイズ (0.0〜1.0)"""
    su, sv, sw = u * scale, v * scale, w * scale
    # 複数周波数の sin/cos を組み合わせて空間的に滑らかなノイズを作る
    val = (
        math.sin(su * 12.9898 + sv * 78.233 + seed) *
        math.cos(sv * 43.758 + sw * 15.432 + seed * 1.7) *
        math.sin(sw * 27.616 + su * 51.329 + seed * 2.3)
    )
    return (math.sin(val * 43758.5453) * 0.5 + 0.5)
```

> [!TIP]
> この関数は斑模様の配置を決めるため、`scale` パラメータが見た目に直結します。最初は `scale=5.0` で試し、斑が大きすぎれば上げ、小さすぎれば下げるのがよいでしょう。

### 4.2 Body / Shell の bake を分ける方法を明記する

プランに「body と fur shell は別 texture で扱う」とありますが、具体的な bake の分離手順が書かれていません。

既存の `apply_calico_texture.py` では全メッシュを同時に select して 1 回の bake で処理しています。body と shell を分ける場合は：

```python
# body だけ select → bake → cat_body_basecolor.png に保存
# shell だけ select → bake → cat_fur_shell_basecolor.png に保存
```

この 2 回 bake のフローを実装メモに入れておくと、実装時に判断が速くなります。

### 4.3 Preview 生成の実装手段

Task 80 の `task80_cat_color_palette_preview.png` と Task 81 の `front/side preview` は生成手段が異なります：

| Preview | 生成手段 |
|---------|---------|
| `task80_cat_color_palette_preview.png` | **Pillow** で入力サムネイル + 色スウォッチを並べた画像を生成 |
| `task81_*_front_preview.png` / `task81_*_side_preview.png` | **Blender render** (`render_glb_preview.py` を再利用) |

Task 80 の preview は Blender 外で完結するため、Pillow だけで実装するのが自然です。この区別を明記しておくと、実装時に Blender 側に持っていくかどうかで迷わなくなります。

---

## 5. まとめ

| 観点 | 評価 |
|------|------|
| レビュー指摘の反映 | ✅ 全8項目に対応済み |
| 方向性 | ✅ 実装に進められる |
| 主経路の明確さ | ✅ vertex color bake に固定、shader node は後回し |
| 既存コード再利用 | ✅ apply_calico_texture.py をベースに派生 |
| モデル汎用性 | ✅ bounding box 正規化 + CLI axis 指定 |
| リスク管理 | ✅ 5つのリスクに具体的対策あり |
| 代替プランの必要性 | **なし** |

> [!IMPORTANT]
> **このプランで Task 80 の実装を開始できます。**
> 最初のコマンド目標:
> ```powershell
> python scripts/080_extract_cat_color_palette.py `
>   --input-dir input/masks `
>   --output config/cat_color_palette.yaml `
>   --num-colors 6 `
>   --seed 0
> ```
