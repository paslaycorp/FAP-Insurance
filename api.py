"""FAP-Insurance API: evidence verification with DPIE assurance enforcement."""
import hashlib
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from audit import get_by_claim_id, get_by_evidence_id, get_by_request_id, get_chain_integrity, store_verification
from auth import verify_api_key
from config import config
from dpie_context import clear_context, get_context, set_context
from dpie_runtime import assess_request_context
from evidence import EvidenceEnvelope, OracleObservation
from fusion import EvidenceFusionEngine
from logger import clear_request_id, log, set_request_id
from models import ErrorResponse, HealthResponse, VerifyClaimRequest, VerifyClaimResponse
from oracles import FapCoreClient, FapCoreUnavailable
from reality_anchor import RealityAnchor
from report_generator import AdjusterReport
from report_templates import generate_audit_report
from settings import SETTINGS
from solar_oracle import evaluate_solar_correlation


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(headers={"User-Agent": f"FAP-Insurance/{SETTINGS.VERSION}"}, timeout=30.0)
    app.state.fap_client = FapCoreClient(app.state.http)
    app.state.reality = RealityAnchor(app.state.http)
    app.state.fusion = EvidenceFusionEngine()
    yield
    await app.state.http.aclose()


app = FastAPI(title="FAP-Insurance", description="Reality-correlated evidence verification for insurance claims", version=SETTINGS.VERSION, docs_url="/docs" if not SETTINGS.is_production else None, lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=[] if SETTINGS.is_production else ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        set_request_id(req_id)
        request.state.request_id = req_id
        start = datetime.now(timezone.utc)
        try:
            response = await call_next(request)
        except Exception:
            log.error("http.unhandled", traceback=traceback.format_exc())
            raise
        finally:
            duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            log.info("http.response", status_code=getattr(locals().get("response"), "status_code", 500), duration_ms=round(duration_ms, 2))
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
    return JSONResponse(status_code=422, content=_err("VALIDATION_ERROR", first.get("msg", "Validation failed."), req_id, field))


@app.exception_handler(ValueError)
async def value_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content=_err("BAD_REQUEST", str(exc), getattr(request.state, "request_id", None)))


@app.exception_handler(FapCoreUnavailable)
async def fap_core_handler(request: Request, exc: FapCoreUnavailable):
    return JSONResponse(status_code=503, content=_err("SERVICE_UNAVAILABLE", "FAP-Core temporarily unavailable.", getattr(request.state, "request_id", None)))


def _map_verdict(verdict: str) -> str:
    return {"STRICT": getattr(config, "STRICT_LABEL", "Verified"), "PROBABLE": getattr(config, "PROBABLE_LABEL", "Likely Authentic"), "SUSPICIOUS": getattr(config, "SUSPICIOUS_LABEL", "Suspicious"), "QUARANTINE": getattr(config, "QUARANTINE_LABEL", "Fraudulent")}.get(verdict, f"UNKNOWN — {verdict}")


def _recommendation(verdict: str, score: float) -> str:
    if verdict == "STRICT":
        return "Photo provenance verified. Proceed with standard claim processing."
    if verdict == "PROBABLE":
        return "Photo likely authentic. Recommend standard review with spot-check."
    if verdict == "SUSPICIOUS":
        return "Anomalies detected. Require claimant interview and secondary documentation."
    return "High fraud probability. Escalate to SIU. Recommend denial pending investigation."


def _build_fap_payload(req: VerifyClaimRequest) -> Dict[str, Any]:
    return {"media_hash": req.media_hash or hashlib.sha256(f"{req.claim_id}:{req.timestamp_claimed.isoformat()}".encode()).hexdigest(), "geo": {"lat": req.lat, "lon": req.lon}, "timestamp_claimed": req.timestamp_claimed.isoformat(), "device": {"model": req.device_model, "manufacturer": req.device_manufacturer, "os_version": req.device_os}, "witness_ids": req.witness_ids}


async def _process_single_claim(req: VerifyClaimRequest, fap_client: FapCoreClient, reality: RealityAnchor, fusion: EvidenceFusionEngine, req_id: str) -> VerifyClaimResponse:
    start = datetime.now(timezone.utc)
    try:
        envelope = EvidenceEnvelope(evidence_id=f"FAP-EV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}", media_hash=req.media_hash or hashlib.sha256(f"{req.claim_id}:{req.timestamp_claimed.isoformat()}".encode()).hexdigest(), c2pa_present=False, c2pa_valid=None, capture_time=req.timestamp_claimed, latitude=req.lat, longitude=req.lon, device_id=req.enrollment_id)
        solar_result = await evaluate_solar_correlation(req.timestamp_claimed)
        envelope.add_observation(OracleObservation(oracle_type="solar_temporal", source="NOAA_SWPC", confidence=solar_result.confidence, raw_value=solar_result.to_dict(), status=solar_result.status, discrepancy_note=solar_result.reason if solar_result.status != "OK" else None))
        try:
            weather_data = await reality.check_weather(req.lat, req.lon)
            envelope.add_observation(OracleObservation(oracle_type="weather", source="Open-Meteo_DIRECT", confidence=0.5 if weather_data.get("available") else 0.0, raw_value=weather_data, status="OK" if weather_data.get("available") else "DEGRADED"))
        except Exception as exc:
            envelope.add_observation(OracleObservation(oracle_type="weather", source="Open-Meteo_DIRECT", confidence=0.0, status="FAILED", discrepancy_note=str(exc)))
        envelope.add_observation(OracleObservation(oracle_type="device", source="DeviceRegistry", confidence=0.85 if req.enrollment_id else 0.3, status="OK" if req.enrollment_id else "DEGRADED", discrepancy_note=None if req.enrollment_id else "Device not enrolled."))
        payload = _build_fap_payload(req)
        try:
            fap_result = await fap_client.verify(config.FAP_CORE_URL, payload)
            fap_components = fap_result.get("components", {})
            envelope.add_observation(OracleObservation(oracle_type="consensus", source="FAP-Core", confidence=float(fap_result.get("total_score", 0.0)), raw_value={"verdict": fap_result.get("verdict"), "components": fap_components}, status="OK"))
        except Exception as exc:
            fap_result, fap_components = {}, {}
            envelope.add_observation(OracleObservation(oracle_type="consensus", source="FAP-Core", confidence=0.0, status="FAILED", discrepancy_note=f"FAP-Core unavailable: {exc}"))
        fusion_result = fusion.evaluate(envelope.observations)
        envelope.confidence_score = fusion_result.confidence
        envelope.verdict = fusion_result.verdict

        dpie_context = get_context()
        dpie_result = None
        if dpie_context is not None:
            dpie_result = assess_request_context(
                evidence_id=envelope.evidence_id,
                verification={"verdict": envelope.verdict},
                context=dpie_context,
            )

        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        report_html = AdjusterReport(claim_id=req.claim_id, policy_number=req.policy_number, adjuster_notes=req.adjuster_notes, fap_result=fap_result, request_data=req.model_dump()).to_html()
        audit_record = store_verification(request_id=req_id, claim_id=req.claim_id, verdict=envelope.verdict, confidence_score=envelope.confidence_score, components=fap_components or {o.oracle_type: o.confidence for o in envelope.observations}, request_payload=req.model_dump(), envelope=envelope.to_audit_payload(), reality_anchor={"solar": solar_result.to_dict()}, raw_fap_response=fap_result or None, engine_version=SETTINGS.VERSION, policy_version="carrier-default-v1", oracle_versions={"fap_core": getattr(config, "FAP_CORE_VERSION", "unknown"), "solar": "noaa-swpc-direct-v1", "weather": "open-meteo-direct-v1", "fusion": "bayesian-v1", "policy": "carrier-default-v1"}, report_html=report_html)
        envelope.audit_record_hash = audit_record.record_hash
        envelope.fap_core_response = fap_result

        if dpie_result and dpie_result["decision"] in {"DENY", "QUARANTINE"}:
            status_code = 403 if dpie_result["decision"] == "DENY" else 409
            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": "DPIE_ASSURANCE_BLOCKED",
                    "decision": dpie_result["decision"],
                    "failure": dpie_result["failure"],
                    "reason": dpie_result["reason"],
                    "transition_id": dpie_result["transition_id"],
                    "evidence_id": envelope.evidence_id,
                    "audit_record_hash": audit_record.record_hash,
                },
            )

        return VerifyClaimResponse(claim_id=req.claim_id, verification_id=audit_record.evidence_id, verdict=envelope.verdict, verdict_label=_map_verdict(envelope.verdict), score=round(envelope.confidence_score, 4), confidence=round(float(fap_result.get("confidence", 0.0)), 4), components=fap_components, solar_flux_at_time=solar_result.flux, weather_match=fap_components.get("weather"), device_enrolled=bool(req.enrollment_id), witness_count=len(req.witness_ids), processing_time_ms=elapsed_ms, report_url=f"/audit/report/{req_id}", recommendation=_recommendation(envelope.verdict, envelope.confidence_score), timestamp_processed=datetime.now(timezone.utc), status=envelope.verdict, processed_at=datetime.now(timezone.utc), request_id=req_id)
    finally:
        clear_context()


@app.get("/health", response_model=HealthResponse)
async def health():
    fap_ok = await app.state.fap_client.health(config.FAP_CORE_URL)
    return HealthResponse(status="healthy", fap_core_connected=fap_ok, version=SETTINGS.VERSION, timestamp=datetime.now(timezone.utc))


@app.post("/verify", response_model=VerifyClaimResponse)
@limiter.limit(SETTINGS.RATE_LIMIT_VERIFY)
async def verify_claim(request: Request, req: VerifyClaimRequest, api_key: str = Depends(verify_api_key)):
    set_context(req.dpie_context())
    return await _process_single_claim(req, app.state.fap_client, app.state.reality, app.state.fusion, request.state.request_id)


@app.post("/verify/batch")
@limiter.limit(SETTINGS.RATE_LIMIT_BATCH)
async def verify_batch(request: Request, requests: List[VerifyClaimRequest], api_key: str = Depends(verify_api_key)):
    if len(requests) > 10:
        raise HTTPException(status_code=400, detail="Batch limit is 10 claims per request.")
    results = []
    for req in requests:
        req_id = str(uuid.uuid4())
        set_context(req.dpie_context())
        try:
            result = await _process_single_claim(req, app.state.fap_client, app.state.reality, app.state.fusion, req_id)
            results.append({"claim_id": req.claim_id, "status": "ok", "result": result.model_dump()})
        except HTTPException as exc:
            results.append({"claim_id": req.claim_id, "status": "blocked", "status_code": exc.status_code, "detail": exc.detail})
        except Exception:
            log.error("verify.batch_error", request_id=req_id, claim_id=req.claim_id, traceback=traceback.format_exc())
            results.append({"claim_id": req.claim_id, "status": "error", "detail": "Verification failed."})
        finally:
            clear_context()
    return {"processed": len(results), "results": results}


@app.get("/audit/report/{request_id}", response_class=HTMLResponse)
async def get_audit_report(request_id: str, api_key: str = Depends(verify_api_key)):
    record = get_by_request_id(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Audit record not found.")
    return HTMLResponse(content=generate_audit_report(record, get_chain_integrity()))


@app.get("/audit/claim/{claim_id}")
async def get_claim_history(claim_id: str, api_key: str = Depends(verify_api_key)):
    records = get_by_claim_id(claim_id)
    return {"claim_id": claim_id, "total_verifications": len(records), "records": [r.to_dict() for r in records]}


@app.get("/audit/integrity")
async def audit_integrity(api_key: str = Depends(verify_api_key)):
    return get_chain_integrity()


@app.get("/audit/evidence/{evidence_id}")
async def get_evidence(evidence_id: str, api_key: str = Depends(verify_api_key)):
    record = get_by_evidence_id(evidence_id)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return record.to_dict()


@app.get("/report/{verification_id}", response_class=HTMLResponse)
async def get_report(verification_id: str, api_key: str = Depends(verify_api_key)):
    return HTMLResponse(content=f"<h1>Legacy endpoint</h1><p>Use /audit/report/{{request_id}}</p><p>ID: {verification_id}</p>")


@app.get("/pricing")
async def pricing(tier: Optional[str] = None):
    tiers = getattr(config, "TIERS", {})
    if tier and tier in tiers:
        item = tiers[tier]
        return {"tier": getattr(item, "name", tier), "price_per_verification": getattr(item, "price_per_verification", 0.0), "monthly_cap": getattr(item, "monthly_cap", 0)}
    return {"tiers": list(tiers.keys())}


@app.get("/demo")
async def demo():
    return {"service": "FAP-Insurance", "version": SETTINGS.VERSION, "audit_chain": get_chain_integrity(), "architecture": "FAP → DPIE → Governor → Decision → Immutable Audit"}
