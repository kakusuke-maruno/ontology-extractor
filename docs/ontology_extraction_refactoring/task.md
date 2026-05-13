# タスクリスト (Ontology Extraction Refactoring)

- [x] `src/ontology_extractor/neo4j_client.py` の改修
  - [x] `SimpleKGPipeline` の削除
  - [x] LLMに対してテキストからオントロジー（スキーマ）を抽出させるプロンプトの実装
  - [x] 抽出されたJSONデータをパースし、Neo4jにオントロジーのメタノード（`OntologyClass` と `ONTOLOGY_RELATIONSHIP`）として格納する処理の実装
- [x] `src/ontology_extractor/main.py` の改修
  - [x] CLIのヘルプメッセージ等の修正
- [x] 動作確認（テストテキストを用いて抽出とNeo4jへの格納を確認）
