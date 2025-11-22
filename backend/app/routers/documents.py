from typing import Annotated
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app import models, schemas
from app.database import get_db
from app.dependencies import get_current_user
from app.controllers import document_controller

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

@router.post("/", response_model=schemas.Document)
async def create_document_and_upload_file(
    db: AsyncSession = Depends(get_db), 
    current_user: models.User = Depends(get_current_user), 
    file: UploadFile = File(...)
):
    return await document_controller.create_document(db, current_user, file)

@router.get("/", response_model=list[schemas.Document])
async def read_documents(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return await document_controller.get_documents(db, current_user)

@router.get("/{doc_id}/chunks", response_model=list[schemas.Chunk])
async def read_document_chunks(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return await document_controller.get_document_chunks(doc_id, db, current_user)

@router.post("/{doc_id}/query", response_model=schemas.QueryResponse)
async def query_document(
    doc_id: int,
    request: schemas.QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    answer, context = await document_controller.query_document(
        doc_id, request.question, db, current_user
    )
    return schemas.QueryResponse(answer=answer, context=context)

@router.post("/query", response_model=schemas.QueryResponse)
async def query_all_documents(
    request: schemas.QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    answer, context = await document_controller.query_all_documents(
        request.question, db, current_user
    )
    return schemas.QueryResponse(answer=answer, context=context)

@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    await document_controller.delete_document(doc_id, db, current_user)
    return None

@router.post("/query", response_model=schemas.QueryResponse)
async def query_all_documents(
    request: schemas.QueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    answer, context = await document_controller.query_all_documents(
        request.question, db, current_user
    )
    return schemas.QueryResponse(answer=answer, context=context)

@router.post("/fetch-sec")
async def fetch_sec_document(
    req: schemas.SecRequest,
    current_user: models.User = Depends(get_current_user)
):
    await document_controller.fetch_sec_document(req.ticker, current_user)
    return {"message": f"Started fetching 10-K for {req.ticker}. Check your documents list in a few minutes."}

@router.get("/{doc_id}/graph", response_model=schemas.GraphData)
async def get_document_graph_data(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return await document_controller.get_graph_data(doc_id, db, current_user)
