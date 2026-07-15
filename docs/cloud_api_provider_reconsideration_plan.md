# Cloud APIプロバイダー再検討計画

## 目的

Tripo と Meshy を、画像から3D参照モデルを作るための任意のクラウドAPI実験として再検討する。

この計画は、現在のMVP進捗を置き換えない。現在のMVPは、Blender、きれいなベースリグ、ゲームエンジン取り込み確認を中心にした、リグ付き・アニメーション可能な猫モデルのワークフローのままとする。Cloud APIの出力は、追加の参照アセットまたは比較アセットとして扱い、必須の最終可動モデルとはしない。

## 現在のベースライン

このプロジェクトでは、すでに次の成果がある。

- ローカルでの画像選択と背景除去。
- ローカルHunyuan3Dによる形状候補。
- Blenderでの取り込み、正規化、エクスポート。
- リグ付き四足動物ベースモデルの経路。
- アニメーション付きGLB/FBX出力。
- Godotでのアニメーション付き取り込み確認。

次の主タスクは引き続き Task 5.5: Cat Appearance Pass on Fox Rig とする。

## Cloud APIを再検討する理由

ローカルのみのImage-to-3D生成では、すでに実用上の制約が見えている。

- TripoSR はローカルの CUDA Toolkit / NVCC セットアップで停止した。
- Hunyuan3D は使える静的形状参照を生成できたが、最終的なリグ付き猫モデルではない。
- 生成された高密度メッシュを直接アニメーションさせるのは、トポロジーとウェイトが安定しないためリスクが高い。

Tripo や Meshy のようなホスト型サービスは、ローカル環境構築の負担を減らしつつ、より整ったテクスチャ付き参照メッシュを作れる可能性がある。期待する価値は、比較の高速化、外観参照の改善、Blender確認向けのquad/remesh出力である。

## 対象外

- Tripo や Meshy をMVP必須にしない。
- 有料クレジットを自動消費しない。
- リグ付きベースモデル経路を置き換えない。
- 生成メッシュがそのままアニメーション可能だと仮定しない。
- 1つのプロバイダーの有用性が確認できる前に、広いプロバイダー抽象化を作らない。

## 追加検討トラック

### Task 8A: Cloud API利用条件・クレジット確認

- ステータス: Proposed
- 優先度: Medium
- 目的: Tripo と Meshy の現在の無料クレジット有無、APIアクセス、料金、出力権利、アセット保持条件を確認する。
- 出力:
  - 確認済みのプロバイダー制約を反映した `docs/cloud_api_provider_reconsideration_plan.md`。
  - 実API送信をユーザーが承認する場合は `docs/decisions.md` の意思決定エントリ。
- 完了条件:
  - API生成は実行しない。
  - 無料/有料クレジットに関する前提を日付付きで明記する。
  - Task 8Bで使うプロバイダーを選ぶ。

### Task 8B: 1プロバイダーのdry-run連携

- ステータス: Proposed
- 優先度: Medium
- 目的: 選んだプロバイダー向けに、dry-run専用のリクエスト計画機能を追加または更新する。
- 候補プロバイダー:
  - Tripo: `scripts/03_tripo_image_to_3d.py` が既にあり、デフォルトでdry-runになっているため。
  - Meshy: APIが Image to 3D、Multi-Image to 3D、remesh/topologyオプション、GLB/FBX/OBJ出力、plugin経路に対応しているため。
- 出力:
  - `output/reports/` 配下のプロバイダーdry-runレポート。
  - デフォルトではクレジット消費を伴う送信をしない。
- 完了条件:
  - APIキーは `.env` からのみ読む。
  - 明示的なsubmitフラグがない限り、実送信を拒否する。
  - 対応している場合、計画payloadに出力形式 `glb` を含める。
  - 送信前にraw response保存先を計画する。

### Task 8C: 無料クレジット内の単発送信

- ステータス: Proposed
- 優先度: Medium
- 目的: 少数の無料クレジット送信で、静的参照メッシュを1つ生成する。
- 入力:
  - `input/masks/` にあるレビュー済みの切り抜き画像1枚。
  - 選択したプロバイダーがmulti-image入力に対応する場合は、必要に応じて正面/側面/背面画像。
- 出力:
  - プロバイダーのraw response JSON。
  - `output/raw_3d/cloud/<provider>/` 配下にダウンロードしたGLB/FBX/OBJ。
  - `output/reports/` 配下の正規化レポート。
- 完了条件:
  - ユーザーがsubmit実行を明示的に承認する。
  - provider、request、task id、status、output URLs、downloaded files、credit-risk noteを記録する。
  - Blender確認とアニメーション確認で別の判断が出ない限り、出力を参照アセットとして分類する。

### Task 8D: Blender比較と再利用判断

- ステータス: Proposed
- 優先度: Medium
- 目的: Cloud生成アセットを、既存のHunyuan3D参照とリグ付きベースモデルと比較する。
- 出力:
  - Blenderで正規化したCloudアセット。
  - シルエット、テクスチャ、トポロジー、スケール、原点、ゲームエンジン適性の比較メモ。
- 判断結果:
  - Cloud出力を外観/形状参照としてのみ使う。
  - Cloud出力をテクスチャ/マテリアル参考として使う。
  - Cloud出力をより良い静的prop/参照として使う。
  - リグ付きモデル経路を改善しない場合はCloud出力を不採用にする。

## プロバイダーメモ

### Tripo

現在のリポジトリ状態:

- `scripts/03_tripo_image_to_3d.py` は既に存在する。
- MVPではdeprecated/experimentalとして扱っている。
- デフォルトはdry-runで、実API呼び出しには `--submit` が必要。
- upload、task creation、polling、raw response capture、任意のoutput downloadに対応している。

推奨する使い方:

- 既存スクリプトがあるため、最小工数で再開できる候補としてTripoを最初に扱う。
- まず選択済みの切り抜き画像1枚で使う。
- 実出力が有用だと確認できるまで、multi-provider抽象化は追加しない。

### Meshy

現在のリポジトリ状態:

- Meshy用スクリプトはまだない。
- `.env.example` には既に `MESHY_API_KEY` がある。

期待できる価値:

- 公式ドキュメントに Image to 3D と Multi-Image to 3D のエンドポイントがある。
- Image to 3Dでは GLB、FBX、OBJ、STL、USDZ、3MF などの形式を要求できる。
- Image to 3Dには、quad-dominant出力を含むremesh/topology制御がある。
- Meshyには Remesh、Rigging、Animation、engine/plugin 関連のドキュメントもある。

リスク:

- Meshyのrigging/animation APIは、四足の猫よりもヒューマノイドやサービス固有のモデル前提に向いている可能性がある。
- このプロジェクトでは、Meshy出力は最初は静的参照メッシュとして扱い、最終リグ付きアセットとはみなさない。

## 安全条件

- Cloud providerの実行は必ずopt-inにする。
- dry-runをデフォルトモードにする。
- 実送信には次を必須にする。
  - `.env` にAPIキーがあること。
  - 明示的なsubmitフラグ。
  - クレジット消費を伴う操作に対するユーザー承認。
- プロバイダーのraw responseは、正規化レポートとは別に保存する。
- APIキー、権利が不明なダウンロード済みprivate asset、一時的な署名付きURLはcommitしない。
- 既存のlocal-first出力を上書きしない。

## 推奨する次の判断

まず Task 8A を承認する。

Task 8A の後、次のどちらかを選ぶ。

1. 既存スクリプトがあり実装変更が最小のため、Tripoを先に再開する。
2. image/multi-image生成、remesh、engine handoffのドキュメント範囲が広いため、Meshy dry-runを先に追加する。

保守的な推奨は、まずコード変更が少ないTripoを試し、Tripoの出力品質や無料クレジットアクセスが不十分な場合にMeshyを試すこと。

## 参照リンク

- Tripo platform docs: https://platform.tripo3d.ai/docs/introduction
- Meshy API docs: https://docs.meshy.ai/
- Meshy Image to 3D API: https://docs.meshy.ai/en/api/image-to-3d
- Meshy Multi-Image to 3D API: https://docs.meshy.ai/en/api/multi-image-to-3d
- Meshy Rigging API: https://docs.meshy.ai/en/api/rigging

無料クレジット数、料金、モデルバージョン、プロバイダー機能の詳細は変更される可能性があるため、Task 8Aで再確認する。
