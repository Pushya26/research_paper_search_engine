"""
Tests for the query compiler evaluator.

Verifies that boolean ASTs are correctly evaluated against the inverted index:
AND → intersection, OR → union, NOT → complement, TERM → posting lookup.
"""
import pytest
from src.query_compiler.parser import compile_query
from src.query_compiler.evaluator import evaluate, extract_terms, has_boolean_operators
from src.index.inverted_index import InvertedIndex


@pytest.fixture
def test_index():
    """Build a small in-memory index for evaluator tests."""
    idx = InvertedIndex()
    # doc1: "neural network deep learning"
    idx.add_document("doc1", ["neural", "network", "deep", "learning"])
    # doc2: "neural network survey"
    idx.add_document("doc2", ["neural", "network", "survey"])
    # doc3: "deep learning transformer"
    idx.add_document("doc3", ["deep", "learning", "transformer"])
    # doc4: "transformer attention mechanism"
    idx.add_document("doc4", ["transformer", "attention", "mechanism"])
    idx.finalize()
    return idx


class TestEvaluator:
    """Test AST evaluation against the inverted index."""

    def test_term_evaluation(self, test_index):
        """Single term returns correct doc_ids from posting list."""
        ast = compile_query("neural")
        result = evaluate(ast, test_index)
        assert result == {"doc1", "doc2"}

    def test_and_evaluation(self, test_index):
        """AND intersects posting lists."""
        ast = compile_query("neural AND deep")
        result = evaluate(ast, test_index)
        assert result == {"doc1"}

    def test_or_evaluation(self, test_index):
        """OR unions posting lists."""
        ast = compile_query("neural OR transformer")
        result = evaluate(ast, test_index)
        assert result == {"doc1", "doc2", "doc3", "doc4"}

    def test_not_evaluation(self, test_index):
        """NOT subtracts from document universe."""
        ast = compile_query("neural NOT survey")
        result = evaluate(ast, test_index)
        # neural → {doc1, doc2}, NOT survey → all - {doc2} = {doc1, doc3, doc4}
        # AND → {doc1}
        assert result == {"doc1"}

    def test_complex_nested_evaluation(self, test_index):
        """Complex nested boolean query evaluates correctly."""
        ast = compile_query("(neural OR transformer) AND deep")
        result = evaluate(ast, test_index)
        # (neural OR transformer) → {doc1, doc2, doc3, doc4}
        # deep → {doc1, doc3}
        # AND → {doc1, doc3}
        assert result == {"doc1", "doc3"}

    def test_no_match(self, test_index):
        """Non-existent term returns empty set."""
        ast = compile_query("nonexistent")
        result = evaluate(ast, test_index)
        assert result == set()

    def test_phrase_evaluation(self, test_index):
        """Phrase intersects constituent terms' posting lists."""
        ast = compile_query('"neural network"')
        result = evaluate(ast, test_index)
        # intersect(neural, network) → {doc1, doc2}
        assert result == {"doc1", "doc2"}


class TestExtractTerms:
    """Test term extraction from AST for BM25 scoring."""

    def test_extract_single_term(self):
        """Single term is extracted."""
        ast = compile_query("neural")
        assert extract_terms(ast) == ["neural"]

    def test_extract_and_terms(self):
        """Both sides of AND are extracted."""
        ast = compile_query("neural AND network")
        terms = extract_terms(ast)
        assert "neural" in terms
        assert "network" in terms

    def test_extract_excludes_not_subtree(self):
        """NOT subtrees should not contribute scoring terms."""
        ast = compile_query("neural NOT survey")
        terms = extract_terms(ast)
        assert "neural" in terms
        assert "survey" not in terms


class TestHasBooleanOperators:
    """Test boolean operator detection in query strings."""

    def test_plain_query(self):
        """Plain query has no boolean operators."""
        assert not has_boolean_operators("neural network")

    def test_and_detected(self):
        assert has_boolean_operators("neural AND network")

    def test_or_detected(self):
        assert has_boolean_operators("neural OR network")

    def test_not_detected(self):
        assert has_boolean_operators("neural NOT survey")

    def test_lowercase_not_detected(self):
        """Only uppercase operators are detected (lowercase treated as search terms)."""
        assert not has_boolean_operators("neural and network")
