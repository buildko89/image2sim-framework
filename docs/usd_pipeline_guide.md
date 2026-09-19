# OpenUSD パイプライン利用手順書 (USD Pipeline Guide)

本ドキュメントは、image2sim-framework における **OpenUSD（Universal Scene Description）を中心としたアセット生成・物理シミュレーション統合（SimReady）・マルチエンジン配信パイプライン** の利用手順および仕様です。

---

## 1. 概要と基本方針 (Single Source of Truth)

本フレームワークでは、**OpenUSD をマスターアセット（Single Source of Truth: SSoT）** として定義しています。

- **マスターアセット (USD)**:
  - 形状（Geometry）、スケルトン（Skeleton）、マテリアル（UsdPreviewSurface）、物理属性（UsdPhysics: 剛体・質量・ジョイント・コライダ）、バリアント（VariantSets）、センサー（Camera/IMU）、BOM メタデータを統合。
  - NVIDIA Isaac Sim / Omniverse や Unreal Engine 5 など、最新の物理シミュレータ・レンダラへ直接ロード可能（SimReady）。
- **派生アセット (Derived GLB / USDZ)**:
  - Godot 4.x などの軽量ゲームエンジンや Web/XR 向けには、マスター USD から自動派生させた最適化 GLB や自己完結型 USDZ パッケージを提供。

詳細なエクスポート方針は [docs/game_engine_export_policy.md](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/game_engine_export_policy.md) を参照してください。

---

## 2. 必要環境

- **OS**: Windows 10/11
- **Python**: 3.10〜3.12 (推奨: Python 3.12)
- **Blender**: 5.2 LTS (標準パス: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`)
- **USD SDK**: `usd-core`

```powershell
pip install -r requirements.txt
pip install usd-core
```

---

## 3. 基本操作：ワンコマンド一括ビルド

`pipeline_v2/run_usd_build.py` を実行することで、USD ステージの生成から物理オーサリング、バリアント設定、USDZ パッケージング、Godot 向け派生 GLB の出力までを一括自動処理します。

### 全アセットの一括ビルド
```powershell
python pipeline_v2/run_usd_build.py --asset all
```

### ドローン（`drone`）のみビルド
```powershell
python pipeline_v2/run_usd_build.py --asset drone
```

### 猫モデル（`cat`）のみビルド
```powershell
python pipeline_v2/run_usd_build.py --asset cat
```

---

## 4. 主な成果物とディレクトリ構成

### ドローンアセット (`drone2_petron_s`)
- **マスター USD**: `output/drone2_parametric/usd/`
  - `drone_assembly.usda`: 物理・センサー・バリアントが統合されたルートステージ
  - `drone_geometry.usdc`: フレーム、ボディ、プロペラ等のメッシュ
  - `drone_collision.usdc`: 凸包コライダジオメトリ
- **SimReady パッケージ**:
  - `output/drone2_parametric/usd/drone2_simready.usdz`: テクスチャ・物理・階層が 1 ファイルにまとまった自己完結型 USDZ
- **Godot 向け派生 GLB**:
  - `output/godot/drone2_derived.glb`: Godot 4.x 向けにコライダ・ボーンを整理した最適化 GLB

### 猫モデルアセット (`koha`)
- **マスター USD**: `output_v2/usd/`
  - `root_cat.usda`: 骨格・三毛柄・毛シェル・バリアントが統合されたルートステージ
  - `geometry.usdc`: 変形済みボディメッシュ
  - `skeleton.usdc`: アニメーション用スケルトン
  - `texture_calico.usda`: 三毛猫マテリアル定義
  - `fur_shells.usdc`: 4層毛シェル & 髭ジオメトリ
- **SimReady パッケージ**:
  - `output_v2/usd/cat_simready.usdz`: 自己完結型 USDZ
- **Godot 向け派生 GLB**:
  - `output_v2/godot/cat_derived.glb`: Godot 4.x 向け派生 GLB

---

## 5. 搭載機能とスキーマ仕様

### ① 物理シミュレーション (UsdPhysics)
- **ドローン**:
  - `UsdPhysics.Scene`: 重力 9.81 m/s²（-Y 方向）
  - `UsdPhysics.RigidBodyAPI` & `MassAPI`: 実測質量（48.5g）、重心オフセット、慣性テンソル
  - `UsdPhysics.RevoluteJoint`: 4 基のローター（FL, FR, RL, RR）の回転軸（Z軸）、回転方向（CW/CCW）、最大回転数（35,000 RPM）
  - `UsdPhysics.CollisionAPI` & `MeshCollisionAPI`: ボディ、フレーム、プロペラガード、脚部に `convexHull` コライダを自動設定
- **猫モデル**:
  - 尻尾の 4 連チェーンジョイント（`UsdPhysics.RevoluteJoint`）
  - 4 足裏の接触球コライダ（`UsdGeom.Sphere` + `UsdPhysics.CollisionAPI`）
  - 胴体メッシュの凸包コライダ

### ② バリアントセット (VariantSets)
再ロードなしで動的に仕様や外観を切り替え可能です：
- **ドローン**:
  - `PropellerGuard`: `equipped`（ガードあり）/ `none`（ガードなし・軽量化）
  - `Battery`: `1S_300mAh`（標準）/ `2S_450mAh`（高出力・質量増加）
- **猫モデル**:
  - `CoatColor`: `Koha_Calico`（三毛猫）/ `Brown_Tabby`（キジトラ）/ `White`（白猫）
  - `LOD`: `Full_Groom`（毛シェル4層あり）/ `Simple_Mesh`（ベースメッシュのみ）

### ③ センサー & BOM メタデータ
- **FPV カメラ**: `UsdGeom.Camera`（焦点距離 2.1mm、広角画角、クリッピング範囲）
- **IMU センサー**: 6 軸ジャイロ・加速度センサーノード（サンプリングレート 1000Hz）
- **BOM メタデータ**: 各部品 Prim に `drone:part_number`, `drone:vendor`, `drone:material` 等の部品台帳データを埋め込み

---

## 6. 目視確認ツール (Blender GUI Viewer)

USD アセットを Blender GUI で直接インタラクティブに確認できます。不要なボーンやコライダを非表示にし、マテリアルプレビュー状態で起動します。

```powershell
# ドローンモデルの確認
python scripts/usd/open_in_blender_gui.py --asset drone

# 猫モデルの確認（毛シェルあり）
python scripts/usd/open_in_blender_gui.py --asset cat

# 猫モデルの確認（軽量 Simple LOD）
python scripts/usd/open_in_blender_gui.py --asset cat --lod simple
```

---

## 7. 自動テスト (CI/CD Quality Assurance)

パイプラインの品質・整合性は `pytest` による自動テストで保証されています。

```powershell
# USD 物理スキーマ、バリアント、マルチエンジンパイプラインの全テストを実行
python -m pytest tests/test_usd_physics.py tests/test_usd_variants_sensors.py tests/test_usd_pipeline_phase4.py -v
```

---

## 8. 関連ドキュメント

- [docs/game_engine_export_policy.md](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/game_engine_export_policy.md): マルチエンジンエクスポート方針 (v2.0.0)
- [docs/usd_physics_schema_spec.md](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/usd_physics_schema_spec.md): USD 物理スキーマ仕様書
- [docs/usd_variants_sensors_spec.md](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/usd_variants_sensors_spec.md): USD バリアント & センサー仕様書
- [docs/isaac_sim_setup_guide.md](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/isaac_sim_setup_guide.md): NVIDIA Isaac Sim 環境導入・検証手順書
- [docs/openusd_integration_plan.md](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/openusd_integration_plan.md): OpenUSD 統合計画書
