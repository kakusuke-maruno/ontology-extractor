# Ontology Extractor CLI Task List

- [x] 初期環境構築 (CLI, Neo4J, LM Studio連携の準備)
  - [x] Poetry/uvなどでのプロジェクト初期化とパッケージ追加
  - [x] コマンドラインパーサーのセットアップ (Click または Argparse)
- [x] LLM クライアントの実装
  - [x] LM Studio(OpenAI互換API)への接続処理
  - [x] オントロジー(知識抽出)用プロンプトの設計
- [x] Neo4j 接続とデータ挿入処理の実装
  - [x] Neo4j Python Driverを用いた接続設定
  - [x] 抽出されたノードとエッジを書き込むCypherクエリの構築
- [x] CLIとパイプラインの統合
  - [x] テキストファイル読み込み -> LLMで抽出 -> Neo4j書き込み の一連の処理の実装
- [x] neo4j-graphrag 対応へのリファクタリング
  - [x] uvからの neo4j-graphrag パッケージ追加
  - [x] SimpleKGPipeline を用いた抽出/保存ロジックの実装
  - [x] main.py と設定ファイル(.env)の更新
- [/] 再ウォークスルー検証 (neo4j-graphrag対応版)
