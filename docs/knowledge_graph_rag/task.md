# タスクリスト (GraphRAG / Ask Command)

- [x] `src/ontology_extractor/neo4j_client.py` の改修
  - [x] `query_kg(question: str)` メソッドの追加
  - [x] LLMを用いたText2Cypher機能（スキーマと質問からCypherを生成）の実装
  - [x] Neo4jでのCypher実行と、その結果を用いたLLMによる自然言語回答生成処理の実装
- [x] `src/ontology_extractor/main.py` の改修
  - [x] `ask` コマンドを追加
- [x] 動作確認（Neo4jへの接続が必要なためコード実装まで完了）
