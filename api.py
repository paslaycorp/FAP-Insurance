"""
FAP-Insurance API — v0.3.0-grand-slam
Architecture:
  POST /verify
      |
      v
  Evidence Envelope CREATED
      |
      +--> Solar Oracle (NOAA SWPC witness)
      +--> Weather Oracle (Open-Meteo witness)
      +--> Device Oracle (enrollment witness)
      +--> FAP-Core Oracle (consensus witness)
      |
      v
  Evidence Fusion Engine
      |
      v
  Confidence + Reason Codes
      |
      v
  Audit Seal (hash-chained, tamper-evident)
"""

from __future__ import annotations

import asyncio
import hashlib
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from auth import verify_api_key
from logger import clear_request_id, log, set_request_id
from models import ErrorResponse, HealthResponse, VerifyClaimRequest, VerifyClaimResponse
from oracles import FapCoreClient, FapCoreUnavailable
from reality_anchor import RealityAnchor
from settings import SETTINGS
from evidence import EvidenceEnvelope, OracleObservation
from fusion import EvidenceFusionEngine
from solar_oracle import evaluate_solar_correlation

from config import config
from pricing import PricingCalculator
from report_generator import AdjusterReport
from audit import store_verification, get_by_evidence_id, get_by_claim_id, get_by_request_id, get_chain_integrity
from report_templates import generate_audit_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(headers={"User-Agent": f"FAP-Insurance/{SETTINGS.VERSION}"}, timeout=30.0)
    app.state.fap_client = FapCoreClient(app.state.http)
    app.state.reality = RealityAnchor(app.state.http)
    app.state.fusion = EvidenceFusionEngine()
    log.info("service.startup", version=SETTINGS.VERSION, env=SETTINGS.ENV)
    yield
    await app.state.http.aclose()
    log.info("service.shutdown")


app = FastAPI(
    title="FAP-Insurance",
    description="Reality-correlated evidence verification for insurance claims",
    version=SETTINGS.VERSION,
    docs_url="/docs" if not SETTINGS.is_production else None,
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter = Limiter(key_func=get_remote_address)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if SETTINGS.is_production else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(req_id)
        request.state.request_id = req_id
        start = datetime.now(timezone.utc)
        log.info("http.request", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            log.error("http.unhandled", traceback=traceback.format_exc())
            raise
        finally:
            duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            log.info("http.response", status_code=response.status_code, duration_ms=round(duration_ms, 2))
            clear_request_id()
        response.headers["X-Request-ID"] = req_id
        return response


app.add_middleware(RequestLoggingMiddleware)


def _err(error: str, detail: str, request_id: Optional[str] = None, field: Optional[str] = None):
    body: Dict[str, Any] = {"error": error, "detail": detail}
    if request_id:
        body["request_id"] = request_id
    if field:
        body["field"] = field
    return body


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", []))
    msg = first.get("msg", "Validation failed.")
    log.warning("validation.error", field=field, msg=msg, request_id=req_id)
    return JSONResponse(status_code=422, content=_err("VALIDATION_ERROR", msg, req_id, field))


@app.exception_handler(ValueError)
async def value_handler(request: Request, exc: ValueError):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    log.warning("value.error", msg=str(exc), request_id=req_id)
    return JSONResponse(status_code=400, content=_err("BAD_REQUEST", str(exc), req_id))


@app.exception_handler(FapCoreUnavailable)
async def fap_core_handler(request: Request, exc: FapCoreUnavailable):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    log.error("fap_core.unavailable", msg=str(exc), request_id=req_id)
    return JSONResponse(status_code=503, content=_err("SERVICE_UNAVAILABLE", "FAP-Core temporarily unavailable.", req_id))


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    log.error("unhandled.exception", error=str(exc), traceback=traceback.format_exc(), request_id=req_id)
    return JSONResponse(status_code=500, content=_err("INTERNAL_ERROR", "Unexpected error logged.", req_id))


def _map_verdict(verdict: str) -> str:
    mapping = {
        "STRICT": getattr(config, "STRICT_LABEL", "Verified"),
        "PROBABLE": getattr(config, "PROBABLE_LABEL", "Likely Authentic"),
        "SUSPICIOUS": getattr(config, "SUSPICIOUS_LABEL", "Suspicious"),
        "QUARANTINE": getattr(config, "QUARANTINE_LABEL", "Fraudulent"),
    }
    return mapping.get(verdict, f"UNKNOWN — {verdict}")


def _recommendation(verdict: str, score: float) -> str:
    if verdict == "STRICT":
        return "Photo provenance verified. Proceed with standard claim processing."
    if verdict == "PROBABLE":
        return "Photo likely authentic. Recommend standard review with spot-check."
    if verdict == "SUSPICIOUS":
        return "Anomalies detected. Require claimant interview and secondary documentation."
    return "High fraud probability. Escalate to SIU. Recommend denial pending investigation."


def _build_fap_payload(req: VerifyClaimRequest) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "media_hash": req.media_hash or hashlib.sha256(
            f"{req.claim_id}:{req.timestamp_claimed.isoformat()}".encode()
        ).hexdigest(),
        "geo": {"lat": req.lat, "lon": req.lon},
        "timestamp_claimed": req.timestamp_claimed.isoformat(),
        "device": {"model": req.device_model, "manufacturer": req.device_manufacturer, "os_version": req.device_os},
        "witness_ids": req.witness_ids,
    }
    if req.enrollment_id:
        payload["device"]["enrollment_id"] = req.enrollment_id
    return payload


def _safe_solar_flux(result: Dict[str, Any]) -> Optional[float]:
    try:
        for entry in result.get("audit_trail", []):
            details = entry.get("details", {})
            if "flux" in details:
                return float(details["flux"])
    except Exception:
        pass
    return None


async def _process_single_claim(
    req: VerifyClaimRequest,
    fap_client: FapCoreClient,
    reality: RealityAnchor,
    fusion: EvidenceFusionEngine,
    req_id: str,
) -> VerifyClaimResponse:
    start = datetime.now(timezone.utc)

    # ═══════════════════════════════════════════════════════
    # 1. EVIDENCE ENVELOPE CREATED (the centerpiece)
    # ═══════════════════════════════════════════════════════
    envelope = EvidenceEnvelope(
        evidence_id=f"FAP-EV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        media_hash=req.media_hash or hashlib.sha256(
            f"{req.claim_id}:{req.timestamp_claimed.isoformat()}".encode()
        ).hexdigest(),
        c2pa_present=False,
        c2pa_valid=None,
        capture_time=req.timestamp_claimed,
        latitude=req.lat,
        longitude=req.lon,
        device_id=req.enrollment_id,
    )

    # ═══════════════════════════════════════════════════════
    # 2. PARALLEL ORACLE OBSERVATIONS (all are witnesses)
    # ═══════════════════════════════════════════════════════

    # 2a. Solar Oracle — independent temporal anchor
    solar_result = await evaluate_solar_correlation(req.timestamp_claimed)
    envelope.add_observation(OracleObservation(
        oracle_type="solar_temporal",
        source="NOAA_SWPC",
        confidence=solar_result.confidence,
        raw_value=solar_result.to_dict(),
        status=solar_result.status,
        discrepancy_note=solar_result.reason if solar_result.status != "OK" else None,
    ))

    # 2b. Weather Oracle — independent environmental anchor
    try:
        weather_data = await reality.check_weather(req.lat, req.lon)
        weather_conf = 0.5 if weather_data.get("available") else 0.0
        envelope.add_observation(OracleObservation(
            oracle_type="weather",
            source="Open-Meteo_DIRECT",
            confidence=weather_conf,
            raw_value=weather_data,
            status="OK" if weather_data.get("available") else "DEGRADED",
            discrepancy_note=None if weather_data.get("available") else "Weather oracle unavailable",
        ))
    except Exception as exc:
        envelope.add_observation(OracleObservation(
            oracle_type="weather",
            source="Open-Meteo_DIRECT",
            confidence=0.0,
            status="FAILED",
            discrepancy_note=str(exc),
        ))

    # 2c. Device Oracle — enrollment witness
    if req.enrollment_id:
        envelope.add_observation(OracleObservation(
            oracle_type="device",
            source="DeviceRegistry",
            confidence=0.85,
            raw_value={"enrollment_id": req.enrollment_id, "model": req.device_model},
            status="OK",
        ))
    else:
        envelope.add_observation(OracleObservation(
            oracle_type="device",
            source="DeviceRegistry",
            confidence=0.3,
            status="DEGRADED",
            discrepancy_note="Device not enrolled. Reduced confidence.",
        ))

    # 2d. FAP-Core Oracle — consensus witness
    payload = _build_fap_payload(req)
    try:
        fap_result = await fap_client.verify(config.FAP_CORE_URL, payload)
        fap_components = fap_result.get("components", {})
        fap_score = fap_result.get("total_score", 0.0)
        envelope.add_observation(OracleObservation(
            oracle_type="consensus",
            source="FAP-Core",
            confidence=fap_score,
            raw_value={"verdict": fap_result.get("verdict"), "components": fap_components},
            status="OK",
        ))
    except Exception as exc:
        fap_result = {}
        fap_components = {}
        fap_score = 0.0
        envelope.add_observation(OracleObservation(
            oracle_type="consensus",
            source="FAP-Core",
            confidence=0.0,
            status="FAILED",
            discrepancy_note=f"FAP-Core unavailable: {exc}",
        ))

    # ═══════════════════════════════════════════════════════
    # 3. EVIDENCE FUSION ENGINE
    # ═══════════════════════════════════════════════════════
    fusion_result = fusion.evaluate(envelope.observations)
    envelope.confidence_score = fusion_result.confidence
    envelope.verdict = fusion_result.verdict

    elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    # ═══════════════════════════════════════════════════════
    # 4. GENERATE REPORT
    # ═══════════════════════════════════════════════════════
    report = AdjusterReport(
        claim_id=req.claim_id,
        policy_number=req.policy_number,
        adjuster_notes=req.adjuster_notes,
        fap_result=fap_result,
        request_data=req.model_dump(),
    )
    report_html = report.to_html()

    # ═══════════════════════════════════════════════════════
    # 5. AUDIT SEAL (hash-chained, tamper-evident)
    # ═══════════════════════════════════════════════════════
    audit_record = store_verification(
        request_id=req_id,
        claim_id=req.claim_id,
        verdict=envelope.verdict,
        confidence_score=envelope.confidence_score,
        components=fap_components or {o.oracle_type: o.confidence for o in envelope.observations},
        request_payload=req.model_dump(),
        envelope=envelope.to_audit_payload(),
        reality_anchor={"solar": solar_result.to_dict()} if solar_result else None,
        raw_fap_response=fap_result if fap_result else None,
        engine_version=SETTINGS.VERSION,
        policy_version="carrier-default-v1",
        oracle_versions={
            "fap_core": getattr(config, "FAP_CORE_VERSION", "unknown"),
            "solar": "noaa-swpc-direct-v1",
            "weather": "open-meteo-direct-v1",
            "fusion": "bayesian-v1",
            "policy": "carrier-default-v1",
        },
        report_html=report_html,
    )

    envelope.audit_record_hash = audit_record.record_hash
    envelope.fap_core_response = fap_result

    return VerifyClaimResponse(
        claim_id=req.claim_id,
        verification_id=fap_result.get("artifact_id", "unknown") if fap_result else "unknown",
        verdict=envelope.verdict,
        verdict_label=_map_verdict(envelope.verdict),
        score=round(envelope.confidence_score, 4),
        confidence=round(fap_result.get("confidence", 0.0), 4) if fap_result else 0.0,
        components=fap_components or {},
        solar_flux_at_time=solar_result.flux,
        weather_match=fap_components.get("weather") if fap_components else None,
        device_enrolled=any(o.oracle_type == "device" and o.status == "OK" for o in envelope.observations),
        witness_count=len(req.witness_ids),
        processing_time_ms=elapsed_ms,
        report_url=f"/audit/report/{req_id}",
        recommendation=_recommendation(envelope.verdict, envelope.confidence_score),
        timestamp_processed=datetime.now(timezone.utc),
    )


# ═════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse)
async def health():
    fap_ok = False
    try:
        fap_ok = await app.state.fap_client.health(config.FAP_CORE_URL)
    except Exception:
        pass
    return HealthResponse(status="healthy", fap_core_connected=fap_ok, version=SETTINGS.VERSION, timestamp=datetime.now(timezone.utc))


@app.post("/verify", response_model=VerifyClaimResponse)
@limiter.limit(SETTINGS.RATE_LIMIT_VERIFY)
async def verify_claim(request: Request, req: VerifyClaimRequest, api_key: str = Depends(verify_api_key)):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    log.info("verify.start", claim_id=req.claim_id, request_id=req_id)
    try:
        result = await _process_single_claim(req, app.state.fap_client, app.state.reality, app.state.fusion, req_id)
        log.info("verify.complete", claim_id=req.claim_id, verdict=result.verdict, request_id=req_id)
        return result
    except Exception:
        log.error("verify.failed", claim_id=req.claim_id, request_id=req_id)
        raise


@app.post("/verify/batch")
@limiter.limit(SETTINGS.RATE_LIMIT_BATCH)
async def verify_batch(request: Request, requests: List[VerifyClaimRequest], api_key: str = Depends(verify_api_key)):
    if len(requests) > 10:
        raise HTTPException(status_code=400, detail="Batch limit is 10 claims per request.")
    results: List[Dict[str, Any]] = []
    for req in requests:
        try:
            req_id = str(uuid.uuid4())
            r = await _process_single_claim(req, app.state.fap_client, app.state.reality, app.state.fusion, req_id)
            results.append({"claim_id": req.claim_id, "status": "ok", "result": r.model_dump()})
        except HTTPException as e:
            results.append({"claim_id": req.claim_id, "status": "error", "detail": e.detail})
        except Exception as e:
            results.append({"claim_id": req.claim_id, "status": "error", "detail": str(e)})
    return {"processed": len(results), "results": results}


@app.get("/audit/report/{request_id}", response_class=HTMLResponse)
async def get_audit_report(request_id: str):
    record = get_by_request_id(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audit record not found.")
    chain = get_chain_integrity()
    html = generate_audit_report(record, chain)
    return HTMLResponse(content=html)


@app.get("/audit/claim/{claim_id}")
async def get_claim_history(claim_id: str):
    records = get_by_claim_id(claim_id)
    return {"claim_id": claim_id, "total_verifications": len(records), "records": [r.to_dict() for r in records]}


@app.get("/audit/integrity")
async def audit_integrity():
    return get_chain_integrity()


@app.get("/audit/evidence/{evidence_id}")
async def get_evidence(evidence_id: str):
    record = get_by_evidence_id(evidence_id)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return record.to_dict()


@app.get("/report/{verification_id}", response_class=HTMLResponse)
async def get_report(verification_id: str):
    return HTMLResponse(content=f"<h1>Legacy endpoint</h1><p>Use /audit/report/{{request_id}}</p><p>ID: {verification_id}</p>")


@app.get("/pricing")
async def pricing(tier: Optional[str] = None):
    if tier and tier in getattr(config, "TIERS", {}):
        t = config.TIERS[tier]
        return {"tier": getattr(t, "name", tier), "price_per_verification": getattr(t, "price_per_verification", 0.0), "monthly_cap": getattr(t, "monthly_cap", 0), "max_monthly": getattr(t, "max_verifications_per_month", 0), "features": getattr(t, "features", [])}
    return {"tiers": {k: {"name": getattr(v, "name", k), "price_per_verification": getattr(v, "price_per_verification", 0.0), "monthly_cap": getattr(v, "monthly_cap", 0), "max_monthly": getattr(v, "max_verifications_per_month", 0), "features": getattr(v, "features", [])} for k, v in getattr(config, "TIERS", {}).items()}}


@app.get("/demo")
@limiter.limit(SETTINGS.RATE_LIMIT_DEMO)
async def demo():
    chain = get_chain_integrity()
    return {
        "service": "FAP-Insurance",
        "version": SETTINGS.VERSION,
        "audit_chain": chain,
        "architecture": "Evidence Envelope → Parallel Oracles → Fusion Engine → Audit Seal",
        "endpoints": {
            "verify": "POST /verify (X-API-Key)",
            "audit_report": "GET /audit/report/{request_id}",
            "claim_history": "GET /audit/claim/{claim_id}",
            "evidence": "GET /audit/evidence/{evidence_id}",
            "integrity_check": "GET /audit/integrity",
        },
        "legitimate": {
            "claim_id": "DEMO-LEGIT-001",
            "verdict": "STRICT",
            "verdict_label": getattr(config, "STRICT_LABEL", "Verified"),
            "score": 0.9175,
            "components": {"solar": 1.0, "signature": 0.95, "hardware": 1.0, "weather": 0.85, "witness": 1.0, "gps": 0.5},
            "recommendation": "Photo provenance verified. Proceed with standard claim processing.",
        },
        "fraudulent": {
            "claim_id": "DEMO-FRAUD-001",
            "verdict": "QUARANTINE",
            "verdict_label": getattr(config, "QUARANTINE_LABEL", "Fraudulent"),
            "score": 0.3675,
            "components": {"solar": 0.0, "signature": 0.95, "hardware": 0.0, "weather": 0.85, "witness": 0.0, "gps": 0.0},
            "recommendation": "High fraud probability. Escalate to SIU. Recommend denial pending investigation.",
        },
    }
