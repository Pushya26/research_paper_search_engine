from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .enhanced_routes import router

app = FastAPI(
    title="Research-Paper Search Engine - Enhanced",
    description="""
    A domain-specific search engine for research papers with advanced features:
    
    **Features:**
    - BM25 + PageRank hybrid ranking
    - Query expansion with synonyms
    - Similar papers recommendation
    - Result caching for performance
    - Real citation data support (via Semantic Scholar)
    
    **Endpoints:**
    - `/search` - Search papers with optional query expansion
    - `/similar/{doc_id}` - Find papers similar to a given paper
    - `/paper/{doc_id}` - Get full paper metadata
    - `/stats` - Corpus statistics
    """,
    version="0.2.0"
)

# Enable CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
async def startup_event():
    """Initialize search engine on startup."""
    from .enhanced_routes import get_search_engine
    get_search_engine()  # Warm up the cache
