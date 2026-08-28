from dpie_assurance import AssuranceState, Decision, FailureCode
from dpie_composition import evaluate_composition


def test_valid_a_and_valid_b_do_not_imply_valid_composition():
    result = evaluate_composition(left=AssuranceState.PRESERVED, right=AssuranceState.PRESERVED, relation_established=False)
    assert result.failure is FailureCode.COMPOSITION_UNRESOLVED
    assert result.state is AssuranceState.UNKNOWN
    assert result.decision is Decision.QUARANTINE


def test_unknown_irrelevant_to_composition_stays_local():
    result = evaluate_composition(left=AssuranceState.UNKNOWN, right=AssuranceState.PRESERVED, relation_established=True)
    assert result.state is AssuranceState.UNKNOWN
    assert result.decision is Decision.DEFER


def test_explicit_composition_relation_authorizes():
    result = evaluate_composition(left=AssuranceState.PRESERVED, right=AssuranceState.PRESERVED, relation_established=True)
    assert result.failure is FailureCode.NONE
    assert result.state is AssuranceState.PRESERVED
    assert result.decision is Decision.AUTHORIZED
