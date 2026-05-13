# ナレッジグラフ作成機能 実装完了

保存されているオントロジー（スキーマ）をもとに、テキストからナレッジグラフ（インスタンスと関係性）を抽出しNeo4jに格納する機能を実装しました。

## 実装内容
1. `src/ontology_extractor/neo4j_client.py` の機能拡充
   - `fetch_ontology_schema`: Neo4jに保存済みの `OntologyClass` および `ONTOLOGY_RELATIONSHIP` を取得し、JSONスキーマを構築します。
   - `populate_kg`: 取得したスキーマと入力テキストをプロンプトに埋め込み、LLMに「**このスキーマの通りに** インスタンス（実体）を抽出しなさい」と指示を出します。また、すべてのノードが `name` プロパティを持つように制約をかけました。
   - `_store_kg_in_neo4j`: 抽出された実データ（ノードとエッジ）を動的なCypherクエリでNeo4jにマージ（`MERGE`）し、保存します。

2. `src/ontology_extractor/main.py` の機能拡充
   - 新たに `populate` コマンドを追加しました。

## 使い方
1. 事前にオントロジーを抽出・保存しておきます。
   ```bash
   uv run ontology-cli extract sample_call_center.txt
   ```
2. 保存したオントロジーに基づき、ナレッジグラフ（実データ）を抽出してNeo4jに格納します。
   ```bash
   uv run ontology-cli populate sample_call_center.txt
   ```

> [!WARNING]
> **実行時の注意点（Neo4jへの接続）**
> 現在のローカル環境では Neo4j に接続できない状態（`Couldn't connect to localhost:7687`）となっています。
> 新しい機能は「Neo4jからスキーマを読み込む」ところからスタートするため、実行前にDocker等でNeo4jコンテナを起動しておく必要があります。
