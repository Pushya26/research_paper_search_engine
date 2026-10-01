import orjson
from pathlib import Path
from functools import lru_cache
from src.tokenizer.tokenizer import Tokenizer
from src.index.inverted_index import InvertedIndex
from src.ranker.hybrid import HybridRanker
from src.search.query_expansion import QueryExpander
from src.query_compiler.parser import compile_query
from src.query_compiler.evaluator import evaluate, extract_terms, has_boolean_operators

class EnhancedSearchEngine:
    def __init__(self, data_dir: Path, alpha: float = 0.7, beta: float = 0.3, use_query_expansion: bool = True):
        self.data_dir = data_dir
        self.tokenizer = Tokenizer(use_stemming=True)
        self.index = InvertedIndex.load(data_dir / "index")
        
        pr_path = data_dir / "pagerank" / "scores.json"
        self.pagerank_scores = orjson.loads(pr_path.read_bytes()) if pr_path.exists() else {}
        
        self.ranker = HybridRanker(alpha=alpha, beta=beta)
        self.papers_dir = data_dir / "papers"
        
        # Query expansion
        self.use_query_expansion = use_query_expansion
        if use_query_expansion:
            self.query_expander = QueryExpander(max_synonyms_per_term=2)
        
        # Cache for paper data
        self._paper_cache = {}
    
    @lru_cache(maxsize=1000)
    def search(self, query: str, page: int = 1, size: int = 10, expand_query: bool = None) -> dict:
        """Search with optional query expansion and result caching."""
        import time
        start = time.time()
        
        # Use instance setting if not specified
        if expand_query is None:
            expand_query = self.use_query_expansion
        
        # Boolean query path: parse → evaluate AST → rank filtered candidates
        # Boolean queries skip expansion (operators would be mangled)
        if has_boolean_operators(query):
            try:
                ast = compile_query(query)
                candidate_ids = evaluate(ast, self.index, self.tokenizer)
                raw_terms = extract_terms(ast)
                query_terms = []
                for t in raw_terms:
                    query_terms.extend(self.tokenizer.tokenize(t))
                
                if not query_terms or not candidate_ids:
                    return {
                        "query": query,
                        "expanded_query": None,
                        "total_hits": 0,
                        "page": page,
                        "size": size,
                        "total_pages": 0,
                        "results": [],
                        "took_ms": int((time.time() - start) * 1000)
                    }
                
                ranked_results = self.ranker.rank_candidates(
                    self.index, query_terms, candidate_ids, self.pagerank_scores
                )
            except SyntaxError:
                # Fall back to plain search on parse error
                query_terms = self.tokenizer.tokenize(query)
                if expand_query and self.use_query_expansion:
                    query_terms = self.query_expander.expand(query_terms)
                if not query_terms:
                    return {
                        "query": query,
                        "expanded_query": None,
                        "total_hits": 0,
                        "page": page,
                        "size": size,
                        "total_pages": 0,
                        "results": [],
                        "took_ms": int((time.time() - start) * 1000)
                    }
                ranked_results = self.ranker.rank(self.index, query_terms, self.pagerank_scores)
        else:
            # Plain search path with optional query expansion
            query_terms = self.tokenizer.tokenize(query)
            
            # Expand query if enabled
            if expand_query and self.use_query_expansion:
                expanded_terms = self.query_expander.expand(query_terms)
                query_terms = expanded_terms
            
            if not query_terms:
                return {
                    "query": query,
                    "expanded_query": None,
                    "total_hits": 0,
                    "page": page,
                    "size": size,
                    "total_pages": 0,
                    "results": [],
                    "took_ms": int((time.time() - start) * 1000)
                }
            
            ranked_results = self.ranker.rank(self.index, query_terms, self.pagerank_scores)
        
        total_hits = len(ranked_results)
        total_pages = (total_hits + size - 1) // size
        
        offset = (page - 1) * size
        page_results = ranked_results[offset:offset + size]
        
        enriched_results = []
        for result in page_results:
            paper = self._get_paper(result['doc_id'])
            if paper:
                enriched_results.append({
                    "doc_id": result["doc_id"],
                    "title": paper["title"],
                    "abstract": paper["abstract"],
                    "authors": paper["authors"],
                    "categories": paper["categories"],
                    "published": paper["published"],
                    "score": round(result["score"], 4),
                    "bm25_score": round(result["bm25_score"], 4),
                    "pagerank_score": round(result["pagerank_score"], 6),
                    "pdf_url": paper["pdf_url"]
                })
        
        return {
            "query": query,
            "expanded_query": query_terms if expand_query else None,
            "total_hits": total_hits,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "results": enriched_results,
            "took_ms": int((time.time() - start) * 1000)
        }
    
    def _get_paper(self, doc_id: str) -> dict:
        """Get paper with caching."""
        if doc_id in self._paper_cache:
            return self._paper_cache[doc_id]
        
        paper_path = self.papers_dir / f"{doc_id}.json"
        if paper_path.exists():
            paper = orjson.loads(paper_path.read_bytes())
            self._paper_cache[doc_id] = paper
            return paper
        return None
    
    def get_similar_papers(self, doc_id: str, top_k: int = 5) -> list[dict]:
        """Find similar papers based on shared categories and terms."""
        paper = self._get_paper(doc_id)
        if not paper:
            return []
        
        # Use paper title and abstract as query
        query = f"{paper['title']} {paper['abstract'][:200]}"
        results = self.search(query, page=1, size=top_k + 1, expand_query=False)
        
        # Filter out the query paper itself
        similar = [r for r in results['results'] if r['doc_id'] != doc_id]
        return similar[:top_k]
