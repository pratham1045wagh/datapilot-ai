from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from app.agents.sql_agent import sql_agent
from app.models.query_models import QueryRequest
from app.services.sql_pdf_report_service import sql_pdf_report_service
from app.services.dataset_service import dataset_service
from app.services.database_service import database_service

router = APIRouter(prefix="/api", tags=["queries"])

@router.post("/query")
async def execute_natural_language_query(payload: QueryRequest):
    if not payload.user_question.strip():
        raise HTTPException(status_code=400, detail="User question cannot be empty.")
    
    try:
        response = sql_agent.execute_query(payload.user_question, payload.dataset_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

@router.get("/query-history")
async def get_query_history(dataset_id: Optional[str] = Query(default=None)):
    history = sql_agent.get_query_history(dataset_id=dataset_id)
    return {"history": history}

@router.get("/dataset/{dataset_id}/sql-report")
async def download_sql_session_report(dataset_id: str):
    history = sql_agent.get_query_history(dataset_id=dataset_id)
    if not history:
        raise HTTPException(status_code=400, detail="No SQL queries have been executed yet. Run at least one query to generate the report.")
    
    # Try to resolve dataset filename & SQLite table name
    orig_filename = None
    if hasattr(dataset_service, "datasets") and isinstance(dataset_service.datasets, dict) and dataset_id in dataset_service.datasets:
        orig_filename = dataset_service.datasets[dataset_id].get("original_filename")
    
    tbl_name = history[0].table_name if history else None
    
    try:
        pdf_bytes = sql_pdf_report_service.generate_pdf_bytes(
            dataset_id=dataset_id,
            queries=history,
            original_filename=orig_filename,
            sqlite_table_name=tbl_name
        )
        safe_filename = f"sql_session_report_{dataset_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate SQL report PDF: {str(e)}")

