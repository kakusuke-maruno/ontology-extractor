# ナレッジグラフ抽出機能の実装計画

保存されているオントロジー（スキーマ）情報をNeo4jから読み込み、それに従って入力テキストからナレッジグラフ（実データ）を抽出・保存する新機能を追加します。

## 変更の目的と概要
これまでは「テキストからオントロジー（設計図）を抽出する機能（`extract`コマンド）」のみでしたが、今回は**「Neo4jに保存済みのオントロジー定義を取得し、そのルールに厳密に従ってテキストからエンティティ（インスタンス）と関係性を抽出し、ナレッジグラフとしてNeo4jに保存する機能（`populate`コマンド）」**を追加します。

## Proposed Changes / 提案する変更内容

### 1. `src/ontology_extractor/neo4j_client.py`
新たにナレッジグラフ抽出用の処理を追加します。
- `fetch_ontology_schema()`: Neo4jの `OntologyClass` と `ONTOLOGY_RELATIONSHIP` をクエリし、定義済みのスキーマを取得するメソッド。
- `populate_kg(text)`: 取得したスキーマ情報をプロンプトに埋め込み、LLMに対して**「このスキーマにのみ従い、具体値（インスタンス）を抽出しなさい」**と指示するメソッド。
- 抽出結果（JSON）をパースし、動的にNeo4jのノードとリレーションを作成する処理を追加。

### 2. `src/ontology_extractor/main.py`
新しいCLIコマンドを追加します。
- `@cli.command()` を用いて、`populate`（または `extract-kg`）コマンドを追加。
- 実行例: `uv run ontology-cli populate sample_call_center.txt`

> [!WARNING]
> **User Review Required / ユーザー確認事項**
> 
> 1. 新しいコマンド名は `populate` （データを流し込む意味）と `extract-kg` のどちらが好みでしょうか？（デフォルトでは `populate` を採用予定です）
> 2. ナレッジグラフのインスタンスを格納する際、すべてのノードを一意に特定するためのキーはプロパティ（例: `name` プロパティ）で表現する想定です。問題ないでしょうか？

## Verification Plan / 検証計画
### 手動検証
1. 事前に `uv run ontology-cli extract sample_call_center.txt` を実行し、スキーマをNeo4jに保存しておく。
2. その後、`uv run ontology-cli populate sample_call_center.txt` を実行する。
3. Neo4j Browser (または Cypher) で確認し、`OntologyClass` ではなく実際のラベル（例: `:Customer` や `:Product`）を持つインスタンスノード（例: "山田太郎"）が作成され、適切な関係性で結ばれているかを確認する。
