"""Public EPM vNext Python interface.

This package is the stable import surface for domain-neutral EPM callers.
FAP-Insurance remains an adapter/host and is not part of the generic contract.
"""
from epm_engine import EPM_ENGINE_VERSION, assess_transition, inspect_state
from epm_envelope import EvidentiaryEnvelope
from epm_state import EvidentiaryState, EvidentiaryStateReport

__all__ = [
    "EPM_ENGINE_VERSION",
    "EvidentiaryEnvelope",
    "EvidentiaryState",
    "EvidentiaryStateReport",
    "assess_transition",
    "inspect_state",
]
