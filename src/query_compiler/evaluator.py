"""
AST evaluator for boolean queries.
Evaluates parsed query AST against the inverted index to produce
a set of matching document IDs.

Phase 3 of query compiler pipeline: Lexer → Parser → Evaluator.

Boolean semantics:
    AND  → intersection of posting lists
    OR   → union of posting lists
    NOT  → complement (all docs minus child matches)
    TERM → doc_ids from that term's posting list
"""
from src.query_compiler.parser import ASTNode, TermNode, PhraseNode, BinaryNode, NotNode


def evaluate(ast_node: ASTNode, index, tokenizer=None) -> set[str]:
    """
    Evaluate an AST node against the inverted index, returning matching doc_ids.

    Args:
        ast_node: Parsed AST from compile_query().
        index: InvertedIndex with get_postings() and doc_lengths.
        tokenizer: Optional Tokenizer for term normalization (stemming, lowering).
                   Pass this when evaluating against an index built with stemmed tokens.
    """
    if isinstance(ast_node, TermNode):
        term = ast_node.term
        if tokenizer:
            normalized = tokenizer.tokenize(term)
            if not normalized:
                return set()  # stopword or empty after normalization
            term = normalized[0]
        return {p.doc_id for p in index.get_postings(term)}

    elif isinstance(ast_node, PhraseNode):
        # Tokenize phrase into individual terms, intersect their posting lists.
        # (Simplified phrase matching — full positional matching would require
        # positional indexes, which this index does not store.)
        phrase = ast_node.phrase
        if tokenizer:
            terms = tokenizer.tokenize(phrase)
        else:
            terms = phrase.lower().split()

        if not terms:
            return set()

        result = {p.doc_id for p in index.get_postings(terms[0])}
        for t in terms[1:]:
            result &= {p.doc_id for p in index.get_postings(t)}
        return result

    elif isinstance(ast_node, BinaryNode):
        left_docs = evaluate(ast_node.left, index, tokenizer)
        right_docs = evaluate(ast_node.right, index, tokenizer)

        if ast_node.op == "AND":
            return left_docs & right_docs
        elif ast_node.op == "OR":
            return left_docs | right_docs
        else:
            raise ValueError(f"Unknown binary operator: {ast_node.op}")

    elif isinstance(ast_node, NotNode):
        all_docs = set(index.doc_lengths.keys())
        child_docs = evaluate(ast_node.child, index, tokenizer)
        return all_docs - child_docs

    return set()


def extract_terms(ast_node: ASTNode) -> list[str]:
    """
    Extract all positive search terms from an AST (for BM25 scoring).

    Returns raw terms from the AST, excluding NOT subtrees.
    NOT terms are exclusions and should not boost relevance scores.
    """
    if isinstance(ast_node, TermNode):
        return [ast_node.term]

    elif isinstance(ast_node, PhraseNode):
        return ast_node.phrase.lower().split()

    elif isinstance(ast_node, BinaryNode):
        return extract_terms(ast_node.left) + extract_terms(ast_node.right)

    elif isinstance(ast_node, NotNode):
        # Don't include NOT terms in scoring — they're exclusions
        return []

    return []


def has_boolean_operators(query: str) -> bool:
    """
    Check if a query string contains explicit boolean operators (AND, OR, NOT).

    Only uppercase operators are detected, matching the lexer's convention
    that lowercase 'and', 'or', 'not' are treated as search terms.
    """
    tokens = query.split()
    operators = {"AND", "OR", "NOT"}
    return any(t in operators for t in tokens)
