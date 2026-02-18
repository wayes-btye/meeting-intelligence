from fastapi import FastAPI

app = FastAPI(
    title="Meeting Intelligence API",
    description="RAG-powered meeting transcript analysis",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "healthy"}
