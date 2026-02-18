from fastapi import FastAPI

from src.api.routes.ingest import router as ingest_router
from src.api.routes.meetings import router as meetings_router
from src.api.routes.query import router as query_router

app = FastAPI(
    title="Meeting Intelligence API",
    description="RAG-powered meeting transcript analysis",
    version="0.1.0",
)

app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(meetings_router)


@app.get("/health")
async def health():
    return {"status": "healthy"}
