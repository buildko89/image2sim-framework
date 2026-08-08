# Hula 3Dモデル改善調査レポート：前方カメラ・赤外線センサー部分

## 1. 概要

本レポートは、`output/hula_parametric` に出力されているHulaドローン3Dモデルの前方カメラおよび赤外線センサー部について、実機参照画像（`カメラ正面.jpg`, `カメラ横.jpg`, `カメラ寸法.png`）と現行3Dモデル実装（`config/hula_model.yaml`, `blender/drone_model/build_drone.py`）を詳細に比較調査し、差分および改善方針をまとめたものです。

現在地：`D:\source\repos\3DModelDevPJ\image2sim-framework`

---

## 2. 参照資料一覧

| 区分 | パス / ファイル名 | 説明 |
| :--- | :--- | :--- |
| 実機写真（正面） | `input/raw_photos/Hula/カメラ正面.jpg` | 前方カメラ・左右赤外線センサーの配置・目視形状 |
| 実機写真（側面） | `input/raw_photos/Hula/カメラ横.jpg` | カメラモジュールの突出量・サイドピボット・筐体構造 |
| 寸法図（注記） | `input/raw_photos/Hula/カメラ寸法.png` | 実測寸法（高さ25mm, 奥行20mm, メインレンズ10mm, 下部レンズ5mm） |
| 現行3Dモデルレンダー | `output/hula_parametric/renders/front.png`, `left.png` | 現行3Dモデルの前方・側面レンダリング画像 |
| 現行設定ファイル | `config/hula_model.yaml` | 幾何パラメータ（`body`, `equipment.cameras`, `equipment.round_sensors`） |
| 現行生成スクリプト | `blender/drone_model/build_drone.py` | Blenderでの3Dメッシュ生成ロジック |

---

## 3. 実機と現行3Dモデルの差分詳細一覧

### 3.1. 赤外線センサー（Infrared Sensors）の空中浮遊・配置問題

- **実機の仕様 (`カメラ正面.jpg`, `カメラ横.jpg`)**:
  - 左右の赤外線センサー（IRセンサー）は、機体前部のダークグレーフロントノーズフレーム（フロントフェイス／アーム基部構造）の**円形窪み内にフラッシュ（埋め込み）実装**されています。
  - 機体から前方へ突き出たり、宙に浮いた部品ではありません。
- **現行3Dモデルの実装 (`config/hula_model.yaml`, `build_drone.py`)**:
  - `round_sensors` として `infrared_left` (X: -11.5, Y: -47.2, Z: 2.5) および `infrared_right` (X: 11.5, Y: -47.2, Z: 2.5) が定義されています。
  - 機体本体ボディ（`body`）の先端は Y = -45.0 mm で終わるため、Y = -47.2 mm に配置されたセンサー円筒は**機体ボディから2.2 mm離れて空中に浮遊**しています。
  - センサーを保持するフロントフレーム構造が存在しないため、単一の円柱が宙に浮いて見える実装となっています。

---

### 3.2. カメラモジュールの形状（半球ドーム vs 縦長カプセル型）

- **実機の仕様 (`カメラ寸法.png`, `カメラ横.jpg`)**:
  - カメラモジュール全体は、**高さ 25 mm、奥行 20 mm、幅 約16 mm の縦長カプセル形状（角丸ピル形状）**です。
  - 両側面にジンバル可動用の丸型ピボット軸がつき、ダークグレーのフロントフレームに挟まれる構造になっています。
- **現行3Dモデルの実装 (`build_drone.py` line 1292-1303)**:
  - `cameras.front` の `shape` に `hemisphere`（半球ドーム）が指定されており、`create_hemisphere_housing` により単一の半球形状（直径 25 mm）として生成されています。
  - そのため、実機の縦長カプセル感・サイドピボット保持構造が表現されておらず、単純な半球がボディ先端にくっついた形状になっています。

---

### 3.3. レンズ構成（単一レンズ vs 上下2連光学素子）

- **実機の仕様 (`カメラ正面.jpg`, `カメラ寸法.png`)**:
  - カメラモジュールの前面には**上下に並ぶ2つの光学素子**があります：
    1. **上部メインカメラレンズ**: 外径 **$\varnothing 10\text{ mm}$**
    2. **下部サブセンサー/レンズ**: 外径 **$\varnothing 5\text{ mm}$**（メインレンズの直下に同一ハウジング内で一体成形）
- **現行3Dモデルの実装 (`hula_model.yaml`, `build_drone.py`)**:
  - `cameras.front` には単一のレンズ barrel (`lens_diameter_mm: 9.0`) のみが配置されています。
  - 代わりに `round_sensors` 内に `front_lower` (X: 0.0, Y: -49.0, Z: -14.0) という別の浮遊センサーが定義されており、カメラハウジングから離れた下部空間に独立した円筒として孤立配置されています。

---

### 3.4. フロントノーズフレーム（フロントバンパー・フレーム）の欠落

- **実機の仕様 (`カメラ正面.jpg`)**:
  - 上部ホワイトシェルと左右アーム、カメラモジュールを繋ぐダークグレーの**フロントノーズフレーム（バンパー構造）**が存在します。
  - このフレーム内に左右の赤外線センサーが埋め込まれ、中央の開口部にカメラモジュールが収まっています。
- **現行3Dモデルの実装 (`hula_model.yaml`)**:
  - フロントノーズフレームが存在せず、`equipment.boxes` に `front_sensor_panel` (`[34.0, 7.0, 25.0]`, Y: -43.0) という単純な直方体ボックスがボディ内部に埋め込まれているのみです。

---

## 4. 差分比較サマリー表

| 項目 | 実機仕様 (`raw_photos/Hula`) | 現行3Dモデル (`hula_parametric`) | 差分・課題 |
| :--- | :--- | :--- | :--- |
| **赤外線センサー取付** | ノーズフレーム表面にフラッシュ埋め込み | Y=-47.2mmの位置に空中に浮遊配置 | フレーム構造が無く、機体から離れて浮いている |
| **カメラハウジング形状** | 縦長カプセル形 (H:25mm, D:20mm) | 半球ドーム (`hemisphere`, $\varnothing 25\text{mm}$) | 単純半球になっており実機のピル形状と異なる |
| **カメラレンズ構成** | 上下2連 (上:$\varnothing 10\text{mm}$, 下:$\varnothing 5\text{mm}$) | 単一レンズ ($\varnothing 9\text{mm}$) + 浮遊センサー `front_lower` | 下部レンズが別個の浮遊センサー `front_lower` に誤分類 |
| **カメラピボット構造** | フレーム側面に挟み込むディスク状ピボット | 棒状ピンが半球横から露出 | フレーム保持構造が欠落 |
| **フロントフレーム** | アーム・ボディ・カメラを保持するノーズフレーム | 単純な直方体 `front_sensor_panel` のみ | ノーズ一体型の幾何メッシュが存在しない |

---

## 5. 根本原因のコード解析

1. **`config/hula_model.yaml` の定義ミス**:
   - `round_sensors` の座標設定（`infrared_left`, `infrared_right`, `front_lower`）が孤立座標で指定されており、支持フレームとの位置関係が考慮されていない。
   - `front_lower` が独立した round_sensor と扱われ、カメラハウジングモジュールに含まれていない。
2. **`blender/drone_model/build_drone.py` の生成ロジックの制約**:
   - `create_camera_module` (line 1274-1361) が `hemisphere` または `rounded_box` しかサポートしておらず、上下2連レンズを持つ縦長カプセル型カメラハウジングに対応していない。
   - フロントフレーム（赤外線センサー埋め込み用ノーズパーツ）を生成する専用メッシュジェネレータが未実装。

---

## 6. 推奨改善アクション・実装設計案

### 6.1. 設定ファイル (`config/hula_model.yaml`) の改修
1. **`cameras.front` の拡張**:
   - `shape: capsule` または `dual_lens_capsule` を追加。
   - `housing_height_mm: 25.0`, `housing_depth_mm: 20.0`, `housing_width_mm: 16.0` を設定。
   - `main_lens_diameter_mm: 10.0`, `aux_lens_diameter_mm: 5.0` の2連レンズ仕様をパラメータ化。
2. **`round_sensors` の整理**:
   - 独立していた `front_lower` を削除（カメラモジュール内へ統合）。
   - `infrared_left`, `infrared_right` の位置をフロントノーズフレーム表面に修正。

### 6.2. Blender生成スクリプト (`build_drone.py`) の改修
1. **`create_capsule_camera_module` の追加**:
   - 上部 $\varnothing 10\text{ mm}$ / 下部 $\varnothing 5\text{ mm}$ の2連レンズを備えた縦長カプセルカメラメッシュを作成。
2. **`create_front_nose_frame`（フロントノーズフレーム生成）の追加**:
   - ダークグレーマテリアルのノーズフレームを作成し、カメラジンバルのピボットを保持するとともに、左右赤外線センサーの埋め込みソケットを設ける。

---
*レポート作成日: 2026年8月8日*
