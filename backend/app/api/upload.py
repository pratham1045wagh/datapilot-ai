from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.dataset_service import dataset_service
from app.agents.data_preparation_agent import data_preparation_agent

router = APIRouter(prefix="/api", tags=["upload"])

@router.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        content = await file.read()
        dataset_id, saved_path, original_filename = dataset_service.save_uploaded_file(content, file.filename)
        profile, issues = data_preparation_agent.profile(dataset_id)
        
        return {
            "status": "success",
            "message": "File uploaded and profiled successfully.",
            "dataset_id": dataset_id,
            "filename": original_filename,
            "profile": profile,
            "issues": issues
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
