# USD Physics スキーマ拡張仕様書 (USD Physics Schema & Mapping Specification)

- バージョン: 1.0.0
- 作成日: 2026-09-19
- 対象フェーズ: OpenUSD Integration Plan Phase 2
- 関連ドキュメント: `docs/openusd_integration_plan.md`, `config/drone2_model.yaml`

---

## 1. 概要と目的

本仕様書は、`image2sim-framework` における機体（ドローン等）および生物モデル（Koha猫等）に対して、**OpenUSD 標準の物理拡張（USD Physics スキーマ / `pxr.UsdPhysics`）** を適用するための YAML スキーマ拡張定義およびデータ変換マッピングルールを策定するものです。

これにより、Blender で生成されたビジュアル階層モデルに対し、質量特性、可動ジョイント（プロペラ回転軸等）、衝突判定（コライダ）、物理シーン定義を完全自動かつ非破壊に付与し、NVIDIA Isaac Sim / Omniverse、MuJoCo、Unreal Engine 等のシミュレータで即座に動作可能な「SimReady」アセットを確立します。

---

## 2. 座標系と単位の定義

USD エクスポート基盤（Phase 1）において、ステージメタデータは以下のように統一されています：

| 項目 | 値 | 備考 |
|---|---|---|
| `metersPerUnit` | `1.0` | メートル単位系 (MKS) |
| `upAxis` | `"Y"` | USD / glTF 標準の Y-Up |
| 重力方向ベクトル | `[0.0, -1.0, 0.0]` | -Y 方向（下向き） |
| 標準重力加速度 | `9.81` m/s² | `physics:gravityMagnitude = 9.81` |

### 座標変換ルール (Blender → USD)
Blender 内の座標系（Z-Up, -Y 前方, +X 右）から USD ステージ（Y-Up, +Z 前方/または -Z 前方, +X 右）への変換は、Blender の USD エクスポータ (`convert_orientation=True`) により自動変換されます。
YAML 内の寸法・位置は原則として **mm単位** または **m単位** で記述されるため、USD Physics へのマッピング時に以下の単位変換を適用します：
- 長さ・位置: `mm / 1000.0` → `m`
- 質量: `g / 1000.0` → `kg`
- 慣性モーメント: `kg·m²`（そのまま）

---

## 3. YAML `physics` スキーマ拡張定義

現行の `config/drone2_model.yaml` 等に含まれる `physics:` セクションを以下のように拡張・標準化します。

```yaml
physics:
  # --- 1. 機体全体の剛体・質量特性 ---
  enabled: true
  mass_g: 48.5                         # 機体総質量 (g)。null の場合は各コンポーネントの合算または形状推定
  center_of_mass_mm: [0.0, 0.0, 3.5]   # 機体重心位置 [X, Y, Z] (mm)
  center_of_mass_source: measured      # measured | photo_estimated | derived | placeholder
  inertia_kg_m2:                       # 主慣性モーメント [Ixx, Iyy, Izz] (kg·m²)
    ixx: 2.1e-5
    iyy: 2.3e-5
    izz: 3.8e-5
  inertia_source: estimated            # measured | estimated | cad | pending

  # --- 2. 衝突判定 (Collision) 設定 ---
  collision:
    enabled: true
    default_approximation: convexHull  # convexHull | boundingCube | boundingSphere | convexDecomposition | mesh
    collision_groups:
      - name: drone_body
        prims: ["Collision", "Frame", "Guards"]
        approximation: convexHull
      - name: landing_gear
        prims: ["LandingGear"]
        approximation: convexHull

  # --- 3. 可動機構 (Joints) 設定 ---
  rotors:
    joint_type: revolute               # revolute (回転) | fixed (固定)
    axis: Z                            # 回転軸 (ローカル軸: X | Y | Z)
    max_rpm: 35000                     # 最大許容回転数 (rpm)
    free_spin: true                    # true の場合リミットなし (無限回転)
    damping: 1.0e-6                    # ジョイント減衰 (N·s/rad)
    friction: 1.0e-5                   # 静止摩擦
    # 各ローターごとの個別指定 (任意)
    overrides:
      fl: { direction: ccw, max_rpm: 35000 }
      fr: { direction: cw,  max_rpm: 35000 }
      rl: { direction: cw,  max_rpm: 35000 }
      rr: { direction: ccw, max_rpm: 35000 }

  # --- 4. 環境・シーン設定 ---
  scene:
    gravity_magnitude: 9.81            # 重力加速度 (m/s²)
    gravity_direction: [0.0, -1.0, 0.0] # Y-Up ステージにおける重力方向
```

---

## 4. YAML から USD Physics へのマッピング仕様

### 4.1 物理シーン (`UsdPhysics.Scene`)
- **Prim パス**: `/PhysicsScene` または `/{RootPrim}/PhysicsScene`
- **適用 API**: `UsdPhysics.Scene.Define(stage, scene_path)`
- **属性マッピング**:
  - `gravityDirection`: `Gf.Vec3f(*yaml["physics"]["scene"]["gravity_direction"])`
  - `gravityMagnitude`: `float(yaml["physics"]["scene"]["gravity_magnitude"])`

### 4.2 剛体・質量 (`UsdPhysics.RigidBodyAPI`, `UsdPhysics.MassAPI`)
- **適用対象 Prim**: `/{RootPrim}` (例: `/Drone_Root`)
- **属性マッピング**:
  - `UsdPhysics.RigidBodyAPI.Apply(prim)`:
    - `rigidBodyEnabled = True`
  - `UsdPhysics.MassAPI.Apply(prim)`:
    - `mass = mass_g / 1000.0` (kg)
    - `centerOfMass = Gf.Vec3f(cx_m, cy_m, cz_m)` (m単位に変換)
    - `diagonalInertia = Gf.Vec3f(ixx, iyy, izz)` (kg·m²)

### 4.3 回転ジョイント (`UsdPhysics.RevoluteJoint`)
- **Prim パス**: `/{RootPrim}/Rotor_{ID}/RevoluteJoint_{ID}` (例: `/Drone_Root/Rotor_FL/RevoluteJoint_FL`)
- **適用 API**: `UsdPhysics.RevoluteJoint.Define(stage, joint_path)`
- **リレーション (Relationship)**:
  - `body0`: モーター固定部 Prim パス
    - 例: `/Drone_Root/Rotor_{ID}/Rotor_{ID}/drone_root/rotor_{id}/motor_{id}`
  - `body1`: プロペラ回転部 Prim パス
    - 例: `/Drone_Root/Rotor_{ID}/Rotor_{ID}/drone_root/rotor_{id}/rotor_{id}_spin`
- **属性マッピング**:
  - `axis`: `"Z"` (プロペラ推力軸)
  - `lowerLimit` / `upperLimit`: **作成しない**（USD Physics では属性未設定 = 無制限回転と解釈）
  - カスタム属性:
    - `custom double drone:max_rpm = max_rpm`
    - `custom string drone:spin_direction = direction` ("cw" / "ccw")

### 4.4 衝突判定 (`UsdPhysics.CollisionAPI`, `UsdPhysics.MeshCollisionAPI`)
- **適用対象 Prim**:
  - `/{RootPrim}/Collision` (専用コライニメッシュ)
  - `/{RootPrim}/Guards` (プロペラガード)
  - `/{RootPrim}/LandingGear` (脚部・足)
- **属性マッピング**:
  - `UsdPhysics.CollisionAPI.Apply(prim)`:
    - `collisionEnabled = True`
  - `UsdPhysics.MeshCollisionAPI.Apply(prim)`:
    - `approximation = "convexHull"` (または YAML 指定の approximation)

---

## 5. 既存 MuJoCo / 物理アンカー (`ANCHORS`) との整合方針

`build_drone.py` にて生成される `ANCHORS` コレクションおよび `blend2mjcf.py` 設計との整合性は以下の通りとします：

1. **重心 (Center of Mass)**:
   - `build_drone.py` は `ANCHOR_CENTER_OF_MASS` コレクションに Empty `center_of_mass` を配置する。
   - USD Physics の `UsdPhysics.MassAPI.centerOfMass` にはこの Empty のローカル座標（mm → m 変換後）がそのまま採用されるため、完全な整合性が保たれる。
2. **推力軸 (Motor / Propeller Axes)**:
   - `build_drone.py` は `motor_{id}_axis` をプロペラ中心に配置し、ローカル +Z 軸を推力方向と定義している。
   - USD Physics の `RevoluteJoint` においても、回転軸をローカル `"Z"` と設定することで、MuJoCo MJCF の `<joint type="hinge" axis="0 0 1"/>` と 1:1 に対応する。
3. **共存方式**:
   - `blend2mjcf.py`（MuJoCo 変換スクリプト）は引き続き `.blend` または `.glb` の `ANCHORS` / `COLLISION` コレクションを参照して動作可能。
   - USD Physics は `.blend` を介さずに USD ステージ上で直接オーサリングされ、Omniverse / Isaac Sim や Unreal Engine へ直接供給される。両者は Single Source of Truth である YAML `physics` 定義を共有する。

---

## 6. 猫モデル (Koha) への物理補助設計

1. **尻尾チェーンジョイント**:
   - 尻尾の関節（`Tail_01` 〜 `Tail_14`）に対して、隣接ボーン間に `UsdPhysics.RevoluteJoint` または柔軟ジョイントを設定。
   - 走る・歩くモーションに自然なしなり（Secondary Motion）を付加。
2. **足裏・胴体コライダ**:
   - 前足・後足の肉球部分および腹部・胸部に `UsdPhysics.CollisionAPI` および `UsdPhysics.MeshCollisionAPI` (`convexHull`) を付与。
   - 地面や障害物との接触シミュレーションを可能にする。
