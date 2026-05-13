import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from neo4j import AsyncGraphDatabase
from openai import AsyncOpenAI

from ontology_extractor.config import settings

logger = logging.getLogger(__name__)


class MemoryManager:
    """3階層メモリ管理クラス。

    - Working Memory: インメモリ（Python辞書）。1ターンで破棄。
    - Short-term Memory: Neo4j (:STM_Session, :STM_Message, :STM_Entity)。セッション単位で永続保存。
    - Long-term Memory: Neo4j (:LTM_Fact, :LTM_Topic)。非同期で昇格・永続。
    """

    def __init__(self, driver, llm_client, model_name: str):
        self.driver = driver
        self.llm_client = llm_client
        self.model_name = model_name
        # Working Memory: インメモリ辞書。session_id -> dict
        self._working_memory: dict[str, dict] = {}

    # =========================================================================
    # Working Memory（ワーキングメモリ）— インメモリ
    # =========================================================================

    def set_working_memory(self, session_id: str, *, question: str,
                           cypher: str = "", results: list | None = None,
                           answer: str = ""):
        """現在のターンの作業コンテキストをセットする。"""
        self._working_memory[session_id] = {
            "question": question,
            "cypher": cypher,
            "results": results or [],
            "answer": answer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_working_memory(self, session_id: str) -> dict | None:
        return self._working_memory.get(session_id)

    def clear_working_memory(self, session_id: str):
        self._working_memory.pop(session_id, None)

    # =========================================================================
    # Short-term Memory（短期記憶）— Neo4j
    # =========================================================================

    async def ensure_session(self, session_id: str):
        """セッションノードが存在しなければ作成する。"""
        now = datetime.now(timezone.utc).isoformat()
        query = """
        MERGE (s:STM_Session {id: $session_id})
        ON CREATE SET s.created_at = $now, s.last_active_at = $now
        ON MATCH SET s.last_active_at = $now
        """
        async with self.driver.session() as session:
            await session.run(query, session_id=session_id, now=now)

    async def add_message(self, session_id: str, role: str, content: str,
                          entities: list[dict] | None = None):
        """短期記憶にメッセージを追加する。"""
        now = datetime.now(timezone.utc).isoformat()
        msg_id = str(uuid.uuid4())

        query_msg = """
        MATCH (s:STM_Session {id: $session_id})
        CREATE (m:STM_Message {
            id: $msg_id,
            role: $role,
            content: $content,
            timestamp: $timestamp
        })
        CREATE (s)-[:HAS_MESSAGE]->(m)
        """
        async with self.driver.session() as session:
            await session.run(query_msg,
                              session_id=session_id, msg_id=msg_id,
                              role=role, content=content, timestamp=now)

            # エンティティがあればリンクする
            if entities:
                for entity in entities:
                    ent_name = entity.get("name", "unknown")
                    ent_label = entity.get("label", "Entity")
                    query_ent = """
                    MATCH (m:STM_Message {id: $msg_id})
                    MERGE (e:STM_Entity {name: $name, label: $label, session_id: $session_id})
                    CREATE (m)-[:MENTIONS]->(e)
                    """
                    await session.run(query_ent,
                                      msg_id=msg_id, name=ent_name,
                                      label=ent_label, session_id=session_id)

    async def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        """短期記憶から直近のメッセージ履歴を取得する。"""
        query = """
        MATCH (s:STM_Session {id: $session_id})-[:HAS_MESSAGE]->(m:STM_Message)
        RETURN m.role AS role, m.content AS content, m.timestamp AS timestamp
        ORDER BY m.timestamp ASC
        LIMIT $limit
        """
        messages = []
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id, limit=limit)
            async for record in result:
                messages.append({
                    "role": record["role"],
                    "content": record["content"],
                    "timestamp": record["timestamp"],
                })
        return messages

    async def get_session_entities(self, session_id: str) -> list[dict]:
        """セッション内で言及されたエンティティ一覧を取得する。"""
        query = """
        MATCH (e:STM_Entity {session_id: $session_id})
        RETURN DISTINCT e.name AS name, e.label AS label
        """
        entities = []
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            async for record in result:
                entities.append({
                    "name": record["name"],
                    "label": record["label"],
                })
        return entities

    async def get_session_info(self, session_id: str) -> dict | None:
        """セッションの情報を取得する。"""
        query = """
        MATCH (s:STM_Session {id: $session_id})
        RETURN s.created_at AS created_at, s.last_active_at AS last_active_at
        """
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            record = await result.single()
            if record is None:
                return None
            return {
                "session_id": session_id,
                "created_at": record["created_at"],
                "last_active_at": record["last_active_at"],
            }

    async def delete_session(self, session_id: str):
        """セッションとそれに紐づくメッセージ・エンティティを削除する。"""
        query = """
        MATCH (s:STM_Session {id: $session_id})
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:STM_Message)
        OPTIONAL MATCH (m)-[:MENTIONS]->(e:STM_Entity {session_id: $session_id})
        DETACH DELETE s, m, e
        """
        async with self.driver.session() as session:
            await session.run(query, session_id=session_id)
        logger.info(f"Deleted session {session_id} and related data.")

    # =========================================================================
    # Long-term Memory（長期記憶）— Neo4j / 非同期昇格
    # =========================================================================

    async def promote_to_long_term(self, session_id: str):
        """短期記憶の内容を非同期で長期記憶（ナレッジグラフ）に昇格させる。

        LLMを使って会話履歴から重要な事実とトピックを抽出し、
        :LTM_Fact および :LTM_Topic として保存する。
        """
        history = await self.get_history(session_id, limit=100)
        if not history:
            logger.info(f"No history found for session {session_id}. Skipping promotion.")
            return

        conversation_text = "\n".join(
            f"[{m['role']}] {m['content']}" for m in history
        )

        prompt = f"""
Given the following conversation history, extract important FACTS and TOPICS that should be remembered long-term.

Conversation:
{conversation_text}

Output a valid JSON object with this structure:
{{
  "facts": [
    {{"content": "A concise statement of fact", "topic": "related topic keyword"}}
  ],
  "topics": [
    {{"name": "topic keyword", "description": "brief description"}}
  ]
}}

Extract only genuinely useful information. Do not include trivial greetings or meta-conversation.
Output valid JSON only.
"""
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a knowledge extraction assistant. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )

            import re
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            content = re.sub(r',\s*([\]}])', r'\1', content)

            data = json.loads(content)
            now = datetime.now(timezone.utc).isoformat()

            async with self.driver.session() as session:
                # LTM_Fact の保存
                for fact in data.get("facts", []):
                    await session.run("""
                        MERGE (f:LTM_Fact {content: $content})
                        ON CREATE SET f.source_session = $session_id,
                                      f.created_at = $now,
                                      f.access_count = 1,
                                      f.topic = $topic
                        ON MATCH SET f.access_count = f.access_count + 1
                    """, content=fact["content"], session_id=session_id,
                        now=now, topic=fact.get("topic", ""))

                # LTM_Topic の保存
                for topic in data.get("topics", []):
                    await session.run("""
                        MERGE (t:LTM_Topic {name: $name})
                        ON CREATE SET t.description = $description,
                                      t.frequency = 1,
                                      t.last_accessed = $now
                        ON MATCH SET t.frequency = t.frequency + 1,
                                     t.last_accessed = $now
                    """, name=topic["name"],
                        description=topic.get("description", ""),
                        now=now)

            logger.info(f"Promoted {len(data.get('facts', []))} facts and "
                        f"{len(data.get('topics', []))} topics to long-term memory "
                        f"from session {session_id}.")

        except Exception as e:
            logger.error(f"Failed to promote to long-term memory: {e}")

    async def get_long_term_context(self, limit: int = 10) -> dict:
        """長期記憶から関連コンテキストを取得する。"""
        facts = []
        topics = []
        async with self.driver.session() as session:
            result_facts = await session.run("""
                MATCH (f:LTM_Fact)
                RETURN f.content AS content, f.topic AS topic, f.access_count AS access_count
                ORDER BY f.access_count DESC
                LIMIT $limit
            """, limit=limit)
            async for record in result_facts:
                facts.append({
                    "content": record["content"],
                    "topic": record["topic"],
                    "access_count": record["access_count"],
                })

            result_topics = await session.run("""
                MATCH (t:LTM_Topic)
                RETURN t.name AS name, t.description AS description, t.frequency AS frequency
                ORDER BY t.frequency DESC
                LIMIT $limit
            """, limit=limit)
            async for record in result_topics:
                topics.append({
                    "name": record["name"],
                    "description": record["description"],
                    "frequency": record["frequency"],
                })

        return {"facts": facts, "topics": topics}
