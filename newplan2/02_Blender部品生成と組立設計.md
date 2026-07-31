# Blender部品生成と組立設計

## 1. 目的

寸法設定からドローンの各部品を生成し、シミュレーションに必要な階層、回転軸、
衝突形状、物理情報を持つ1個のモデルへ組み立てる。

## 2. 正規生成経路

正規成果物は次の1コマンドで生成する。

```powershell
python scripts\drone_model\run_build.py --config config\drone2_model.yaml
```

ランナーはBlenderを`--background --factory-startup`で起動し、
`blender/drone_model/build_drone.py`を実行する。出力済みファイルがある場合は、
`--overwrite`なしで上書きしない。

Blender MCPは調整と確認に使うが、MCPの会話履歴がなくても同じモデルを再生成できる
ことを必須とする。

## 3. シーン構成

```text
Scene
├─ REF_PHOTOS
│  ├─ ref_top
│  ├─ ref_bottom
│  ├─ ref_front
│  ├─ ref_back
│  ├─ ref_left
│  └─ ref_right
├─ MODEL_VISUAL
│  └─ drone_root
│     ├─ body
│     ├─ arm_fl / arm_fr / arm_rl / arm_rr
│     ├─ motor_fl / motor_fr / motor_rl / motor_rr
│     ├─ rotor_fl / rotor_fr / rotor_rl / rotor_rr
│     └─ guard_fl / guard_fr / guard_rl / guard_rr
├─ ANCHORS
│  ├─ center_of_mass
│  ├─ motor_fl_axis / motor_fr_axis / motor_rl_axis / motor_rr_axis
│  ├─ imu_anchor
│  └─ battery_anchor
├─ COLLISION
│  ├─ collision_body
│  ├─ collision_arm_fl / ...
│  └─ collision_guard_fl / ...
├─ CAMERAS
└─ LIGHTS
```

参照写真、表示用形状、アンカー、衝突形状をCollection単位で切り替えられるようにする。
GLBへは原則として`MODEL_VISUAL`、`ANCHORS`、必要な`COLLISION`だけを出力し、
参照写真と評価カメラは含めない。

## 4. 座標と原点

- `+X`：機体の右
- `-Y`：機体の前
- `+Z`：機体の上
- 長さの内部単位：メートル
- 設定ファイルの入力単位：mm
- `drone_root`の原点：推定重心
- 各ローターの原点：モーター軸中心
- 各ローターのローカル`+Z`：回転軸上向き

表示用モデルの底面を`Z=0`へ置く正規化は行わない。飛翔体では重心原点の方が、
姿勢制御と力・トルク適用に適している。評価レンダーで接地基準が必要な場合は、
評価用コピーだけを移動する。

## 5. 部品ごとの生成方針

### 5.1 中央ボディ

初期形状は角丸直方体を基本とし、上面ドームと下面電池部を別部品にする。

- `body_core`：角丸直方体または断面押出し
- `body_top_shell`：上面輪郭を持つ低いドーム
- `body_bottom_shell`：下面の張り出し
- `body_front_detail`、`body_rear_detail`：写真で明確な場合だけ追加

角丸はBevel Modifier、左右対称はMirror Modifierを優先する。写真の輪郭に合わせるために
多数の頂点を直接編集するのではなく、幅、長さ、高さ、角丸半径、上面高さなどの少数
パラメータで形を制御する。

### 5.2 アーム

最初に前左1本をテンプレートとして生成する。

- 根元と先端で幅が異なる台形プリズム
- 根元高さとモーター側高さを独立指定
- 中央ボディへの食込み量を指定
- モーター中心へ向かうローカル軸を持つ

形状確定後、4方向へ複製する。完全対称を基本とし、写真で確認できた差だけ
`arm_overrides.fl`などで上書きする。

### 5.3 モーターハウジング

円柱と段付き円柱を組み合わせる。ローターとは別Objectにし、ハウジング自体は回転させない。

- 外径
- 高さ
- 上下段の径
- 軸径
- 軸突出量

4個は同じMesh datablockを共有してよい。ただしObject名、位置、カスタムプロパティは
個別に持たせる。

### 5.4 プロペラ

ハブと羽根を別形状として生成し、最終的に1個の`rotor_*`親へまとめる。

- 直径
- 羽根枚数
- 根元幅、先端幅
- 厚さ
- 平面内の後退角
- ピッチ角
- CW／CCWの向き

初期版は、平面輪郭を押し出した低ポリゴン羽根でよい。空力解析用の正確な翼型は別工程とする。
回転時の見た目が必要なら、静止羽根と半透明の回転円盤を切り替えられるようにする。

ローター回転方向は対角で同じにする構成を初期値にできるが、実機の方向を未確認のまま
固定しない。設定ファイルに`cw`または`ccw`を明記する。

### 5.5 プロペラガード

Curveの円弧とBevelを使い、リング部と接続支柱を生成する。

- 外径
- 内径またはチューブ径
- 高さ
- 円弧の欠け角度
- 支柱本数
- 支柱幅、厚さ

写真でガードが完全な円でない場合は、開始角と終了角を設定する。表示用ガードは曲線形状で
よいが、衝突形状は必要に応じて複数の単純BoxまたはCapsuleへ分解する。

### 5.6 小部品

LED、コネクタ、電池蓋、脚、ねじなどは、Blockout合格後に追加する。
最初から細部へ時間を使わず、次の優先順位とする。

1. 外形を決める部品
2. シミュレーション構造に必要な部品
3. 正面・上面で識別性が高い部品
4. 材質・色
5. 微細部品

## 6. 組立方法

### 6.1 基本配置

設定から4個のモーター中心座標を求め、その位置を部品配置の正とする。
アームは中央ボディ接続点からモーター中心へ伸ばす。

```text
body center → arm → motor housing → rotor axis
                           └→ propeller guard
```

部品を目視で移動して組み立てない。位置と回転はすべて設定から計算する。

### 6.2 対称性と差分

標準値から4方向を作った後、次のような差分だけを許可する。

```yaml
overrides:
  motor_fl:
    offset_mm: [0.0, 0.0, 0.0]
  guard_rr:
    rotation_deg: [0.0, 0.0, 1.5]
```

差分には必ず写真または実測の根拠を`note`へ書く。単なる写真傾きを部品非対称として
モデル化しない。

## 7. 表示用形状と物理用形状

### 7.1 表示用

- 外観確認用
- 適切なBevelと法線を持つ
- LOD0の目標は概ね2万～6万triangles
- 小部品は必要に応じて統合可能

### 7.2 衝突用

- 中央ボディ：Box、Convex Hull、または少数の凸形状
- アーム：4本のBoxまたはCapsule
- モーター：Cylinder
- ガード：必要な場合だけ分割Capsule
- プロペラ：通常は衝突対象から除外し、回転円盤またはセンサー領域として扱う

衝突用メッシュは表示用メッシュから自動Decimateしたものを正としない。単純形状を
設定値から直接作る。

## 8. 質量と慣性

写真と外形だけから正確な質量分布は決められない。次の段階で扱う。

1. 実機総質量を測る。
2. 重心を吊り下げ法またはバランス法で推定する。
3. 初期慣性はBox近似または部品質量配分から計算する。
4. 実機ログや応答が得られたら慣性を同定して更新する。

表示メッシュの体積に一様密度を掛けた値は、確認用の参考値に限定する。電池やモーターが
集中質量を持つため、その値をそのまま飛行物理へ使わない。

設定とGLB extrasには次を保持する。

```text
mass_kg
center_of_mass_m
inertia_diagonal_kg_m2
inertia_source
```

## 9. オブジェクト命名規約

| 種類 | 例 |
|---|---|
| ルート | `drone_root` |
| 表示用中央部 | `body_core`、`body_top_shell` |
| アーム | `arm_fl`、`arm_fr`、`arm_rl`、`arm_rr` |
| モーター | `motor_fl`、`motor_fr`、`motor_rl`、`motor_rr` |
| ローター | `rotor_fl`、`rotor_fr`、`rotor_rl`、`rotor_rr` |
| ガード | `guard_fl`、`guard_fr`、`guard_rl`、`guard_rr` |
| 回転軸Empty | `motor_fl_axis`など |
| 衝突形状 | `collision_body`、`collision_arm_fl`など |

Blenderが自動付与する`.001`を正規名として許可しない。生成前に対象Collectionを明示的に
作り直し、名前衝突を検査する。

## 10. 写真参照シーン

既存の`blender/create_reference_scene.py`は写真を横一列へ並べる用途であり、立体採寸には
そのまま使わない。新しい`references.py`では次を行う。

- 6枚を機体中心へ向けた参照面またはCamera Backgroundとして配置
- 写真ごとに独立した倍率、回転、平行移動を保持
- 上、下、前、後、左、右の正投影カメラを作成
- 参照写真の表示／非表示を一括切替
- 元画像パス、画像ハッシュ、補正値をカスタムプロパティへ記録

参照画像はGLBへ出力しない。

## 11. MCPを使った調整手順

1. 正規スクリプトで`drone2.blend`を生成する。
2. Blenderを起動し、MCPサーバーを開始する。
3. Codexがシーン、Collection、Object名、寸法、Modifierを読み取る。
4. 6方向の参照カメラを順に表示し、スクリーンショットで差を確認する。
5. 修正値を`config/drone2_model.yaml`へ反映する。
6. バックグラウンドビルドを再実行する。
7. 比較レンダーとQAを更新する。

探索のためMCPで形状を直接変更した場合は、その`.blend`を最終成果物にしない。
変更内容をスクリプトへ移植し、工場出荷状態から再生成して一致を確認する。

## 12. エクスポート

GLB出力前に次を実施する。

- 参照Collectionと評価カメラを除外
- 対象Objectを明示的に選択
- scaleを適用し、負のscaleがないことを検査
- 原点とローカル軸を検査
- 単位をメートルに統一
- カスタムプロパティをextrasとして出力
- 部品名の重複と`.001`を検査
- 表示用と衝突用の命名を維持

`.blend`は編集・調整用、GLBはゲームエンジン連携用として両方保存する。
