# OpenUSD VariantSets & センサー・BOM スキーマ仕様書

- バージョン: 1.0.0
- 作成日: 2026-09-19
- 対象フェーズ: OpenUSD Integration Plan Phase 3
- 関連ドキュメント: `docs/openusd_integration_plan.md`, `docs/usd_physics_schema_spec.md`, `config/drone2_model.yaml`

---

## 1. 概要と目的

本仕様書は、`image2sim-framework` における OpenUSD アセット（ドローンおよび猫モデル）に対し、**VariantSets（非破壊バリエーション切り替え）** および **センサー Prim・BOM（部品表）メタデータ** を統合するための設計およびマッピングルールを策定するものです。

OpenUSD の VariantSets を活用することで、単一のマスターファイル内で：
- 機体構成（プロペラガードの有無、バッテリー容量・質量の違い）
- 外観・毛柄（三毛猫、キジトラ、白猫）
- シミュレーション LOD（高精細毛シェル付き、軽量基本メッシュのみ）
を瞬時に切り替え可能にします。

また、シミュレータ（Isaac Sim 等）でそのまま認識可能なセンサー Prim（Camera, IMU）および製造・運用管理用の BOM 属性を埋め込むことで、完全なデジタルツイン（SimReady）を確立します。

---

## 2. ドローンアセットの VariantSets & センサー & BOM 設計

### 2.1 VariantSets

ドローンのルート Prim `/Drone_Root` に以下の 2 つの VariantSet を付与します。

#### 1. `PropellerGuard` VariantSet
プロペラガードの装着状態を制御します。

| バリアント名 | 状態・挙動 | 備考 |
|---|---|---|
| **`equipped`**（既定） | `/Drone_Root/Guards` を有効化 (`active = true`) | 通常飛行・安全シミュレーション用 |
| **`none`** | `/Drone_Root/Guards` を無効化 (`active = false`) | レース・軽量アクロバット飛行用 |

#### 2. `Battery` VariantSet
搭載バッテリーの仕様・質量・重心オフセットを切り替えます。

| バリアント名 | 仕様 | 質量 | BOMメタデータ |
|---|---|---|---|
| **`1S_300mAh`**（既定） | 1S LiPo (300mAh) | 8.5g | `drone:part_number = "BT20-1S-300"`<br/>`drone:capacity_mah = 300` |
| **`2S_450mAh`** | 2S LiPo (450mAh) | 13.0g | `drone:part_number = "LIPO-2S-450"`<br/>`drone:capacity_mah = 450` |

`/Drone_Root/Battery` Prim に適用され、バリアント選択に応じて質量 (`physics:mass`) および BOM カスタム属性が更新されます。

---

### 2.2 センサー Prim

機体階層 `/Drone_Root/Sensors` 配下に以下のセンサー Prim を配置します。

#### 1. FPV フロントカメラ (`UsdGeom.Camera`)
- **Prim パス**: `/Drone_Root/Sensors/FrontFPVCamera`
- **属性**:
  - `focalLength`: `2.1` (mm)
  - `horizontalAperture`: `3.6` (mm)
  - `verticalAperture`: `2.7` (mm)
  - `clippingRange`: `(0.01, 1000.0)`
  - `projection`: `perspective`
- **配置 (Transform)**:
  - 機首前方上部: `(0.0, 0.015, -0.025)` (USD Y-Up 座標系)

#### 2. IMU 慣性計測ノード (`UsdGeom.Xform`)
- **Prim パス**: `/Drone_Root/Sensors/IMU`
- **属性**:
  - `custom token sensor:type = "6axis_gyro_accel"`
  - `custom double sensor:rate_hz = 1000.0`
  - `custom double sensor:accel_noise_density = 0.0001`
  - `custom double sensor:gyro_noise_density = 0.00005`
- **配置 (Transform)**:
  - 機体重心位置: `(0.0, 0.0035, 0.0)`

---

### 2.3 BOM (Bill of Materials) メタデータ

各構成 Prim に以下のカスタム属性を付与します。

| Prim パス | 属性名 | 型 | 値の例 | 説明 |
|---|---|---|---|---|
| `/Drone_Root` | `drone:model` | string | `"drone2_petron_s"` | 機体モデル識別子 |
| `/Drone_Root` | `drone:vendor` | string | `"Byrobot"` | 機体メーカー |
| `/Drone_Root` | `drone:version` | string | `"1.0"` | アセット仕様バージョン |
| `/Drone_Root/Frame` | `drone:part_number` | string | `"FRM-PETRON-01"` | フレーム部品番号 |
| `/Drone_Root/Frame` | `drone:material` | string | `"CarbonFiber_Polycarbonate"` | 材質定義 |
| `/Drone_Root/Guards` | `drone:part_number` | string | `"GRD-PETRON-01"` | ガード部品番号 |
| `/Drone_Root/Guards` | `drone:supplier` | string | `"BetaFPV"` | 部品サプライヤー |
| `/Drone_Root/Rotor_*` | `drone:part_number` | string | `"MTR-0820-BRUSHED"` | モーター部品番号 |
| `/Drone_Root/Rotor_*` | `drone:motor_type` | string | `"coreless_brushed"` | モーター種別 |

---

## 3. 猫モデル (Koha) の VariantSets 設計

猫モデルのルート Prim `/KohaCat` に以下の 2 つの VariantSet を付与します。

### 3.1 `CoatColor` VariantSet
猫の毛柄バリエーションを切り替えます。

| バリアント名 | 概要 | 実装方式 |
|---|---|---|
| **`Koha_Calico`**（既定） | Koha 三毛猫（写真実測パレット） | `textures/p3_koha9face_basecolor.png` をバインド |
| **`Brown_Tabby`** | キジトラ（茶トラ）パターン | キジトラ用 diffuse テクスチャ／カラー調整 |
| **`White`** | 白猫（単色ソリッド） | アルベド RGB `(0.92, 0.92, 0.92)` を設定 |

### 3.2 `LOD` VariantSet
用途に応じた計算負荷の最適化を行います。

| バリアント名 | 概要 | 実装方式 |
|---|---|---|
| **`Full_Groom`**（既定） | 高精細レンダリング・点検用 | `/KohaCat/Groom` (毛シェル4層 + 髭) を有効化 (`active = true`) |
| **`Simple_Mesh`** | 高速シミュレーション・群衆用 | `/KohaCat/Groom` を無効化 (`active = false`)。基本メッシュのみで動作 |

---

## 4. テスト検証戦略

1. **Variant 切り替え検証**:
   - `PropellerGuard`: `equipped` と `none` の各状態で、Guards Prim の active 状態およびステージの整合性を確認。
   - `Battery`: `1S_300mAh` と `2S_450mAh` の各状態で、質量および BOM 属性の切り替わりを確認。
   - `LOD`: `Full_Groom` と `Simple_Mesh` の各状態で、Groom Prim の active 状態を確認。
   - `CoatColor`: 各バリアントでステージが壊れずにロードできることを確認。
2. **センサー & BOM 属性検証**:
   - Camera Prim の焦点距離、画角、IMU Prim のサンプリングレート等の諸元が正しく設定されていることを確認。
   - 各 Prim の BOM カスタム属性の存在と値を検証。
