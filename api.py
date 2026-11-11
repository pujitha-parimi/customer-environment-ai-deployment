"""HTTP API: authentication, validation, metrics and error handling.

Business logic lives in service.py; Gemini access in llm_client.py.
"""
import logging
import re
import time
import uuid
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from starlette.routing import Match

import metrics
from config import get_settings
from llm_client import LLMConfigError, LLMError
from logging_config import configure_logging
from secrets_provider import get_secret, vault_status
from security import configured_tokens, verify_token
from service import route_query

configure_logging()
logger = logging.getLogger("api")
settings = get_settings()

app = FastAPI(
    title="Multi-Agent Customer Support API",
    description="Routes customer questions to billing, technical or general support agents.",
    version="1.1.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

bearer = HTTPBearer(auto_error=False, description="Customer API token")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


# ---------- schemas ----------
class CustomerQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., min_length=1, max_length=2000, description="Customer support question")


class SupportResponse(BaseModel):
    category: Literal["billing", "technical", "general"]
    answer: str
    request_id: str


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, bool | str]


class ErrorResponse(BaseModel):
    detail: str


# ---------- auth ----------
def _auth(scope: str, secret_name: str):
    def dependency(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
        token = credentials.credentials if credentials else None
        if not verify_token(token, secret_name):
            metrics.AUTH_FAILURES.labels(scope).inc()
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return dependency


require_customer = _auth("query", "CUSTOMER_API_TOKENS")
require_metrics = _auth("metrics", "METRICS_TOKEN")


# ---------- middleware ----------
def _route_label(request: Request) -> str:
    for route in request.app.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            return route.path
    return "unmatched"


@app.middleware("http")
async def observability(request: Request, call_next):
    incoming = request.headers.get("x-request-id", "")
    request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.perf_counter()
    status = 500
    metrics.IN_PROGRESS.inc()
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        elapsed = time.perf_counter() - start
        path = _route_label(request)
        metrics.IN_PROGRESS.dec()
        metrics.HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
        metrics.HTTP_LATENCY.labels(request.method, path).observe(elapsed)
        logger.info(
            "request",
            extra={"fields": {
                "request_id": request_id, "method": request.method, "path": path,
                "status": status, "duration_ms": round(elapsed * 1000, 1),
            }},
        )


# ---------- error handlers (never echo request bodies or internals) ----------
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Invalid request.", "errors": errors})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.error("unhandled error", extra={"fields": {"error_type": type(exc).__name__}})
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


# ---------- endpoints ----------
@app.get("/health", response_model=HealthResponse, tags=["operations"], summary="Liveness probe")
def health():
    return HealthResponse(status="healthy", service="multi-agent-customer-support")


@app.get(
    "/ready", response_model=ReadyResponse, tags=["operations"], summary="Readiness probe",
    responses={503: {"model": ReadyResponse}},
)
def ready():
    """Configuration readiness only. Does not call Gemini (avoids cost and rate limits)."""
    vault = vault_status()
    checks: dict[str, bool | str] = {
        "gemini_api_key_configured": bool(get_secret("GEMINI_API_KEY")),
        "customer_tokens_configured": bool(configured_tokens("CUSTOMER_API_TOKENS")),
        "secret_backend": "vault" if vault != "disabled" else "file_or_env",
        "vault": vault,
    }
    ok = checks["gemini_api_key_configured"] and checks["customer_tokens_configured"] and vault != "unavailable"
    body = ReadyResponse(status="ready" if ok else "not_ready", checks=checks)
    return JSONResponse(status_code=200 if ok else 503, content=body.model_dump())


@app.post(
    "/query", response_model=SupportResponse, tags=["support"], summary="Ask the support system",
    dependencies=[Depends(require_customer)],
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
               502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def query(payload: CustomerQuery, request: Request):
    request_id = request.state.request_id
    try:
        category, answer = route_query(payload.query)
    except LLMConfigError:
        metrics.GEMINI_ERRORS.labels("not_configured").inc()
        logger.error("gemini not configured", extra={"fields": {"request_id": request_id}})
        raise HTTPException(status_code=503, detail="Service temporarily unavailable.") from None
    except LLMError as exc:
        metrics.GEMINI_ERRORS.labels(exc.reason).inc()
        logger.error("gemini failure", extra={"fields": {"request_id": request_id, "reason": exc.reason}})
        raise HTTPException(
            status_code=502, detail="The AI provider is temporarily unavailable. Please try again later."
        ) from None
    except Exception as exc:
        logger.error("query failed", extra={"fields": {"request_id": request_id, "error_type": type(exc).__name__}})
        raise HTTPException(status_code=500, detail="Internal server error.") from None
    metrics.QUERIES.labels(category).inc()
    return SupportResponse(category=category, answer=answer, request_id=request_id)


@app.get("/metrics", include_in_schema=False, dependencies=[Depends(require_metrics)])
def prometheus_metrics():
    return Response(content=metrics.generate_latest(), media_type=metrics.CONTENT_TYPE_LATEST)
