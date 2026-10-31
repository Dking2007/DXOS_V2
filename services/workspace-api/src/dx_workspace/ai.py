# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""AI features across the app: dossiers, documents, work, conversations, and their settings.

Every endpoint checks the same permissions as the screen it serves before reading anything,
sends only what that person may see, and returns suggestions for a person to accept. Nothing
here decides, submits, approves or assigns on its own.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Literal

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends
from jsonschema import Draft202012Validator
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ai_core, ai_docx, ai_index, ai_text
from . import assistant_llm as llm
from . import models as m
from . import schemas as s
from .policies import (
    approval_assignees,
    case_filter,
    current_user,
    file_access,
    folder_access,
    get_case,
    get_file,
    membership,
    permissions,
    require,
)
from .services import audit, enqueue, serial
from .tasks import visible as task_visible
from .text import fold

MANAGE = "assistant.manage"
VIETNAM = timezone(timedelta(hours=7))
WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
STATUS_TEXT = {
    "draft": "bản nháp",
    "pending_workflow_start": "đang khởi tạo luồng duyệt",
    "processing": "đang chờ duyệt",
    "needs_revision": "bị trả lại, cần chỉnh sửa",
    "approved": "đã được duyệt",
    "rejected": "bị từ chối",
    "cancelled": "đã hủy",
    "assigned": "mới giao",
    "accepted": "đã nhận",
    "in_progress": "đang làm",
    "submitted": "đã nộp, chờ nghiệm thu",
    "returned": "bị trả lại",
    "blocked": "vướng mắc",
    "completed": "đã nghiệm thu",
}


class FeatureSetting(s.Input):
    enabled: bool = False
    provider_id: str | None = None
    # A model of that service for this feature only; empty uses the service's default model.
    model: str = Field(default="", max_length=120)


class EmbeddingSetting(s.Input):
    provider_id: str | None = None
    model: str = Field(default="", max_length=120)


class SettingsInput(s.Revision):
    features: dict[str, FeatureSetting]
    embedding: EmbeddingSetting = Field(default_factory=EmbeddingSetting)


class ExtractInput(s.Input):
    file_id: str


class DecisionDraftInput(s.Input):
    decision: Literal["approve", "reject", "return"]
    notes: str = Field(default="", max_length=2000)


class DocumentDraftInput(s.Input):
    kind: Literal["to_trinh", "cong_van", "thong_bao", "ke_hoach", "bao_cao", "giay_moi"]
    points: str = Field(min_length=5, max_length=6000)
    recipients: str = Field(default="", max_length=500)
    signer_title: str = Field(default="", max_length=120)
    signer_name: str = Field(default="", max_length=120)
    folder_id: str | None = None


class QuestionInput(s.Input):
    question: str = Field(min_length=2, max_length=1000)


class SearchInput(s.Input):
    q: str = Field(min_length=2, max_length=300)
    limit: int = Field(default=12, ge=1, le=30)


class TaskTextInput(s.Input):
    text: str = Field(min_length=3, max_length=2000)


class NarrativeInput(s.Input):
    days: int = Field(default=30, ge=1, le=366)
    scope: Literal["all", "mine", "managed"] = "all"


class ChatSummaryInput(s.Input):
    limit: int = Field(default=150, ge=10, le=400)


class WriteInput(s.Input):
    action: Literal["rewrite", "proofread", "title"]
    text: str = Field(min_length=3, max_length=8000)


def now_vn() -> datetime:
    return datetime.now(UTC).astimezone(VIETNAM)


def today_text() -> str:
    day = now_vn()
    return f"{WEEKDAYS[day.weekday()]}, ngày {day:%d/%m/%Y}"


def quote_on_page(document: ai_text.Document, page: int, quote: str) -> bool:
    """Whether the quoted words really are on that page (ignoring case, accents and spacing)."""
    target = " ".join(fold(quote).split())
    for item in document.pages:
        if item.number == page and target and target in " ".join(fold(item.text).split()):
            return True
    return False


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["ai"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def transport():
        return getattr(app.state, "assistant_transport", None)

    def user_for(db, actor) -> m.User:
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        return current_user(db, actor)

    def ask(db, user, feature, system, prompt, **options) -> str:
        return ai_core.ask(db, settings, user, feature, system, prompt, transport=transport(), **options)

    def ask_json(db, user, feature, system, prompt, **options):
        return ai_core.ask_json(db, settings, user, feature, system, prompt, transport=transport(), **options)

    def load(db, feature: str, file: m.DriveFile, version_id: str | None = None):
        """A file's text, plus the file itself when its text is not enough and the service can look."""
        data, version_id = ai_core.file_bytes(app.state.core_service, file, version_id)
        document = ai_text.read(file.name, file.mime, data)
        attachment = None
        if not document.has_text:
            kind = ai_core.provider_for(db, feature).kind
            if document.is_image or (ai_text.kind_of(file.name, file.mime) == "pdf" and llm.reads_pdf(kind)):
                attachment = llm.Attachment(file.name, document.mime, data)
            else:
                raise AppError(
                    422,
                    "ai_file_unreadable",
                    "Không đọc được chữ trong tệp này. Tệp scan hoặc ảnh cần dịch vụ AI đọc được ảnh và PDF.",
                )
        return document, attachment, version_id

    # ---- Who may use what -----------------------------------------------------------

    @router.get("/ai/features")
    def features(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        enabled = ai_core.enabled_features(db)
        result = {
            "enabled": enabled,
            "semantic_ready": "semantic_search" in enabled and ai_index.provider(db) is not None,
            "remaining": ai_core.remaining(db, user),
        }
        db.commit()
        return result

    # ---- Settings (same people as the help chat) -------------------------------------

    def manager(db, actor):
        user = user_for(db, actor)
        require(db, user, MANAGE)
        return user

    def settings_data(db):
        config = ai_core.config(db)
        chosen = config.features or {}
        providers = list(db.scalars(select(m.AssistantProvider).order_by(m.AssistantProvider.created_at)))
        return {
            "revision": config.revision,
            "groups": [{"key": k, "label": v} for k, v in ai_core.GROUPS.items()],
            "features": [
                {
                    "key": key,
                    "group": group,
                    "label": label,
                    "description": description,
                    "needs_vision": vision,
                    "enabled": bool((chosen.get(key) or {}).get("enabled")),
                    "provider_id": (chosen.get(key) or {}).get("provider_id"),
                    "model": (chosen.get(key) or {}).get("model", ""),
                }
                for key, (group, label, description, vision) in ai_core.FEATURES.items()
            ],
            "embedding": {
                "provider_id": (config.embedding or {}).get("provider_id"),
                "model": (config.embedding or {}).get("model", ""),
            },
            "providers": [
                {
                    "id": p.id,
                    "name": p.name,
                    "kind": p.kind,
                    "model": p.model,
                    "active": p.active,
                    "embeds": p.kind in llm.EMBED_KINDS,
                    "reads_pdf": llm.reads_pdf(p.kind),
                    "sees_images": p.kind not in llm.NO_FILES,
                }
                for p in providers
            ],
            "index": ai_index.status(db),
        }

    @router.get("/ai/settings")
    def get_settings(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        manager(db, actor)
        data = settings_data(db)
        db.commit()
        return data

    @router.put("/ai/settings")
    def put_settings(body: SettingsInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        config = ai_core.config(db)
        if config.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Cấu hình đã được người khác sửa. Tải lại trang.")
        unknown = set(body.features) - set(ai_core.FEATURES)
        if unknown:
            raise AppError(422, "ai_feature_unknown", "Có tính năng AI không tồn tại.")
        for key, value in body.features.items():
            chosen = db.get(m.AssistantProvider, value.provider_id) if value.provider_id else None
            if value.provider_id and not chosen:
                raise AppError(422, "provider_not_found", "Dịch vụ AI được chọn không còn tồn tại.")
            value.model = value.model.strip()
            if value.model and not chosen:
                raise AppError(
                    422,
                    "ai_model_needs_provider",
                    f"“{ai_core.FEATURES[key][1]}”: chọn dịch vụ trước khi chọn model.",
                )
            if value.model:
                try:
                    llm.check_model(chosen.kind, value.model)
                except llm.LlmError as exc:
                    raise AppError(422, exc.code, exc.message) from exc
        embedding = {}
        if body.embedding.provider_id:
            chosen = db.get(m.AssistantProvider, body.embedding.provider_id)
            if not chosen or chosen.kind not in llm.EMBED_KINDS:
                raise AppError(422, "assistant_embed_unsupported", "Dịch vụ này không tạo được vector.")
            if not body.embedding.model.strip():
                raise AppError(422, "assistant_model_invalid", "Nhập tên model tạo vector, ví dụ bge-m3.")
            try:
                llm.check_model(chosen.kind, body.embedding.model.strip())
            except llm.LlmError as exc:
                raise AppError(422, exc.code, exc.message) from exc
            embedding = {"provider_id": chosen.id, "model": body.embedding.model.strip()}
        changed_embedding = embedding != (config.embedding or {})
        config.features = {key: value.model_dump() for key, value in body.features.items()}
        config.embedding = embedding
        config.revision += 1
        config.updated_at = m.utcnow()
        if changed_embedding and embedding:
            enqueue(db, "ai.index", "all", {"all": True})
        audit(db, user, "assistant.features_updated", "default", {"enabled": ai_core.enabled_features(db)})
        db.commit()
        return settings_data(db)

    @router.post("/ai/index")
    def reindex(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        if not ai_index.provider(db):
            raise AppError(409, "ai_embedding_off", "Chọn dịch vụ và model tạo vector trước.")
        enqueue(db, "ai.index", "all", {"all": True})
        audit(db, user, "assistant.index_requested", "default")
        db.commit()
        return {"queued": True}

    @router.post("/ai/settings/test-embedding")
    def test_embedding(
        body: EmbeddingSetting, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        manager(db, actor)
        chosen = db.get(m.AssistantProvider, body.provider_id or "")
        if not chosen:
            raise AppError(404, "provider_not_found", "Không tìm thấy dịch vụ AI.")
        from dx_platform.security import SecretBox

        box = SecretBox(settings.credential_encryption_key)
        try:
            [vector] = llm.embed(
                chosen.kind,
                body.model.strip(),
                box.decrypt(chosen.secret) if chosen.secret else "",
                ["Kiểm tra kết nối tạo vector"],
                base_url=chosen.base_url,
                allowed_hosts=ai_core.allowed_hosts(settings),
                transport=transport(),
            )
        except llm.LlmError as exc:
            return {"ok": False, "message": exc.message}
        return {"ok": True, "message": f"Tạo được vector {len(vector)} chiều."}

    # ---- 1–4. Dossiers ---------------------------------------------------------------

    def form_fields_text(form: m.Form) -> str:
        lines = []
        for field in form.fields:
            extra = (
                f"; chọn một trong: {', '.join(field.get('options') or [])}" if field.get("options") else ""
            )
            lines.append(f"- {field['key']}: {field['label']} (kiểu {field['type']}{extra})")
        return "\n".join(lines)

    def payload_text(form: m.Form, payload: dict) -> str:
        labels = {f["key"]: f["label"] for f in form.fields}
        return "\n".join(f"- {labels.get(k, k)}: {v}" for k, v in payload.items() if v not in (None, "", []))

    def editable_case(db, user, case_id):
        case = get_case(db, user, case_id)
        if case.owner_id != user.id or case.status not in {"draft", "needs_revision"}:
            raise AppError(
                409, "case_not_editable", "Chỉ người lập được dùng tính năng này khi hồ sơ là bản nháp."
            )
        return case

    def case_payload(case: m.Case) -> dict:
        return app.state.core_service.get(f"/records/{case.payload_record_id}")["payload"]

    def attachments_text(db, user, case: m.Case, feature: str, limit_files=3, limit_chars=12000) -> str:
        parts = []
        for file_id in case.file_ids[:limit_files]:
            file = db.get(m.DriveFile, file_id)
            if not file or file.deleted_at or not file_access(db, user, file):
                continue
            try:
                data, _ = ai_core.file_bytes(app.state.core_service, file)
            except AppError:
                continue
            document = ai_text.read(file.name, file.mime, data)
            body = (
                document.as_prompt(limit_chars)
                if document.has_text
                else "(không đọc được chữ, có thể là ảnh hoặc bản scan)"
            )
            parts.append(f"### Tệp: {file.name}\n{body}")
        return "\n\n".join(parts) or "(không có tài liệu đính kèm đọc được)"

    @router.post("/ai/cases/{case_id}/extract")
    def extract(
        case_id: str, body: ExtractInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        """1. Read an attached file and propose a value, with page and quote, for each field."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "case_extract")
        case = editable_case(db, user, case_id)
        if body.file_id not in case.file_ids:
            raise AppError(422, "source_not_attached", "Tài liệu chưa được đính kèm hồ sơ.")
        file = get_file(db, user, body.file_id)
        form = db.get(m.Form, case.form_id)
        document, attachment, version_id = load(db, "case_extract", file)
        content = (
            "Tài liệu đính kèm (đã gửi kèm dạng tệp)." if attachment else ai_core.wrap(document.as_prompt())
        )
        provider = ai_core.provider_for(db, "case_extract")
        answer = ask_json(
            db,
            user,
            "case_extract",
            "Bạn trích thông tin từ tài liệu hành chính tiếng Việt để điền biểu mẫu. Chỉ điền trường có giá trị "
            "ghi rõ trong tài liệu, không suy đoán. Số tiền ghi bằng số nguyên (đồng), ngày theo YYYY-MM-DD.",
            f"Các trường của biểu mẫu “{form.name}”:\n{form_fields_text(form)}\n\n"
            f"Tài liệu “{file.name}”, mỗi phần đánh dấu [{document.unit} N]:\n{content}\n\n"
            'Trả về {"fields": [{"key": "...", "value": ..., "page": số trang, "quote": "câu nguyên văn trong '
            'tài liệu chứa giá trị"}]}. Bỏ qua trường không tìm thấy.',
            files=[attachment] if attachment else None,
        )
        schema = s.json_schema(form.fields)["properties"]
        _, version = app.state.core_service.file_version(file.core_file_id)
        created, skipped = [], []
        for item in (answer.get("fields") if isinstance(answer, dict) else None) or []:
            key, value = item.get("key"), item.get("value")
            quote = str(item.get("quote") or "").strip()[:1500]
            page = item.get("page") if isinstance(item.get("page"), int) and item.get("page") >= 1 else 1
            if key not in schema or not quote:
                skipped.append({"key": key, "reason": "Không có trường này hoặc thiếu câu trích."})
                continue
            if list(Draft202012Validator(schema[key]).iter_errors(value)):
                skipped.append({"key": key, "reason": f"Giá trị “{value}” không đúng kiểu của trường."})
                continue
            if document.has_text and not quote_on_page(document, page, quote):
                skipped.append({"key": key, "reason": "Câu trích không có trong trang AI chỉ ra."})
                continue
            row = m.FieldEvidence(
                case_id=case.id,
                field_key=key,
                source_file_id=file.id,
                source_version_id=version_id,
                source_checksum=version.get("checksum", ""),
                source_page=min(page, 10000),
                source_quote=quote,
                suggested_value={"value": value},
                source_kind="ai",
                provenance={
                    "feature": "case_extract",
                    "provider": provider.kind,
                    "model": ai_core.model_for(db, "case_extract", provider),
                    "prompt_version": ai_core.PROMPT_VERSION,
                    "requested_by": user.id,
                },
                created_by_id=user.id,
            )
            db.add(row)
            db.flush()
            created.append(serial(row))
        audit(db, user, "field_evidence.ai_extracted", case.id, {"file_id": file.id, "created": len(created)})
        db.commit()
        return {"created": created, "skipped": skipped}

    def summary_key(db, case: m.Case) -> str:
        decided = db.scalar(
            select(m.ApprovalTask.id)
            .where(m.ApprovalTask.case_id == case.id, m.ApprovalTask.decided_at.is_not(None))
            .order_by(m.ApprovalTask.decided_at.desc())
            .limit(1)
        )
        return "case-summary:" + ai_core.fingerprint(
            case.id, case.submission_no, case.payload_revision, case.file_ids, decided, ai_core.PROMPT_VERSION
        )

    @router.get("/ai/cases/{case_id}/summary")
    def stored_summary(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        case = get_case(db, user, case_id)
        return {"summary": ai_core.cached(db, summary_key(db, case))}

    @router.post("/ai/cases/{case_id}/summary")
    def make_summary(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """2. A few lines for the approver: what is asked, how much, what is attached, who said what."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "case_summary")
        case = get_case(db, user, case_id)
        form = db.get(m.Form, case.form_id)
        history = []
        for task in db.scalars(
            select(m.ApprovalTask)
            .where(m.ApprovalTask.case_id == case.id)
            .order_by(m.ApprovalTask.created_at)
        ):
            if task.decision:
                person = db.get(m.User, task.decided_by_id or task.assignee_id)
                history.append(
                    f"- {task.label}: {person.display_name if person else ''} "
                    f"{ {'approve': 'đồng ý', 'reject': 'từ chối', 'return': 'trả lại'}.get(task.decision, task.decision) }"
                    + (f" — “{task.reason}”" if task.reason else "")
                )
        answer = ask_json(
            db,
            user,
            "case_summary",
            "Bạn tóm tắt hồ sơ trình duyệt cho lãnh đạo đọc trong 10 giây. Chỉ dùng thông tin được cung cấp, "
            "nêu số liệu cụ thể, không đánh giá thay người duyệt.",
            ai_core.wrap(
                f"Hồ sơ HS-{case.number:06d}: {case.title}\nMẫu: {form.name}\n"
                f"Nội dung biểu mẫu:\n{payload_text(form, case_payload(case))}\n\n"
                f"Ý kiến các bước trước:\n{chr(10).join(history) or '(chưa có)'}\n\n"
                f"Tài liệu kèm:\n{attachments_text(db, user, case, 'case_summary', limit_chars=6000)}"
            )
            + '\n\nTrả về {"lines": ["3 đến 5 dòng ngắn"]}: nội dung xin duyệt; số tiền/số lượng; tài liệu kèm '
            "và điểm chính; ý kiến các bước trước (nếu có).",
            max_tokens=1200,
        )
        lines = [
            str(x).strip()
            for x in (answer.get("lines") if isinstance(answer, dict) else answer) or []
            if str(x).strip()
        ]
        content = {"lines": lines[:6], "created_at": m.utcnow().isoformat()}
        ai_core.store(db, "case_summary", summary_key(db, case), content)
        db.commit()
        return {"summary": content}

    @router.post("/ai/cases/{case_id}/check")
    def check_case(case_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """3. Before submitting: what might be wrong, from fixed rules and from the attachments."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "case_check")
        case = editable_case(db, user, case_id)
        form = db.get(m.Form, case.form_id)
        payload = case_payload(case)
        issues = []
        try:
            s.validate_payload(form, payload)
        except AppError as exc:
            issues.append({"level": "error", "message": exc.detail, "source": "rule"})
        version = db.get(m.PackageVersion, case.package_version_id) if case.package_version_id else None
        if version and len(case.file_ids) < version.required_file_count:
            issues.append(
                {
                    "level": "error",
                    "message": f"Gói nghiệp vụ cần ít nhất {version.required_file_count} tài liệu, hồ sơ mới có {len(case.file_ids)}.",
                    "source": "rule",
                }
            )
        answer = ask_json(
            db,
            user,
            "case_check",
            "Bạn soát hồ sơ trước khi trình duyệt. So nội dung biểu mẫu với tài liệu kèm: số tiền, ngày, tên, "
            "số lượng không khớp; tài liệu có vẻ thiếu chữ ký, dấu, ngày; thông tin còn trống quan trọng. Chỉ nêu "
            "điều có căn cứ trong dữ liệu, mỗi điều một câu ngắn. Không có gì đáng lưu ý thì trả danh sách rỗng.",
            ai_core.wrap(
                f"Hồ sơ: {case.title}\nMẫu: {form.name}\nNội dung biểu mẫu:\n{payload_text(form, payload)}\n\n"
                f"Tài liệu kèm:\n{attachments_text(db, user, case, 'case_check')}"
            )
            + '\n\nTrả về {"issues": [{"level": "error|warning|info", "message": "..."}]}.',
            max_tokens=1500,
        )
        for item in (answer.get("issues") if isinstance(answer, dict) else None) or []:
            level = item.get("level") if item.get("level") in {"error", "warning", "info"} else "warning"
            if str(item.get("message") or "").strip():
                issues.append({"level": level, "message": str(item["message"]).strip()[:500], "source": "ai"})
        db.commit()
        return {"issues": issues, "ok": not any(i["level"] == "error" for i in issues)}

    @router.post("/ai/cases/{case_id}/decision-draft")
    def decision_draft(
        case_id: str,
        body: DecisionDraftInput,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """4. A polite approval note or return reason, for the person deciding to edit."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "decision_draft")
        case = get_case(db, user, case_id)
        pending = db.scalar(
            select(m.ApprovalTask).where(
                m.ApprovalTask.case_id == case.id,
                m.ApprovalTask.state == "pending",
                m.ApprovalTask.assignee_id.in_(approval_assignees(db, user)),
            )
        )
        if not pending:
            raise AppError(403, "not_your_decision", "Bạn không có bước duyệt nào đang chờ ở hồ sơ này.")
        form = db.get(m.Form, case.form_id)
        intent = {
            "approve": "ý kiến phê duyệt",
            "reject": "lý do từ chối",
            "return": "lý do trả lại để chỉnh sửa",
        }[body.decision]
        answer = ask(
            db,
            user,
            "decision_draft",
            "Bạn soạn giúp lãnh đạo một đoạn ngắn (2–4 câu), giọng hành chính, lịch sự, cụ thể. Với trả lại "
            "hoặc từ chối, nêu rõ cần bổ sung hay điều chỉnh gì. Chỉ trả về đoạn văn, không thêm lời dẫn.",
            ai_core.wrap(
                f"Hồ sơ: {case.title}\nBước duyệt: {pending.label}\nNội dung:\n{payload_text(form, case_payload(case))}\n"
                f"Ghi chú của người duyệt: {body.notes or '(không có)'}"
            )
            + f"\n\nSoạn {intent}.",
            max_tokens=600,
        )
        db.commit()
        return {"text": answer.strip()[:3000]}

    # ---- 5–8. Documents ---------------------------------------------------------------

    @router.post("/ai/documents/draft", status_code=201)
    def draft_document(
        body: DocumentDraftInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        """5. Turn a few points into an administrative document laid out per Decree 30."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "document_draft")
        require(db, user, "drive.use")
        department = db.get(m.Department, user.department_id) if user.department_id else None
        label = ai_docx.KIND_LABELS[body.kind]
        answer = ask_json(
            db,
            user,
            "document_draft",
            "Bạn là chuyên viên văn thư, soạn văn bản hành chính tiếng Việt theo Nghị định 30/2020/NĐ-CP: câu "
            "văn trang trọng, rõ ràng, không dùng từ địa phương, không bịa số liệu ngoài các ý được cho.",
            f"Loại văn bản: {label}\nNgười nhận: {body.recipients or '(tự đề xuất phù hợp)'}\n"
            f"Các ý chính:\n{ai_core.wrap(body.points)}\n\n"
            'Trả về {"subject": "trích yếu ngắn, không viết hoa toàn bộ", "recipients": ["nơi nhận ở mục Kính '
            'gửi"], "paragraphs": ["từng đoạn nội dung"], "copies": ["nơi nhận cuối văn bản, ví dụ Như trên;"]}.',
            max_tokens=3000,
        )
        if not isinstance(answer, dict) or not answer.get("paragraphs"):
            raise AppError(502, "ai_bad_json", "AI chưa soạn được nội dung. Thử lại với ý chính rõ hơn.")
        today = now_vn()
        draft = ai_docx.Draft(
            kind=body.kind,
            subject=str(answer.get("subject") or label).strip()[:300],
            paragraphs=[str(p) for p in answer["paragraphs"]][:40],
            agency=department.name if department else "TÊN CƠ QUAN",
            place_date=f"......, ngày {today.day:02d} tháng {today.month:02d} năm {today.year}",
            recipients=[str(r) for r in (answer.get("recipients") or [])][:10]
            if body.kind in {"to_trinh", "cong_van", "giay_moi"}
            else [],
            signer_title=body.signer_title or "THỦ TRƯỞNG CƠ QUAN",
            signer_name=body.signer_name,
            copies=[str(c) for c in (answer.get("copies") or [])][:10],
        )
        name = re.sub(r"[\\/:*?\"<>|]+", "", f"{label} - {draft.subject}")[:120].strip() + ".docx"
        created = app.state.save_upload(
            db, actor, user, name, ai_docx.MIME, ai_docx.build(draft), body.folder_id, m.uid()
        )
        return created

    def file_for(db, user, file_id) -> m.DriveFile:
        file = get_file(db, user, file_id)
        if file.acl_state != "ready":
            raise AppError(409, "file_not_ready", "Tài liệu chưa sẵn sàng.")
        return file

    @router.post("/ai/files/{file_id}/summary")
    def summarize_file(file_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """6a. A short summary of a document, each point with the page it comes from."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "document_qa")
        file = file_for(db, user, file_id)
        _, version = app.state.core_service.file_version(file.core_file_id)
        key = "file-summary:" + ai_core.fingerprint(file.id, version["id"], ai_core.PROMPT_VERSION)
        stored = ai_core.cached(db, key)
        if stored:
            return stored
        document, attachment, _ = load(db, "document_qa", file, version["id"])
        answer = ask_json(
            db,
            user,
            "document_qa",
            "Bạn tóm tắt tài liệu cho cán bộ đọc nhanh. Mỗi ý ghi kèm số trang nguồn.",
            f"Tài liệu “{file.name}”:\n"
            + ("(đã gửi kèm dạng tệp)" if attachment else ai_core.wrap(document.as_prompt()))
            + '\n\nTrả về {"points": [{"text": "một ý ngắn", "page": số}], "kind": "loại tài liệu"}. 3 đến 7 ý.',
            files=[attachment] if attachment else None,
            max_tokens=1500,
        )
        points = [
            {
                "text": str(p.get("text") or "").strip(),
                "page": p.get("page") if isinstance(p.get("page"), int) else None,
            }
            for p in (answer.get("points") if isinstance(answer, dict) else None) or []
            if isinstance(p, dict) and str(p.get("text") or "").strip()
        ]
        result = {
            "points": points[:8],
            "kind": str(answer.get("kind") or "") if isinstance(answer, dict) else "",
            "unit": document.unit,
        }
        ai_core.store(db, "document_qa", key, result)
        db.commit()
        return result

    @router.post("/ai/files/{file_id}/ask")
    def ask_file(
        file_id: str, body: QuestionInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        """6b. Answer a question from the document only, quoting the page it rests on."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "document_qa")
        file = file_for(db, user, file_id)
        document, attachment, _ = load(db, "document_qa", file)
        answer = ask_json(
            db,
            user,
            "document_qa",
            "Bạn trả lời câu hỏi chỉ dựa trên tài liệu. Không có trong tài liệu thì nói rõ là tài liệu không đề cập.",
            f"Tài liệu “{file.name}”:\n"
            + ("(đã gửi kèm dạng tệp)" if attachment else ai_core.wrap(document.as_prompt()))
            + f"\n\nCâu hỏi: {body.question}\n\n"
            'Trả về {"answer": "câu trả lời", "citations": [{"page": số, "quote": "câu nguyên văn làm căn cứ"}]}.',
            files=[attachment] if attachment else None,
            max_tokens=1500,
        )
        citations = []
        for item in (answer.get("citations") if isinstance(answer, dict) else None) or []:
            page, quote = item.get("page"), str(item.get("quote") or "").strip()
            if isinstance(page, int) and quote:
                verified = bool(attachment) or quote_on_page(document, page, quote)
                citations.append({"page": page, "quote": quote[:600], "verified": verified})
        db.commit()
        return {
            "answer": str(answer.get("answer") or "").strip() if isinstance(answer, dict) else "",
            "citations": citations[:5],
            "unit": document.unit,
        }

    @router.post("/ai/search")
    def semantic_search(body: SearchInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """7. Items whose content means what was asked, only those this person may open."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "semantic_search")
        if not ai_index.provider(db):
            raise AppError(409, "ai_embedding_off", "Tìm theo ý nghĩa chưa được cấu hình dịch vụ tạo vector.")
        ai_core.count_call(db, user)
        try:
            ranked = ai_index.nearest(db, settings, body.q, transport())
        except llm.LlmError as exc:
            raise AppError(502, exc.code, exc.message) from exc
        readable_cases = None
        hits = []
        for item in ranked:
            if len(hits) >= body.limit or item["score"] < 0.2:
                break
            if item["ref_type"] == "file":
                file = db.get(m.DriveFile, item["ref_id"])
                if (
                    not file
                    or file.deleted_at
                    or file.acl_state != "ready"
                    or not file_access(db, user, file)
                ):
                    continue
                hits.append(
                    {"type": "file", "id": file.id, "title": file.name, "link": f"/drive?q={file.name}"}
                )
            elif item["ref_type"] == "task":
                task = db.get(m.Task, item["ref_id"])
                if not task or not task_visible(db, user, task):
                    continue
                hits.append({"type": "task", "id": task.id, "title": task.title, "link": f"/tasks/{task.id}"})
            elif item["ref_type"] == "case":
                if readable_cases is None:
                    readable_cases = set(db.scalars(select(m.Case.id).where(case_filter(db, user))))
                case = db.get(m.Case, item["ref_id"]) if item["ref_id"] in readable_cases else None
                if not case:
                    continue
                hits.append({"type": "case", "id": case.id, "title": case.title, "link": f"/cases/{case.id}"})
            else:
                continue
            hits[-1].update(score=round(item["score"], 3), snippet=item["text"][:220])
        db.commit()
        return {"items": hits}

    @router.post("/ai/files/{file_id}/labels")
    def suggest_labels(file_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """8. Labels and a folder that fit a document, from the labels and folders already in use."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "file_labels")
        file = file_for(db, user, file_id)
        known: dict[str, int] = {}
        for labels in db.scalars(
            select(m.DriveFile.labels).where(m.DriveFile.deleted_at.is_(None)).limit(2000)
        ):
            for label in labels or []:
                known[label] = known.get(label, 0) + 1
        common = sorted(known, key=lambda k: -known[k])[:40]
        folders = [
            f
            for f in db.scalars(select(m.Folder).where(m.Folder.deleted_at.is_(None)).limit(300))
            if folder_access(db, user, f, True)
        ][:60]
        try:
            document, attachment, _ = load(db, "file_labels", file)
            content = "(đã gửi kèm dạng tệp)" if attachment else ai_core.wrap(document.as_prompt(8000))
        except AppError:
            document, attachment, content = None, None, "(không đọc được nội dung, chỉ dựa vào tên tệp)"
        answer = ask_json(
            db,
            user,
            "file_labels",
            "Bạn phân loại tài liệu văn phòng. Ưu tiên dùng nhãn đã có; nhãn mới thì ngắn, viết hoa chữ đầu.",
            f"Tên tệp: {file.name}\nNhãn đang dùng: {', '.join(common) or '(chưa có)'}\n"
            f"Thư mục được ghi (id: tên):\n"
            + "\n".join(f"- {f.id}: {f.name}" for f in folders)
            + f"\n\nNội dung:\n{content}\n\n"
            'Trả về {"labels": ["1 đến 3 nhãn"], "folder_id": "id thư mục phù hợp hoặc null", "reason": "một câu"}.',
            files=[attachment] if attachment else None,
            max_tokens=600,
        )
        labels = (
            s.normalize_labels([str(x) for x in (answer.get("labels") or [])][:3])
            if isinstance(answer, dict)
            else []
        )
        folder = next(
            (f for f in folders if isinstance(answer, dict) and f.id == answer.get("folder_id")), None
        )
        db.commit()
        return {
            "labels": labels or [],
            "folder_id": folder.id if folder and folder.id != file.folder_id else None,
            "folder_name": folder.name if folder and folder.id != file.folder_id else None,
            "reason": str(answer.get("reason") or "")[:300] if isinstance(answer, dict) else "",
        }

    # ---- 9–12. Work ------------------------------------------------------------------

    def people(db) -> list[m.User]:
        return list(
            db.scalars(select(m.User).where(m.User.active.is_(True)).order_by(m.User.display_name).limit(400))
        )

    def parse_due(value) -> str | None:
        if not value:
            return None
        try:
            text = str(value)
            due = datetime.fromisoformat(text if "T" in text else text + "T17:00:00")
        except ValueError:
            return None
        if due.tzinfo is None:
            due = due.replace(tzinfo=VIETNAM)
        return due.astimezone(UTC).isoformat()

    @router.post("/ai/tasks/parse")
    def parse_task(body: TaskTextInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """9. Fill the assign-work form from one sentence; the person still reviews and presses Assign."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "task_parse")
        require(db, user, "tasks.create")
        staff = people(db)
        departments = list(db.scalars(select(m.Department)))
        names = {d.id: d.name for d in departments}
        answer = ask_json(
            db,
            user,
            "task_parse",
            "Bạn chuyển câu giao việc tiếng Việt thành phiếu giao việc. Người nhận phải lấy đúng id trong danh "
            "sách; gọi tắt bằng tên (ví dụ “Châu”) thì chọn người có tên cuối khớp, không chắc thì để null. "
            "Ngày tương đối (thứ Sáu, cuối tuần, mai) tính từ hôm nay. Mặc định hạn lúc 17:00.",
            f"Hôm nay: {today_text()}. Người giao: {user.display_name}.\n"
            "Nhân sự (id | tên | đơn vị):\n"
            + "\n".join(f"- {p.id} | {p.display_name} | {names.get(p.department_id, '')}" for p in staff)
            + "\nĐơn vị (id | tên):\n"
            + "\n".join(f"- {d.id} | {d.name}" for d in departments)
            + f"\n\nCâu giao việc:\n{ai_core.wrap(body.text)}\n\n"
            'Trả về {"title": "...", "description": "...", "assignee_id": "id hoặc null", "department_id": "id '
            'hoặc null", "due_at": "YYYY-MM-DDTHH:MM hoặc null", "priority": "low|normal|high|urgent", '
            '"checklist": ["các bước nếu câu có nêu"]}.',
            max_tokens=800,
        )
        if not isinstance(answer, dict) or not str(answer.get("title") or "").strip():
            raise AppError(
                502, "ai_bad_json", "AI chưa hiểu câu giao việc. Viết rõ hơn: giao ai, việc gì, hạn khi nào."
            )
        ids = {p.id for p in staff}
        db.commit()
        return {
            "title": str(answer["title"]).strip()[:250],
            "description": str(answer.get("description") or "").strip()[:4000],
            "assignee_id": answer.get("assignee_id") if answer.get("assignee_id") in ids else None,
            "department_id": answer.get("department_id") if answer.get("department_id") in names else None,
            "due_at": parse_due(answer.get("due_at")),
            "priority": answer.get("priority")
            if answer.get("priority") in {"low", "normal", "high", "urgent"}
            else "normal",
            "checklist": [str(x).strip()[:300] for x in (answer.get("checklist") or []) if str(x).strip()][
                :20
            ],
        }

    @router.post("/ai/tasks/{task_id}/breakdown")
    def breakdown(task_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """10. Steps or sub-tasks for a large task, with suggested due dates before the task's own."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "task_breakdown")
        task = db.get(m.Task, task_id)
        if not task or not task_visible(db, user, task):
            raise AppError(404, "task_not_found", "Không tìm thấy công việc.")
        due = task.due_at.replace(tzinfo=UTC) if task.due_at and task.due_at.tzinfo is None else task.due_at
        answer = ask_json(
            db,
            user,
            "task_breakdown",
            "Bạn chia một công việc văn phòng thành các việc con cụ thể, làm được, theo thứ tự hợp lý. Hạn mỗi "
            "việc con không muộn hơn hạn việc lớn.",
            f"Hôm nay: {today_text()}\nViệc: {task.title}\nMô tả:\n{ai_core.wrap(task.description or '(không có)')}\n"
            + (
                f"Hạn việc lớn: {due.astimezone(VIETNAM):%Y-%m-%d %H:%M}\n"
                if due
                else "Việc lớn chưa có hạn.\n"
            )
            + '\nTrả về {"items": [{"title": "...", "due_at": "YYYY-MM-DDTHH:MM hoặc null", "note": "một câu"}]}, 3 đến 8 việc.',
            max_tokens=1200,
        )
        items = []
        for item in (answer.get("items") if isinstance(answer, dict) else None) or []:
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            item_due = parse_due(item.get("due_at"))
            if item_due and due and datetime.fromisoformat(item_due) > due:
                item_due = due.isoformat()
            items.append(
                {"title": title[:250], "due_at": item_due, "note": str(item.get("note") or "")[:300]}
            )
        db.commit()
        return {"items": items[:10]}

    def digest_key(user) -> str:
        return f"digest:{user.id}:{now_vn().date().isoformat()}:{ai_core.PROMPT_VERSION}"

    @router.get("/ai/digest")
    def stored_digest(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = user_for(db, actor)
        return {"digest": ai_core.cached(db, digest_key(user))}

    @router.post("/ai/digest")
    def make_digest(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """11. This morning in words: what is urgent, what waits for approval, what is about to slip."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "daily_digest")
        overview = app.state.me_overview(db=db, actor=actor)
        lines = []
        for item in overview["agenda"][:25]:
            due = (
                item["due_at"].astimezone(VIETNAM).strftime("%d/%m %H:%M") if item["due_at"] else "không hạn"
            )
            lines.append(
                f"- [{item['kind']}] {item['title']} — {item['detail']} — hạn {due}"
                + (" — QUÁ HẠN" if item["overdue"] else "")
            )
        team = ""
        if {"tasks.assign.department", "tasks.assign.organization"} & permissions(db, user):
            report = app.state.reports_overview(days=7, scope="managed", db=db, actor=actor)
            busiest = ", ".join(
                f"{r['display_name']} ({r['open']} việc, {r['overdue']} quá hạn)"
                for r in report["tasks"]["by_assignee"][:5]
            )
            team = f"\nViệc bạn giao/điều phối: {report['tasks']['open']} đang mở, {report['tasks']['overdue']} quá hạn. Theo người: {busiest}"
        answer = ask(
            db,
            user,
            "daily_digest",
            "Bạn viết bản tin đầu ngày cho một cán bộ: 3–6 gạch đầu dòng ngắn bằng tiếng Việt, việc gấp và quá "
            "hạn trước, rồi hồ sơ chờ duyệt, rồi việc của phòng nếu có. Xưng “bạn”. Không bịa thêm việc.",
            ai_core.wrap(
                f"Hôm nay: {today_text()}\nViệc đang chờ {user.display_name}:\n"
                + ("\n".join(lines) or "(không có)")
                + team
            ),
            max_tokens=700,
        )
        content = {"text": answer.strip(), "created_at": m.utcnow().isoformat()}
        ai_core.store(db, "daily_digest", digest_key(user), content)
        db.commit()
        return {"digest": content}

    @router.post("/ai/reports/narrative")
    def narrative(body: NarrativeInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """12. The report page in words, with where things stall and what to look at."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "report_narrative")
        report = app.state.reports_overview(days=body.days, scope=body.scope, db=db, actor=actor)
        process = None
        if {"cases.read.department", "cases.read.organization"} & permissions(db, user):
            process = app.state.process_metrics(days=body.days, db=db, actor=actor)
        facts = {
            "khoang_thoi_gian_ngay": body.days,
            "cong_viec": {k: v for k, v in report["tasks"].items() if k != "by_assignee"},
            "theo_nguoi": report["tasks"]["by_assignee"][:10],
            "ho_so": report["cases"],
            "buoc_duyet": (process or {}).get("steps", [])[:8],
        }
        key = "narrative:" + ai_core.fingerprint(user.id, facts, ai_core.PROMPT_VERSION)
        stored = ai_core.cached(db, key)
        if stored:
            return stored
        answer = ask(
            db,
            user,
            "report_narrative",
            "Bạn viết nhận xét điều hành cho lãnh đạo từ số liệu: 1 đoạn tình hình chung (4–6 câu, có số cụ "
            "thể), rồi 2–4 gạch đầu dòng gợi ý xử lý. Nêu chỗ tắc (người/khâu) nếu số liệu cho thấy. Không bịa "
            "số, không phán xét cá nhân.",
            ai_core.wrap(str(facts)),
            max_tokens=900,
        )
        result = {"text": answer.strip(), "created_at": m.utcnow().isoformat()}
        ai_core.store(db, "report_narrative", key, result)
        db.commit()
        return result

    # ---- 13–14. Conversations and the feed --------------------------------------------

    @router.post("/ai/conversations/{conversation_id}/summary")
    def chat_summary(
        conversation_id: str,
        body: ChatSummaryInput,
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """13. What a long conversation said and agreed, from the messages this member can read."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "chat_summary")
        member = membership(db, conversation_id, user.id)
        if not member:
            raise AppError(404, "conversation_not_found", "Không tìm thấy cuộc trò chuyện.")
        rows = list(
            db.scalars(
                select(m.Message)
                .where(
                    m.Message.conversation_id == conversation_id,
                    m.Message.seq > member.history_from_seq,
                    m.Message.deleted_at.is_(None),
                )
                .order_by(m.Message.seq.desc())
                .limit(body.limit)
            )
        )[::-1]
        if len(rows) < 3:
            raise AppError(422, "chat_too_short", "Cuộc trò chuyện còn quá ngắn để tóm tắt.")
        names = {
            u.id: u.display_name
            for u in db.scalars(select(m.User).where(m.User.id.in_({r.sender_id for r in rows})))
        }
        transcript = "\n".join(
            f"[{r.created_at:%d/%m %H:%M}] {names.get(r.sender_id, '?')}: {r.body[:800]}"
            for r in rows
            if r.body
        )
        answer = ask_json(
            db,
            user,
            "chat_summary",
            "Bạn tóm tắt cuộc trò chuyện công việc cho người vừa vào. Nêu điều đã thống nhất và việc cần làm "
            "(ai làm, hạn nếu có). Không thêm thông tin ngoài tin nhắn.",
            f"Hôm nay: {today_text()}\nTin nhắn:\n{ai_core.wrap(transcript)}\n\n"
            'Trả về {"summary": ["2 đến 5 ý"], "decisions": ["điều đã thống nhất"], "actions": [{"text": "việc '
            'cần làm, viết như một câu giao việc", "assignee": "tên người hoặc null"}]}.',
            max_tokens=1500,
        )
        answer = answer if isinstance(answer, dict) else {}

        def strings(key):
            return [str(x).strip()[:400] for x in answer.get(key) or [] if str(x).strip()][:8]

        actions = [
            {"text": str(a.get("text") or "").strip()[:400], "assignee": a.get("assignee")}
            for a in answer.get("actions") or []
            if isinstance(a, dict) and str(a.get("text") or "").strip()
        ][:8]
        db.commit()
        return {
            "summary": strings("summary"),
            "decisions": strings("decisions"),
            "actions": actions,
            "messages": len(rows),
        }

    @router.post("/ai/write")
    def write(body: WriteInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """14a. Rewrite a post more concisely, fix spelling, or suggest titles."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "writing_help")
        if body.action == "title":
            answer = ask_json(
                db, user, "writing_help",
                "Bạn gợi ý tiêu đề ngắn (dưới 12 chữ), rõ nội dung cho bài đăng nội bộ.",
                ai_core.wrap(body.text) + '\n\nTrả về {"titles": ["3 tiêu đề"]}.',
                max_tokens=300,
            )  # fmt: skip
            titles = answer.get("titles") if isinstance(answer, dict) else answer
            db.commit()
            return {"titles": [str(t).strip() for t in titles or [] if str(t).strip()][:5]}
        instruction = {
            "rewrite": "Viết lại cho gọn, rõ, giữ nguyên ý và giọng văn, giữ các chi tiết cụ thể.",
            "proofread": "Chỉ sửa lỗi chính tả, dấu câu và lỗi gõ; không đổi cách diễn đạt.",
        }[body.action]
        answer = ask(
            db, user, "writing_help",
            f"Bạn biên tập bài đăng bảng tin nội bộ tiếng Việt. {instruction} Chỉ trả về bài đã sửa, không giải thích.",
            ai_core.wrap(body.text),
            max_tokens=2500,
        )  # fmt: skip
        db.commit()
        return {"text": answer.strip()}

    @router.post("/ai/post-attachments/{attachment_id}/describe")
    def describe_image(attachment_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """14b. A text alternative for an image the author is posting, saved on the attachment."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "writing_help")
        value = db.get(m.PostAttachment, attachment_id)
        if not value or value.uploader_id != user.id:
            raise AppError(404, "attachment_not_found", "Không tìm thấy ảnh.")
        if value.kind != "image":
            raise AppError(422, "not_an_image", "Chỉ tạo mô tả cho ảnh.")
        ticket = app.state.core_service.post(
            f"/storage/versions/{app.state.core_service.file_version(value.core_file_id)[1]['id']}/download-tickets",
            {},
        )
        data = app.state.core_service.get(f"/storage/download/{ticket['ticket']}", raw=True)
        answer = ask(
            db, user, "writing_help",
            "Bạn viết mô tả ảnh cho người dùng trình đọc màn hình: một câu tiếng Việt dưới 25 chữ, nêu người, "
            "vật, hoạt động, chữ đáng chú ý trong ảnh. Không mở đầu bằng “Ảnh”.",
            "Mô tả ảnh này.",
            files=[llm.Attachment(value.name, value.mime, data)],
            max_tokens=200,
        )  # fmt: skip
        value.alt = answer.strip().strip('"')[:300]
        db.commit()
        return {"alt": value.alt}

    # ---- 17. Test scenarios for a business package ------------------------------------

    @router.post("/ai/package-versions/{version_id}/scenarios")
    def scenarios(version_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """17. Scenarios worth testing (amounts at the threshold, missing files) with their real path."""
        user = user_for(db, actor)
        ai_core.require_feature(db, "package_scenarios")
        version = db.get(m.PackageVersion, version_id)
        if not version:
            raise AppError(404, "package_version_not_found", "Không tìm thấy phiên bản gói.")
        package = db.get(m.BusinessPackage, version.package_id)
        require(db, user, "forms.manage")
        if package.owner_id != user.id and user.role != "director":
            raise AppError(404, "package_not_found", "Không tìm thấy gói nghiệp vụ.")
        form = db.get(m.Form, version.form_id)
        steps = "\n".join(
            f"- Bước {i + 1}: {step['label']}"
            + (
                f" (chỉ khi {step['condition']['field']} {step['condition']['operator']} {step['condition'].get('value')})"
                if step.get("condition")
                else ""
            )
            for i, step in enumerate(version.approval_steps)
        )
        answer = ask_json(
            db,
            user,
            "package_scenarios",
            "Bạn là kiểm thử viên quy trình phê duyệt. Đề xuất kịch bản thử bao phủ: giá trị sát ngưỡng điều "
            "kiện (dưới, bằng, trên), thiếu tài liệu bắt buộc, trường bắt buộc để trống, có người trả lại.",
            f"Biểu mẫu “{form.name}”:\n{form_fields_text(form)}\n\nCác bước duyệt:\n{steps}\n"
            f"Số tài liệu bắt buộc: {version.required_file_count}\n\n"
            'Trả về {"cases": [{"name": "tên ngắn", "payload": {"key": giá trị}, "file_count": số, "decisions": '
            '["approve|return|reject cho từng bước theo thứ tự"], "why": "kiểm tra điều gì"}]}, 4 đến 8 kịch bản.',
            max_tokens=3000,
        )
        fixtures = []
        for item in (answer.get("cases") if isinstance(answer, dict) else None) or []:
            if not isinstance(item, dict) or not isinstance(item.get("payload"), dict):
                continue
            decisions = {
                f"review_{i}": {"decision": d if d in {"approve", "return", "reject"} else "approve"}
                for i, d in enumerate((item.get("decisions") or [])[: len(version.approval_steps)])
            }
            for i in range(len(version.approval_steps)):
                decisions.setdefault(f"review_{i}", {"decision": "approve"})
            fixture = {
                "name": str(item.get("name") or "Kịch bản AI")[:120],
                "payload": item["payload"],
                "decisions": decisions,
                "file_count": max(0, min(30, int(item.get("file_count") or 0))),
                "expected_path": [],
                "expected_assignees": [],
                "expected_error_code": None,
                "why": str(item.get("why") or "")[:300],
            }
            # The expectation is what the package actually does today; the person checks it is right.
            try:
                result = app.state.simulate_package(
                    db,
                    version,
                    SimpleNamespace(
                        payload=fixture["payload"],
                        decisions=fixture["decisions"],
                        file_count=fixture["file_count"],
                        owner_id=user.id,
                        department_id=user.department_id,
                    ),
                )
                fixture["expected_path"] = result.get("path", [])
            except AppError as exc:
                fixture["expected_error_code"] = exc.code if exc.code in {
                    "required_documents_missing", "approval_configuration_error", "form_validation_error", "self_approval_denied"
                } else None  # fmt: skip
                if not fixture["expected_error_code"]:
                    continue
            fixtures.append(fixture)
        db.commit()
        return {"fixtures": fixtures[:10]}

    return router


def personal_context(db: Session, user: m.User) -> str:
    """16. What the help chat may know about the person asking: their own work, nothing else."""
    lines = [f"Người hỏi: {user.display_name}. Hôm nay: {today_text()}."]
    cases = list(
        db.scalars(
            select(m.Case)
            .where(m.Case.owner_id == user.id, m.Case.deleted_at.is_(None), m.Case.archived_at.is_(None))
            .order_by(m.Case.updated_at.desc())
            .limit(15)
        )
    )
    if cases:
        lines.append("Hồ sơ của người hỏi:")
    for case in cases:
        waiting = [
            (db.get(m.User, t.assignee_id), t.label)
            for t in db.scalars(
                select(m.ApprovalTask).where(
                    m.ApprovalTask.case_id == case.id, m.ApprovalTask.state == "pending"
                )
            )
        ]
        who = (
            "; đang chờ " + ", ".join(f"{u.display_name if u else '?'} ({label})" for u, label in waiting)
            if waiting
            else ""
        )
        lines.append(
            f"- HS-{case.number:06d} “{case.title}”: {STATUS_TEXT.get(case.status, case.status)}{who}"
        )
    tasks = [
        t
        for t in db.scalars(
            select(m.Task).where(m.Task.assignee_id == user.id).order_by(m.Task.due_at).limit(40)
        )
        if t.status not in {"completed", "cancelled"}
    ][:15]
    if tasks:
        lines.append("Việc được giao cho người hỏi:")
    for task in tasks:
        due = task.due_at.replace(tzinfo=UTC) if task.due_at and task.due_at.tzinfo is None else task.due_at
        lines.append(
            f"- “{task.title}”: {STATUS_TEXT.get(task.status, task.status)}"
            + (f", hạn {due.astimezone(VIETNAM):%d/%m/%Y %H:%M}" if due else "")
        )
    approvals = list(
        db.scalars(
            select(m.ApprovalTask).where(
                m.ApprovalTask.assignee_id.in_(approval_assignees(db, user)),
                m.ApprovalTask.state == "pending",
            )
        )
    )[:15]
    if approvals:
        lines.append("Hồ sơ đang chờ người hỏi duyệt:")
    for item in approvals:
        case = db.get(m.Case, item.case_id)
        lines.append(f"- “{case.title if case else '?'}” ở bước {item.label}")
    return "\n".join(lines)
