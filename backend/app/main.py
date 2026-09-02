import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import upload, datasets, cleaning, queries

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

app = FastAPI(
    title="DataPilot AI Platform API",
    description="Full-stack AI Platform combining Data Preparation Agent and Natural Language SQL Agent",
    version="1.0.0"
)

# Enable CORS for React frontend (supports environment CORS_ORIGINS for production deployment)
raw_cors = os.getenv("CORS_ORIGINS", "*")
if raw_cors.strip() and raw_cors.strip() != "*":
    cors_origins = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]
else:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Register routers
app.include_router(upload.router)
app.include_router(datasets.router)
app.include_router(cleaning.router)
app.include_router(queries.router)

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "DataPilot AI Platform API"}

if __name__ == "__main__":
    import uvicorn
    from app.config import settings
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
