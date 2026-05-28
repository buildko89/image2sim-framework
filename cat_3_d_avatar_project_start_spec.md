# image2sim-framework 開始仕様書 Ver.1.1

旧題: 猫3Dアバター生成プロジェクト

## 1. プロジェクト目的

`image2sim-framework` は、画像観測データからシミュレーション利用可能な仮想アセットを生成するための半自動パイプラインである。

最初のリファレンスケースとして、自宅の猫の写真を入力し、ゲームエンジン上で表示・動作可能な「うちの猫っぽい3Dアバター」を生成する。

ただし、最初から完全自動・本人完全再現・自然なアニメーションを狙わず、まずは以下を達成する。

- 写真フォルダから3Dモデル生成APIへ入力する画像を整理する
- 背景除去済み画像を作る
- Tripo APIを第一候補として静的3Dモデルを生成する
- GLB/FBXとして取得する
- Blenderで最低限の後処理を行う
- Unityで表示する
- 将来的には既存猫リグ・アニメーションに見た目を転写する

このプロジェクトの長期的な目的は、猫に限定せず、少数画像からシミュレーション用3Dアセットを生成・評価・改善する汎用フレームワークへ発展させることである。

## 2. 最初のMVP定義

### MVPゴール

「猫写真10〜30枚を用意し、うちの猫っぽい静的3DモデルをGLBで生成し、Unity上に表示できる」こと。

### MVPでやること

- GitHubリポジトリ初期構成
- Python仮想環境の整備
- 入力写真フォルダの整理
- 写真のインベントリ作成
- 人手またはVision AIによる画像選別
- 背景除去
- 3D生成API疎通確認
- Tripo APIを優先した3D生成API呼び出し
- GLB保存
- Blenderによる自動スケール調整
- 足元原点化
- Unity向け軸設定
- Unityプロジェクトへの配置

### MVPでやらないこと

- 完全自動リギング
- 自然な猫歩行アニメーション
- LoRA/DreamBooth学習
- 再投影誤差による自動最適化
- 毛並みの完全再現
- 商用品質のリトポロジー

## 2.1 採用済みレビュー反映事項

Claude/Geminiレビューを踏まえ、Ver.1.1では以下を採用する。

- Task 0.2: GitHub運用ルール追加
- Task 0.5: 3D生成API選定・APIキー取得・疎通確認追加
- Task 1: 画像インベントリ作成に限定
- Task 1.5: 画像選別工程を追加
- Blenderバージョン・CLI実行パス確認を追加
- Python venv運用をREADMEに明記
- Tripo APIを第一候補とする
- Quad出力またはリトポロジータスクを優先確認
- rembg処理後の影・マスク確認工程を追加
- Blender後処理で足元原点化・Unity向けForward/Up軸設定を追加
- metadata仕様を先に定義する
- Phase 4/5は将来構想として残すが、MVP実装対象外と明記する

## 3. フェーズ構成

### Phase 1: 静的3Dモデル生成パイプライン

目的: 写真からGLBモデルを得る。

入力:

- 猫写真 10〜30枚
- できれば正面、横、斜め、後ろ、全身写真

出力:

- `output/cat_model_raw.glb`
- `output/cat_model_preview.png`
- `output/metadata.json`

主要処理:

1. 写真一覧取得
2. 品質チェック
3. 背景除去
4. 3D生成APIに投入
5. 生成結果をダウンロード
6. メタデータ保存

成功条件:

- API経由でGLBが取得できる
- Blenderまたはビューアで開ける
- 猫として認識可能な外観である

---

### Phase 2: Blender後処理

目的: 生成モデルをゲームエンジンに入れやすくする。

処理:

- GLBインポート
- 原点調整
- Bounding Boxの最下点をZ=0に合わせ、足元原点化
- スケール調整
- 不要オブジェクト削除
- ポリゴン数・マテリアル数確認
- GLB/FBX再出力

出力:

- `output/cat_model_clean.glb`
- `output/cat_model_clean.fbx`
- `output/model_report.json`

成功条件:

- Blender CLIで処理できる
- Unity/Unrealにインポートできる

---

### Phase 3: 既存猫リグ・アニメーションへの適用

目的: 生成猫モデルを直接リグ化するのではなく、既存の綺麗に動く猫モデルへ見た目を寄せる。

方式:

- ベース猫モデルを用意する
- 生成猫モデルからテクスチャ・色・模様特徴を抽出する
- ベース猫へテクスチャ転写する
- 必要に応じてベース猫の形状を微調整する

候補技術:

- Blender Python
- Shrinkwrap
- Surface Deform
- Texture Bake
- Geometry Nodes
- Unity既存アニメーション

成功条件:

- 既存猫リグで歩行アニメーションが再生できる
- 見た目が元猫にある程度似ている

---

### Phase 4: 観測不足補完

注意: Phase 4はMVP対象外。将来Backlogとして管理する。

目的: 写真に不足している角度をAIで補完する。

候補:

- LoRA
- DreamBooth
- 画像生成AIによる正面・横・後ろ画像生成
- Gemini/Claudeによる画像差分レビュー

成功条件:

- 不足視点を補完した画像で3D生成品質が改善する

---

### Phase 5: 再投影誤差ループ

注意: Phase 5はMVP対象外。将来Backlogとして管理する。

目的: 生成3Dモデルを元写真と比較し、差分を使って改善する。

処理イメージ:

1. 元写真と近いカメラ角度を推定
2. 生成3Dモデルを仮想カメラでレンダリング
3. 元写真とレンダリング画像を比較
4. 差分領域を特定
5. テクスチャまたは形状を修正

成功条件:

- 元写真との一致度を定量評価できる
- 修正前後の改善が見える

## 4. 推奨ディレクトリ構成

```text
image2sim-framework/
  README.md
  requirements.txt
  .env.example
  .gitignore
  config/
    pipeline.yaml
  input/
    raw_photos/
    selected_photos/
    masks/
    masks_review/
  output/
    raw_3d/
    clean_3d/
    unity/
    reports/
  scripts/
    01_inventory_images.py
    015_select_images.py

命名規則:

- 基本は `NN_name.py` の2〜3桁プレフィックスを使う
- 中間タスクは `015_` のように3桁で表現する
- 将来の追加タスクを考慮し、整数番号のみ使用する
    02_remove_background.py
    03_check_3d_api.py
    04_generate_3d.py
    05_blender_cleanup.py
    06_export_to_unity.py
  blender/
    cleanup_model.py
    inspect_model.py
  unity/
    CatAvatarImportGuide.md
  docs/
    workflow.md
    review_log.md
    decisions.md
    backlog.md
```text
image2sim-framework/
  README.md
  requirements.txt
  .env.example
  config/
    pipeline.yaml
  input/
    raw_photos/
    selected_photos/
    masks/
  output/
    raw_3d/
    clean_3d/
    unity/
    reports/
  scripts/
    01_select_images.py
    02_remove_background.py
    03_generate_3d.py
    04_blender_cleanup.py
    05_export_to_unity.py
  blender/
    cleanup_model.py
    inspect_model.py
  unity/
    CatAvatarImportGuide.md
  docs/
    workflow.md
    review_log.md
    decisions.md
```

## 5. 技術候補

### 画像前処理

- Python
- OpenCV
- Pillow
- rembg

### 画像評価

- Gemini Vision
- Claude Vision
- ChatGPT Vision
- OpenCVによるブレ・解像度チェック

### 3D生成

第一候補:

- Tripo API

確認事項:

- APIキー取得
- 料金・利用制限
- Image-to-3D対応
- Multi-image対応
- Quad出力またはリトポロジータスク対応
- Unity向けにForward/Up軸を固定してFBX出力
- GLB/FBX出力対応

代替候補:

- Meshy API
- Hunyuan3D系OSS

### 3D後処理

- Blender CLI
- Blender Python

### ゲームエンジン

優先:

- Unity

理由:

- 既存の猫アニメーションアセットを使いやすい
- FBX/GLB対応
- ユーザーの既存経験と合う

## 6. 役割分担

### ユーザー

- プロダクトオーナー
- 最終意思決定者
- 猫写真の提供
- 出力品質の主観評価

### ChatGPT

- PM / アーキテクト
- 仕様整理
- タスク分解
- 技術リスク整理
- Claude/Geminiレビュー結果の統合
- Codex向けプロンプト作成

### Codex

- 主実装担当
- Pythonスクリプト作成
- Blender Python作成
- Unity取り込み補助
- リポジトリ整備

### Claude

- 副実装担当
- コードレビュー
- 設計レビュー
- 代替案提案
- 研究的観点の整理

### Gemini

- 副実装担当
- API調査
- 最新3D生成サービス調査
- Google系ツール評価
- 実装案レビュー

## 7. 開発ワークフロー

1. ChatGPTがタスク仕様を作る
2. Codexが主実装する
3. Claudeが副実装・コードレビュー・設計レビューを行う
4. Geminiが副実装・API/ツール選定レビューを行う
5. ChatGPTがレビューを統合して次タスクを決める
6. ユーザーが採否を決定する

### ドキュメント運用

- `docs/decisions.md`: 採用・不採用の判断理由を記録する
- `docs/review_log.md`: Claude/Gemini/ChatGPTレビューの要約を記録する
- `docs/backlog.md`: MVP外の提案、Phase 4/5関連、将来アイデアを記録する
- `docs/workflow.md`: 実行環境、コマンド、作業手順を記録する
- ChatGPTが次タスク定義時に、必要な追記内容を提示する
- Codexは実装時にREADMEと該当docsを更新する
- Windows / WSL2 / Docker など実行環境に関わる判断は `docs/decisions.md` に必ず残す

## 8. レビュー観点

### Claudeレビュー観点

- 設計が過剰になっていないか
- コードが保守しやすいか
- MVPから逸脱していないか
- 研究テーマとして筋が良いか
- 失敗時の切り分けが可能か

### Geminiレビュー観点

- より適切なAPIやサービスがあるか
- API利用条件・料金・制約は妥当か
- 最新ツールに置き換えた方がよい部分はあるか
- 実装の自動化余地はあるか

### ChatGPT統合観点

- MVPゴールに近づいているか
- 技術リスクを減らせているか
- 次の実装単位が明確か
- 作業が発散していないか

## 9. 初期タスク一覧

### Task 0: リポジトリ初期構成

目的:

- プロジェクトの土台を作る

成果物:

- ディレクトリ構成
- README
- requirements.txt
- `.env.example`
- `.gitignore`
- `config/pipeline.yaml`

完了条件:

- `python --version` と依存ライブラリ導入手順がREADMEにある
- Python venvの構築手順がREADMEにある
- APIキーは `.env` で管理し、Gitに含めない
- Windows環境での実行を前提にした手順がある

---

### Task 0.2: GitHub運用ルール整備

目的:

- 複数AIレビューとCodex実装の判断履歴を残す

成果物:

- `docs/decisions.md`
- `docs/review_log.md`
- `docs/backlog.md`
- `docs/workflow.md`

完了条件:

- 採用/不採用理由を記録できる
- MVP外の提案をbacklogへ退避できる

---

### Task 0.5: 3D生成API・Blender環境確認

目的:

- Task 3で詰まらないよう、外部依存を先に確認する
- Windows / WSL2 / Blender CLI の実行境界を明確にする

確認項目:

- Tripo APIキー取得可否
- Tripo APIの利用料金・制約
- Image-to-3D / Multi-image-to-3Dの対応状況
- Quad出力またはリトポロジー機能の有無
- Blenderバージョン
- Blender CLI実行パス
- Windows PowerShellからBlender CLIを実行できるか
- Python実行環境を Windows venv / WSL2 venv / Docker のどれにするか
- Blenderを Windows版 `.exe` で呼ぶか、WSL2内Linux版Blenderで呼ぶか
- WSL2を使う場合、`/mnt/c/...` と `C:\...` のパス変換方針

成果物:

- `docs/decisions.md` にAPI選定結果を記録
- `docs/workflow.md` にBlender CLI確認手順を記録

完了条件:

- 最初に使う3D生成APIが決まっている
- Blender CLIの実行コマンドが確認できている
- 実行環境方針が `docs/decisions.md` に記録されている

---

### Task 1: 入力写真インベントリ作成スクリプト

目的:

- `input/raw_photos/` に入れた画像を検査し、画像一覧レポートを作る
- このタスクでは画像選別までは行わない

処理:

- jpg/png/jpeg対応
- 解像度取得
- ファイルサイズ取得
- EXIF取得できる範囲で取得
- 低解像度画像を警告
- 結果をJSON/CSV出力

成果物:

- `scripts/01_inventory_images.py`
- `output/reports/image_inventory.json`
- `output/reports/image_inventory.csv`

完了条件:

- 写真フォルダを指定すると一覧レポートが出る

---

### Task 1.5: 画像選別フロー

目的:

- 3D生成APIに投入する画像を選ぶ
- 将来の再投影誤差ループに向け、最低限の視点情報を残す

処理:

- インベントリ結果をもとに候補画像を選別する
- 初期版は人手選別を基本とする
- 将来的にVision AIによる角度分類・品質評価を追加する
- 正面、横、斜め、後ろ、全身に近い画像を優先する
- `view_hint` を `front|side|back|diagonal|unknown` で人手入力する
- `camera_pose_estimate` は初期段階では null を許容する

成果物:

- `scripts/015_select_images.py`
- `input/selected_photos/`
- `output/reports/selected_images.json`

完了条件:

- 選別した画像と選別理由がJSONに残る
- `view_hint` が記録されている

---

### Task 2: 背景除去スクリプト

目的:

- 3D生成APIに渡すため、猫を切り抜いた画像を作る

処理:

- rembgで背景除去
- PNG透過で保存
- 影や床の残りを確認しやすいプレビューを出力
- `input/masks_review/` に確認用画像を保存
- 失敗画像をログ出力
- アルファマット閾値などを設定で調整可能にする

成果物:

- `scripts/02_remove_background.py`
- `input/selected_photos/*.png`

完了条件:

- 画像を一括処理できる
- 元画像と出力画像の対応が分かる

---

### Task 3: 3D生成API接続プロトタイプ

注意: Task 0.5完了後に着手する。

目的:

- TripoまたはMeshy APIを使って、1枚または複数枚画像からGLBを生成する

処理:

- `.env` からAPIキー取得
- Tripo APIを第一候補として利用
- Quad出力またはリトポロジー機能が利用可能なら優先
- 画像アップロード
- タスク作成
- ポーリング
- GLBダウンロード
- メタデータ保存

成果物:

- `scripts/03_generate_3d.py`
- `output/raw_3d/cat_model_raw.glb`
- `output/reports/generation_metadata.json`

完了条件:

- API経由でGLBを取得できる
- 失敗時のログが残る

---

### Task 4: Blender CLI後処理

注意: Blenderバージョン・CLIパス確認後に着手する。

目的:

- 生成GLBをBlenderで読み込み、基本整形して再出力する

処理:

- GLBインポート
- オブジェクト数確認
- 原点調整
- スケール調整
- 不要カメラ/ライト削除
- GLB/FBX出力
- モデル情報レポート出力（頂点数、面数、マテリアル数、Bounding Box、原点位置など）

成果物:

- `blender/cleanup_model.py`
- `scripts/04_blender_cleanup.py`
- `output/clean_3d/cat_model_clean.glb`
- `output/clean_3d/cat_model_clean.fbx`
- `output/reports/model_report.json`

完了条件:

- コマンド一発でGLBからFBXまで生成できる

---

### Task 5: Unity取り込み確認

目的:

- 生成モデルをUnityで表示する

処理:

- UnityプロジェクトのAssets配下へコピー
- インポート手順の文書化
- 表示確認用Scene作成方針の整理

成果物:

- `unity/CatAvatarImportGuide.md`
- `output/unity/`

完了条件:

- Unity上でモデルを配置・表示できる

## 10. 初期のCodex向けプロンプト

以下をCodexに渡す。

```text
image2sim-framework のMVPを作成します。

このプロジェクトは、画像観測データからシミュレーション利用可能な3Dアセットを生成するための半自動パイプラインです。
最初のリファレンスケースとして、猫写真からUnityで表示可能な3D猫モデルを生成します。

まず Task 0 / Task 0.2 / Task 1 を実装してください。
Task 0.5 / Task 1.5 / Task 2 はまだ実装せず、READMEまたはdocs/backlog.mdに次タスクとして記載してください。

要件:
- Pythonプロジェクトとして構成する
- リポジトリ名は image2sim-framework
- ディレクトリ構成は以下
  image2sim-framework/
    README.md
    requirements.txt
    .env.example
    .gitignore
    config/pipeline.yaml
    input/raw_photos/
    input/selected_photos/
    input/masks/
    input/masks_review/
    output/raw_3d/
    output/clean_3d/
    output/unity/
    output/reports/
    scripts/
    blender/
    unity/
    docs/
- docs 配下に workflow.md, review_log.md, decisions.md, backlog.md を作成する
- APIキーはまだ使わないが、将来のため `.env.example` を用意する
- `.env`、生成物、キャッシュ、仮想環境、巨大な3DファイルはGit管理しない方針を `.gitignore` に入れる
- Python venv の構築手順を README に記載する
- `scripts/01_inventory_images.py` を作成する
- 入力フォルダ内の jpg/jpeg/png を走査する
- 解像度、ファイルサイズ、形式、EXIFの有無、低解像度警告を取得する
- 結果を `output/reports/image_inventory.json` と `output/reports/image_inventory.csv` に出力する
- CLI引数で入力フォルダと出力フォルダを指定できるようにする
- エラー処理とログを入れる
- READMEに実行方法を書く
- READMEに次にやるべき Task 0.5, Task 1.5, Task 2 のメモも追記する

実装後、使い方、確認方法、今後のタスクをREADMEに追記してください。
```

## 10.1 metadata仕様

Phase 1以降で保存するmetadataは、将来の再投影誤差ループに接続できるよう、初期から以下の構造を意識する。

```json
{
  "project": "image2sim-framework",
  "reference_case": "cat_avatar",
  "input_images": [
    {
      "file": "input/selected_photos/example.png",
      "source_file": "input/raw_photos/example.jpg",
      "width": 0,
      "height": 0,
      "view_hint": "front|side|back|unknown",
      "quality_score": null,
      "camera_pose_estimate": null,
      "notes": ""
    }
  ],
  "generation": {
    "provider": "tripo|meshy|local|unknown",
    "task_id": "",
    "parameters": {},
    "status": "",
    "created_at": ""
  },
  "outputs": {
    "raw_glb": "",
    "clean_glb": "",
    "fbx": "",
    "preview_image": ""
  },
  "review": {
    "human_notes": "",
    "issues": []
  }
}
```

## 11. Claude/Geminiにレビュー依頼する内容

### Claude向けレビュー依頼

```text
以下は「猫写真からゲームエンジン用3Dアバターを生成するプロジェクト」の開始仕様です。
MVPは、写真フォルダからGLB生成、Blender後処理、Unity表示までです。

レビュー観点:
1. MVPとして過剰または不足している部分
2. 実装順序のリスク
3. Codexに渡すTask 0/1プロンプトの改善点
4. 将来の再投影誤差ループにつながる設計になっているか
5. 失敗時の切り分けがしやすいか

辛口でレビューしてください。
```

### Gemini向けレビュー依頼

```text
以下は「猫写真からゲームエンジン用3Dアバターを生成するプロジェクト」の開始仕様です。
MVPは、写真フォルダから3D生成API、Blender後処理、Unity表示までです。

レビュー観点:
1. Tripo/Meshy/Hunyuan3Dなど最新3D生成ツールの選定観点
2. API連携で最初に確認すべき制約
3. 画像前処理で追加すべき工程
4. Blender CLI処理で注意すべき点
5. Task 0/1の時点で将来のAPI連携に備えて入れるべき設計

実装に役立つ観点でレビューしてください。
```

## 12. 判断ルール

- MVPを超える提案は `docs/backlog.md` に送る
- すぐ実装するのは、Phase 1に直接必要なものだけ
- APIは最初から複数対応にしすぎない
- まず1つの3D生成APIで成功させる
- 生成品質よりも、パイプラインが最後まで通ることを優先する

## 13. 最初に確認すること

ユーザー側で確認すること:

- Unityを使うかUnrealを使うか。初期案はUnity
- 3D生成APIはTripoかMeshyのどちらから試すか
- 猫写真を何枚程度用意できるか
- 全身写真があるか
- 正面・横・後ろに近い写真があるか
- Windows上でBlender CLIを使えるか

