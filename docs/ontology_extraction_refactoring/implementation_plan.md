# オントロジー抽出ツールへの改修計画

既存の「ナレッジグラフ（実データ）抽出ツール」を、本来の「オントロジー（スキーマ）抽出ツール」になるように修正します。

## 変更の目的と概要
現在のシステムは、事前にハードコードされたオントロジー（スキーマ）を用いてテキストからインスタンス（事実関係）を抽出し、Neo4jに格納しています。
今回の改修により、テキスト自体から**「どのような概念（Node Type）が存在するか」「それらはどう関連しているか（Relationship Type, Pattern）」という設計図（オントロジー）自体を抽出**するツールへと変更します。

> [!WARNING]
> **User Review Required / ユーザー確認事項**
> 
> オントロジーを抽出した後、そのデータをどのように保存・出力したいですか？
> 
> 1. **JSONファイルとしてローカルに出力する**（推奨: オントロジーの定義ファイルとして扱いやすい）
> 2. **Neo4jにオントロジースキーマとして格納する**（例: `Concept` や `RelationshipDef` というメタノードとして保存する）
> 3. その他（標準出力に表示するだけ、など）
> 
> ※Neo4jは主にナレッジグラフ（実データ）の保存に向いているため、オントロジー（スキーマ定義）自体の出力先としては **1 の JSON出力** が一般的でおすすめです。いかがでしょうか？

## Proposed Changes / 提案する変更内容

### `src/ontology_extractor/`

#### [MODIFY] [main.py](file:///Users/kakusuke/python/ontology_extractor/src/ontology_extractor/main.py)
- CLIのコマンド説明を「Knowledge Graph抽出」から「Ontology抽出」に修正。
- 抽出したオントロジーを（ユーザーの選択に応じて）JSONファイル等に出力する処理を追加。

#### [MODIFY] [neo4j_client.py](file:///Users/kakusuke/python/ontology_extractor/src/ontology_extractor/neo4j_client.py)
- `SimpleKGPipeline`（ナレッジグラフ抽出用）の使用を廃止。
- 代わりに `self.llm.invoke()` （または直接OpenAI APIクライアント）を使用し、テキストからオントロジー（Node Types, Relationship Types, Patterns）を抽出するためのカスタムプロンプトを実行するように変更。
- ハードコードされていた `node_types`, `relationship_types`, `patterns` を削除。
- （JSON出力が選ばれた場合）Neo4jドライバーの接続処理を削除するか、オプション扱いに変更。

## Verification Plan / 検証計画

### 手動検証
- サンプルテキストを用いてCLIを実行し、テキストに登場する概念や関係性がオントロジー（JSON等）として正しく抽出・出力されるかを確認する。
- 抽出結果がインスタンス（例: "山田太郎"）ではなく、クラス/概念（例: "人物", "組織"）になっているかを確認する。
