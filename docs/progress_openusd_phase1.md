# OpenUSD 統合 Phase 1 進捗レポート

- 日付: 2026-09-19
- 担当: Antigravity
- 参照計画書: [`docs/openusd_integration_plan.md`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/openusd_integration_plan.md)
- 決定事項: [`docs/decisions.md` (DEC-20260919-001)](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/decisions.md)

---

## 1. 完了した作業内容

### 1.1 ポリシー改定と環境構築
- **ポリシー改定**: [`docs/game_engine_export_policy.md`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/docs/game_engine_export_policy.md) を改定し、OpenUSD をマスターアセット（Single Source of Truth）、GLB を派生出力形式とする二段階運用方針を確立。
- **USD SDK (`pxr`) 環境**:
  - システム Python 3.12 に `usd-core 26.8` をインストールし、[`requirements.txt`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/requirements.txt) に `usd-core>=26.0` を追加。
  - Blender 5.2.0 LTS にも `pxr` が標準バンドルされていることを確認。

### 1.2 ドローンモデルのレイヤー分解 & マスターアセンブリ
- **スクリプト**:
  - [`scripts/usd/export_drone_usd_blender.py`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/scripts/usd/export_drone_usd_blender.py)
  - [`scripts/usd/export_drone_usd.py`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/scripts/usd/export_drone_usd.py)
- **出力物**: [`output/drone2_parametric/usd/`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output/drone2_parametric/usd)
  - `drone_frame.usdc`, `drone_guards.usdc`, `drone_landing_gear.usdc`, `drone_rotor_*.usdc`, `drone_collision.usdc`
  - マスターアセンブリ: [`drone_assembly.usda`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output/drone2_parametric/usd/drone_assembly.usda) (各部品を非破壊 Reference 結合)

### 1.3 猫モデル（koha）のパーツ分解 & マスター合成
- **スクリプト**:
  - [`scripts/usd/export_cat_usd_blender.py`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/scripts/usd/export_cat_usd_blender.py)
  - [`scripts/usd/export_cat_usd.py`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/scripts/usd/export_cat_usd.py)
- **出力物**: [`output_v2/usd/`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output_v2/usd)
  - `skeleton.usdc`, `geometry.usdc`, `fur_shells.usdc`
  - マスターステージ: [`root_cat.usda`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output_v2/usd/root_cat.usda)
- **Shell Fur マテリアル表現**:
  - `UsdPreviewSurface` のテクスチャバインディング（diffuseColor, opacity）を確立。
  - `opacityThreshold`（0.0, 0.32, 0.52, 0.70）を各毛シェル層に自動オーサリング。

### 1.4 自動テスト (pytest)
- [`tests/test_usd_export.py`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/tests/test_usd_export.py) を作成し、3件すべてのテストが PASS：
  1. `test_drone_usd_assembly`: PASSED
  2. `test_cat_usd_root`: PASSED
  3. `test_cat_fur_shell_materials`: PASSED

---

## 2. 次回着手予定（Phase 2: USD Physics 実装と SimReady 化）

1. **ドローン YAML `physics` スキーマの拡張設計**:
   - `max_rpm`, `joint_type`, `collision_shape` 等の定義を追加。
2. **USD Physics オーサリングロジックの実装**:
   - `UsdPhysics.RigidBodyAPI`, `UsdPhysics.MassAPI`, `UsdPhysics.RevoluteJoint`, `UsdPhysics.CollisionAPI` を付与。
3. **猫モデルへの物理補助付与**:
   - 尻尾のチェーンジョイント、足裏コライダ。
4. **シミュレータ接続テスト**:
   - NVIDIA Isaac Sim / Omniverse での物理挙動検証。
