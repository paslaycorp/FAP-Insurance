"""EPM Assurance Exchange v0.1 cryptographic binding primitives."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

EXCHANGE_VERSION = "0.1"
NONCE_BYTES = 32

class ExchangeError(ValueError): pass
class BindingError(ExchangeError): pass
class ReplayError(ExchangeError): pass
class SignatureError(ExchangeError): pass
class CanonicalizationError(ExchangeError): pass


def _normalize(value: Any) -> Any:
    if isinstance(value, str): return unicodedata.normalize("NFC", value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None: raise CanonicalizationError("timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Mapping): return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [_normalize(v) for v in value]
    if isinstance(value, (set, frozenset)): raise CanonicalizationError("unordered collections are not canonical")
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))): raise CanonicalizationError("non-finite numbers are not canonical")
    if value is None or isinstance(value, (bool, int, float)): return value
    raise CanonicalizationError(f"unsupported canonical value: {type(value).__name__}")


def canonical_bytes(payload: Mapping[str, Any], *, exclude: frozenset[str] = frozenset()) -> bytes:
    if not isinstance(payload, Mapping): raise CanonicalizationError("payload must be a mapping")
    normalized = _normalize({k: v for k, v in payload.items() if k not in exclude})
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest_hex(payload: Mapping[str, Any], *, exclude: frozenset[str] = frozenset()) -> str:
    return hashlib.sha256(canonical_bytes(payload, exclude=exclude)).hexdigest()


def _b64(data: bytes) -> str: return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _unb64(value: str) -> bytes:
    if not isinstance(value, str) or not value: raise SignatureError("signature is missing")
    try: return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc: raise SignatureError("signature encoding is invalid") from exc

def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None: raise ExchangeError("timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class AssuranceRequest:
    request_id: str
    nonce: str
    claim_id: str
    evidence_id: str
    media_hash: str
    timestamp_claimed: datetime
    purpose: str
    scope: str
    jurisdiction: str
    rule_id: str
    rule_version: str
    authority: str
    consequence: str
    requested_at: datetime
    requester_service_id: str
    verification_input_digest: str
    request_digest: str

    @classmethod
    def create(cls, **kwargs: Any) -> "AssuranceRequest":
        request_id = kwargs.pop("request_id", None) or str(uuid.uuid4())
        nonce = kwargs.pop("nonce", None) or _b64(secrets.token_bytes(NONCE_BYTES))
        requested_at = kwargs.pop("requested_at", None) or datetime.now(timezone.utc)
        vid = kwargs.get("verification_input_digest")
        if not isinstance(vid, str) or len(vid) != 64 or any(c not in "0123456789abcdefABCDEF" for c in vid): raise BindingError("verification_input_digest must be a SHA-256 hex digest")
        kwargs["verification_input_digest"] = vid.lower()
        kwargs["timestamp_claimed"] = _utc(kwargs["timestamp_claimed"])
        kwargs["requested_at"] = _utc(requested_at)
        fields = {"exchange_version": EXCHANGE_VERSION, "request_id": request_id, "nonce": nonce, **kwargs}
        return cls(request_digest=digest_hex(fields), **{k: v for k, v in fields.items() if k != "exchange_version"})

    def payload(self) -> dict[str, Any]: return {"exchange_version": EXCHANGE_VERSION, **{k: getattr(self, k) for k in self.__dataclass_fields__}}
    def verify_digest(self) -> None:
        if not secrets.compare_digest(digest_hex(self.payload(), exclude=frozenset({"request_digest"})), self.request_digest): raise BindingError("request digest mismatch")


@dataclass(frozen=True, slots=True)
class AssuranceAttestation:
    request_id: str
    nonce: str
    request_digest: str
    response_digest: str
    evidence_id: str
    artifact_id: str
    engine_id: str
    engine_version: str
    policy_id: str
    policy_version: str
    oracle_versions: tuple[str, ...]
    processed_at: datetime
    result: str
    confidence: float | None
    failure_state: str | None
    responder_service_id: str
    signature: str
    def payload(self) -> dict[str, Any]: return {"exchange_version": EXCHANGE_VERSION, **{k: getattr(self, k) for k in self.__dataclass_fields__}}
    def unsigned_payload(self) -> dict[str, Any]: return {k: v for k, v in self.payload().items() if k not in {"response_digest", "signature"}}
    def verify_response_digest(self) -> None:
        if not secrets.compare_digest(digest_hex(self.unsigned_payload()), self.response_digest): raise BindingError("response digest mismatch")


class AttestationSigner:
    def __init__(self, service_id: str, private_key: Ed25519PrivateKey):
        if not service_id: raise ExchangeError("service identity is required")
        self.service_id, self._private_key = service_id, private_key
    @classmethod
    def generate(cls, service_id: str) -> "AttestationSigner": return cls(service_id, Ed25519PrivateKey.generate())
    @property
    def public_key(self) -> Ed25519PublicKey: return self._private_key.public_key()
    def sign(self, payload: Mapping[str, Any]) -> str: return _b64(self._private_key.sign(canonical_bytes(payload)))


class ReplayGuard:
    def __init__(self, max_entries: int = 100_000):
        if max_entries < 1: raise ValueError("max_entries must be positive")
        self._max_entries, self._seen, self._lock = max_entries, {}, threading.Lock()
    def accept_once(self, responder_service_id: str, nonce: str, request_digest: str) -> None:
        key = (responder_service_id, nonce, request_digest)
        with self._lock:
            if key in self._seen: raise ReplayError("attestation replay detected")
            if len(self._seen) >= self._max_entries: raise ReplayError("replay state capacity exhausted")
            self._seen[key] = None


def build_attestation(request: AssuranceRequest, *, artifact_id: str, engine_id: str, engine_version: str, policy_id: str, policy_version: str, oracle_versions: tuple[str, ...] = (), processed_at: datetime, result: str, confidence: float | None, failure_state: str | None, signer: AttestationSigner) -> AssuranceAttestation:
    request.verify_digest(); processed_at = _utc(processed_at)
    unsigned = {"exchange_version": EXCHANGE_VERSION, "request_id": request.request_id, "nonce": request.nonce, "request_digest": request.request_digest, "evidence_id": request.evidence_id, "artifact_id": artifact_id, "engine_id": engine_id, "engine_version": engine_version, "policy_id": policy_id, "policy_version": policy_version, "oracle_versions": list(oracle_versions), "processed_at": processed_at, "result": result, "confidence": confidence, "failure_state": failure_state, "responder_service_id": signer.service_id}
    response_digest = digest_hex(unsigned); signature = signer.sign(unsigned | {"response_digest": response_digest})
    return AssuranceAttestation(request.request_id, request.nonce, request.request_digest, response_digest, request.evidence_id, artifact_id, engine_id, engine_version, policy_id, policy_version, tuple(oracle_versions), processed_at, result, confidence, failure_state, signer.service_id, signature)


def verify_attestation(request: AssuranceRequest, attestation: AssuranceAttestation, *, trusted_keys: Mapping[str, Ed25519PublicKey], replay_guard: ReplayGuard, expected_engine_id: str | None = None, expected_engine_version: str | None = None, expected_policy_id: str | None = None, expected_policy_version: str | None = None, expected_evidence_id: str | None = None) -> None:
    request.verify_digest()
    if attestation.request_id != request.request_id or attestation.nonce != request.nonce: raise BindingError("request correlation mismatch")
    if not secrets.compare_digest(attestation.request_digest, request.request_digest): raise BindingError("request digest binding mismatch")
    if attestation.evidence_id != request.evidence_id or (expected_evidence_id is not None and attestation.evidence_id != expected_evidence_id): raise BindingError("evidence binding mismatch")
    if expected_engine_id is not None and attestation.engine_id != expected_engine_id: raise BindingError("engine identity mismatch")
    if expected_engine_version is not None and attestation.engine_version != expected_engine_version: raise BindingError("engine version mismatch")
    if expected_policy_id is not None and attestation.policy_id != expected_policy_id: raise BindingError("policy identity mismatch")
    if expected_policy_version is not None and attestation.policy_version != expected_policy_version: raise BindingError("policy version mismatch")
    public_key = trusted_keys.get(attestation.responder_service_id)
    if public_key is None: raise SignatureError("unknown responder service identity")
    attestation.verify_response_digest()
    try: public_key.verify(_unb64(attestation.signature), canonical_bytes(attestation.unsigned_payload() | {"response_digest": attestation.response_digest}))
    except InvalidSignature as exc: raise SignatureError("attestation signature is invalid") from exc
    replay_guard.accept_once(attestation.responder_service_id, attestation.nonce, attestation.request_digest)
