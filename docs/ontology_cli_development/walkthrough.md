# Ontology Extractor CLI ウォークスルー検証 (neo4j-graphrag対応版)

`neo4j-graphrag` (`SimpleKGPipeline`) を用いたアーキテクチャへの移行が完了しました。
以下の手順に従ってテスト実行をお願いします。

## 前提環境の準備
1. **Neo4J** と **APOC プラグイン**
   - Neo4J が起動していること。
   - APOC プラグインがインストールおよび有効化されていること。
2. **LM Studio** 
   - 「Local Server」モード(`http://localhost:1234/v1`)を開始してください。
   - LLM（Gemma 4/2 E4Bなど）と、Embeddingモデル（`text-embedding-mxbai-embed-large-v1`など）がAPIから利用可能な状態にしてください。
3. **環境変数**
   - 新しい `.env.example` の内容に合わせて `.env` を再設定してください。(`LLM_MODEL` や `EMBEDDING_MODEL` も設定可能です)

## 動作確認手順

### 1. サンプルテキストの準備
テスト用にプロジェクト直下に `sample.txt` を用意しています。（Alan Turingに関する説明文）

### 2. オントロジー抽出コマンドの実行
Terminal から以下を実行します。
```bash
uv run ontology-cli extract sample.txt
```
※ `SimpleKGPipeline` によりテキストが処理され、Neo4jへの書き込みが行われます。

### 3. Neo4Jブラウザでのグラフ確認
処理成功後、コンソールに「Successfully extracted and stored ontology in Neo4j!」と出力されます。
Neo4Jのブラウザ画面 (`http://localhost:7474` 等) を開き、以下のCYPHERクエリで抽出されたグラフを確認してください。
```cypher
MATCH (n) RETURN n
```

想定通りにノードと関係性が構築されていれば完了です！
