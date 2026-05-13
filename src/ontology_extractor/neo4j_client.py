import os
import re
import json
import asyncio
import logging
from neo4j import AsyncGraphDatabase
from openai import AsyncOpenAI

from ontology_extractor.config import settings

logger = logging.getLogger(__name__)

class OntologyPipeline:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password)
        )
        
        self.llm_client = AsyncOpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key
        )
        self.model_name = settings.llm_model
        self._schema_cache = None

    async def run(self, text: str):
        prompt = f"""
Given the following text, extract the underlying ontology (schema) that describes the domain.
Identify the abstract concepts (Node Types) and the valid relationships between them (Patterns).

CRITICAL INSTRUCTION: You are extracting a SCHEMA (Ontology), NOT a Knowledge Graph. 
DO NOT extract specific instances or concrete values (e.g., do NOT extract "山田太郎", "北海道", "11月15日", "090-1234-5678").
Instead, extract the ABSTRACT CONCEPTS or ROLES they represent. 
IMPORTANT: Do not over-generalize concepts. If distinguishing roles is important in this domain, extract specific role-based concepts like "Customer", "Operator", or "Recipient" instead of a generic "Person".
All "source" and "target" in your patterns MUST be abstract concepts, classes, or roles, never specific instances.

Output the result ONLY as a valid JSON object with the following structure:
{{
  "node_types": ["Concept1", "Concept2", ...],
  "patterns": [
    {{"source": "Concept1", "type": "RELATIONSHIP_TYPE", "target": "Concept2"}},
    ...
  ]
}}

CRITICAL RULE: Every single "source" and "target" used in your "patterns" MUST be explicitly included in the "node_types" list. Do not use any concept in patterns if it is not defined in node_types.

Ensure that the output is strictly valid JSON without markdown blocks if possible, or inside a ```json block. Do not add any conversational text.

Text:
{text}
"""
        logger.info("Calling LLM to extract ontology...")
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert ontology extractor. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            content = response.choices[0].message.content.strip()
            
            content = content.strip()
            
            # Clean up potential markdown blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            # Remove trailing commas before closing brackets/braces (JSON parsing fix)
            content = re.sub(r',\s*([\]}])', r'\1', content)
                
            try:
                ontology_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON. Raw content was:\n{content}")
                raise e
                
            logger.info(f"Extracted Ontology: {json.dumps(ontology_data, indent=2, ensure_ascii=False)}")
            
            # Update in-memory cache
            self._schema_cache = ontology_data
            
            await self._store_in_neo4j(ontology_data)
            
        except Exception as e:
            logger.error(f"Failed to extract or store ontology: {e}")
            raise

    async def _store_in_neo4j(self, ontology_data: dict):
        node_types = set(ontology_data.get("node_types", []))
        patterns = ontology_data.get("patterns", [])

        # Auto-repair: Add any missing concepts from patterns into node_types
        for p in patterns:
            source = p.get("source")
            target = p.get("target")
            if source:
                node_types.add(source)
            if target:
                node_types.add(target)

        node_types_list = list(node_types)

        query_nodes = """
        UNWIND $node_types AS nt
        MERGE (n:OntologyClass {name: nt})
        """

        query_patterns = """
        UNWIND $patterns AS p
        MATCH (s:OntologyClass {name: p.source})
        MATCH (t:OntologyClass {name: p.target})
        MERGE (s)-[r:ONTOLOGY_RELATIONSHIP {name: p.type}]->(t)
        """

        logger.info("Storing ontology in Neo4j...")
        async with self.driver.session() as session:
            if node_types_list:
                await session.run(query_nodes, node_types=node_types_list)
            if patterns:
                await session.run(query_patterns, patterns=patterns)
        logger.info("Ontology successfully stored in Neo4j.")

    async def fetch_ontology_schema(self) -> dict:
        if self._schema_cache is not None:
            return self._schema_cache

        logger.info("Fetching ontology schema from Neo4j...")
        query_nodes = "MATCH (n:OntologyClass) RETURN n.name AS name"
        query_patterns = "MATCH (s:OntologyClass)-[r:ONTOLOGY_RELATIONSHIP]->(t:OntologyClass) RETURN s.name AS source, r.name AS type, t.name AS target"
        
        node_types = []
        patterns = []
        
        async with self.driver.session() as session:
            result_nodes = await session.run(query_nodes)
            async for record in result_nodes:
                node_types.append(record["name"])
                
            result_patterns = await session.run(query_patterns)
            async for record in result_patterns:
                patterns.append({
                    "source": record["source"],
                    "type": record["type"],
                    "target": record["target"]
                })
        
        self._schema_cache = {"node_types": node_types, "patterns": patterns}
        return self._schema_cache

    async def populate_kg(self, text: str):
        schema = await self.fetch_ontology_schema()
        if not schema["node_types"]:
            logger.warning("No ontology schema found in Neo4j. Please run 'extract' first.")
            return

        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)
        
        prompt = f"""
Given the following text and the provided Ontology Schema, extract the Knowledge Graph instances.
You must strictly follow the provided schema. Do not invent new node types or relationship types.

SCHEMA:
{schema_json}

CRITICAL INSTRUCTION: You are extracting INSTANCES (Knowledge Graph), NOT the schema.
For each entity in the text, assign it to one of the `node_types` in the schema and give it a specific `name` (the actual instance value, e.g., "山田太郎", "11月15日").
If the name is unknown but the entity exists, use "unknown" or a descriptive placeholder for `name`.
Relationships must only use the `type` defined in the schema `patterns`.

Output the result ONLY as a valid JSON object with the following structure:
{{
  "nodes": [
    {{"id": "unique_id_1", "label": "SchemaNodeType1", "name": "Actual Instance Name 1"}},
    {{"id": "unique_id_2", "label": "SchemaNodeType2", "name": "Actual Instance Name 2"}}
  ],
  "relationships": [
    {{"source_id": "unique_id_1", "type": "SCHEMA_RELATIONSHIP_TYPE", "target_id": "unique_id_2"}}
  ]
}}

Ensure that the output is strictly valid JSON without markdown blocks if possible, or inside a ```json block. Do not add any conversational text.

Text:
{text}
"""
        logger.info("Calling LLM to populate knowledge graph based on schema...")
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert knowledge graph extractor. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            content = response.choices[0].message.content.strip()
            content = content.strip()
            
            # Clean up potential markdown blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            # Remove trailing commas
            content = re.sub(r',\s*([\]}])', r'\1', content)
                
            try:
                kg_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON. Raw content was:\n{content}")
                raise e
                
            logger.info(f"Extracted Knowledge Graph: {json.dumps(kg_data, indent=2, ensure_ascii=False)}")
            
            await self._store_kg_in_neo4j(kg_data)
            
        except Exception as e:
            logger.error(f"Failed to populate knowledge graph: {e}")
            raise

    async def _store_kg_in_neo4j(self, kg_data: dict):
        nodes = kg_data.get("nodes", [])
        relationships = kg_data.get("relationships", [])

        logger.info("Storing knowledge graph instances in Neo4j...")
        async with self.driver.session() as session:
            # Create Nodes
            for node in nodes:
                node_id = node.get("id")
                label = node.get("label", "Entity")
                name = node.get("name", "unknown")
                
                # Sanitize label to prevent injection
                label = re.sub(r'[^a-zA-Z0-9_]', '', label)
                if not label:
                    label = "Entity"
                
                query = f"""
                MERGE (n:`{label}` {{name: $name}})
                SET n.kg_id = $id
                """
                await session.run(query, name=name, id=node_id)
                
            # Create Relationships
            for rel in relationships:
                source_id = rel.get("source_id")
                target_id = rel.get("target_id")
                rel_type = rel.get("type")
                
                # Sanitize rel_type
                rel_type = re.sub(r'[^a-zA-Z0-9_]', '', rel_type)
                if not rel_type:
                    continue
                
                query = f"""
                MATCH (s {{kg_id: $source_id}})
                MATCH (t {{kg_id: $target_id}})
                MERGE (s)-[r:`{rel_type}`]->(t)
                """
                await session.run(query, source_id=source_id, target_id=target_id)
                
        logger.info("Knowledge Graph successfully stored in Neo4j.")

    async def query_kg(self, question: str) -> str:
        schema = await self.fetch_ontology_schema()
        if not schema["node_types"]:
            return "オントロジースキーマが登録されていません。先に extract コマンドを実行してください。"

        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)

        # 1. Text2Cypher (Generate Cypher query)
        cypher_prompt = f"""
You are an expert Neo4j Cypher developer.
Given the following ontology schema, write a Cypher query that answers the user's question.

SCHEMA:
{schema_json}

IMPORTANT RULES:
1. Output ONLY the raw Cypher query string. Do not include Markdown formatting (like ```cypher).
2. Do not include any explanations or conversational text.
3. Use the exact node labels and relationship types from the schema.
4. Remember that entities store their value in the `name` property. Example: `MATCH (c:Customer {{name: '山田太郎'}})`
5. Return the relevant nodes or properties that answer the question.

Question: {question}
"""
        logger.info("Generating Cypher query via LLM...")
        try:
            cypher_response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a Cypher query generator. Output only valid Cypher."},
                    {"role": "user", "content": cypher_prompt}
                ],
                temperature=0.0
            )
            
            cypher_query = cypher_response.choices[0].message.content.strip()
            # Clean up potential markdown blocks if LLM disobeyed
            if cypher_query.startswith("```cypher"):
                cypher_query = cypher_query[9:]
            if cypher_query.startswith("```"):
                cypher_query = cypher_query[3:]
            if cypher_query.endswith("```"):
                cypher_query = cypher_query[:-3]
            cypher_query = cypher_query.strip()
            
            logger.info(f"Generated Cypher:\n{cypher_query}")
            
            # 2. Execute Cypher query
            results = []
            async with self.driver.session() as session:
                result_cursor = await session.run(cypher_query)
                async for record in result_cursor:
                    results.append(record.data())
                    
            logger.info(f"Query Results: {json.dumps(results, ensure_ascii=False)}")
            
            # 3. Generate natural language answer
            answer_prompt = f"""
You are an AI assistant answering a user's question based on Knowledge Graph data.

Question: {question}

Data retrieved from the Neo4j database:
{json.dumps(results, ensure_ascii=False, indent=2)}

Please provide a natural, concise, and helpful answer in Japanese based ONLY on the provided data.
If the data is empty or does not contain the answer, politely state that you do not have the information.
"""
            logger.info("Generating final answer via LLM...")
            answer_response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": answer_prompt}
                ],
                temperature=0.0
            )
            
            return answer_response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to query knowledge graph: {e}")
            return f"検索中にエラーが発生しました: {e}"

    async def query_kg_with_session(self, question: str, memory) -> dict:
        """セッション対応版のナレッジグラフ検索。

        MemoryManagerを活用して会話履歴・長期記憶のコンテキストを
        LLMに渡し、文脈を踏まえたCypher生成と回答生成を行う。

        Returns:
            dict: {"answer", "cypher", "data", "entities"}
        """
        from ontology_extractor.memory import MemoryManager
        mem: MemoryManager = memory

        schema = await self.fetch_ontology_schema()
        if not schema["node_types"]:
            return {
                "answer": "オントロジースキーマが登録されていません。先に extract を実行してください。",
                "cypher": "", "data": [], "entities": []
            }

        schema_json = json.dumps(schema, indent=2, ensure_ascii=False)

        # 会話履歴の取得（短期記憶）
        session_id = getattr(mem, '_current_session_id', None)
        history_text = ""
        if session_id:
            history = await mem.get_history(session_id, limit=10)
            if history:
                history_text = "\n".join(
                    f"[{m['role']}] {m['content']}" for m in history
                )
                history_text = f"\nCONVERSATION HISTORY:\n{history_text}\n"

        # 長期記憶の取得
        ltm_context = await mem.get_long_term_context(limit=5)
        ltm_text = ""
        if ltm_context.get("facts"):
            facts_str = "\n".join(f"- {f['content']}" for f in ltm_context["facts"])
            ltm_text = f"\nKNOWN FACTS (from long-term memory):\n{facts_str}\n"

        # 1. Text2Cypher
        cypher_prompt = f"""
You are an expert Neo4j Cypher developer.
Given the following ontology schema and context, write a Cypher query that answers the user's question.

SCHEMA:
{schema_json}
{history_text}{ltm_text}
IMPORTANT RULES:
1. Output ONLY the raw Cypher query string. Do not include Markdown formatting (like ```cypher).
2. Do not include any explanations or conversational text.
3. Use the exact node labels and relationship types from the schema.
4. Remember that entities store their value in the `name` property. Example: `MATCH (c:Customer {{name: '山田太郎'}})`
5. Return the relevant nodes or properties that answer the question.
6. If the user refers to something from the conversation history (e.g. "that person", "its", "the same one"), resolve it using the conversation context.

Question: {question}
"""
        logger.info("Generating Cypher query via LLM (session-aware)...")
        try:
            cypher_response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a Cypher query generator. Output only valid Cypher."},
                    {"role": "user", "content": cypher_prompt}
                ],
                temperature=0.0
            )

            cypher_query = cypher_response.choices[0].message.content.strip()
            if cypher_query.startswith("```cypher"):
                cypher_query = cypher_query[9:]
            if cypher_query.startswith("```"):
                cypher_query = cypher_query[3:]
            if cypher_query.endswith("```"):
                cypher_query = cypher_query[:-3]
            cypher_query = cypher_query.strip()

            logger.info(f"Generated Cypher:\n{cypher_query}")

            # 2. Execute Cypher query
            results = []
            async with self.driver.session() as session:
                result_cursor = await session.run(cypher_query)
                async for record in result_cursor:
                    results.append(record.data())

            logger.info(f"Query Results: {json.dumps(results, ensure_ascii=False)}")

            # 3. Generate natural language answer
            answer_prompt = f"""
You are an AI assistant answering a user's question based on Knowledge Graph data.
{history_text}
Question: {question}

Data retrieved from the Neo4j database:
{json.dumps(results, ensure_ascii=False, indent=2)}

Please provide a natural, concise, and helpful answer in Japanese based ONLY on the provided data.
If the data is empty or does not contain the answer, politely state that you do not have the information.
"""
            logger.info("Generating final answer via LLM...")
            answer_response = await self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": answer_prompt}
                ],
                temperature=0.0
            )

            answer = answer_response.choices[0].message.content.strip()

            # エンティティ抽出（回答に含まれるエンティティを簡易的に抽出）
            entities = []
            for r in results:
                for v in r.values():
                    if isinstance(v, str) and v != "unknown":
                        entities.append({"name": v, "label": "Entity"})

            return {
                "answer": answer,
                "cypher": cypher_query,
                "data": results,
                "entities": entities,
            }

        except Exception as e:
            logger.error(f"Failed to query knowledge graph: {e}")
            return {
                "answer": f"検索中にエラーが発生しました: {e}",
                "cypher": "", "data": [], "entities": []
            }

    async def close(self):
        await self.driver.close()

