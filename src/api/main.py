from fastapi import FastAPI
from .routes import router

app = FastAPI(
    title="Research-Paper Search Engine",
    description="A domain-specific search engine for research papers with BM25 + PageRank hybrid ranking",
    version="0.1.0"
)

app.include_router(router)
