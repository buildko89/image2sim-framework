# NVIDIA Omniverse & Isaac Sim 導入・検証ガイド

- 作成日: 2026-09-19
- 対象: `image2sim-framework` で生成した SimReady USD アセットのシミュレーション検証
- 関連ドキュメント: `docs/openusd_integration_plan.md`, `docs/usd_physics_schema_spec.md`

---

## 1. 動作環境・ハードウェア前提要件

Isaac Sim を快適に動作させるためには、以下のハードウェア環境が必要です。

| 項目 | 最低要件 | 推奨要件 |
|---|---|---|
| **OS** | Windows 10/11 64-bit、または Ubuntu 20.04 / 22.04 LTS | Windows 11 64-bit / Ubuntu 22.04 LTS |
| **GPU** | NVIDIA GeForce RTX 2070 以上 (VRAM 8GB) | **GeForce RTX 3080 / 4070 以上 (VRAM 12GB〜16GB)** |
| **GPU ドライバ** | NVIDIA Production Branch 535.xx 以上 (RTX Driver) | 最新の Game Ready または Studio Driver (550.xx以上) |
| **CPU** | Intel Core i7 (第10世代以上) / AMD Ryzen 7 | Intel Core i9 / AMD Ryzen 9 |
| **RAM** | 32 GB 以上 | 64 GB 以上 |
| **ストレージ** | 50 GB 以上の空き容量 (SSD 必須) | 高速 NVMe M.2 SSD |

> [!WARNING]
> NVIDIA GTX シリーズ（GTX 1660等）、Intel Arc、AMD Radeon GPU では Omniverse / Isaac Sim は起動できません（RTX レイトレーシングコアおよび CUDA が必須です）。

---

## 2. インストール手順

### Step 1: NVIDIA アカウントの準備
1. [NVIDIA 公式サイト](https://www.nvidia.com/) にアクセスし、無料の NVIDIA アカウントを作成・ログインします。

### Step 2: Omniverse Launcher のダウンロードとインストール
1. [NVIDIA Omniverse ダウンロードページ](https://www.nvidia.com/ja-jp/omniverse/download/) にアクセスします。
2. 「個人向け (Free)」の **Omniverse Launcher** をダウンロードします。
3. ダウンロードしたインストーラ（`omniverse-launcher-win.exe`）を実行し、画面の指示に従ってインストールします。
4. インストール完了後、Omniverse Launcher を起動し、NVIDIA アカウントでログインします。

### Step 3: Isaac Sim のインストール
1. Omniverse Launcher の上部メニューから **「EXCHANGE（エクスチェンジ）」** タブを開きます。
2. 検索バーに **「Isaac Sim」** と入力します。
3. 検索結果から **「Isaac Sim」** を選択し、**「INSTALL（インストール）」** ボタンをクリックします。
   - ※ バージョンは最新の安定版（例: 2023.1.1 や 4.0.0 以降）を選択します。
   - インストールには 15〜30 GB 程度のダウンロードが発生します。
4. インストールが完了すると、**「LIBRARY（ライブラリ）」** タブに Isaac Sim が追加されます。

---

## 3. 本フレームワークの USD アセットを Isaac Sim で検証する手順

`image2sim-framework` で生成された `drone_assembly.usda` や `root_cat.usda` を Isaac Sim に読み込み、物理シミュレーションをテストする手順です。

### 3.1 ドローンモデル (`drone_assembly.usda`) の物理検証

1. **Isaac Sim の起動**:
   - Omniverse Launcher の「LIBRARY」から Isaac Sim を選択し、**「LAUNCH」** をクリックします。
2. **ステージの読み込み**:
   - メニューバーの `File` → `Open` を選択します。
   - リポジトリ内の以下のパスを選択して開きます：
     ```text
     image2sim-framework/output/drone2_parametric/usd/drone_assembly.usda
     ```
3. **ステージ構成の確認**:
   - 画面右側の **Stage** パネルを展開し、以下が認識されていることを確認します：
     - `/Drone_Root`: `PhysicsRigidBodyAPI`, `PhysicsMassAPI`（質量: 0.0485 kg, 重心位置）
     - `/Drone_Root/Rotor_FL/RevoluteJoint_FL` 等: 各ローターの回転ジョイント（Body0=Motor, Body1=Propeller Spin, Axis=Z）
     - `/Drone_Root/Collision`, `Guards`, `LandingGear`: `PhysicsCollisionAPI`（Convex Hull 凸包）
     - `/Drone_Root/Sensors/FrontFPVCamera`: FPV カメラ
     - `/Drone_Root/Sensors/IMU`: 6軸 IMU ノード
4. **VariantSets の切り替え確認**:
   - `/Drone_Root` を選択し、**Property** パネル内の **Variants** セクションを確認します：
     - `PropellerGuard`: `equipped` ⇔ `none` を切り替えて、ガードの表示/非表示・衝突判定が切り替わることを確認。
     - `Battery`: `1S_300mAh` ⇔ `2S_450mAh` を切り替えて、質量や容量属性が変化することを確認。
5. **物理シミュレーション（PhysX）の実行**:
   - 画面左側のツールバーにある **「Play（再生ボタン ▶）」** をクリックします。
   - 重力（-9.81 m/s²）に従って機体が自然落下し、床面（Ground Plane）に衝突・接地することを確認します。
   - 各ローターの RevoluteJoint が正常に回転可能（エラーや拘束破綻の警告が出ないこと）を確認します。

---

### 3.2 猫モデル (`root_cat.usda`) の検証

1. **ステージの読み込み**:
   - `File` → `Open` から以下を開きます：
     ```text
     image2sim-framework/output_v2/usd/root_cat.usda
     ```
2. **VariantSets & 物理補助の確認**:
   - `/KohaCat` を選択し、Variants を確認：
     - `LOD`: `Full_Groom`（毛シェル4層+髭） ⇔ `Simple_Mesh`（軽量基本メッシュ）の切り替え。
     - `CoatColor`: `Koha_Calico` ⇔ `Brown_Tabby` ⇔ `White` の切り替え。
   - `/KohaCat/Physics`:
     - 尻尾の 4 連ジョイント（`TailJoint_0` 〜 `3`）
     - 4足の球コライダ（`Paw_FL`, `FR`, `RL`, `RR`）
3. **シミュレーション実行**:
   - **Play ▶** を押して、ジョイントの破綻や警告が発生しないことを確認します。

---

## 4. トラブルシューティング

| 現象 | 主な原因 | 対処法 |
|---|---|---|
| 起動時にクラッシュする | GPU ドライバが古い、または RTX 非対応 GPU | 最新の NVIDIA Studio / Game Ready ドライバをクリーンインストールする。 |
| テクスチャが表示されない | 相対パスの参照切れ | `.usda` と同じディレクトリ構造（`./drone_frame.usdc` や `textures/`）が保たれているか確認する。 |
| 再生時にオブジェクトが吹き飛ぶ | ジョイントの body0/body1 の重複、またはコライダ同士の初期めり込み | `CollisionAPI` の approximation を確認し、初期接触マージンを調整する。 |
