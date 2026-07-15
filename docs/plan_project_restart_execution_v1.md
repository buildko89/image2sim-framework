# 🚀 ネコ3Dモデル開発PJ — 再スタート実行計画 v1

> **作成日:** 2026-07-08  
> **方針:** Route B（既存猫モデル + テクスチャ変更）先行 → Route A（AIメッシュ生成）へ段階移行  
> **Route C（フォトグラメトリ）:** 除外（ネコの撮影が非現実的）

---

## 0. PCスペックと制約

| 項目 | スペック |
|------|---------|
| CPU | Intel Core i9-12900HX (16コア / 24スレッド) |
| RAM | 64 GB |
| GPU | **NVIDIA GeForce RTX 4060 Laptop (8GB VRAM)** |
| iGPU | Intel UHD Graphics |
| OS | Windows |

### VRAM 8GB での制約

| ツール | 利用可否 | 備考 |
|--------|---------|------|
| TRELLIS 2 | ❌ 困難 | 16GB+ VRAM 推奨。8GB では品質低下 |
| Hunyuan3D | ✅ 可能 | Web版無料。ローカルは `--low_vram` モード対応 |
| TripoSR | ✅ 可能 | ~6GB VRAM。ローカル実行可能 |
| Pixal3D | ⚠️ 条件付き | GGUF量子化版で6GB対応の報告あり。Web/API版も利用可 |
| Blender | ✅ 問題なし | Cycles CPUレンダリングは RAM 64GB で十分 |

### Pixal3D について

- **2026年SIGGRAPH発表** のTencent ARC Lab開発モデル
- 「ピクセル整列」方式で入力画像への忠実度が高い
- PBR テクスチャ（最大4K）生成対応
- ローカル実行は通常24GB VRAM推奨だが、GGUF量子化版で6GBでも動作可能
- **Web/APIでの利用** が8GB VRAMの環境では現実的
- Route A で AI メッシュ生成を試す際の候補として有力

---

## 1. 既存アセット棚卸し結果

### 利用可能な猫モデル

| モデル | パス | リグ | アニメ | テクスチャ | サイズ |
|--------|------|------|--------|-----------|--------|
| **Koha9 Cat** | `input/cat2/koha9_cat/scene.gltf` | ❌ なし（MorphTargetのみ） | ✅ MorphTarget | ✅ 2枚 (baseColor) | 67MB |
| **House Cat** | `input/cat/.../Model/House_cat.fbx` | ✅ あり | ✅ あり | 要確認 | 4.1MB |
| **Lazy Cat** | `input/cat/.../Model/Lazy_cat.fbx` | ✅ あり | ✅ あり | 要確認 | 4.7MB |
| **Modn Cat** | `input/cat/.../Model/Modn_cat.fbx` | ✅ あり | ✅ あり | 要確認 | 3.9MB |
| **Nimble Cat** | `input/cat/.../Model/Nimble_cat.fbx` | ✅ あり | ✅ あり | 要確認 | 3.1MB |
| **Leopard Hybrid** | `input/cat/.../Leopard_Hybrid_A1.Fbx` | ✅ あり | ✅ あり | ✅ Diffuse+Normal+Opacity | 71MB |
| **Cat.fbx** | `input/cat/uploads_files_5203269_Cat.fbx` | 要確認 | 要確認 | 要確認 | 23.6MB |
| **White Tiger** | `input/cat/uploads_files_5119404_White+Tiger.blend` | 要確認 | 要確認 | 要確認 | 155MB |

> ⚠️ **重要発見:** koha9_cat は **スキン（リグ）なし** です。MorphTarget アニメーションはありますが、骨格ベースのアニメーションには非対応。
> Route B のベースモデルとしては、**リグ付きの `input/cat/` モデル群**（House_cat, Lazy_cat 等）の方が適切です。

### 再利用するスクリプト・設定

| ファイル | 用途 | 状態 |
|---------|------|------|
| `scripts/080_extract_cat_color_palette.py` | カラーパレット抽出 | ✅ そのまま使える |
| `config/cat_color_palette.yaml` | 抽出済みパレット | ✅ そのまま使える |
| `input/selected_photos/*.jpg` | 参照写真 | ✅ 選定済み |

---

## 2. Phase 1: Route B 実行計画（1〜2週間）

### 目標

```
既存のリグ付き猫モデル + 写真由来のカラーパレット → 三毛猫テクスチャ → Godot で動く猫
```

### タスク一覧

| # | タスク名 | 内容 | 自動化 | 成果物 |
|---|---------|------|--------|--------|
| B-0 | **モデル棚卸し・選定** | input/cat の全モデルを Blender で開き、リグ・メッシュ・アニメーション品質を確認。ベストモデルを1つ選定 | Python スクリプト (Blender CLI) | 棚卸しレポート (JSON) + ベストモデル決定 |
| B-1 | **ベースモデル準備** | 選定モデルを Blender で開き、スケール正規化・原点設定・不要オブジェクト削除 | Python スクリプト (Blender CLI) | `output_v2/base/cat_base_clean.blend` |
| B-2 | **カラーパレット確認** | 既存の `cat_color_palette.yaml` を確認。不足なら `080_extract_cat_color_palette.py` を再実行 | 既存スクリプト | `config/cat_color_palette.yaml` (確認 or 更新) |
| B-3 | **テクスチャ生成・適用** | パレットを使い、ベースモデルの UV に三毛猫パターンをペイント。Blender のテクスチャペイントを Python で自動化 | Python スクリプト (Blender CLI) | テクスチャ PNG + 適用済み .blend |
| B-4 | **GLB/FBX エクスポート** | テクスチャ適用済みモデルを GLB/FBX でエクスポート | Python スクリプト (Blender CLI) | `output_v2/final/cat_calico_v1.glb` |
| B-5 | **Godot 検証** | GLB を Godot にインポートし、表示・アニメーション再生を確認 | 手動 (Godot) | スクリーンショット + 確認レポート |

### B-0: モデル棚卸しスクリプトの方針

```
[入力] input/cat/*.fbx, input/cat2/koha9_cat/scene.gltf
[処理] Blender CLI で各モデルをロード → 情報抽出
[出力] JSON レポート:
  - メッシュ数、頂点数、ポリゴン数
  - アーマチュア有無、ボーン数
  - アニメーション一覧 (アクション名、フレーム数)
  - マテリアル数、テクスチャ有無
  - バウンディングボックスサイズ
```

### B-3: テクスチャ生成の方針

**以前の失敗との違い:**

| 項目 | 以前 (失敗) | 今回 |
|------|-----------|------|
| ベースモデル | Fox から変形した `cat_animated.blend` | **未加工の猫FBXモデル** |
| テクスチャ方式 | 頂点カラー → ベイク (複雑) | **UV テクスチャに直接ペイント** (シンプル) |
| パイプライン | 累積変形チェーン (Task 55→...→81) | **独立した1スクリプト** |
| 座標系問題 | 複数モデル間の座標変換が複雑 | **1モデル完結** |

---

## 3. Phase 2: Route A 実行計画（2〜4週間、Phase 1 完了後）

### 目標

```
猫写真 → AI 3Dメッシュ生成 → リトポ → Route B で選定したモデルのリグを転写 → テクスチャ → Godot
```

### タスク一覧

| # | タスク名 | 内容 | 自動化 | 成果物 |
|---|---------|------|--------|--------|
| A-1 | **AI 3D生成環境セットアップ** | TripoSR ローカルセットアップ + Hunyuan3D Web版の利用確認 + Pixal3D Web/API確認 | 手動 + スクリプト | 動作確認レポート |
| A-2 | **静的メッシュ生成** | 選定した猫写真から複数ツールで3Dメッシュ生成。比較評価 | ツール依存 | `output_v2/meshes/` に生成メッシュ群 |
| A-3 | **メッシュ品質評価・選定** | 生成メッシュを Blender で開き、形状・トポロジー・テクスチャ品質を比較 | Python スクリプト (Blender CLI) | 評価レポート + ベストメッシュ選定 |
| A-4 | **リトポロジー** | 選定メッシュをゲーム向けポリゴン数にリトポ | Blender (Remesh / Instant Meshes) | リトポ済みメッシュ |
| A-5 | **UV展開** | リトポ済みメッシュの UV 展開 | Blender Smart UV Project | UV付きメッシュ |
| A-6 | **リグ転写** | Phase 1 で使用した猫モデルのアーマチュアを生成メッシュに適用 | Python スクリプト (Blender CLI) | リグ付きメッシュ |
| A-7 | **ウェイト調整** | 自動ウェイトペイント → 問題箇所の確認 | Blender 自動 + 手動微調整 | ウェイト調整済みモデル |
| A-8 | **テクスチャ適用** | Phase 1 で作成したテクスチャ or AI生成PBRテクスチャを適用 | Python スクリプト | テクスチャ付きモデル |
| A-9 | **アニメーション適用** | 既存アニメーションをリターゲット or 新規作成 | Blender | アニメーション付きモデル |
| A-10 | **エクスポート・Godot 検証** | GLB/FBX → Godot | スクリプト + 手動 | 最終モデル + 確認レポート |

---

## 4. AI 3Dメッシュ生成ツール選定（VRAM 8GB 対応）

### 優先順位

| 優先度 | ツール | 利用方法 | 期待品質 | 備考 |
|--------|--------|---------|---------|------|
| 1️⃣ | **Hunyuan3D** | Web版 (無料) | ⭐⭐⭐⭐ | 最も手軽。アカウント不要で即利用可 |
| 2️⃣ | **TripoSR** | ローカル (~6GB VRAM) | ⭐⭐⭐ | MIT License。高速。ローカルで完結 |
| 3️⃣ | **Pixal3D** | Web/API or GGUF量子化版 | ⭐⭐⭐⭐⭐ | 2026年最新。ピクセル整列で高忠実度。Web版推奨 |
| 4️⃣ | **Meshy AI** | Web (Free Tier) | ⭐⭐⭐ | ゲーム向けPBR出力。無料枠あり |

### 推奨手順

1. まず **Hunyuan3D Web版** で猫写真から生成を試す（無料・即座に結果確認）
2. 並行して **TripoSR** をローカルセットアップ（既に `.venv_triposr` が存在）
3. 品質に不満があれば **Pixal3D** の Web/API を試す
4. 複数ツールの結果を比較し、最良のメッシュを選定

---

## 5. 新ディレクトリ構造

```
image2sim-framework/
├── input/                       # 既存 (変更なし)
│   ├── raw_photos/
│   ├── selected_photos/
│   ├── cat/                     # リグ付き猫モデル群
│   └── cat2/koha9_cat/       # MorphTarget猫モデル
├── config/                      # 既存 (変更なし)
│   └── cat_color_palette.yaml
├── pipeline_v2/                 # 🆕 新パイプラインスクリプト
│   ├── b0_inspect_cat_assets.py       # モデル棚卸し
│   ├── b1_prepare_base_model.py       # ベースモデル準備
│   ├── b3_generate_calico_texture.py  # テクスチャ生成
│   ├── b4_export_model.py             # エクスポート
│   ├── a1_setup_ai_tools.py           # AI ツールセットアップ
│   ├── a2_generate_mesh.py            # AI メッシュ生成
│   └── ...
├── output_v2/                   # 🆕 新出力 (v1 の output/ と分離)
│   ├── base/                    # ベースモデル
│   ├── meshes/                  # AI 生成メッシュ
│   ├── final/                   # 最終出力 (GLB/FBX)
│   ├── textures/                # テクスチャ
│   ├── reports/                 # レポート
│   └── godot/                   # Godot ステージング
├── output/                      # 旧出力 (凍結・参照用に残す)
├── scripts/                     # 旧スクリプト (凍結・参照用に残す)
├── blender/                     # 旧Blenderスクリプト (凍結・参照用に残す)
└── docs/                        # ドキュメント
```

---

## 6. 設計原則（前回の失敗から学んだ教訓）

### ❌ やらないこと

1. **累積変形チェーン** — `.blend` を次々加工しない。各スクリプトは入力→出力が明確
2. **Fox モデルの流用** — Fox 由来のファイルは一切使わない
3. **過度なスクリプト分割** — 目的ごとに最小限のスクリプトに留める
4. **Shader Node 自動化** — Blender バージョン依存が高く、失敗リスク大
5. **一度に完璧を目指す** — Phase 1 は「動けば OK」の精神

### ✅ やること

1. **独立タスク方式** — 各スクリプトは `入力ファイル → 出力ファイル` が明確
2. **未加工モデルを直接使用** — 変形の累積を防ぐ
3. **Phase 1 で早期成功** — Godot で動く猫を最短で実現
4. **都度 Godot で確認** — 各ステップの成果物を Godot にインポートして目視確認
5. **Python スクリプトでの補助** — Blender 手動操作を最小化し、再現性を確保

---

## 7. 次のアクション

### 即座に実行 (今日〜明日)

1. ✅ `pipeline_v2/` ディレクトリと `output_v2/` ディレクトリを作成
2. ✅ **B-0: モデル棚卸しスクリプト** を作成・実行し、ベストモデルを選定
3. ✅ `config/cat_color_palette.yaml` の内容確認

### Phase 1 (1〜2週間)

4. B-1: ベースモデル準備
5. B-2: カラーパレット確認
6. B-3: テクスチャ生成・適用
7. B-4: GLB/FBX エクスポート
8. B-5: Godot 検証

### Phase 2 (Phase 1 完了後)

9. A-1〜A-10: AI メッシュ生成 → リグ転写パイプライン
