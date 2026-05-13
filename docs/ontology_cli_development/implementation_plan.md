# Ontology Extractor CLI 実装計画 (neo4j-graphrag対応版)

CLI機能およびLLMによる知識抽出処理を、公式パッケージである `neo4j-graphrag` (`SimpleKGPipeline`) を利用する構成へ移行します。自作した JSON パーサーなどを廃止し、より堅牢な公式のソリューションに差し替えます。

## アーキテクチャと依存技術
- **主要ライブラリ:** `neo4j-graphrag`
- **LLM/API:** LM Studioのローカルサーバー (`OPENAI_BASE_URL` などを環境変数で設定することで標準の `OpenAILLM` クラスで扱う)
- **データベース:** Neo4J （**※APOCプラグイン必須**）

## User Review Required
> [!IMPORTANT]
> 1. **APOCプラグインの要否**
>    `neo4j-graphrag` のナレッジグラフ構築機能（`SimpleKGPipeline`）を使用するには、Neo4J側に **APOC library** がインストールされている必要があります。Neo4J Desktop等からAPOCプラグインをインストールしていただくことは可能でしょうか？
> 2. **Embeddingモデルについて**
>    同パイプラインは内部でのベクトル検索インデックス作成等により **Embedder (Embedding Model)** を必要とします。LM Studio側でメインのLLM(Gemma)とは別に、Embeddingモデル(例:`nomic-embed-text`等) も利用可能にできる想定でよろしいでしょうか？

## Proposed Changes
### Configuration
#### [MODIFY] pyproject.toml
`neo4j-graphrag` の追加

### Source Code
#### [DELETE] src/ontology_extractor/llm_client.py
カスタムLLMパースロジックは不要となるため削除。
#### [MODIFY] src/ontology_extractor/neo4j_client.py
`SimpleKGPipeline` パイプラインを初期化してテキストを直接流し込むクラスにリファクタリング。
#### [MODIFY] src/ontology_extractor/main.py
CLIエンドポイントの再構築。
