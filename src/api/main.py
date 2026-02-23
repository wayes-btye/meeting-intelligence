from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.extraction import router as extraction_router
from src.api.routes.image_summary import router as image_summary_router
from src.api.routes.ingest import router as ingest_router
from src.api.routes.meetings import router as meetings_router
from src.api.routes.query import router as query_router

app = FastAPI(
    title="Meeting Intelligence API",
    description="RAG-powered meeting transcript analysis",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8501",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router)
app.include_router(query_router)
app.include_router(meetings_router)
app.include_router(extraction_router)
app.include_router(image_summary_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
