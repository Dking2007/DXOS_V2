from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Revision(Input):
    expected_revision: int = Field(ge=1)


class DepartmentCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)
    parent_id: str | None = None
    manager_id: str | None = None


class DepartmentPatch(Revision):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: str | None = None
    manager_id: str | None = None


class UserCreate(Input):
    subject: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    department_id: str | None = None
    role: str = Field(default="staff", min_length=1, max_length=40)


class UserPatch(Input):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    department_id: str | None = None
    role: str | None = None
    active: bool | None = None


class RolePatch(Revision):
    name: str = Field(min_length=1, max_length=200)
    permissions: list[str]


class FolderCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None


class FolderPatch(Revision):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: str | None = None
    trashed: bool | None = None


def normalize_labels(labels: list[str] | None) -> list[str] | None:
    """Normalize to unique, non-empty, sorted labels.

    Comparison is case-insensitive so "Hợp đồng" and "hợp đồng" are one label rather
    than two that look identical in the list.
    """
    if labels is None:
        return None
    cleaned = {}
    for label in labels:
        value = label.strip()
        if not value:
            raise ValueError("Nhãn không được để trống.")
        if len(value) > 40:
            raise ValueError("Nhãn tối đa 40 ký tự.")
        cleaned.setdefault(value.casefold(), value)
    return sorted(cleaned.values())


class FilePatch(Revision):
    name: str | None = Field(default=None, min_length=1, max_length=250)
    folder_id: str | None = None
    trashed: bool | None = None
    labels: list[str] | None = Field(default=None, max_length=20)

    # The same rule governs labels wherever they can be set, so the copy of a document
    # cannot end up holding a label the list view would have rejected.
    normalize = field_validator("labels")(normalize_labels)


class FileCopy(Input):
    """Duplicate a document the caller can already read.

    No revision is taken on the source: copying changes nothing about it. An
    Idempotency-Key is required instead, because a retried copy would otherwise create a
    second independent document.
    """

    name: str | None = Field(default=None, min_length=1, max_length=250)
    folder_id: str | None = None
    labels: list[str] | None = Field(default=None, max_length=20)

    normalize = field_validator("labels")(normalize_labels)


class ShareInput(Revision):
    user_id: str
    access: Literal["read", "write", "none"]


class RestoreInput(Revision):
    version_id: str


class NewDocument(Input):
    name: str = Field(min_length=1, max_length=220)
    kind: Literal["docx", "xlsx", "pptx"] = "docx"
    folder_id: str | None = None


class FormField(Input):
    key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=200)
    type: Literal["text", "textarea", "number", "date", "select", "checkbox"]
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)
    default: Any = None
    visible_when: Condition | None = None

    @model_validator(mode="after")
    def valid_options(self):
        if self.type == "select" and (not self.options or len(set(self.options)) != len(self.options)):
            raise ValueError("Trường lựa chọn cần danh sách giá trị không trùng.")
        return self

    @model_validator(mode="after")
    def default_matches_type(self):
        """A default that the field could never hold is a misconfiguration, not a saved value."""
        if self.default is None:
            return self
        if self.type in {"checkbox"} and not isinstance(self.default, bool):
            raise ValueError("Giá trị mặc định của ô tích phải là đúng/sai.")
        if self.type == "number" and isinstance(self.default, bool):
            raise ValueError("Giá trị mặc định của trường số phải là số.")
        if self.type in {"text", "textarea"} and not isinstance(self.default, str):
            raise ValueError("Giá trị mặc định của trường văn bản phải là chuỗi.")
        if self.type == "select" and self.default not in self.options:
            raise ValueError("Giá trị mặc định phải là một trong các phương án.")
        return self


class Condition(Input):
    field: str
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte"]
    value: Any


class ApprovalStep(Input):
    label: str = Field(min_length=1, max_length=200)
    resolver: Literal["user", "department_manager"]
    user_id: str | None = None
    condition: Condition | None = None

    @model_validator(mode="after")
    def user_required(self):
        if self.resolver == "user" and not self.user_id:
            raise ValueError("Chọn người duyệt cho bước này.")
        return self


class FormCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=3000)
    fields: list[FormField] = Field(min_length=1, max_length=80)
    approval_steps: list[ApprovalStep] = Field(min_length=1, max_length=10)

    @field_validator("fields")
    @classmethod
    def unique_keys(cls, fields):
        if len({f.key for f in fields}) != len(fields):
            raise ValueError("Key trường bị trùng.")
        return fields

    @model_validator(mode="after")
    def known_conditions(self):
        keys = {f.key for f in self.fields}
        for step in self.approval_steps:
            if step.condition and step.condition.field not in keys:
                raise ValueError("Điều kiện tham chiếu trường không tồn tại.")
        # A field whose visibility depends on itself can never be evaluated, so refuse it
        # rather than silently treating it as always hidden.
        for field in self.fields:
            if field.visible_when and field.visible_when.field == field.key:
                raise ValueError(f"Điều kiện hiển thị của '{field.key}' không được tham chiếu chính nó.")
            if field.visible_when and field.visible_when.field not in keys:
                raise ValueError(f"Điều kiện hiển thị của '{field.key}' tham chiếu trường không tồn tại.")
        return self


class CaseCreate(Input):
    title: str = Field(min_length=1, max_length=250)
    form_id: str
    package_version_id: str | None = None
    payload: dict[str, Any]
    file_ids: list[str] = Field(default_factory=list, max_length=30)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_at: datetime | None = None
    assignee_id: str | None = None

    @field_validator("due_at")
    @classmethod
    def due_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Hạn xử lý phải có múi giờ.")
        return value


class CasePatch(Revision):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    payload: dict[str, Any] | None = None
    file_ids: list[str] | None = Field(default=None, max_length=30)
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    due_at: datetime | None = None
    assignee_id: str | None = None

    @field_validator("due_at")
    @classmethod
    def due_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Hạn xử lý phải có múi giờ.")
        return value


class WithdrawInput(Revision):
    reason: str = Field(default="", max_length=2000)


class DecisionInput(Revision):
    decision: Literal["approve", "reject", "return"]
    reason: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def reason_required(self):
        if self.decision != "approve" and not self.reason.strip():
            raise ValueError("Cần ghi lý do khi từ chối hoặc trả lại.")
        return self


def json_schema(fields: list[dict], payload: dict | None = None) -> dict:
    """JSON Schema for a form's fields.

    With a payload, `required` reflects what that payload must actually supply: a required
    field hidden by a condition is not demanded. Without one — the schema registered in Core
    for the whole form — a conditionally-required field is left out of `required` entirely,
    because whether it is required depends on the payload Core is only asked to store.
    WorkMMODIARY enforces that condition itself before the payload ever reaches Core.
    """
    properties = {}
    required = []
    for field in fields:
        kind = field["type"]
        value = {
            "title": field["label"],
            "type": "number" if kind == "number" else "boolean" if kind == "checkbox" else "string",
        }
        if kind == "select":
            value["enum"] = field["options"]
        if kind == "date":
            value["format"] = "date"
        if field.get("required"):
            conditional = field.get("visible_when") is not None
            hidden = payload is not None and not condition_matches(field.get("visible_when"), payload)
            if not conditional and not hidden:
                required.append(field["key"])
            if value["type"] == "string":
                value["minLength"] = 1
        properties[field["key"]] = value
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def condition_matches(condition: dict | None, payload: dict) -> bool:
    if not condition:
        return True
    value = payload.get(condition["field"])
    target = condition.get("value")
    operator = condition["operator"]
    if operator == "eq":
        return value == target
    if operator == "ne":
        return value != target
    if isinstance(value, bool) or isinstance(target, bool):
        return False
    if not isinstance(value, (int, float)) or not isinstance(target, (int, float)):
        return False
    return {"gt": value > target, "gte": value >= target, "lt": value < target, "lte": value <= target}[
        operator
    ]


def visible_fields(fields: list[dict], payload: dict) -> list[dict]:
    """Fields whose `visible_when` condition the payload satisfies.

    Visibility is resolved from what was submitted, not from the form order, so a chain
    (A shows B, B shows C) converges in one pass over a validated payload.
    """
    return [field for field in fields if condition_matches(field.get("visible_when"), payload)]


def apply_defaults(fields: list[dict], payload: dict) -> dict:
    """Fill in a field's configured default where the payload left it absent.

    Applies to every field, not only visible ones: a hidden field keeps its default so
    that revealing it later shows a coherent value instead of a blank.
    """
    result = dict(payload)
    for field in fields:
        if field.get("default") is not None and result.get(field["key"]) is None:
            result[field["key"]] = field["default"]
    return result
