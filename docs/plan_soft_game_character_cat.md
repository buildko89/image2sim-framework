# Soft Game Character Cat Plan

## 方針転換

これまでの検証で、実写真に近いtexture / projection / bakeだけでは、毛並みの柔らかさや低ポリ感の解消には限界があると分かった。

今後は「実物そっくりの再現」ではなく、「実物の特徴を残した、現実寄りで柔らかいゲームキャラクタ」を目標にする。

## 目標

`cat_soft_game_character_pass.glb` を作成する。

重視すること:

- Godotで動かしたときに可愛く見える
- 低ポリ感を無理に隠さず、ゲームキャラクタとして成立させる
- 短足、丸い胴体、ふわっとした尻尾、白い胸毛、三毛柄を残す
- 写真一致より、遠目で見たシルエットと動きの印象を優先する
- 既存のskin / animation setをできるだけ維持する

## 捨てること

- 写真をそのまま貼って実物そっくりにする方針
- textureだけで毛並みや柔らかさを出す方針
- Tripo / photo projection bakeだけで完成度を上げる方針
- 細かい模様位置の完全一致

## 残すこと

- 既存のアニメーション付き猫リグ
- Godotで確認できるGLB出力フロー
- 三毛猫として読める色配置
- ふわっと見せるためのfur shell系アプローチ
- 参照写真から得た特徴:
  - 白い胸と腹
  - 茶色の背中・腰・尻尾
  - 黒い背中の斑
  - 顔周りの三毛柄
  - 太い尻尾
  - 短めの足

## Phase 1: Game Character Baseline

目的: まずゲームキャラとして見える形へ寄せる。

作業:

- `cat_tripo_reference_visual_pass.blend` または `cat_fluffy_shortleg_pass.blend` をベースにする
- 胴体を少し丸くする
- 首周りと胸を太めに見せる
- 足を短く、足先を少し大きめにする
- 尻尾を太く、先端までふわっとした形にする
- 低ポリ面が硬く見えすぎる箇所を少し丸める

成果物:

- `output/rigged/cat_soft_game_character_pass.blend`
- `output/clean_3d/cat_soft_game_character_pass.glb`
- `output/reports/task68_cat_soft_game_character_pass.json`
- `output/reports/task68_cat_soft_game_character_side_preview.png`
- `output/reports/task68_cat_soft_game_character_front_preview.png`

判定:

- 横から見て短足・丸い・ふわっとした猫に見える
- 正面から見て顔と胸毛が硬すぎない
- 既存アニメーションが維持される

## Phase 2: Readable Calico Pattern

目的: 写真一致ではなく、三毛猫として読みやすい色配置に整理する。

作業:

- texture projectionではなく、material / polygon group / simple textureの組み合わせで色を置く
- 白をベースにする
- 背中・腰・尻尾に茶色と黒を大きめに配置する
- 顔周りは細かくしすぎず、正面で三毛猫と分かる程度にする
- 体側の模様は大きく、ゲーム中に読めるサイズにする

判定:

- 小さい表示でも三毛猫に見える
- 色のノイズが少ない
- Godotのライト下で暗くつぶれない

## Phase 3: Soft Fur Expression

目的: textureではなく、形と追加メッシュで柔らかさを出す。

作業候補:

- fur shellを少し外側へ膨らませる
- 胸、腹、尻尾、頬周りに追加shellを足す
- 尻尾だけhair-card風の板メッシュを検討する
- 輪郭に少しだけ毛束感を出す
- 過剰なリアル毛ではなく、ゲーム向けの柔らかい輪郭を狙う

判定:

- 横シルエットでふわっと見える
- 透明materialや大量ポリゴンに頼りすぎない
- Walk / Idleで破綻しない

## Phase 4: Godot Review

目的: Blenderプレビューではなく、ゲーム画面で成立するか確認する。

作業:

- `godot/Godot3dcat/` にGLBをコピー
- `MainAppearance.tscn` を新GLBへ切り替え
- `force_cat_materials = false` を維持
- walk / idleで見た目を確認

判定:

- 動いたときに短足・丸さ・尻尾の可愛さが出る
- textureの細部に頼らなくてもキャラクタとして見える
- ポリゴン感が「味」として許容できる

## Phase 5: 次の分岐

Task 68の結果を見て判断する。

### A. 既存リグ路線を継続

条件:

- 形とfur shellで十分かわいく見える
- animationが破綻しない
- Godotで扱いやすい

次:

- material整理
- 追加animation確認
- 軽量化

### B. AI生成メッシュ路線へ切り替え

条件:

- 既存低ポリ形状では柔らかさが足りない
- fur shellだけでは不自然
- もっと自然なキャラ形状が必要

次:

- Hunyuan3Dで「現実寄りの柔らかい三毛猫キャラクタ」を生成
- 生成meshを観察
- 既存rigへ寄せるか、別リグ化するか検討

## 最初にやる作業

次回はTask 68として、まず `cat_soft_game_character_pass` を作る。

最初の実装方針:

1. 既存リグ付きモデルをベースにする
2. 胴体・胸・尻尾・足先のシルエットを調整する
3. 三毛柄は大きめのmaterial色で整理する
4. fur shellを控えめに強化する
5. GLB出力、preview、Godot配置まで行う

## 判断基準

成功:

- 実物そっくりではないが、柔らかい三毛猫キャラとして見える
- Godotで動かして違和感が少ない
- textureの細部に依存しない

失敗:

- 低ポリ感が強く、柔らかさが出ない
- 色を整理してもキャラとして可愛く見えない
- animation時に形が破綻する

失敗した場合は、Hunyuan3DなどのAI生成メッシュ検証に進む。
