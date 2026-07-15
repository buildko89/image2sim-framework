# Task 6.1: Tripo v2.5 手動download GLBレビュー

## 実施日

2026-06-30

## 背景

MeshyはWeb UI生成結果が良さそうだったが、downloadが有料のため今回の無料枠検証対象から外した。

Tripoはv3.1だとdownloadが有料の見込みだったが、v2.5ではGLB形式でdownloadできたため、Framework側で受け入れて検査した。

## 入力

ユーザー配置:

- `input/cloud_manual/tripo/calico cat 3d model.glb`

Framework処理用コピー:

- `output/raw_3d/cloud_manual/tripo/calico_cat_v25/calico_cat_v25.glb`

## 生成した確認成果物

- `output/reports/task61_tripo_v25_glb_inspection.json`
- `output/reports/task61_tripo_v25_side_preview.png`
- `output/reports/task61_tripo_v25_front_preview.png`

## GLB検査結果

`scripts/056_inspect_glb.py` で確認した結果:

- generator: `Tripo`
- mesh数: 1
- material数: 1
- base color texture: あり
- skin数: 0
- animation数: 0
- primitive attributes:
  - `POSITION`
  - `NORMAL`
  - `TEXCOORD_0`

判断:

- 静的なtexture付き参照アセットとして有用。
- skin / animation はないため、現時点で最終可動モデルにはしない。
- `cat_fluffy_shortleg_pass.glb` の代替ではなく、見た目・毛流れ・三毛柄・形状シルエットの参照として使う。

## 目視レビュー

### 良い点

- 低テクスチャの `cat_fluffy_shortleg_pass.glb` より、白毛、茶毛、黒毛の質感情報が多い。
- 長毛の縦方向の毛流れがあり、現行のフラットマテリアルより実猫らしさの参考になる。
- 正面・横のシルエットが猫として成立しており、三毛猫の雰囲気も出ている。
- base color textureを持つため、今後のtexture改善方針の参照として使える。

### 注意点

- 実猫そのものとは一致していない。
- 尻尾がかなり誇張されており、形状参照としては使いすぎに注意。
- 顔と口まわりに生成AIらしい崩れがある。
- 脚・足先は現行可動モデルへそのまま転用できない。
- skin / animationがないため、直接Godotの可動モデルにはできない。

## 現時点の採用判断

Tripo v2.5 GLBは採用候補。ただし用途は限定する。

採用する用途:

- texture付き三毛猫参照。
- 長毛表現の参考。
- 色味、毛流れ、柄の参考。
- `cat_fluffy_shortleg_pass.glb` の次段階見た目改善に使う比較対象。

採用しない用途:

- 最終可動GLB。
- 直接リグ付きモデル。
- そのままGodotでアニメーションさせる対象。

## 次の作業

1. Tripo v2.5 GLBと `cat_fluffy_shortleg_pass.glb` のプレビューを並べ、見た目改善に使う要素を選ぶ。
2. 必要ならBlender自動処理でTripo assetを正規化し、比較用GLBとして `output/clean_3d/` に出す。
3. Tripo v2.5の参照品質で十分なら、Hunyuan3D texture生成はまだ保留する。
4. Tripo v2.5の形状・textureが不十分なら、Hunyuan3D fallbackを検討する。
