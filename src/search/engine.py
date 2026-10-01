import orjson
from pathlib import Path
from src.tokenizer.tokenizer import Tokenizer
from src.index.inverted_index import InvertedIndex
from src.ranker.hybrid import HybridRanker
from src.query_compiler.parser import compile_query
from src.query_compiler.evaluator import evaluate, extract_terms, has_boolean_operators

class SearchEngine:
    def __init__(self, data_dir: Path, alpha: float = 0.7, beta: float = 0.3):
        self.data_dir = data_dir
        self.tokenizer = Tokenizer(use_stemming=True)
        self.index = InvertedIndex.load(data_dir / "index")
        
        pr_path = data_dir / "pagerank" / "scores.json"
        self.pagerank_scores = orjson.loads(pr_path.read_bytes()) if pr_path.exists() else {}
        
        self.ranker = HybridRanker(alpha=alpha, beta=beta)
        self.papers_dir = data_dir / "papers"
    
    def search(self, query: str, page: int = 1, size: int = 10) -> dict:
        import time
        start = time.time()
        
        # Boolean query path: parse → evaluate AST → rank filtered candidates
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
                if not query_terms:
                    return {
                        "query": query,
                        "total_hits": 0,
                        "page": page,
                        "size": size,
                        "total_pages": 0,
                        "results": [],
                        "took_ms": int((time.time() - start) * 1000)
                    }
                ranked_results = self.ranker.rank(self.index, query_terms, self.pagerank_scores)
        else:
            # Plain search path
            query_terms = self.tokenizer.tokenize(query)
            
            if not query_terms:
                return {
                    "query": query,
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
            paper_path = self.papers_dir / f"{result['doc_id']}.json"
            if paper_path.exists():
                paper = orjson.loads(paper_path.read_bytes())
                enriched_results.append({
                    "doc_id": result["doc_id"],
                    "title": paper["title"],
                    "abstract": paper["abstract"],
                    "authors": paper["authors"],
                    "score": round(result["score"], 4),
                    "bm25_score": round(result["bm25_score"], 4),
                    "pagerank_score": round(result["pagerank_score"], 6),
                    "pdf_url": paper["pdf_url"]
                })
        
        return {
            "query": query,
            "total_hits": total_hits,
            "page": page,
            "size": size,
            "total_pages": total_pages,
            "results": enriched_results,
            "took_ms": int((time.time() - start) * 1000)
        }
