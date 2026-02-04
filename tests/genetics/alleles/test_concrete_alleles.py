"""
Black-box tests for concrete allele types.

Tests validate domain validation, clamping behavior, and type-specific semantics
for FloatAllele, IntAllele, LogFloatAllele, BoolAllele, and StringAllele.

Focus on type-specific behavior only - AbstractAllele behavior is tested separately.
"""

import pytest
from src.clan_tune.genetics.alleles import (
    AbstractAllele,
    FloatAllele,
    IntAllele,
    LogFloatAllele,
    BoolAllele,
    StringAllele,
)


class TestFloatAlleleDomainNormalization:
    """Test suite for FloatAllele domain normalization."""

    def test_domain_normalized_when_none(self):
        """Domain defaults to fully unbounded when not provided."""
        allele = FloatAllele(5.0)
        assert allele.domain == {"min": None, "max": None}

    def test_domain_normalized_with_partial_min(self):
        """Domain normalized when only min provided."""
        allele = FloatAllele(5.0, domain={"min": 0.0})
        assert allele.domain == {"min": 0.0, "max": None}

    def test_domain_normalized_with_partial_max(self):
        """Domain normalized when only max provided."""
        allele = FloatAllele(5.0, domain={"max": 10.0})
        assert allele.domain == {"min": None, "max": 10.0}

    def test_domain_normalized_with_both(self):
        """Domain normalized when both min and max provided."""
        allele = FloatAllele(5.0, domain={"min": 0.0, "max": 10.0})
        assert allele.domain == {"min": 0.0, "max": 10.0}


class TestFloatAlleleClamping:
    """Test suite for FloatAllele value clamping."""

    def test_value_clamped_to_min(self):
        """Value below min is clamped to min."""
        allele = FloatAllele(-5.0, domain={"min": 0.0, "max": 10.0})
        assert allele.value == 0.0

    def test_value_clamped_to_max(self):
        """Value above max is clamped to max."""
        allele = FloatAllele(15.0, domain={"min": 0.0, "max": 10.0})
        assert allele.value == 10.0

    def test_value_within_bounds_unchanged(self):
        """Value within bounds is not clamped."""
        allele = FloatAllele(5.0, domain={"min": 0.0, "max": 10.0})
        assert allele.value == 5.0

    def test_value_not_clamped_when_min_none(self):
        """Value below min not clamped when min is None."""
        allele = FloatAllele(-100.0, domain={"min": None, "max": 10.0})
        assert allele.value == -100.0

    def test_value_not_clamped_when_max_none(self):
        """Value above max not clamped when max is None."""
        allele = FloatAllele(100.0, domain={"min": 0.0, "max": None})
        assert allele.value == 100.0

    def test_with_value_applies_clamping(self):
        """with_value applies clamping to new value."""
        allele = FloatAllele(5.0, domain={"min": 0.0, "max": 10.0})
        new_allele = allele.with_value(15.0)
        assert new_allele.value == 10.0


class TestFloatAlleleTypeNarrowing:
    """Test suite for FloatAllele type narrowing."""

    def test_value_property_returns_float(self):
        """value property returns float type."""
        allele = FloatAllele(5.0)
        assert isinstance(allele.value, float)


class TestFloatAlleleSerialization:
    """Test suite for FloatAllele serialization."""

    def test_round_trip_preserves_domain(self):
        """Serialize then deserialize preserves domain."""
        original = FloatAllele(5.0, domain={"min": 0.0, "max": 10.0})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.domain == {"min": 0.0, "max": 10.0}

    def test_round_trip_preserves_unbounded_domain(self):
        """Serialize then deserialize preserves unbounded domain."""
        original = FloatAllele(5.0, domain={"min": None, "max": None})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.domain == {"min": None, "max": None}


class TestIntAlleleDomainNormalization:
    """Test suite for IntAllele domain normalization."""

    def test_domain_normalized_when_none(self):
        """Domain defaults to fully unbounded when not provided."""
        allele = IntAllele(5)
        assert allele.domain == {"min": None, "max": None}

    def test_domain_normalized_with_partial_min(self):
        """Domain normalized when only min provided."""
        allele = IntAllele(5, domain={"min": 0})
        assert allele.domain == {"min": 0, "max": None}

    def test_domain_normalized_with_partial_max(self):
        """Domain normalized when only max provided."""
        allele = IntAllele(5, domain={"max": 10})
        assert allele.domain == {"min": None, "max": 10}


class TestIntAlleleFloatBacking:
    """Test suite for IntAllele float backing behavior."""

    def test_accepts_float_value(self):
        """Constructor accepts float value."""
        allele = IntAllele(3.7)
        assert allele.raw_value == 3.7

    def test_accepts_int_value(self):
        """Constructor accepts int value."""
        allele = IntAllele(3)
        assert allele.raw_value == 3.0

    def test_value_returns_rounded_int(self):
        """value property returns rounded integer."""
        allele = IntAllele(3.7)
        assert allele.value == 4
        assert isinstance(allele.value, int)

    def test_raw_value_returns_float(self):
        """raw_value property returns stored float."""
        allele = IntAllele(3.7)
        assert allele.raw_value == 3.7
        assert isinstance(allele.raw_value, float)

    def test_value_rounds_negative_floats(self):
        """value property rounds negative floats correctly."""
        allele = IntAllele(-3.7)
        assert allele.value == -4

    def test_value_rounds_half_away_from_zero(self):
        """value property uses round() semantics."""
        allele = IntAllele(2.5)
        assert allele.value == 2  # Python's round() rounds to even


class TestIntAlleleClamping:
    """Test suite for IntAllele clamping behavior."""

    def test_float_clamped_to_min(self):
        """Float value below min is clamped."""
        allele = IntAllele(-5.5, domain={"min": 0, "max": 10})
        assert allele.raw_value == 0.0

    def test_float_clamped_to_max(self):
        """Float value above max is clamped."""
        allele = IntAllele(15.5, domain={"min": 0, "max": 10})
        assert allele.raw_value == 10.0

    def test_clamping_preserves_float_precision(self):
        """Clamping happens to float, preserving precision within bounds."""
        allele = IntAllele(5.7, domain={"min": 0, "max": 10})
        assert allele.raw_value == 5.7
        assert allele.value == 6


class TestIntAlleleWithValue:
    """Test suite for IntAllele with_value method."""

    def test_with_value_accepts_float(self):
        """with_value accepts float value."""
        allele = IntAllele(3)
        new_allele = allele.with_value(4.7)
        assert new_allele.raw_value == 4.7
        assert new_allele.value == 5

    def test_with_value_accepts_int(self):
        """with_value accepts int value."""
        allele = IntAllele(3.7)
        new_allele = allele.with_value(5)
        assert new_allele.raw_value == 5.0
        assert new_allele.value == 5

    def test_with_value_applies_clamping(self):
        """with_value applies clamping to new float value."""
        allele = IntAllele(3, domain={"min": 0, "max": 10})
        new_allele = allele.with_value(15.5)
        assert new_allele.raw_value == 10.0


class TestIntAlleleSerialization:
    """Test suite for IntAllele serialization."""

    def test_round_trip_preserves_raw_value(self):
        """Serialize then deserialize preserves raw float value."""
        original = IntAllele(3.7)
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.raw_value == 3.7
        assert restored.value == 4

    def test_round_trip_preserves_domain(self):
        """Serialize then deserialize preserves domain."""
        original = IntAllele(5, domain={"min": 0, "max": 10})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.domain == {"min": 0, "max": 10}


class TestLogFloatAlleleDomainValidation:
    """Test suite for LogFloatAllele domain validation."""

    def test_raises_on_missing_min(self):
        """Raises ValueError when domain min is None."""
        with pytest.raises(ValueError) as exc_info:
            LogFloatAllele(0.01, domain={"min": None, "max": 1.0})
        assert "min" in str(exc_info.value).lower()

    def test_raises_on_missing_min_in_default_domain(self):
        """Raises ValueError when domain not provided (min would be None)."""
        with pytest.raises(ValueError) as exc_info:
            LogFloatAllele(0.01)
        assert "min" in str(exc_info.value).lower()

    def test_raises_on_min_zero(self):
        """Raises ValueError when domain min is zero."""
        with pytest.raises(ValueError) as exc_info:
            LogFloatAllele(0.01, domain={"min": 0.0, "max": 1.0})
        assert "0" in str(exc_info.value).lower()

    def test_raises_on_min_negative(self):
        """Raises ValueError when domain min is negative."""
        with pytest.raises(ValueError) as exc_info:
            LogFloatAllele(0.01, domain={"min": -0.1, "max": 1.0})
        assert "0" in str(exc_info.value).lower()

    def test_accepts_positive_min(self):
        """Accepts domain with positive min."""
        allele = LogFloatAllele(0.01, domain={"min": 1e-6, "max": 1.0})
        assert allele.value == 0.01


class TestLogFloatAlleleClamping:
    """Test suite for LogFloatAllele clamping behavior."""

    def test_value_clamped_to_min(self):
        """Value below min is clamped to min."""
        allele = LogFloatAllele(1e-10, domain={"min": 1e-6, "max": 1e-2})
        assert allele.value == 1e-6

    def test_value_clamped_to_max(self):
        """Value above max is clamped to max."""
        allele = LogFloatAllele(1.0, domain={"min": 1e-6, "max": 1e-2})
        assert allele.value == 1e-2

    def test_value_within_bounds_unchanged(self):
        """Value within bounds is not clamped."""
        allele = LogFloatAllele(1e-4, domain={"min": 1e-6, "max": 1e-2})
        assert allele.value == 1e-4

    def test_value_not_clamped_when_max_none(self):
        """Value above max not clamped when max is None."""
        allele = LogFloatAllele(100.0, domain={"min": 1e-6, "max": None})
        assert allele.value == 100.0


class TestLogFloatAlleleTypeNarrowing:
    """Test suite for LogFloatAllele type narrowing."""

    def test_value_property_returns_float(self):
        """value property returns float type."""
        allele = LogFloatAllele(0.01, domain={"min": 1e-6, "max": 1.0})
        assert isinstance(allele.value, float)


class TestLogFloatAlleleSerialization:
    """Test suite for LogFloatAllele serialization."""

    def test_round_trip_preserves_domain(self):
        """Serialize then deserialize preserves domain."""
        original = LogFloatAllele(0.01, domain={"min": 1e-6, "max": 1e-2})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.domain == {"min": 1e-6, "max": 1e-2}


class TestBoolAlleleDomain:
    """Test suite for BoolAllele domain behavior."""

    def test_domain_is_true_false_set(self):
        """Domain is always {True, False}."""
        allele = BoolAllele(True)
        assert allele.domain == {True, False}

    def test_domain_property_returns_copy(self):
        """Domain property returns copy for safety."""
        allele = BoolAllele(True)
        domain_copy = allele.domain
        domain_copy.add("invalid")
        assert allele.domain == {True, False}


class TestBoolAlleleValidation:
    """Test suite for BoolAllele value validation."""

    def test_accepts_true(self):
        """Constructor accepts True."""
        allele = BoolAllele(True)
        assert allele.value is True

    def test_accepts_false(self):
        """Constructor accepts False."""
        allele = BoolAllele(False)
        assert allele.value is False

    def test_raises_on_non_boolean(self):
        """Raises ValueError on non-boolean value."""
        with pytest.raises(ValueError) as exc_info:
            BoolAllele("not a bool")
        assert "domain" in str(exc_info.value).lower()

    def test_accepts_integer_zero_as_false(self):
        """Accepts integer 0 (equivalent to False in Python)."""
        allele = BoolAllele(0)
        assert allele.value == False
        assert allele.value == 0

    def test_accepts_integer_one_as_true(self):
        """Accepts integer 1 (equivalent to True in Python)."""
        allele = BoolAllele(1)
        assert allele.value == True
        assert allele.value == 1


class TestBoolAlleleTypeNarrowing:
    """Test suite for BoolAllele type narrowing."""

    def test_value_property_returns_bool(self):
        """value property returns bool type."""
        allele = BoolAllele(True)
        assert isinstance(allele.value, bool)


class TestBoolAlleleSerialization:
    """Test suite for BoolAllele serialization."""

    def test_round_trip_preserves_true(self):
        """Serialize then deserialize preserves True value."""
        original = BoolAllele(True)
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.value is True

    def test_round_trip_preserves_false(self):
        """Serialize then deserialize preserves False value."""
        original = BoolAllele(False)
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.value is False

    def test_serialization_does_not_include_domain(self):
        """Serialization does not include domain (always same)."""
        allele = BoolAllele(True)
        serialized = allele.serialize_subclass()
        assert "domain" not in serialized


class TestStringAlleleDomainValidation:
    """Test suite for StringAllele domain validation."""

    def test_raises_on_missing_domain(self):
        """Raises ValueError when domain not provided."""
        with pytest.raises(ValueError) as exc_info:
            StringAllele("adam")
        assert "domain" in str(exc_info.value).lower()

    def test_accepts_domain_set(self):
        """Constructor accepts domain as set."""
        allele = StringAllele("adam", domain={"adam", "sgd", "rmsprop"})
        assert allele.value == "adam"

    def test_domain_property_returns_copy(self):
        """Domain property returns copy for safety."""
        allele = StringAllele("adam", domain={"adam", "sgd"})
        domain_copy = allele.domain
        domain_copy.add("new")
        assert "new" not in allele.domain


class TestStringAlleleValueValidation:
    """Test suite for StringAllele value validation."""

    def test_accepts_value_in_domain(self):
        """Constructor accepts value in domain."""
        allele = StringAllele("sgd", domain={"adam", "sgd", "rmsprop"})
        assert allele.value == "sgd"

    def test_raises_on_value_not_in_domain(self):
        """Raises ValueError when value not in domain."""
        with pytest.raises(ValueError) as exc_info:
            StringAllele("invalid", domain={"adam", "sgd", "rmsprop"})
        assert "domain" in str(exc_info.value).lower()
        assert "invalid" in str(exc_info.value)


class TestStringAlleleTypeNarrowing:
    """Test suite for StringAllele type narrowing."""

    def test_value_property_returns_str(self):
        """value property returns str type."""
        allele = StringAllele("adam", domain={"adam", "sgd"})
        assert isinstance(allele.value, str)


class TestStringAlleleSerialization:
    """Test suite for StringAllele serialization."""

    def test_round_trip_preserves_value(self):
        """Serialize then deserialize preserves value."""
        original = StringAllele("adam", domain={"adam", "sgd", "rmsprop"})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.value == "adam"

    def test_round_trip_preserves_domain(self):
        """Serialize then deserialize preserves domain set."""
        original = StringAllele("adam", domain={"adam", "sgd", "rmsprop"})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.domain == {"adam", "sgd", "rmsprop"}

    def test_serialization_converts_set_to_list(self):
        """Serialization converts domain set to list for JSON compatibility."""
        allele = StringAllele("adam", domain={"adam", "sgd"})
        serialized = allele.serialize_subclass()
        assert isinstance(serialized["domain"], list)
        assert set(serialized["domain"]) == {"adam", "sgd"}
