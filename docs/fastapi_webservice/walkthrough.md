# FastAPI Webサービス + メモリ階層型KG 実装完了

## 概要

CLIを維持したまま、FastAPIによるWeb APIサーバーと、3階層のメモリ管理をNeo4j上に実装しました。

## 作成・変更したファイル

| ファイル | 種別 | 内容 |
|---------|------|------|
| `pyproject.toml` | 変更 | `fastapi`, `uvicorn` を依存に追加。`ontology-api` エントリーポイント追加 |
| `src/ontology_extractor/memory.py` | 新規 | `MemoryManager` クラス。3階層メモリ管理 |
| `src/ontology_extractor/neo4j_client.py` | 変更 | `query_kg_with_session()` メソッド追加 |
| `src/ontology_extractor/api.py` | 新規 | FastAPIアプリケーション本体 |

## メモリアーキテクチャ

| メモリ層 | 保存先 | 寿命 | Neo4jラベル |
|---------|--------|------|------------|
| Working Memory | Python辞書（インメモリ） | 1ターン | — |
| Short-term Memory | Neo4j | 明示的削除まで永続 | `:STM_Session`, `:STM_Message`, `:STM_Entity` |
| Long-term Memory | Neo4j | 永続 | `:LTM_Fact`, `:LTM_Topic` |

- **長期記憶への昇格**: `DELETE /sessions/{session_id}` 時に FastAPI の `BackgroundTasks` で非同期実行。LLMが会話履歴から重要な事実・トピックを抽出して `:LTM_Fact`, `:LTM_Topic` に保存した後、セッションデータを削除。

## API エンドポイント一覧

| Method | Path | 説明 |
|--------|------|------|
| `GET` | `/health` | ヘルスチェック |
| `POST` | `/extract` | テキストからオントロジー抽出 |
| `POST` | `/populate` | テキストからKG構築 |
| `POST` | `/sessions` | 新規セッション作成 |
| `GET` | `/sessions/{id}` | セッション情報・履歴取得 |
| `DELETE` | `/sessions/{id}` | セッション削除（非同期で長期記憶昇格） |
| `POST` | `/ask` | セッション対応GraphRAG検索 |

## テスト結果

### 1. サーバー起動
```bash
uv run ontology-api
# → Uvicorn running on http://0.0.0.0:8000
```

### 2. セッション作成
```bash
curl -s -X POST http://localhost:8000/sessions
# → {"session_id": "75e69c38-...", "created_at": "...", "last_active_at": "..."}
```

### 3. マルチターン対話（文脈解決の確認）
```bash
# 1問目
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id": "75e69c38-...", "question": "山田太郎が注文した商品は？"}'
# → answer: "快眠プレミアムマットレスが注文されています。"
# → cypher: "MATCH (c:Customer {name: '山田太郎'})-[:HAS_ORDERED]->(p:Product) RETURN p"

# 2問目（「その人」= 山田太郎と文脈解決）
curl -s -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id": "75e69c38-...", "question": "その人の届け先はどこですか？"}'
# → cypher: "MATCH (c:Customer {name: '山田太郎'})-[:PROVIDES]->(da:DeliveryAddress) RETURN da.name"
# ↑ 「その人」が正しく「山田太郎」に解決されている！
```

### 4. セッション履歴確認
```bash
curl -s http://localhost:8000/sessions/75e69c38-...
# → messages: [user: "山田太郎が注文した商品は？", assistant: "快眠プレミアム...", ...]
```

### 5. セッション削除 → 長期記憶昇格
```bash
curl -s -X DELETE http://localhost:8000/sessions/75e69c38-...
# → {"status": "accepted", "message": "Session deletion scheduled..."}

# サーバーログ:
# Promoted 2 facts and 2 topics to long-term memory from session 75e69c38-...
# Deleted session 75e69c38-... and related data.
```

## 起動方法

```bash
# CLI（既存のまま動作）
uv run ontology-cli extract sample.txt
uv run ontology-cli populate sample.txt
uv run ontology-cli ask "質問"

# Web API（新規）
uv run ontology-api
# → http://localhost:8000/docs で Swagger UIが利用可能
```
