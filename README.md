# image2sim-framework

実在の猫（koha）の写真から、ゲームエンジンで動く リグ+アニメーション付き 3D モデルを作るプロジェクト。

現在の成果物は **`output_v2/base/p3_koha9face.glb`**（三毛猫 koha の可動モデル。8アニメーション内蔵、
Godot 4.x で再生確認済み）。このリポジトリには、その生成パイプライン一式と経緯ドキュメントが入っている。

| 顔（正面, 1440px キャプチャ） | 全アニメ × 4方向 |
|---|---|
| ![face](docs/images/koha9face_head_front.png) | ![overview](docs/images/koha9face_overview.png) |

## 経緯（v1 → v2）

- **v1**（タグ `v1-tripo` まで）: 画像→3D 生成（TripoSR 等のローカル生成、Tripo API 検証）を軸にした
  汎用フレームワーク構想。写真からの直接生成は品質が足りず、方針転換した。
- **v2**（現在, `pipeline_v2/`）: **市販のリグ付き猫ベースモデルを土台に、写真の猫へ「作り替える」**
  アプローチ。再バインド→体型・顔のメッシュ変形→写真実測の三毛柄をテクスチャに焼き込み→髭・毛シェル
  生成→アニメーションのリターゲット、までをすべてスクリプトで決定的に再生成できる。

## v2 パイプラインの構成

すべて `python pipeline_v2/<script>.py` で実行する（Blender 5.0 を `--background` で呼ぶ）。

| 段 | ランナー | 内容 |
|---|---|---|
| P1a〜P2 | `p2_run.py` | ベースモデルの再バインド（Automatic Weights + Data Transfer）→ 頭・体型の整形 → 尻尾カール（Apply as Rest Pose）→ 8アニメのワールド差分リターゲット |
| UVベイク | `p3_uv_bake.py` | UV テクセル→3D位置/支配ボーンのマップ（柄を3D座標で定義するための土台） |
| P3〜P4 | `p3_run_koha9face.py` | 三毛柄の塗り（写真実測パレット）→ 髭生成 → 毛シェル4層 → 尻尾高密度化・細身化・伸長 → 機械ゲート → 1440px キャプチャ |

品質は2本の機械ゲートで回帰検証する:

- `qa_skin_stretch.py` — 全アニメの辺の伸びからスキニング破綻を検出（皮膚 0.5% / 毛シェル 1.0%）
- `qa_belly_bind.py` — 腹のウェイトが脚ボーンに吸われていないか

顔まわりの数値調整の方法は **`FACE_TUNING_GUIDE.md`** にまとめてある。
メッシュ変形時の塗りアンカー追従は `pipeline_v2/p4_remap_anchors.py`（新旧 UV ベイクの同一テクセル対応）。

## リポジトリ構成

```text
pipeline_v2/   v2 パイプライン本体（現在の主戦場）
newplan/       v2 の経緯・結果ドキュメント（P0仕様、各段の結果、セッションログ）
blender/       v1〜v2 初期の Blender スクリプト群
godot/         Godot 確認用プロジェクト（ViewKoha9.tscn = 実機ビューア）
docs/          v1 の設計・タスク文書 + 調査メモ
scripts/       v1 のタスクスクリプト（画像インベントリ・背景除去・Tripo 検証）
config/        パレット等の設定（cat_color_palette_v3_raw_photos.yaml が現行）
output_v2/     生成物（p3_koha9face の glb/blend/テクスチャのみコミット。他はローカル再生成）
FACE_TUNING_GUIDE.md   顔の数値調整ガイド
```

## 含めていないもの（公開リポジトリのため）

- `input/` — 実物の猫の写真 **再配布不可のため除外**
- `output_v2/` の大部分 — パイプラインで決定的に再生成できる中間生成物・バックアップ
- `png/`、Godot が自動展開したテクスチャ

**アセットの利用について**: コミットされている `p3_koha9face.*`（GLB/blend/テクスチャ）は、プレビュー・学習目的での閲覧を想定しており、**素材としての再配布・再利用はできません**。

## 再生成のしかた（ローカル）

前提: Windows / Blender 5.0 / Python 3.x / `input/` に素材と写真がある環境。

```powershell
python pipeline_v2\p2_run.py                                   # 上流（バインド〜リターゲット）
python pipeline_v2\p3_uv_bake.py --glb output_v2\base\p2_koha.glb
python pipeline_v2\p3_run_koha9face.py                         # 柄・髭・毛・ゲート・キャプチャ
```

結果画像: `output_v2/reports/p1_shots/p3k9f_head_*.png`（顔4方向）、
`output_v2/reports/p1_contact_p3k9f_overview.png`（全アニメ×4方向）。

## v1 のドキュメント

v1 期のタスク仕様・レビュー運用は `docs/`（workflow.md, decisions.md, backlog.md 等）に残している。
v1 最終時点のコードはタグ `v1-tripo` を参照。
