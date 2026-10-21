from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import httpx
import jwt
from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DriveFile, OfficeSave, OfficeSession, uid, utcnow
from .policies import current_user, file_access, get_file
from .services import audit


def callback_claims(secret: str, body: dict, authorization: str = ""):
    token = body.get("token") or (authorization[7:] if authorization.startswith("Bearer ") else "")
    if not secret or not token:
        raise AppError(401, "office_signature_required", "Callback Office thiếu chữ ký.")
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError as exc:
        raise AppError(401, "office_signature_invalid", "Chữ ký callback Office không hợp lệ.") from exc
    signed = claims.get("payload", claims)
    for key in ("key", "status", "url", "forcesavetype"):
        if body.get(key) != signed.get(key):
            raise AppError(401, "office_payload_mismatch", "Nội dung callback không khớp chữ ký.")
    return signed


def allowed_save_url(url: str, internal_url: str) -> bool:
    try:
        target, allowed = urlparse(url), urlparse(internal_url)
        return bool(
            target.scheme in {"http", "https"}
            and not target.username
            and not target.password
            and target.scheme == allowed.scheme
            and target.hostname == allowed.hostname
            and (target.port or (443 if target.scheme == "https" else 80))
            == (allowed.port or (443 if allowed.scheme == "https" else 80))
        )
    except ValueError:
        return False


def save_source_url(url: str, public_url: str, internal_url: str) -> str | None:
    """Where to download a save from, or None when the URL is not the configured Document Server.

    Behind the gateway, Document Server builds save links from the address the browser used
    (ONLYOFFICE_PUBLIC_URL, e.g. http://localhost:8080/office/...). That address is not
    reachable from inside the Workspace container, so a link under exactly that prefix is
    fetched from ONLYOFFICE_INTERNAL_URL instead; every other host stays refused.
    """
    if allowed_save_url(url, internal_url):
        return url
    try:
        target, public = urlparse(url), urlparse(public_url)
    except ValueError:
        return None
    prefix = public.path.rstrip("/") + "/"
    if not (allowed_save_url(url, public_url) and target.path.startswith(prefix)):
        return None
    rest = target.path[len(prefix) :]
    return internal_url.rstrip("/") + "/" + rest + (f"?{target.query}" if target.query else "")


def fetch_document(url: str, settings) -> bytes:
    url = save_source_url(url, settings.onlyoffice_public_url, settings.onlyoffice_internal_url)
    if not url:
        raise AppError(403, "office_save_host_denied", "URL lưu không thuộc Document Server đã cấu hình.")
    data = bytearray()
    try:
        with httpx.stream("GET", url, timeout=60, follow_redirects=False) as response:
            if response.status_code != 200:
                raise AppError(503, "office_download_failed", "Document Server chưa cung cấp được bản lưu.")
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > settings.max_upload_bytes:
                    raise AppError(413, "office_save_too_large", "Bản lưu vượt dung lượng cho phép.")
    except httpx.HTTPError as exc:
        raise AppError(503, "office_download_failed", "Không tải được bản lưu từ Document Server.") from exc
    if not data:
        raise AppError(422, "office_empty_save", "Document Server trả nội dung rỗng.")
    return bytes(data)


def office_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["office"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    @router.post("/drive/files/{file_id}/office-sessions")
    def open_office(file_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        if not settings.onlyoffice_enabled or not settings.onlyoffice_jwt_secret:
            raise AppError(
                503,
                "office_not_configured",
                "ONLYOFFICE chưa bật. Chạy profile office và cấu hình JWT secret.",
            )
        user = current_user(db, actor)
        file = get_file(db, user, file_id)
        editable = file_access(db, user, file, True)
        extension = file.name.rsplit(".", 1)[-1].lower()
        types = {"docx": "word", "xlsx": "cell", "pptx": "slide"}
        if extension not in types:
            raise AppError(422, "office_format_unsupported", "Bản pilot hỗ trợ DOCX, XLSX và PPTX.")
        # Lock the logical file before choosing a shared session/key.
        db.scalar(select(DriveFile).where(DriveFile.id == file_id).with_for_update())
        session = (
            db.scalar(
                select(OfficeSession)
                .where(
                    OfficeSession.file_id == file_id,
                    OfficeSession.state.in_(["open", "saving", "save_failed"]),
                )
                .order_by(OfficeSession.created_at.desc())
            )
            if editable
            else None
        )
        metadata, version = app.state.core_service.file_version(file.core_file_id)
        if session and session.state == "save_failed":
            raise AppError(
                409,
                "office_save_failed",
                "Phiên trước chưa lưu được. Kiểm tra lỗi đồng bộ trước khi mở tiếp.",
            )
        if session is None:
            session = OfficeSession(
                file_id=file_id,
                document_key=uid().replace("-", ""),
                base_version_id=version["id"],
                base_revision=metadata["revision"],
                state="open" if editable else "view",
            )
            db.add(session)
            db.flush()
        content_token = jwt.encode(
            {
                "session_id": session.id,
                "purpose": "office-content",
                "exp": datetime.now(UTC) + timedelta(hours=8),
            },
            settings.onlyoffice_jwt_secret,
            algorithm="HS256",
        )
        document_url = (
            settings.internal_base_url.rstrip("/")
            + f"/workspace/v1/office/content/{session.id}?"
            + urlencode({"token": content_token})
        )
        callback_url = settings.internal_base_url.rstrip("/") + f"/workspace/v1/office/callback/{session.id}"
        config = {
            "documentType": types[extension],
            "type": "desktop",
            "width": "100%",
            "height": "100%",
            "document": {
                "fileType": extension,
                "key": session.document_key,
                "title": file.name,
                "url": document_url,
                "permissions": {"edit": editable, "download": True, "print": True},
            },
            "editorConfig": {
                "mode": "edit" if editable else "view",
                "lang": "vi",
                "callbackUrl": callback_url,
                "user": {"id": user.id, "name": user.display_name},
                "customization": {"forcesave": True},
            },
        }
        config["token"] = jwt.encode(config, settings.onlyoffice_jwt_secret, algorithm="HS256")
        audit(
            db,
            user,
            "office.opened",
            file_id,
            {"session_id": session.id, "mode": "edit" if editable else "view"},
        )
        db.commit()
        return {
            "session_id": session.id,
            "document_server_url": settings.onlyoffice_public_url.rstrip("/"),
            "config": config,
        }

    @router.get("/office/content/{session_id}")
    def office_content(session_id: str, token: str, db: Session = Depends(db_dep)):
        try:
            claims = jwt.decode(
                token, settings.onlyoffice_jwt_secret, algorithms=["HS256"], options={"require": ["exp"]}
            )
        except jwt.PyJWTError as exc:
            raise AppError(
                401, "office_content_ticket_invalid", "Ticket nội dung Office không hợp lệ."
            ) from exc
        session = db.get(OfficeSession, session_id)
        if (
            not session
            or claims.get("session_id") != session_id
            or claims.get("purpose") != "office-content"
            or session.state not in {"open", "saving", "view", "save_failed"}
        ):
            raise AppError(403, "office_content_ticket_invalid", "Phiên Office không còn hiệu lực.")
        file = db.get(DriveFile, session.file_id)
        if not file or file.deleted_at or file.acl_state != "ready":
            raise AppError(403, "office_file_unavailable", "Tài liệu không còn khả dụng.")
        ticket = app.state.core_service.post(
            f"/storage/versions/{session.base_version_id}/download-tickets", {}
        )
        data = app.state.core_service.get(f"/storage/download/{ticket['ticket']}", raw=True)
        return Response(data, media_type=file.mime, headers={"Content-Disposition": "attachment"})

    @router.post("/office/callback/{session_id}")
    async def office_callback(session_id: str, request: Request, db: Session = Depends(db_dep)):
        if not settings.onlyoffice_enabled:
            raise AppError(503, "office_not_configured", "ONLYOFFICE chưa bật.")
        if int(request.headers.get("Content-Length", "0")) > 1024 * 1024:
            raise AppError(413, "callback_too_large", "Callback vượt giới hạn.")
        body = await request.json()
        callback_claims(settings.onlyoffice_jwt_secret, body, request.headers.get("Authorization", ""))
        session_file_id = db.scalar(select(OfficeSession.file_id).where(OfficeSession.id == session_id))
        if not session_file_id:
            raise AppError(403, "office_session_mismatch", "Callback không thuộc phiên chỉnh sửa.")
        file = db.scalar(
            select(DriveFile)
            .where(DriveFile.id == session_file_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        session = db.scalar(
            select(OfficeSession)
            .where(OfficeSession.id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not session or session.document_key != body.get("key"):
            raise AppError(403, "office_session_mismatch", "Callback không thuộc phiên chỉnh sửa.")
        status = body.get("status")
        if session.state in {"closed", "view"}:
            return {"error": 0}
        if status in {3, 7}:
            session.state, session.error, session.updated_at = (
                "save_failed",
                "document_server_save_error",
                utcnow(),
            )
            db.commit()
            return {"error": 0}
        if status == 4:
            if session.state == "save_failed":
                # A disconnect after a failed save must not make an old version submittable.
                return {"error": 1}
            session.state, session.updated_at = "closed", utcnow()
            db.commit()
            return {"error": 0}
        if status == 1:
            return {"error": 0}
        if status not in {2, 6} or not body.get("url"):
            raise AppError(422, "office_callback_invalid", "Trạng thái callback không hợp lệ.")
        if not file or file.deleted_at:
            return {"error": 1}
        try:
            data = fetch_document(body["url"], settings)
            checksum = hashlib.sha256(data).hexdigest()
            fingerprint = checksum
            old = db.scalar(
                select(OfficeSave).where(
                    OfficeSave.session_id == session.id, OfficeSave.fingerprint == fingerprint
                )
            )
            if old:
                if status == 2:
                    session.state, session.error, session.updated_at = "closed", None, utcnow()
                    db.commit()
                return {"error": 0}
            metadata, current_version = app.state.core_service.file_version(file.core_file_id)
            if metadata["revision"] != session.base_revision and current_version.get("checksum") != checksum:
                raise AppError(
                    409, "office_late_save", "Phiên bản mới hơn đã tồn tại; callback cũ không được ghi đè."
                )
            if current_version.get("checksum") == checksum:
                saved = metadata
                version_id = current_version["id"]
            else:
                saved = app.state.core_service.request(
                    "POST",
                    f"/storage/files/{file.core_file_id}/versions",
                    content=data,
                    params={"expected_revision": session.base_revision, "source": "onlyoffice"},
                    headers={"Content-Type": file.mime},
                    key="office:" + session.id + ":" + checksum,
                )
                version_id = saved.get("current_version_id") or saved.get("version", {}).get("id")
            db.add(
                OfficeSave(
                    session_id=session.id, fingerprint=fingerprint, status=status, core_version_id=version_id
                )
            )
            session.base_revision = saved["revision"]
            session.state = "closed" if status == 2 else "open"
            session.error = None
            session.updated_at = utcnow()
            file.size = len(data)
            file.revision += 1
            db.commit()
            return {"error": 0}
        except AppError as exc:
            session.state, session.error, session.updated_at = "save_failed", exc.code, utcnow()
            db.commit()
            return {"error": 1}

    return router
