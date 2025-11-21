import json
import logging
import re
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable
from app.config import settings
from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential

# Logger & Driver Setup
log = logging.getLogger("uvicorn.error")

driver = AsyncGraphDatabase.driver(
    settings.NEO4J_URI, 
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)


# Helper function for readable labels
def create_readable_label(node_id: str, node_type: str) -> str:
    """Create a user-friendly label for graph nodes"""
    if not node_id:
        return "Unknown"
    
    # Add type prefix/suffix for clarity
    type_prefixes = {
        "ORG": "🏢",
        "PERSON": "👤", 
        "PRODUCT": "📦",
        "INDUSTRY": "🏭",
        "CONCEPT": "💡",
        "ENTITY": "⚪",
        "BUSINESS_CONCEPT": "💼"
    }
    
    prefix = type_prefixes.get(node_type, "")
    
    # Clean up the label
    cleaned_id = node_id.replace("_", " ").title()
    
    return f"{prefix} {cleaned_id}".strip()

def format_relation_label(relation: str) -> str:
    """Make relationship labels more readable"""
    relation_map = {
        "CEO_OF": "is CEO of",
        "OPERATES_IN": "operates in",
        "COMPETES_WITH": "competes with",
        "MANUFACTURES": "manufactures",
        "PARTNERS_WITH": "partners with",
        "SUPPLIES_TO": "supplies to",
        "RELATED_TO": "related to",
        "HAS_RISK": "has risk in",
        "PRODUCES": "produces"
    }
    return relation_map.get(relation, relation.replace("_", " ").lower())

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


# --- Core Logic: AI Extraction (Updated: No filename) ---

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
async def extract_graph_from_text(text_chunk: str) -> dict:
    """
    Extracts Nodes and Relationships from text using LLM with balanced accuracy and completeness.
    """
    prompt = f"""
    You are an expert Financial Analyst AI building a comprehensive Knowledge Graph from SEC 10-K documents.
    
    Extract entities and relationships from the following text, focusing on business relevance and accuracy.
    
    RULES:
    1. Extract: Companies, People, Products, Industries, Technologies, Business Concepts
    2. Include relationships that are clearly stated or strongly implied in business context
    3. Focus on the PRIMARY company mentioned, but include competitive landscape
    4. Use clear entity names (e.g., "NVIDIA" not "NVIDIA Corporation")
    5. Be conservative with CEO relationships - only extract if explicitly mentioned with title
    
    RELATIONSHIP TYPES:
    - CEO_OF, FOUNDED, OPERATES_IN, COMPETES_WITH, PARTNERS_WITH, PRODUCES, MANUFACTURES
    - HAS_SUBSIDIARY, SUPPLIES_TO, LOCATED_IN, SPECIALIZES_IN
    
    OUTPUT JSON FORMAT:
    {{
        "nodes": [
            {{"id": "NVIDIA", "type": "ORG"}},
            {{"id": "Jensen Huang", "type": "PERSON"}},
            {{"id": "Gaming", "type": "INDUSTRY"}},
            {{"id": "AI Computing", "type": "TECHNOLOGY"}}
        ],
        "edges": [
            {{"source": "Jensen Huang", "target": "NVIDIA", "relation": "CEO_OF"}},
            {{"source": "NVIDIA", "target": "Gaming", "relation": "OPERATES_IN"}},
            {{"source": "NVIDIA", "target": "AI Computing", "relation": "SPECIALIZES_IN"}}
        ]
    }}
    
    TEXT: {text_chunk}
    """
    
    try:
        response = await acompletion(
            model=f"{settings.LLM_PROVIDER}/llama-3.1-8b-instant",
            api_key=settings.LLM_API_KEY,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,  # Balanced between creativity and consistency
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(content)
        
        # Light validation - only filter obvious errors
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        
        # Basic CEO validation only
        filtered_edges = []
        ceo_count = {}
        
        for edge in edges:
            source = edge.get('source', '').strip()
            target = edge.get('target', '').strip()
            relation = edge.get('relation', '')
            
            if not source or not target:
                continue
                
            # Only filter CEO relationships that are obviously wrong
            if relation == "CEO_OF":
                source_lower = source.lower()
                
                # Prevent one person being CEO of more than 2 companies (allow some flexibility)
                if source_lower in ceo_count:
                    ceo_count[source_lower] += 1
                    if ceo_count[source_lower] > 2:
                        continue
                else:
                    ceo_count[source_lower] = 1
            
            filtered_edges.append(edge)
        
        result = {"nodes": nodes, "edges": filtered_edges}
        return result
        
    except Exception as e:
        log.error(f"Graph extraction failed: {e}")
        return {"nodes": [], "edges": []}


# --- Core Logic: Neo4j Storage (Global Nodes / Local Edges) ---

async def store_graph_data(document_id: int, graph_data: dict):
    raw_nodes = graph_data.get("nodes", [])
    raw_edges = graph_data.get("edges", [])

    log.info(f"🔍 Raw data - Nodes: {len(raw_nodes)}, Edges: {len(raw_edges)}")
    if not raw_nodes and not raw_edges:
        return

    # --- 🛡️ FILTERING LOGIC (Balanced) ---
    valid_nodes = []
    valid_node_ids = set()
    
    # Reasonable blacklist - not too strict
    BLACKLIST_TERMS = ["us-gaap", "xbrl", "Member", "Domain", "Table", "Abstract"]
    
    for i, node in enumerate(raw_nodes):
        if isinstance(node, dict):
            node_id = node.get("id", "").strip()
            node_type = node.get("type", "CONCEPT")
        elif isinstance(node, str):
            node_id = node.strip()
            node_type = "CONCEPT"
        else:
            continue

        if not node_id:
            continue
            
        original_id = node_id
        
        # Basic cleaning
        node_id = re.sub(r'Member$', '', node_id, flags=re.IGNORECASE).strip()

        # Balanced filter conditions
        if len(node_id) < 2 or node_id.isdigit(): 
            continue
        if any(term.lower() in node_id.lower() for term in BLACKLIST_TERMS): 
            continue

        valid_nodes.append({"id": node_id, "type": node_type})
        valid_node_ids.add(node_id)

    # Balanced edge filtering
    valid_edges = []
    ceo_relationships = {}  # Track CEO relationships but allow some flexibility
    
    for edge in raw_edges:
        if not isinstance(edge, dict): 
            continue
        
        src = str(edge.get("source", "")).strip()
        tgt = str(edge.get("target", "")).strip()
        relation = edge.get("relation", "RELATED_TO")
        
        if not src or not tgt:
            continue
        
        # Clean Source/Target 
        src = re.sub(r'Member$', '', src, flags=re.IGNORECASE).strip()
        tgt = re.sub(r'Member$', '', tgt, flags=re.IGNORECASE).strip()

        # Light CEO validation - only prevent obvious errors
        if relation == "CEO_OF":
            src_lower = src.lower()
            if src_lower in ceo_relationships:
                # Allow up to 2 CEO relationships per person (some flexibility for complex structures)
                if len(ceo_relationships[src_lower]) >= 2:
                    log.warning(f"⚠️ Limiting CEO relationships for {src} (already CEO of {ceo_relationships[src_lower]})")
                    continue
                ceo_relationships[src_lower].append(tgt)
            else:
                ceo_relationships[src_lower] = [tgt]
        
        valid_edges.append({
            "source": src,
            "target": tgt,
            "relation": relation
        })
        
        # Add nodes if they don't exist
        if src and src not in valid_node_ids:
            valid_nodes.append({"id": src, "type": "ENTITY"})
            valid_node_ids.add(src)
            
        if tgt and tgt not in valid_node_ids:
            valid_nodes.append({"id": tgt, "type": "ENTITY"})
            valid_node_ids.add(tgt)

    nodes = valid_nodes
    edges = valid_edges

    log.info(f"📊 After filtering - Nodes: {len(nodes)}, Edges: {len(edges)}")
    
    if not nodes and not edges:
        return

    # --- 💾 STORAGE LOGIC ---
    # Store nodes first with labels
    if nodes:
        # Add readable labels to nodes before storing
        for node in nodes:
            if 'label' not in node:
                node['label'] = create_readable_label(node['id'], node['type'])
        
        node_query = """
        UNWIND $nodes AS n_data
        MERGE (n:Entity {id: n_data.id})
        ON CREATE SET n.type = n_data.type, n.label = n_data.label, n.name = n_data.id
        ON MATCH SET n.type = n_data.type, n.label = n_data.label, n.name = n_data.id
        """
        
        try:
            async with driver.session() as session:
                await session.run(node_query, nodes=nodes)
            log.info(f"✅ Stored {len(nodes)} nodes with labels")
        except Exception as e:
            log.error(f"❌ Error storing nodes: {e}")
            return
    
    # Store edges separately
    if edges:
        edge_query = """
        UNWIND $edges AS e_data
        MATCH (source:Entity {id: e_data.source})
        MATCH (target:Entity {id: e_data.target})
        MERGE (source)-[r:RELATION {type: e_data.relation, doc_id: $doc_id}]->(target)
        """
        
        try:
            async with driver.session() as session:
                await session.run(edge_query, edges=edges, doc_id=document_id)
            log.info(f"✅ Stored {len(edges)} edges for Document {document_id}")
        except Exception as e:
            log.error(f"❌ Error storing edges: {e}")


async def get_document_graph(document_id: int) -> dict:
    """
    ดึง Nodes และ Edges เฉพาะของเอกสาร ID นี้
    """
    # First, let's check if there are any relationships for this document
    check_query = """
    MATCH ()-[r {doc_id: $doc_id}]->()
    RETURN count(r) as edge_count
    """
    
    nodes_dict = {}
    edges_list = []
    
    try:
        async with driver.session() as session:
            # Check edge count first
            check_result = await session.run(check_query, doc_id=document_id)
            check_record = await check_result.single()
            edge_count = check_record["edge_count"] if check_record else 0
            
            if edge_count == 0:
                # Try to get all nodes that might be related (even without doc_id)
                fallback_query = """
                MATCH (n:Entity)
                RETURN n
                LIMIT 100
                """
                result = await session.run(fallback_query)
                async for record in result:
                    n = record["n"]
                    n_id = n.get("id")
                    if n_id:
                        # Use stored label if available, otherwise create one
                        stored_label = n.get("label")
                        if stored_label:
                            readable_label = stored_label
                        else:
                            n_type = n.get("type", "Unknown")
                            readable_label = create_readable_label(n_id, n_type)
                        
                        nodes_dict[n_id] = {
                            "id": n_id, 
                            "label": readable_label, 
                            "type": n.get("type", "Unknown")
                        }
            else:
                # Get nodes and edges for this specific document
                main_query = """
                MATCH (n)-[r {doc_id: $doc_id}]->(m)
                RETURN n, r, m
                LIMIT 2000
                """
                result = await session.run(main_query, doc_id=document_id)
                
                async for record in result:
                    n = record["n"]
                    n_id = n.get("id")
                    if n_id and n_id not in nodes_dict:
                        # Use stored label if available
                        stored_label = n.get("label")
                        if stored_label:
                            readable_label = stored_label
                        else:
                            n_type = n.get("type", "Unknown")
                            readable_label = create_readable_label(n_id, n_type)
                        
                        nodes_dict[n_id] = {
                            "id": n_id, 
                            "label": readable_label, 
                            "type": n.get("type", "Unknown")
                        }

                    m = record["m"]
                    m_id = m.get("id")
                    if m_id and m_id not in nodes_dict:
                        # Use stored label if available
                        stored_label = m.get("label")
                        if stored_label:
                            readable_label = stored_label
                        else:
                            m_type = m.get("type", "Unknown")
                            readable_label = create_readable_label(m_id, m_type)
                        
                        nodes_dict[m_id] = {
                            "id": m_id, 
                            "label": readable_label, 
                            "type": m.get("type", "Unknown")
                        }

                    r = record["r"]
                    relation_type = r.get("type", "RELATED_TO")
                    edges_list.append({
                        "source": n_id,
                        "target": m_id,
                        "relation": format_relation_label(relation_type)
                    })
                    
    except Exception as e:
        log.error(f"❌ Error fetching graph for document {document_id}: {e}")
        
    result = {
        "nodes": list(nodes_dict.values()),
        "edges": edges_list
    }
    
    return result


async def query_graph_context(query_text: str, doc_id: int = None) -> str:
    """
    GraphRAG: ค้นหาข้อมูลจากกราฟ
    """
    log.info(f"🧠 GraphRAG processing question: '{query_text[:100]}{'...' if len(query_text) > 100 else ''}'")
    
    # Try LLM extraction first, with fallback to simple parsing
    entities = []
    
    try:
        # Simple and reliable LLM prompt
        extraction_prompt = f"""Extract 3-5 key terms from this question that could be company names, product names, or person names.

Question: {query_text}

Return JSON format: {{"terms": ["term1", "term2", "term3"]}}"""
        
        response = await acompletion(
            model=f"{settings.LLM_PROVIDER}/llama-3.1-8b-instant",
            api_key=settings.LLM_API_KEY,
            messages=[{"role": "user", "content": extraction_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=100
        )
        
        content = response.choices[0].message.content.strip()
        # Clean up content
        content = content.replace('```json', '').replace('```', '').replace('\n', '').strip()
        
        data = json.loads(content)
        
        # Extract entities from various possible keys
        for key in ["terms", "entities", "keywords", "names"]:
            if key in data and isinstance(data[key], list):
                entities = [str(item).strip() for item in data[key] if item]
                break
        
        # Filter out empty/short entities
        entities = [e for e in entities if len(e) > 1][:5]
        
        if entities:
            log.info(f"📋 GraphRAG entities extracted: {entities}")
        
    except Exception as e:
        log.error(f"LLM extraction failed: {e}")
        # Fallback to simple regex extraction
        import re
        words = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b', query_text)
        stopwords = {'What', 'How', 'When', 'Where', 'Why', 'Who', 'The', 'This', 'That', 'These', 'Those', 'Which', 'Can', 'Does', 'Is', 'Are'}
        entities = [word for word in words if word not in stopwords and len(word) > 2][:5]
        
        if entities:
            log.info(f"📋 GraphRAG fallback entities: {entities}")
    
    if not entities:
        log.info("❌ No entities extracted for GraphRAG")
        return ""

    # Search graph with extracted entities
    cypher_query = """
    UNWIND $entities AS target_name
    MATCH (n:Entity)
    WHERE toLower(n.id) CONTAINS toLower(target_name)
    """
    
    if doc_id:
        cypher_query += """
        MATCH (n)-[r]-(neighbor)
        WHERE r.doc_id = $doc_id
        """
    else:
        cypher_query += """
        MATCH (n)-[r]-(neighbor)
        """

    cypher_query += """
    RETURN n.id AS source, r.type AS rel, neighbor.id AS target
    LIMIT 30
    """

    context_lines = []
    try:
        async with driver.session() as session:
            result = await session.run(cypher_query, entities=entities, doc_id=doc_id)
            async for record in result:
                source = record['source']
                rel = record['rel'] 
                target = record['target']
                line = f"{source} --[{rel}]--> {target}"
                context_lines.append(line)
                
        if context_lines:
            log.info(f"🔗 GraphRAG found {len(context_lines)} connections:")
            for line in context_lines[:3]:  # Show first 3 connections
                log.info(f"   {line}")
            if len(context_lines) > 3:
                log.info(f"   ... and {len(context_lines) - 3} more connections")
        else:
            log.info("❌ No graph connections found for extracted entities")
            
    except Exception as e:
        log.error(f"Error running graph query: {e}")
        return ""
            
    if not context_lines:
        return ""
        
    graph_context = "Knowledge Graph Connections:\n" + "\n".join(context_lines)
    log.info(f"✅ GraphRAG returning {len(graph_context)} character context")
    return graph_context


async def delete_document_graph(document_id: int):
    """
    ลบเส้นความสัมพันธ์ของเอกสารนี้ และลบ Node ที่ไม่เหลือความสัมพันธ์ใดๆ
    """
    async with driver.session() as session:
        # 1. ลบเส้น (Edges) ทั้งหมดที่มี doc_id นี้
        await session.run("""
            MATCH ()-[r {doc_id: $doc_id}]->()
            DELETE r
        """, doc_id=document_id)
        
        # 2. ลบ Node กำพร้า (Orphan Nodes)
        # Node ไหนที่ไม่มีเส้นเข้าหรือออกเลย ให้ลบทิ้ง
        await session.run("""
            MATCH (n:Entity)
            WHERE NOT (n)--()
            DELETE n
        """)