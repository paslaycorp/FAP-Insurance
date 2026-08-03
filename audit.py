"""
FAP-Insurance — Forensic Evidence Ledger

Accepts EvidenceEnvelope as primary input.
Hash-chained. Thread-locked. WAL-hardened.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import log
from settings import SETTINGS

_db_path: Path = Path(SETTINGS.AUDIT_DB_PATH)
_local = threading.local()
_chain_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=FULL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_records (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id         TEXT NOT NULL UNIQUE,
    request_id          TEXT NOT NULL,
    claim_id            TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    verdict             TEXT NOT NULL,
    confidence_score    REAL NOT NULL,
    components_json     TEXT NOT NULL,
    reality_anchor_json TEXT,
    fap_core_response_json TEXT,
    engine_version      TEXT NOT NULL,
    policy_version      TEXT NOT NULL DEFAULT 'carrier-default-v1',
    oracle_versions     TEXT,
    previous_hash       TEXT,
    record_hash         TEXT NOT NULL,
    report_hash         TEXT,
    report_location     TEXT,
    replay_inputs_hash  TEXT NOT NULL,
    envelope_json       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence ON audit_records(evidence_id);
CREATE INDEX IF NOT EXISTS idx_claim    ON audit_records(claim_id);
CREATE INDEX IF NOT EXISTS idx_request  ON audit_records(request_id);

CREATE TABLE IF NOT EXISTS merkle_roots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    root_hash   TEXT NOT NULL,
    record_from INTEGER NOT NULL,
    record_to   INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    evidence_count INTEGER NOT NULL
);
"""


def _init_db() -> None:
    conn = _get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


def _generate_evidence_id() -> str:
    return f"FAP-EV-{date.today().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _compute_hash(
    evidence_id: str, claim_id: str, created_at: str, verdict: str,
    confidence_score: float, components_json: str, reality_anchor_json: Optional[str],
    fap_core_response_json: Optional[str], engine_version: str, policy_version: str,
    oracle_versions: Optional[str], previous_hash: Optional[str],
    replay_inputs_hash: str, envelope_json: str,
) -> str:
    payload = "|".join([
        evidence_id, claim_id, created_at, verdict, f"{confidence_score:.6f}",
        components_json, reality_anchor_json or "", fap_core_response_json or "",
        engine_version, policy_version, oracle_versions or "",
        previous_hash or "GENESIS", replay_inputs_hash, envelope_json,
    ])
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditRecord:
    evidence_id: str
    request_id: str
    claim_id: str
    created_at: datetime
    verdict: str
    confidence_score: float
    components: Dict[str, float]
    reality_anchor: Optional[Dict[str, Any]]
    fap_core_response: Optional[Dict[str, Any]]
    engine_version: str
    policy_version: str
    oracle_versions: Optional[Dict[str, Any]]
    previous_hash: Optional[str]
    record_hash: str
    report_hash: Optional[str]
    report_location: Optional[str]
    replay_inputs_hash: str
    envelope: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "request_id": self.request_id,
            "claim_id": self.claim_id,
            "created_at": self.created_at.isoformat(),
            "verdict": self.verdict,
            "confidence_score": self.confidence_score,
            "components": self.components,
            "reality_anchor": self.reality_anchor,
            "fap_core_response": self.fap_core_response,
            "engine_version": self.engine_version,
            "policy_version": self.policy_version,
            "oracle_versions": self.oracle_versions,
            "previous_hash": self.previous_hash,
            "record_hash": self.record_hash,
            "report_hash": self.report_hash,
            "report_location": self.report_location,
            "replay_inputs_hash": self.replay_inputs_hash,
            "envelope": self.envelope,
        }


def _hash_replay_inputs(request_payload: Dict[str, Any], components: Dict[str, float]) -> str:
    return hashlib.sha256(_canonical_json({"request": request_payload, "components": components}).encode()).hexdigest()


def store_verification(
    request_id: str,
    claim_id: str,
    verdict: str,
    confidence_score: float,
    components: Dict[str, float],
    request_payload: Dict[str, Any],
    envelope: Dict[str, Any],
    reality_anchor: Optional[Dict[str, Any]] = None,
    raw_fap_response: Optional[Dict[str, Any]] = None,
    engine_version: Optional[str] = None,
    policy_version: Optional[str] = None,
    oracle_versions: Optional[Dict[str, Any]] = None,
    report_html: Optional[str] = None,
) -> AuditRecord:
    _init_db()
    conn = _get_conn()

    evidence_id = _generate_evidence_id()
    now = datetime.now(timezone.utc)

    components_json = _canonical_json(components)
    reality_anchor_json = _canonical_json(reality_anchor) if reality_anchor else None
    fap_core_json = _canonical_json(raw_fap_response) if raw_fap_response else None
    oracle_versions_json = _canonical_json(oracle_versions) if oracle_versions else None
    envelope_json = _canonical_json(envelope)

    replay_inputs_hash = _hash_replay_inputs(request_payload, components)

    report_hash: Optional[str] = None
    report_location: Optional[str] = None
    if report_html:
        report_hash = hashlib.sha256(report_html.encode()).hexdigest()
        report_location = f"reports/{evidence_id}.html"

    with _chain_lock:
        cursor = conn.execute("SELECT record_hash FROM audit_records ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        previous_hash = row["record_hash"] if row else None

        record_hash = _compute_hash(
            evidence_id, claim_id, now.isoformat(), verdict, confidence_score,
            components_json, reality_anchor_json, fap_core_json,
            engine_version or SETTINGS.VERSION, policy_version or "carrier-default-v1",
            oracle_versions_json, previous_hash, replay_inputs_hash, envelope_json,
        )

        conn.execute(
            """INSERT INTO audit_records
            (evidence_id, request_id, claim_id, created_at, verdict, confidence_score,
             components_json, reality_anchor_json, fap_core_response_json,
             engine_version, policy_version, oracle_versions,
             previous_hash, record_hash, report_hash, report_location, replay_inputs_hash, envelope_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, request_id, claim_id, now.isoformat(), verdict, confidence_score,
             components_json, reality_anchor_json, fap_core_json,
             engine_version or SETTINGS.VERSION, policy_version or "carrier-default-v1",
             oracle_versions_json, previous_hash, record_hash, report_hash, report_location,
             replay_inputs_hash, envelope_json),
        )
        conn.commit()

    log.info("audit.stored", evidence_id=evidence_id, claim_id=claim_id, verdict=verdict)

    return AuditRecord(
        evidence_id=evidence_id, request_id=request_id, claim_id=claim_id,
        created_at=now, verdict=verdict, confidence_score=confidence_score,
        components=components, reality_anchor=reality_anchor,
        fap_core_response=raw_fap_response,
        engine_version=engine_version or SETTINGS.VERSION,
        policy_version=policy_version or "carrier-default-v1",
        oracle_versions=oracle_versions, previous_hash=previous_hash,
        record_hash=record_hash, report_hash=report_hash,
        report_location=report_location, replay_inputs_hash=replay_inputs_hash,
        envelope=envelope,
    )


def get_by_evidence_id(evidence_id: str) -> Optional[AuditRecord]:
    _init_db()
    row = _get_conn().execute("SELECT * FROM audit_records WHERE evidence_id = ? LIMIT 1", (evidence_id,)).fetchone()
    return _row_to_record(row) if row else None


def get_by_claim_id(claim_id: str) -> List[AuditRecord]:
    _init_db()
    rows = _get_conn().execute("SELECT * FROM audit_records WHERE claim_id = ? ORDER BY created_at DESC", (claim_id,)).fetchall()
    return [_row_to_record(r) for r in rows]


def get_by_request_id(request_id: str) -> Optional[AuditRecord]:
    _init_db()
    row = _get_conn().execute("SELECT * FROM audit_records WHERE request_id = ? LIMIT 1", (request_id,)).fetchone()
    return _row_to_record(row) if row else None


def list_recent(limit: int = 100) -> List[AuditRecord]:
    _init_db()
    rows = _get_conn().execute("SELECT * FROM audit_records ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_row_to_record(r) for r in rows]


def get_chain_integrity() -> Dict[str, Any]:
    _init_db()
    rows = _get_conn().execute("SELECT * FROM audit_records ORDER BY id ASC").fetchall()
    if not rows:
        return {"status": "empty", "total_records": 0, "breaks": [], "head_hash": None}

    breaks: List[Dict[str, Any]] = []
    prev_hash: Optional[str] = None
    head_hash: Optional[str] = None

    for row in rows:
        expected = _compute_hash(
            row["evidence_id"], row["claim_id"], row["created_at"], row["verdict"],
            row["confidence_score"], row["components_json"], row["reality_anchor_json"],
            row["fap_core_response_json"], row["engine_version"], row["policy_version"],
            row["oracle_versions"], prev_hash, row["replay_inputs_hash"], row["envelope_json"],
        )
        if expected != row["record_hash"]:
            breaks.append({"evidence_id": row["evidence_id"], "expected_hash": expected, "actual_hash": row["record_hash"]})
        prev_hash = row["record_hash"]
        head_hash = row["record_hash"]

    return {"status": "intact" if not breaks else "compromised", "total_records": len(rows), "breaks": breaks, "head_hash": head_hash}


def get_replay_inputs(evidence_id: str) -> Optional[Dict[str, Any]]:
    record = get_by_evidence_id(evidence_id)
    if not record:
        return None
    return {"evidence_id": record.evidence_id, "envelope": record.envelope, "replay_inputs_hash": record.replay_inputs_hash}


def compute_merkle_root(record_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    _init_db()
    conn = _get_conn()
    if record_ids:
        placeholders = ",".join("?" * len(record_ids))
        cursor = conn.execute(f"SELECT id, record_hash FROM audit_records WHERE id IN ({placeholders}) ORDER BY id", tuple(record_ids))
    else:
        cursor = conn.execute("SELECT id, record_hash FROM audit_records ORDER BY id")
    rows = cursor.fetchall()
    if not rows:
        return {"root_hash": None, "count": 0}

    hashes = [r["record_hash"] for r in rows]
    ids = [r["id"] for r in rows]
    while len(hashes) > 1:
        next_level = []
        for i in range(0, len(hashes), 2):
            left, right = hashes[i], hashes[i + 1] if i + 1 < len(hashes) else hashes[i]
            next_level.append(hashlib.sha256(f"{left}{right}".encode()).hexdigest())
        hashes = next_level

    root_hash = hashes[0]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("INSERT INTO merkle_roots (root_hash, record_from, record_to, created_at, evidence_count) VALUES (?, ?, ?, ?, ?)",
                 (root_hash, min(ids), max(ids), now, len(ids)))
    conn.commit()
    log.info("audit.merkle_root", root_hash=root_hash[:16], count=len(ids))
    return {"root_hash": root_hash, "record_from": min(ids), "record_to": max(ids), "count": len(ids), "timestamp": now}


def _row_to_record(row: sqlite3.Row) -> AuditRecord:
    return AuditRecord(
        evidence_id=row["evidence_id"], request_id=row["request_id"], claim_id=row["claim_id"],
        created_at=datetime.fromisoformat(row["created_at"]), verdict=row["verdict"],
        confidence_score=row["confidence_score"],
        components=json.loads(row["components_json"]),
        reality_anchor=json.loads(row["reality_anchor_json"]) if row["reality_anchor_json"] else None,
        fap_core_response=json.loads(row["fap_core_response_json"]) if row["fap_core_response_json"] else None,
        engine_version=row["engine_version"], policy_version=row["policy_version"],
        oracle_versions=json.loads(row["oracle_versions"]) if row["oracle_versions"] else None,
        previous_hash=row["previous_hash"], record_hash=row["record_hash"],
        report_hash=row["report_hash"], report_location=row["report_location"],
        replay_inputs_hash=row["replay_inputs_hash"],
        envelope=json.loads(row["envelope_json"]),
    )
