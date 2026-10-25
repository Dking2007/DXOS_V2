# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("dx.errors")


class AppError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status, self.code, self.detail = status, code, detail
        super().__init__(detail)


def install_handlers(app: FastAPI):
    @app.middleware("http")
    async def trace(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        try:
            trace_id = str(uuid.UUID(incoming))
        except ValueError:
            trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    def response(request, status, code, detail):
        return JSONResponse(
            status_code=status,
            content={
                "status": status,
                "code": code,
                "detail": detail,
                "trace_id": getattr(request.state, "trace_id", ""),
            },
        )

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return response(request, exc.status, exc.code, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc):
        return response(
            request,
            422,
            "validation_error",
            "Dữ liệu không hợp lệ: "
            + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()),
        )

    @app.exception_handler(IntegrityError)
    async def conflict(request: Request, exc):
        return response(request, 409, "conflict", "Dữ liệu đã thay đổi hoặc khóa thao tác đã được sử dụng.")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc):
        logger.error(
            "request_failed trace_id=%s type=%s", getattr(request.state, "trace_id", ""), type(exc).__name__
        )
        return response(
            request, 500, "internal_error", "Không thể hoàn tất thao tác. Dùng mã truy vết để kiểm tra."
        )
