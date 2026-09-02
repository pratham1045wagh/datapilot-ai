from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from app.agents.data_preparation_agent import data_preparation_agent
from app.services.dataset_service import dataset_service
from app.services.database_service import database_service
from app.config import REPORTS_DIR

router = APIRouter(prefix="/api/dataset", tags=["datasets"])

@router.get("/{dataset_id}/profile")
async def get_dataset_profile(dataset_id: str):
    try:
        profile, issues = data_preparation_agent.profile(dataset_id)
        return {"dataset_id": dataset_id, "profile": profile, "issues": issues}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{dataset_id}/preview")
async def get_cleaned_dataset_preview(
    dataset_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: Optional[str] = Query(default=None)
):
    """
    Returns real paginated rows from the cleaned dataset on screen.
    """
    try:
        res = data_preparation_agent.get_cleaned_preview(dataset_id, page=page, page_size=page_size, search=search)
        return res
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Cleaned dataset preview not found. Please clean dataset first.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")

@router.get("/{dataset_id}/schema")
async def get_dataset_schema(dataset_id: str):
    try:
        # Find SQLite table
        conn = database_service._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?;", (f"%{dataset_id[:8]}%",))
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="SQLite table not found for dataset")
        
        table_name = row["name"]
        schema = database_service.get_table_schema(table_name)
        sample = database_service.get_sample_rows(table_name, limit=5)
        return {
            "dataset_id": dataset_id,
            "table_name": table_name,
            "schema": schema,
            "sample_rows": sample
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{dataset_id}/download")
async def download_cleaned_dataset(dataset_id: str, format: Optional[str] = Query(default=None)):
    result = dataset_service.get_cleaned_file_path(dataset_id, fmt=format)
    if not result:
        raise HTTPException(status_code=404, detail="Cleaned dataset not found. Please run cleaning first.")
    
    cleaned_path, ext = result
    media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if ext == ".xlsx" else "text/csv"
    download_name = f"dataset_cleaned_{dataset_id[:8]}{ext}"
    
    return FileResponse(
        path=str(cleaned_path),
        media_type=media_type,
        filename=download_name
    )

@router.get("/{dataset_id}/cleaning-report")
async def download_cleaning_report(dataset_id: str):
    pdf_path = REPORTS_DIR / f"report_{dataset_id}.pdf"
    if pdf_path.exists():
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=f"cleaning_report_{dataset_id[:8]}.pdf"
        )
    
    # Fallback to Markdown if PDF does not exist yet
    md_path = REPORTS_DIR / f"report_{dataset_id}.md"
    if md_path.exists():
        return FileResponse(
            path=str(md_path),
            media_type="text/markdown",
            filename=f"cleaning_report_{dataset_id[:8]}.md"
        )

    raise HTTPException(status_code=404, detail="Cleaning report not found for this dataset.")
