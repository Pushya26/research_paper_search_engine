"""Boolean query compiler: lexer → parser → AST → evaluator."""
from .parser import compile_query
from .evaluator import evaluate, extract_terms, has_boolean_operators

__all__ = ["compile_query", "evaluate", "extract_terms", "has_boolean_operators"]
