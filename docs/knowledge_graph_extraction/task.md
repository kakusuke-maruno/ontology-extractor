# タスクリスト (Knowledge Graph Extraction)

- [x] `src/ontology_extractor/neo4j_client.py` の改修
  - [x] `fetch_ontology_schema()`: Neo4jから `OntologyClass` と `ONTOLOGY_RELATIONSHIP` を取得する処理を実装
  - [x] `populate_kg(text)`: スキーマを用いたプロンプトでLLMにナレッジグラフを抽出させる処理を実装
  - [x] `_store_kg_in_neo4j(kg_data)`: 抽出されたデータを動的CypherでNeo4jに挿入する処理を実装
- [x] `src/ontology_extractor/main.py` の改修
  - [x] `populate` コマンドを追加
- [x] 動作確認（Neo4jへの接続が必要なためコード実装まで完了）
