# タスクリスト (FastAPI + メモリ階層型KG)

- [x] `pyproject.toml` の更新（`fastapi`, `uvicorn` 追加）
- [x] `src/ontology_extractor/memory.py` の新規作成
  - [x] ワーキングメモリ（Python辞書、インメモリ）
  - [x] 短期記憶（Neo4j: `:STM_Session`, `:STM_Message`, `:STM_Entity`）
  - [x] 長期記憶（Neo4j: `:LTM_Fact`, `:LTM_Topic`）
  - [x] 長期記憶への非同期昇格処理
- [x] `src/ontology_extractor/neo4j_client.py` の拡張（セッション対応の `query_kg_with_session`）
- [x] `src/ontology_extractor/api.py` の新規作成
  - [x] `POST /extract`
  - [x] `POST /populate`
  - [x] `POST /ask`（session_id対応）
  - [x] `POST /sessions`
  - [x] `GET /sessions/{session_id}`
  - [x] `DELETE /sessions/{session_id}`
  - [x] `GET /health`
- [x] 動作確認
