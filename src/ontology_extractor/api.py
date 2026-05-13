import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ontology_extractor.neo4j_client import OntologyPipeline
from ontology_extractor.memory import MemoryManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
pipeline: Optional[OntologyPipeline] = None
memory_manager: Optional[MemoryManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: サーバー起動時にリソースを初期化し、終了時にクローズする。"""
    global pipeline, memory_manager
    pipeline = OntologyPipeline()
    memory_manager = MemoryManager(
        driver=pipeline.driver,
        llm_client=pipeline.llm_client,
        model_name=pipeline.model_name,
    )
    logger.info("OntologyPipeline and MemoryManager initialized.")
    yield
    if pipeline:
        await pipeline.close()
    logger.info("OntologyPipeline closed.")


app = FastAPI(
    title="Ontology Extractor API",
    description="オントロジー抽出・ナレッジグラフ構築・GraphRAG検索を行うWebサービス",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TextRequest(BaseModel):
    text: str


class AskRequest(BaseModel):
    session_id: str
    question: str


class AskResponse(BaseModel):
    session_id: str
    answer: str
    cypher: str
    data: list


class SessionResponse(BaseModel):
    session_id: str
    created_at: Optional[str] = None
    last_active_at: Optional[str] = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    created_at: Optional[str] = None
    last_active_at: Optional[str] = None
    messages: list
    entities: list


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract(req: TextRequest):
    """テキストからオントロジーを抽出し、Neo4jに保存する。"""
    try:
        await pipeline.run(req.text)
        return {"status": "success", "message": "Ontology extracted and stored."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/populate")
async def populate(req: TextRequest):
    """テキストからナレッジグラフインスタンスを抽出し、Neo4jに保存する。"""
    try:
        await pipeline.populate_kg(req.text)
        return {"status": "success", "message": "Knowledge graph populated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions", response_model=SessionResponse)
async def create_session():
    """新しいセッションを作成する。"""
    session_id = str(uuid.uuid4())
    await memory_manager.ensure_session(session_id)
    info = await memory_manager.get_session_info(session_id)
    return SessionResponse(
        session_id=session_id,
        created_at=info["created_at"] if info else None,
        last_active_at=info["last_active_at"] if info else None,
    )


@app.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session(session_id: str):
    """セッション情報と会話履歴を取得する。"""
    info = await memory_manager.get_session_info(session_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    messages = await memory_manager.get_history(session_id, limit=100)
    entities = await memory_manager.get_session_entities(session_id)
    return SessionHistoryResponse(
        session_id=session_id,
        created_at=info["created_at"],
        last_active_at=info["last_active_at"],
        messages=messages,
        entities=entities,
    )


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, background_tasks: BackgroundTasks):
    """セッションを削除する。非同期で長期記憶への昇格を行った後に削除する。"""
    info = await memory_manager.get_session_info(session_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    # 非同期で長期記憶に昇格させてからセッションを削除する
    async def _promote_and_delete():
        await memory_manager.promote_to_long_term(session_id)
        await memory_manager.delete_session(session_id)

    background_tasks.add_task(_promote_and_delete)
    return {"status": "accepted", "message": "Session deletion scheduled. Long-term memory promotion in progress."}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """セッション対応のナレッジグラフ検索。会話履歴と長期記憶を活用する。"""
    session_id = req.session_id
    question = req.question

    # セッション存在確認・更新
    await memory_manager.ensure_session(session_id)

    # MemoryManagerに現在のsession_idをセット（query_kg_with_sessionが参照する）
    memory_manager._current_session_id = session_id

    # ワーキングメモリに質問をセット
    memory_manager.set_working_memory(session_id, question=question)

    # 質問を短期記憶に記録
    await memory_manager.add_message(session_id, role="user", content=question)

    # セッション対応版のKG検索を実行
    result = await pipeline.query_kg_with_session(question, memory_manager)

    # ワーキングメモリを更新
    memory_manager.set_working_memory(
        session_id,
        question=question,
        cypher=result["cypher"],
        results=result["data"],
        answer=result["answer"],
    )

    # 回答を短期記憶に記録（エンティティ情報も付与）
    await memory_manager.add_message(
        session_id,
        role="assistant",
        content=result["answer"],
        entities=result.get("entities"),
    )

    # ワーキングメモリをクリア（ターン終了）
    memory_manager.clear_working_memory(session_id)

    return AskResponse(
        session_id=session_id,
        answer=result["answer"],
        cypher=result["cypher"],
        data=result["data"],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def start():
    """ontology-api スクリプトエントリーポイント。"""
    uvicorn.run(
        "ontology_extractor.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    start()
