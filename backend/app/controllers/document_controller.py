import asyncio
import os
import sqlalchemy as sa
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, models, processing, sec_service
from app.processing import UPLOAD_DIRECTORY
from app.knowledge_graph import get_document_graph, delete_document_graph

async def create_document(
    db: AsyncSession, 
    current_user: models.User, 
    file: UploadFile
):
    # 1. Read content
    content = await file.read()

    # 2. Create Document record
    db_doc = await crud.create_document(
        db=db, 
        filename=file.filename, 
        owner_id=current_user.id
    )

    # 3. Process document (extract, chunk, embed, save) in background
    asyncio.create_task(
        processing.save_extract_chunk_and_embed( 
            document_id=db_doc.id,
            filename=file.filename,
            content_type=file.content_type,
            content=content
        )
    )

    # 4. Return immediately
    return db_doc

async def get_documents(db: AsyncSession, current_user: models.User):
    stmt = (
        sa.select(models.Document)
        .where(models.Document.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_document_chunks(
    doc_id: int,
    db: AsyncSession,
    current_user: models.User
):
    # 1. Check ownership
    stmt_doc = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result_doc = await db.execute(stmt_doc)
    if result_doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. Get chunks
    stmt_chunks = (
        sa.select(models.Chunk)
        .where(models.Chunk.document_id == doc_id)
    )
    result_chunks = await db.execute(stmt_chunks)
    return result_chunks.scalars().all()

async def query_document(
    doc_id: int,
    query_text: str,
    db: AsyncSession,
    current_user: models.User
):
    # 1. Check ownership
    stmt_doc = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result_doc = await db.execute(stmt_doc)
    if result_doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. Retrieve relevant chunks
    relevant_chunks = await processing.retrieve_relevant_chunks(
        document_id=doc_id,
        query_text=query_text
    )

    # 3. Generate answer
    answer = await processing.generate_answer(
        query=query_text,
        context_chunks=relevant_chunks,
        doc_id=doc_id
    )

    return answer, relevant_chunks

async def query_all_documents(
    query_text: str,
    db: AsyncSession,
    current_user: models.User
):
    # 1. Retrieve relevant chunks from all user's documents
    relevant_chunks = await processing.retrieve_relevant_chunks_global(
        user_id=current_user.id,
        query_text=query_text
    )
    
    # 2. Generate answer
    answer = await processing.generate_answer(
        query=query_text,
        context_chunks=relevant_chunks,
        doc_id=None
    )
    
    return answer, relevant_chunks

async def delete_document(
    doc_id: int,
    db: AsyncSession,
    current_user: models.User
):
    # 1. Check ownership
    stmt = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result = await db.execute(stmt)
    db_doc = result.scalar_one_or_none()
    
    if db_doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # 2. Delete file from disk
    file_path = os.path.join(UPLOAD_DIRECTORY, f"doc_{doc_id}_{db_doc.filename}")
    if os.path.exists(file_path):
        os.remove(file_path)
        
    # 3. Delete graph from Neo4j
    try:
        await delete_document_graph(doc_id)
    except Exception as e:
        print(f"⚠️ Failed to delete graph: {e}")

    # 4. Delete from Database
    await crud.delete_document(db, doc_id)

async def get_graph_data(
    doc_id: int,
    db: AsyncSession,
    current_user: models.User
):
    # 1. Check ownership
    stmt_doc = (
        sa.select(models.Document)
        .where(models.Document.id == doc_id)
        .where(models.Document.owner_id == current_user.id)
    )
    result_doc = await db.execute(stmt_doc)
    if result_doc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found")

    # 2. Get graph data from Neo4j
    graph_data = await get_document_graph(doc_id)
    
    return graph_data

async def fetch_sec_document(
    ticker: str,
    current_user: models.User
):
    asyncio.create_task(
        sec_service.fetch_and_process_10k(
            user_id=current_user.id,
            ticker=ticker
        )
    )
