# Ontology Extractor CLI 改修完了

## 概要
既存の「ナレッジグラフ抽出ツール」を、本来の「オントロジー（スキーマ）抽出ツール」として動作するように改修しました。テキストから具体的なインスタンス（実体）ではなく、**「概念（Node Type）」と「関係性（Relationship Type/Pattern）」を抽出**し、Neo4jにオントロジースキーマとして格納する仕組みになっています。

## 変更内容
1. `src/ontology_extractor/neo4j_client.py`
   - `SimpleKGPipeline` の使用を廃止しました。
   - LLMに直接プロンプトを送信し、テキストの背後にあるオントロジーをJSON形式で抽出させる処理 (`_extract_async`) を追加しました。
   - 抽出されたJSONデータを元に、Neo4jにメタノード (`OntologyClass` ノード) およびメタ関係 (`ONTOLOGY_RELATIONSHIP` エッジ) を作成する処理を追加しました。

2. `src/ontology_extractor/main.py`
   - コマンドラインツール（CLI）のヘルプメッセージを修正し、機能の実態に合わせた説明（"Extract ontology schema from text"）に更新しました。
   - 抽出処理を非同期処理 (`asyncio.run()`) に対応させるよう、フローを修正しました。

## テスト結果
以下のテキストを用いて動作確認を行いました：
> 山田太郎は株式会社AのCEOであり、東京に住んでいます。
> 彼は「次世代AIの開発」というプロジェクトに参加しており、佐藤花子もそのプロジェクトのメンバーです。
> 佐藤花子は京都大学の出身です。

**LLMによって抽出されたオントロジーの例：**
```json
{
  "node_types": [
    "Person",
    "Company",
    "Location",
    "Project"
  ],
  "patterns": [
    {
      "source": "Person",
      "type": "WORKS_FOR",
      "target": "Company"
    },
    {
      "source": "Person",
      "type": "RESIDES_IN",
      "target": "Location"
    },
    {
      "source": "Person",
      "type": "PARTICIPATES_IN",
      "target": "Project"
    }
    // ...
  ]
}
```

上記で抽出されたスキーマ（Node TypesとPatterns）が、Cypherクエリによって正しくパースされ、Neo4jに格納されるフローを確認しました。
