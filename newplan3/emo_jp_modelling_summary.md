# EMO-JP ドローンショー機体 3Dモデリング完了サマリー (2026-08-05)

## 概要
High Great社ドローンショー専用機体 **EMO-JP** (HG-B03 EMO Formation UAV Drone) およびその拡張アタッチメント（花火/パイロ、レーザー照射、LEDランタン）の3Dパラメトリックモデリング、ならびに `hula_parametric` 拠出のプロペラガード・屈折ストラット・モーターガード・着陸脚（`landing_leg_xx`, `foot_xx`）構造の完全適用を完了しました。

---

## 主な寸法仕様・確定パラメータ

- **全体寸法**: 全長 350 mm × 全幅 318 mm × 全高 136 mm（確定値）
- **対角ホイールベース**: 232 mm（モーター軸間, モーター位置 X/Y: ±82.02 mm）
- **コアボディ**: 125 × 90 × 60 mm (角丸 `rounded_box`, ベベル 8mm)
- **上部アンテナ**: RTK測位アンテナ (φ30 × 高さ35mm)
- **下部発光シェード**: 四角型LEDカバー (123 × 87 × 37mm, 発光マテリアル `led_emissive`)
- **プロペラ**: 5.5インチ (139.7mm, 5528規格) 2ブレード ブルノーズ
- **モーター体 (`motor_xx`)**: 1808規格ブラシレスモーター (φ23mm × 高さ28mm, center Z=-4mm)
- **モーターガードカラー (`guard_mount_xx`)**: φ27mm × 高さ10mm
- **屈折ガードストラット (`guard_xx_strut_01~03`)**: `hula` 方式 bent ストラット 12本 (-90°, 0°, +90°)
- **着陸脚 (`landing_leg_xx`)**: φ8mm × 高さ30mm (center Z=-33mm)
- **ゴム足 (`foot_xx`)**: φ12mm × 高さ5mm (center Z=-50.5mm)

---

## 設定ファイルおよびビルド成果物一覧

1. **標準 EMO-JP 機体**
   - 設定: [`config/emo_jp_model.yaml`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/config/emo_jp_model.yaml)
   - 成果物: [`output/emo_jp_parametric/emo_jp.glb`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output/emo_jp_parametric/emo_jp.glb) / `.blend` (QA: **PASS**)

2. **花火（パイロ）装着機**
   - 設定: [`config/emo_jp_pyro_model.yaml`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/config/emo_jp_pyro_model.yaml)
   - 成果物: [`output/emo_jp_pyro_parametric/emo_jp_pyro.glb`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output/emo_jp_pyro_parametric/emo_jp_pyro.glb) / `.blend` (QA: **PASS**)

3. **レーザー照射装着機**
   - 設定: [`config/emo_jp_laser_model.yaml`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/config/emo_jp_laser_model.yaml)
   - 成果物: [`output/emo_jp_laser_parametric/emo_jp_laser.glb`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output/emo_jp_laser_parametric/emo_jp_laser.glb) / `.blend` (QA: **PASS**)

4. **LEDランタン球体装着機**
   - 設定: [`config/emo_jp_lantern_model.yaml`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/config/emo_jp_lantern_model.yaml)
   - 成果物: [`output/emo_jp_lantern_parametric/emo_jp_lantern.glb`](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output/emo_jp_lantern_parametric/emo_jp_lantern.glb) / `.blend` (QA: **PASS**)

---

## ビルド再生成コマンド

```powershell
python scripts\drone_model\run_build.py --config config\emo_jp_model.yaml --skip-contact-sheet --overwrite
python scripts\drone_model\run_build.py --config config\emo_jp_pyro_model.yaml --skip-contact-sheet --overwrite
python scripts\drone_model\run_build.py --config config\emo_jp_laser_model.yaml --skip-contact-sheet --overwrite
python scripts\drone_model\run_build.py --config config\emo_jp_lantern_model.yaml --skip-contact-sheet --overwrite
```
