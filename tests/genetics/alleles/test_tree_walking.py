"""
Black-box tests for allele tree walking utilities.

Tests validate tree walking and synthesis behavior through observable contracts
without coupling to implementation details.
"""

import pytest
from src.clan_tune.genetics.alleles import (
    AbstractAllele,
    FloatAllele,
    IntAllele,
    walk_allele_trees,
    synthesize_allele_trees,
)


class TestWalkAlleleTreesBasics:
    """Test suite for walk_allele_trees basic behavior."""

    def test_walks_single_leaf_node(self):
        """Handler called once for single leaf node."""
        allele = FloatAllele(5.0)
        results = []

        def handler(nodes):
            results.append(nodes[0].value)
            return nodes[0].value

        collected = list(walk_allele_trees([allele], handler))

        assert results == [5.0]
        assert collected == [5.0]

    def test_walks_tree_children_first(self):
        """Children processed before parent (children-first order)."""
        child = FloatAllele(10.0)
        parent = FloatAllele(5.0, metadata={"child": child})

        order = []

        def handler(nodes):
            order.append(nodes[0].value)
            return nodes[0].value

        list(walk_allele_trees([parent], handler))

        assert order == [10.0, 5.0]  # Child first, then parent

    def test_walks_multiple_metadata_children(self):
        """All metadata children are walked before parent."""
        child1 = FloatAllele(1.0)
        child2 = FloatAllele(2.0)
        parent = FloatAllele(5.0, metadata={"a": child1, "b": child2})

        values = []

        def handler(nodes):
            values.append(nodes[0].value)
            return nodes[0].value

        list(walk_allele_trees([parent], handler))

        # Children walked first (sorted keys: "a", "b"), then parent
        assert values == [1.0, 2.0, 5.0]

    def test_walks_deeply_nested_tree(self):
        """Walks deeply nested trees correctly."""
        level3 = FloatAllele(3.0)
        level2 = FloatAllele(2.0, metadata={"child": level3})
        level1 = FloatAllele(1.0, metadata={"child": level2})

        values = []

        def handler(nodes):
            values.append(nodes[0].value)
            return nodes[0].value

        list(walk_allele_trees([level1], handler))

        # Deepest first, then up
        assert values == [3.0, 2.0, 1.0]


class TestWalkAlleleTreesParallelWalking:
    """Test suite for parallel walking of multiple trees."""

    def test_walks_two_trees_in_parallel(self):
        """Handler receives list with both alleles at each node."""
        tree1 = FloatAllele(1.0)
        tree2 = FloatAllele(2.0)

        def handler(nodes):
            assert len(nodes) == 2
            return (nodes[0].value, nodes[1].value)

        results = list(walk_allele_trees([tree1, tree2], handler))

        assert results == [(1.0, 2.0)]

    def test_walks_parallel_trees_with_children(self):
        """Parallel walk processes corresponding nodes together."""
        child1 = FloatAllele(10.0)
        child2 = FloatAllele(20.0)
        tree1 = FloatAllele(1.0, metadata={"child": child1})
        tree2 = FloatAllele(2.0, metadata={"child": child2})

        collected = []

        def handler(nodes):
            collected.append([n.value for n in nodes])
            return None

        list(walk_allele_trees([tree1, tree2], handler))

        # Children first, then parents
        assert collected == [[10.0, 20.0], [1.0, 2.0]]


class TestSynthesizeAlleleTreesBasics:
    """Test suite for synthesize_allele_trees basic behavior."""

    def test_rebuilds_leaf_node_with_new_value(self):
        """Handler value is used to rebuild leaf node."""
        allele = FloatAllele(5.0)

        def handler(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(allele, [allele], handler)

        assert result.value == 10.0

    def test_preserves_allele_type(self):
        """Result is the same type as input allele."""
        allele = FloatAllele(5.0)

        def handler(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(allele, [allele], handler)

        assert isinstance(result, FloatAllele)

    def test_rebuilds_tree_children_first(self):
        """Children rebuilt before parent."""
        child = FloatAllele(10.0)
        parent = FloatAllele(5.0, metadata={"child": child})

        def handler(template, sources):
            # Double all values
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(parent, [parent], handler)

        # Parent value doubled
        assert result.value == 10.0
        # Child value doubled in metadata
        assert result.metadata["child"].value == 20.0

    def test_rebuilds_deeply_nested_tree(self):
        """Rebuilds deeply nested trees correctly."""
        level3 = FloatAllele(3.0)
        level2 = FloatAllele(2.0, metadata={"child": level3})
        level1 = FloatAllele(1.0, metadata={"child": level2})

        def handler(template, sources):
            return template.with_value(sources[0].value + 100)

        result = synthesize_allele_trees(level1, [level1], handler)

        assert result.value == 101.0
        assert result.metadata["child"].value == 102.0
        assert result.metadata["child"].metadata["child"].value == 103.0


class TestSynthesizeAlleleTreesMetadataFlattening:
    """Test suite for metadata flattening in synthesize."""

    def test_handler_receives_flattened_metadata(self):
        """Handler receives alleles with flattened metadata."""
        child = FloatAllele(10.0)
        parent = FloatAllele(5.0, metadata={"std": child})

        def handler(template, sources):
            if sources[0].value == 5.0:
                # Sources' metadata should be flattened
                assert sources[0].metadata["std"] == 10.0
                assert not isinstance(sources[0].metadata["std"], AbstractAllele)
            return template.with_value(sources[0].value)

        synthesize_allele_trees(parent, [parent], handler)

    def test_result_has_updated_metadata_alleles(self):
        """Result metadata contains updated alleles (not flattened values)."""
        child = FloatAllele(10.0)
        parent = FloatAllele(5.0, metadata={"std": child})

        def handler(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(parent, [parent], handler)

        # Result metadata should contain allele, not flattened value
        assert isinstance(result.metadata["std"], FloatAllele)
        assert result.metadata["std"].value == 20.0


class TestSynthesizeAlleleTreesFiltering:
    """Test suite for filtering behavior in synthesize."""

    def test_filtered_node_preserves_original_value(self):
        """Filtered nodes keep original value but get updated metadata."""
        child = FloatAllele(10.0, can_mutate=True)
        parent = FloatAllele(5.0, can_mutate=False, metadata={"child": child})

        def handler(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(parent, [parent], handler, include_can_mutate=False)

        # Parent value unchanged (filtered out)
        assert result.value == 5.0
        # Child value doubled (not filtered)
        assert result.metadata["child"].value == 20.0

    def test_filtered_by_can_crossbreed(self):
        """Nodes filtered by can_crossbreed keep original value."""
        allele = FloatAllele(5.0, can_crossbreed=False)

        def handler(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(allele, [allele], handler, include_can_crossbreed=False)

        assert result.value == 5.0  # Original value preserved


class TestSynthesizeAlleleTreesParallelSynthesis:
    """Test suite for parallel synthesis from multiple trees."""

    def test_combines_two_trees(self):
        """Handler can combine values from multiple trees."""
        tree1 = FloatAllele(1.0)
        tree2 = FloatAllele(2.0)

        def handler(template, sources):
            # Average the values
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        result = synthesize_allele_trees(tree1, [tree1, tree2], handler)

        assert result.value == 1.5

    def test_result_is_same_type_as_template_tree(self):
        """Result type matches template tree."""
        tree1 = IntAllele(5)
        tree2 = IntAllele(10)

        def handler(template, sources):
            return template.with_value(sum(s.value for s in sources))

        result = synthesize_allele_trees(tree1, [tree1, tree2], handler)

        assert isinstance(result, IntAllele)


class TestSynthesizeAlleleTreesImmutability:
    """Test suite for immutability contracts."""

    def test_does_not_modify_original_tree(self):
        """Original tree is not modified by synthesis."""
        original = FloatAllele(5.0)

        def handler(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(original, [original], handler)

        assert original.value == 5.0
        assert result.value == 10.0

    def test_does_not_modify_original_metadata(self):
        """Original metadata alleles are not modified."""
        child = FloatAllele(10.0)
        original = FloatAllele(5.0, metadata={"child": child})

        def handler(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_allele_trees(original, [original], handler)

        # Original unchanged
        assert original.metadata["child"].value == 10.0
        # Result updated
        assert result.metadata["child"].value == 20.0


class TestInstanceMethodWrappers:
    """Test suite for walk_tree and update_tree instance methods."""

    def test_walk_tree_wraps_walk_allele_trees(self):
        """walk_tree is thin wrapper around walk_allele_trees."""
        allele = FloatAllele(5.0, metadata={"child": FloatAllele(10.0)})

        values = []

        def handler(node):
            values.append(node.value)
            return node.value

        results = list(allele.walk_tree(handler))

        assert values == [10.0, 5.0]  # Children first
        assert results == [10.0, 5.0]

    def test_update_tree_wraps_synthesize_allele_trees(self):
        """update_tree is thin wrapper around synthesize_allele_trees."""
        allele = FloatAllele(5.0, metadata={"child": FloatAllele(10.0)})

        def handler(node):
            return node.with_value(node.value * 2)

        result = allele.update_tree(handler)

        assert result.value == 10.0
        assert result.metadata["child"].value == 20.0

    def test_walk_tree_passes_filter_flags(self):
        """walk_tree passes filtering flags through."""
        allele = FloatAllele(5.0, can_mutate=False)

        visited = []

        def handler(node):
            visited.append(node.value)
            return None

        list(allele.walk_tree(handler, include_can_mutate=False))

        assert visited == []

    def test_update_tree_passes_filter_flags(self):
        """update_tree passes filtering flags through."""
        allele = FloatAllele(5.0, can_mutate=False)

        def handler(node):
            return node.with_value(node.value * 2)

        result = allele.update_tree(handler, include_can_mutate=False)

        assert result.value == 5.0  # Unchanged (filtered)
