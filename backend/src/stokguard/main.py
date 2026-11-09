from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from stokguard.approvals.router import router as approvals_router
from stokguard.audit.router import router as audit_router
from stokguard.auth.router import router as auth_router
from stokguard.auth.sessions import LoginLimiter
from stokguard.businesses.router import router as business_router
from stokguard.core.clock import SystemClock
from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.errors import DomainError
from stokguard.core.maintenance import operation_slot
from stokguard.drafts.router import router as drafts_router
from stokguard.files.router import router as files_router
from stokguard.inventory.router import router as inventory_router
from stokguard.investigations.router import router as cases_router
from stokguard.ocr.router import router as ocr_router
from stokguard.products.router import router as products_router
from stokguard.risk.router import router as risk_router
from stokguard.stocktakes.router import router as stocktakes_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title="StokGuard API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.clock = SystemClock()
    app.state.login_limiter = LoginLimiter()
    app.include_router(auth_router)
    app.include_router(business_router)
    app.include_router(products_router)
    app.include_router(inventory_router)
    app.include_router(audit_router)
    app.include_router(stocktakes_router)
    app.include_router(cases_router)
    app.include_router(approvals_router)
    app.include_router(risk_router)
    app.include_router(files_router)
    app.include_router(ocr_router)
    app.include_router(drafts_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "Authorization"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            try:
                with operation_slot(app.state.settings, f"http-{request.method.lower()}"):
                    response = await call_next(request)
            except DomainError as exc:
                response = error_response(request, exc)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def error_response(request: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status,
            headers={"Retry-After": "900"} if error.status == 429 else None,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "fields": error.fields,
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        fields = {
            ".".join(str(part) for part in item["loc"]): "Nilai tidak valid."
            for item in error.errors()
        }
        return error_response(
            request, DomainError("validation_error", 422, "Periksa isian Anda.", fields)
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return error_response(
            request,
            DomainError("http_error", error.status_code, "Permintaan tidak dapat diproses."),
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
app = create_app()