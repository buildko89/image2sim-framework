# hula_jp_education_drone パラメトリックモデル生成結果

生成日時：2026-08-08T14:57:24+09:00

## 判定

- 構造・寸法QA：`PASS`
- 使用テンプレート：`quad_x_guarded`
- 配置方式：`square_diagonal`、ローター数：4
- 寸法状態：暫定
- 物理状態：未確定（質量・重心・慣性・ローター回転方向の実測が必要）

## 入力寸法

| 項目 | 値 |
|---|---:|
| 機体全長 | 189.300 mm |
| 機体全幅 | 184.600 mm |
| 機体全高 | 50.000 mm |
| 対角モーター中心間 | 128.000 mm |
| プロペラ直径 | 75.000 mm |
| 中央ボディ前後長 | 90.000 mm |
| 中央ボディ高さ | 35.000 mm |
| body_width_mm | 40.000 mm |
| motor_housing_diameter_mm | 10.000 mm |
| guard_mount_tube_diameter_mm | 15.000 mm |
| front_camera_diameter_mm | 25.000 mm |
| front_camera_protrusion_mm | 20.000 mm |
| front_arm_outer_length_mm | 30.000 mm |
| front_arm_inner_length_mm | 25.000 mm |
| rear_arm_outer_length_mm | 40.000 mm |
| rear_arm_inner_length_mm | 35.000 mm |
| guard_nominal_outer_diameter_mm | 100.000 mm |
| guard_tube_diameter_mm | 3.000 mm |
| guard_mount_to_arc_mm | 40.000 mm |
| guard_height_above_motor_pod_mm | 20.000 mm |
| mass_without_guard_g | 94.000 g |
| mass_with_guard_g | 100.000 g |
| max_takeoff_mass_g | 120.000 g |

## 派生値

- ローターID：fl, fr, rl, rr
- 左右・前後モーター中心間：90.510 mm
- ガード外径：94.090 mm
- ガード内径：88.090 mm
- プロペラ先端の半径方向隙間：6.545 mm
- モーター中心スパン：X=90.510 mm、Y=90.510 mm

## 生成結果

- バウンディング寸法：X=184.600、Y=189.300、Z=50.000 mm
- 中央ボディ寸法：幅=40.000、長さ=90.000、高さ=35.000 mm
- 表示用Mesh数：87
- triangles：22556
- Blender：5.2.0 LTS

## 注意

- 写真は形状判断の資料であり、画像から形状を自動推定しているわけではありません。
- 質量、重心、慣性、各ローター回転方向は実測・確認後に更新してください。
