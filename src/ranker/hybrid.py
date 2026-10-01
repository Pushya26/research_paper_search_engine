from .bm25 import BM25
from src.index.inverted_index import InvertedIndex

class HybridRanker:
    def __init__(self, alpha: float = 0.7, beta: float = 0.3, k1: float = 1.5, b: float = 0.75):
        self.alpha = alpha
        self.beta = beta
        self.bm25 = BM25(k1, b)
    
    def rank(self, index: InvertedIndex, query_terms: list[str], pagerank_scores: dict[str, float]) -> list[dict]:
        # Get candidate documents
        candidates = set()
        for term in query_terms:
            for posting in index.get_postings(term):
                candidates.add(posting.doc_id)
        
        if not candidates:
            return []
        
        # Compute BM25 scores
        bm25_scores = {}
        for doc_id in candidates:
            bm25_scores[doc_id] = self.bm25.score(index, query_terms, doc_id)
        
        # Normalize scores
        bm25_values = list(bm25_scores.values())
        bm25_min, bm25_max = min(bm25_values), max(bm25_values)
        bm25_range = bm25_max - bm25_min if bm25_max > bm25_min else 1.0
        
        pr_values = [pagerank_scores.get(doc_id, 0.0) for doc_id in candidates]
        pr_min, pr_max = min(pr_values), max(pr_values)
        pr_range = pr_max - pr_min if pr_max > pr_min else 1.0
        
        # Compute hybrid scores
        results = []
        for doc_id in candidates:
            bm25_norm = (bm25_scores[doc_id] - bm25_min) / bm25_range
            pr_norm = (pagerank_scores.get(doc_id, 0.0) - pr_min) / pr_range
            
            hybrid_score = self.alpha * bm25_norm + self.beta * pr_norm
            
            results.append({
                "doc_id": doc_id,
                "score": hybrid_score,
                "bm25_score": bm25_scores[doc_id],
                "pagerank_score": pagerank_scores.get(doc_id, 0.0)
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    
    def rank_candidates(self, index: InvertedIndex, query_terms: list[str],
                        candidate_doc_ids: set[str], pagerank_scores: dict[str, float]) -> list[dict]:
        """Rank pre-filtered candidate documents (from boolean query evaluation).
        
        Same BM25 + PageRank hybrid scoring as rank(), but operates on an
        externally-provided candidate set instead of discovering candidates
        by scanning posting lists.
        """
        if not candidate_doc_ids or not query_terms:
            return []
        
        # Compute BM25 scores for candidates only
        bm25_scores = {}
        for doc_id in candidate_doc_ids:
            bm25_scores[doc_id] = self.bm25.score(index, query_terms, doc_id)
        
        # Normalize scores
        bm25_values = list(bm25_scores.values())
        bm25_min, bm25_max = min(bm25_values), max(bm25_values)
        bm25_range = bm25_max - bm25_min if bm25_max > bm25_min else 1.0
        
        pr_values = [pagerank_scores.get(doc_id, 0.0) for doc_id in candidate_doc_ids]
        pr_min, pr_max = min(pr_values), max(pr_values)
        pr_range = pr_max - pr_min if pr_max > pr_min else 1.0
        
        # Compute hybrid scores
        results = []
        for doc_id in candidate_doc_ids:
            bm25_norm = (bm25_scores[doc_id] - bm25_min) / bm25_range
            pr_norm = (pagerank_scores.get(doc_id, 0.0) - pr_min) / pr_range
            
            hybrid_score = self.alpha * bm25_norm + self.beta * pr_norm
            
            results.append({
                "doc_id": doc_id,
                "score": hybrid_score,
                "bm25_score": bm25_scores[doc_id],
                "pagerank_score": pagerank_scores.get(doc_id, 0.0)
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
