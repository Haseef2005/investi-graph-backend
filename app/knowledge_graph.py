# app/knowledge_graph.py

import json
import logging
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable
from app.config import settings

# LLM imports
from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_fixed

# 1. Logger & Driver Setup
log = logging.getLogger("uvicorn.error")

driver = AsyncGraphDatabase.driver(
    settings.NEO4J_URI, 
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

# --- Connection Management ---
async def check_neo4j_connection():
    """Checks the Neo4j connection status."""
    try:
        await driver.verify_connectivity()
        log.info("Neo4j connection verified successfully.")
        return True
    except ServiceUnavailable:
        log.error("Neo4j connection failed. Check Docker container status.")
        return False
    except Exception as e:
        log.error(f"Error checking Neo4j connection: {e}")
        return False

async def close_neo4j_driver():
    """Closes the Neo4j driver connection."""
    await driver.close()
    log.info("Neo4j driver closed.")


# --- Core Logic: AI Extraction ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def extract_graph_from_text(text_chunk: str) -> dict:
    """
    ส่ง Text ไปให้ LLM เพื่อสกัด Nodes และ Relationships ออกมาเป็น JSON
    """
    # Prompt ที่สั่งให้ AI ทำตัวเป็น Graph Extractor
    prompt = f"""
    You are a Knowledge Graph extraction system.
    Your task is to extract meaningful "Entities" (Nodes) and "Relationships" (Edges) from the given text.

    Rules:
    1. Nodes: Identify key people, organizations, locations, concepts, or products.
    2. Relationships: Identify how these nodes are connected (e.g., "IS_CEO_OF", "LOCATED_IN", "PRODUCED_BY").
    3. Output JSON ONLY. No markdown, no explanations.

    Format:
    {{
      "nodes": [
        {{"id": "Name of Entity", "type": "PERSON/ORG/ETC"}},
        ...
      ],
      "edges": [
        {{"source": "Name of Source Node", "target": "Name of Target Node", "relation": "RELATION_NAME"}},
        ...
      ]
    }}

    TEXT TO PROCESS:
    {text_chunk}
    """

    try:
        response = await acompletion(
            model=f"{settings.LLM_PROVIDER}/llama-3.1-8b-instant",
            api_key=settings.LLM_API_KEY,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"} # บังคับ JSON (ฟีเจอร์ใหม่ของ Groq/OpenAI)
        )
        
        content = response.choices[0].message.content
        
        # Clean string (เผื่อ LLM เผลอใส่ ```json ... ``` มา)
        content = content.replace("```json", "").replace("```", "").strip()
        
        # Parse JSON
        data = json.loads(content)
        return data

    except Exception as e:
        log.error(f"Graph extraction failed: {e}")
        return {"nodes": [], "edges": []} # คืนค่าว่างถ้าพัง


# --- Core Logic: Neo4j Storage ---

async def store_graph_data(document_id: int, graph_data: dict):
    """
    บันทึก Nodes และ Edges ลง Neo4j ด้วย Cypher Query
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    if not nodes and not edges:
        return

    # Cypher Query: ใช้ UNWIND เพื่อ Loop สร้างข้อมูลทีละเยอะๆ (Batch)
    query = """
    // 1. สร้าง Nodes
    UNWIND $nodes AS node
    MERGE (e:Entity {name: node.id})
    SET e.type = node.type, e.doc_id = $doc_id

    // 2. สร้าง Relationships
    WITH e
    UNWIND $edges AS edge
    MATCH (source:Entity {name: edge.source})
    MATCH (target:Entity {name: edge.target})
    MERGE (source)-[r:RELATED_TO {type: edge.relation}]->(target)
    """

    async with driver.session() as session:
        try:
            await session.run(query, nodes=nodes, edges=edges, doc_id=document_id)
            log.info(f"Graph stored: {len(nodes)} nodes, {len(edges)} edges for Doc {document_id}")
        except Exception as e:
            log.error(f"Neo4j storage failed: {e}")