from fastapi import APIRouter, HTTPException
from app.agents.data_preparation_agent import data_preparation_agent
from app.models.cleaning_models import (
    PreviewRequest,
    CleaningExecutionRequest,
    UserSuggestionRequest,
    UserSuggestionResponse,
    PostCleanSuggestionRequest,
    PostCleanSuggestionAnalysis,
    PostCleanApplyRequest,
    PostCleanApplyResponse
)

router = APIRouter(prefix="/api/dataset", tags=["cleaning"])

@router.get("/{dataset_id}/recommendations")
async def get_cleaning_recommendations(dataset_id: str):
    try:
        recs = data_preparation_agent.get_recommendations(dataset_id)
        return {"dataset_id": dataset_id, "recommendations": recs}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{dataset_id}/user-suggestion")
async def add_user_suggestion(dataset_id: str, payload: UserSuggestionRequest):
    try:
        res = data_preparation_agent.add_user_suggestion(dataset_id, payload.user_instruction)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process suggestion: {str(e)}")

@router.post("/{dataset_id}/post-clean-suggestion/analyze", response_model=PostCleanSuggestionAnalysis)
async def analyze_post_clean_suggestion(dataset_id: str, payload: PostCleanSuggestionRequest):
    try:
        return data_preparation_agent.analyze_post_clean_suggestion(dataset_id, payload.user_instruction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze post-cleaning suggestion: {str(e)}")

@router.post("/{dataset_id}/post-clean-suggestion/apply", response_model=PostCleanApplyResponse)
async def apply_post_clean_suggestion(dataset_id: str, payload: PostCleanApplyRequest):
    try:
        return data_preparation_agent.apply_post_clean_suggestion(dataset_id, payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply post-cleaning suggestion: {str(e)}")

@router.post("/{dataset_id}/preview-cleaning")
async def preview_cleaning(dataset_id: str, payload: PreviewRequest):
    try:
        previews = data_preparation_agent.preview(dataset_id, payload.actions)
        return {"dataset_id": dataset_id, "previews": previews}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{dataset_id}/clean")
async def apply_cleaning(dataset_id: str, payload: CleaningExecutionRequest):
    try:
        report = data_preparation_agent.clean(dataset_id, payload.actions)
        return {"status": "success", "message": "Cleaning complete, verified, and SQLite database updated.", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleaning failed: {str(e)}")

