# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Sector packs (gói giao diện): business content and appearance, installed and removed as one unit.

A pack is a folder (or a .zip of one) with a `desktiny-pack.json` manifest, contract
`desktiny-pack/1`. It carries no code. Its two halves can be used alone or together:

* business: processes (a form plus a flow), forms, flow templates for the "new flow" dialog,
  automations (installed switched off) and knowledge articles for the AI assistant;
* appearance: name, logo, favicon, light and dark colours, font, density, corner radius, the
  login page, terminology, menu and home page blocks.

Everything a pack says is checked before anything is written: only known colour variables (with
WCAG AA contrast in both themes), known fonts, menu keys and home blocks, cleaned SVG. Installing
records what it created, so an upgrade updates the same objects and an uninstall takes them back,
except what dossiers already use: a process with dossiers is only unpublished, never deleted.

One pack's appearance is in force at a time; removing that pack returns to stock Desktiny. The
core pack `desktiny.core` ships the ready-made process templates and is always installed. Packs
the organisation draws on the pack builder have ids `local.*`: they point at things that already
exist and never delete them.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Literal
from xml.etree import ElementTree as ET

from dx_platform.auth import Actor
from dx_platform.errors import AppError
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .automations import Graph, require_valid, trigger_event, trigger_form
from .policies import current_user, permissions
from .services import audit

SCHEMA = "desktiny-pack/1"
CORE_PACK = "desktiny.core"
MANAGE = "organization.manage"
MAX_ZIP_BYTES = 10 * 1024 * 1024
MAX_UNPACKED_BYTES = 25 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 300
MAX_ASSET_BYTES = {"logo": 512 * 1024, "favicon": 256 * 1024, "background": 2 * 1024 * 1024}
PACK_ID = r"^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$"
SEMVER = r"^\d+\.\d+\.\d+$"

# Colour variables a pack may set (as in apps/shared/src/style.css), hex values only.
COLOR_VARS = (
    "navy", "ink-2", "muted", "canvas", "surface", "surface-2", "surface-3", "surface-4",
    "border", "border-soft", "border-strong", "teal", "teal-strong", "teal-soft", "teal-ink",
    "teal-line", "green-ink", "green-soft", "green-line", "red", "red-ink", "red-soft", "red-line",
    "amber", "amber-ink", "amber-soft", "amber-line", "blue-ink", "blue-soft", "blue-line",
    "violet-ink", "violet-soft", "violet-line", "focus",
)  # fmt: skip
# Stock values of the colours the contrast check reads; "on-teal" is the text of main buttons.
DEFAULT_COLORS = {
    "light": {
        "navy": "#0f172a", "ink-2": "#334155", "muted": "#475569", "canvas": "#f8fafc",
        "surface": "#ffffff", "surface-2": "#f4f7fa", "teal": "#1e3a5f", "teal-soft": "#e9eef5",
        "teal-ink": "#1e3a5f", "red": "#b91c1c", "red-ink": "#b91c1c", "red-soft": "#fdecec",
        "green-ink": "#15803d", "green-soft": "#e8f6ee", "on-teal": "#ffffff",
    },
    "dark": {
        "navy": "#e3ecf4", "ink-2": "#bccbd9", "muted": "#a9b8c8", "canvas": "#0b1220",
        "surface": "#111c2b", "surface-2": "#162333", "teal": "#60a5fa", "teal-soft": "#172a44",
        "teal-ink": "#93c5fd", "red": "#ff8798", "red-ink": "#ff95a4", "red-soft": "#3b1c24",
        "green-ink": "#74d6a8", "green-soft": "#13321f", "on-teal": "#0b1220",
    },
}  # fmt: skip
# (text, background, what it is): every pair must reach 4.5:1 in both themes.
CONTRAST_PAIRS = (
    ("navy", "surface", "Chữ chính trên nền thẻ"),
    ("navy", "canvas", "Chữ chính trên nền trang"),
    ("ink-2", "surface", "Chữ phụ đậm trên nền thẻ"),
    ("muted", "surface", "Chữ phụ trên nền thẻ"),
    ("teal-ink", "surface", "Liên kết, chữ nhấn"),
    ("teal-ink", "teal-soft", "Chữ trên nền nhấn nhạt"),
    ("on-teal", "teal", "Chữ trên nút chính"),
    ("red", "surface", "Chữ báo lỗi"),
    ("red-ink", "red-soft", "Nhãn lỗi"),
    ("green-ink", "green-soft", "Nhãn thành công"),
)
FONTS = {"source-sans-3": "Source Sans 3 (mặc định)", "be-vietnam-pro": "Be Vietnam Pro"}
LOGIN_STYLES = {"framed": "Khung trang trí", "flat": "Phẳng, theo màu chính", "image": "Ảnh nền"}
# Menu keys as in apps/workspace-web/src/ui/nav.ts. Only work modules may be hidden: hiding
# approvals, the home page or the administration screens would lock people out.
MENU_KEYS = (
    "home", "tasks", "approvals", "cases", "chat", "feed", "drive", "reports",
    "processes", "assistant", "plugins", "packs", "settings",
)  # fmt: skip
HIDEABLE = ("tasks", "cases", "chat", "feed", "drive", "reports")
HOME_BLOCKS = {
    "tasks.today": "Việc cần làm hôm nay",
    "quick.start": "Bắt đầu nhanh",
    "cases.recent": "Hồ sơ gần đây",
    "ai.digest": "Bản tin việc hôm nay (AI)",
    "plugins.widgets": "Khối của plugin",
}
IMAGE_MAGIC = {b"\x89PNG\r\n\x1a\n": "image/png", b"RIFF": "image/webp", b"\xff\xd8\xff": "image/jpeg"}
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)


def app_version() -> str:
    try:
        return package_version("dx-workspace")
    except PackageNotFoundError:  # running from a source tree without an install
        return "0.0.0"


def parse_version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


# ---- Manifest ---------------------------------------------------------------------------


class LoginLook(s.Input):
    style: Literal["framed", "flat", "image"] = "framed"
    title: str = Field(default="", max_length=120)
    subtitle: str = Field(default="", max_length=160)
    background: str | None = Field(default=None, max_length=200)


class MenuLook(s.Input):
    hide: list[str] = Field(default_factory=list, max_length=len(MENU_KEYS))
    order: list[str] = Field(default_factory=list, max_length=len(MENU_KEYS))

    @model_validator(mode="after")
    def known(self):
        if set(self.hide) - set(HIDEABLE):
            raise ValueError("Chỉ ẩn được các phân hệ: " + ", ".join(HIDEABLE) + ".")
        if set(self.order) - set(MENU_KEYS) or len(set(self.order)) != len(self.order):
            raise ValueError("Thứ tự menu chỉ gồm các phân hệ có sẵn, mỗi phân hệ một lần.")
        return self


class Colors(s.Input):
    light: dict[str, str] = Field(default_factory=dict)
    dark: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def hex_only(self):
        for theme in (self.light, self.dark):
            for name, value in theme.items():
                if name not in COLOR_VARS:
                    raise ValueError(f"Màu “{name}” không phải biến màu có sẵn.")
                if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                    raise ValueError(f"Màu “{name}” phải là mã hex dạng #rrggbb.")
        return self


class Appearance(s.Input):
    app_name: str = Field(default="", max_length=60)
    org_name: str = Field(default="", max_length=120)
    logo: str | None = Field(default=None, max_length=200)
    favicon: str | None = Field(default=None, max_length=200)
    colors: Colors = Field(default_factory=Colors)
    font: Literal["source-sans-3", "be-vietnam-pro"] | None = None
    density: Literal["comfortable", "compact"] = "comfortable"
    radius: Literal["small", "medium", "large"] = "medium"
    login: LoginLook = Field(default_factory=LoginLook)
    terminology: dict[str, str] = Field(default_factory=dict, max_length=60)
    menu: MenuLook = Field(default_factory=MenuLook)
    home: list[str] | None = Field(default=None, max_length=len(HOME_BLOCKS))

    @field_validator("terminology")
    @classmethod
    def words(cls, value):
        for source, target in value.items():
            if not 1 <= len(source.strip()) <= 60 or not 1 <= len(target.strip()) <= 80:
                raise ValueError("Mỗi cặp từ ngữ cần chữ gốc (≤ 60 ký tự) và chữ thay (≤ 80 ký tự).")
        return {source.strip(): target.strip() for source, target in value.items()}

    @field_validator("home")
    @classmethod
    def blocks(cls, value):
        if value is not None and (set(value) - set(HOME_BLOCKS) or len(set(value)) != len(value)):
            raise ValueError("Khối trang chủ chỉ gồm: " + ", ".join(HOME_BLOCKS) + ", mỗi khối một lần.")
        return value


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_: Literal["desktiny-pack/1"] = Field(alias="schema")
    id: str = Field(pattern=PACK_ID, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=SEMVER)
    license: str = Field(min_length=1, max_length=60)
    authors: list[str] = Field(default_factory=list, max_length=20)
    description: str = Field(default="", max_length=1000)
    requires: dict[str, str] = Field(default_factory=dict)
    appearance: Appearance | None = None
    processes: list[str] = Field(default_factory=list, max_length=60)
    forms: list[str] = Field(default_factory=list, max_length=60)
    templates: list[str] = Field(default_factory=list, max_length=80)
    automations: list[str] = Field(default_factory=list, max_length=60)
    knowledge: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("requires")
    @classmethod
    def requires_known(cls, value):
        for name, spec in value.items():
            if name != "desktiny" or not re.fullmatch(r"(>=\s*\d+\.\d+\.\d+|\*)", spec.strip()):
                raise ValueError("`requires` chỉ nhận {\"desktiny\": \">=x.y.z\"}.")
        return value


class FormSpec(s.Input):
    name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=3000)
    fields: list[s.FormField] = Field(min_length=1, max_length=80)
    approval_steps: list[s.ApprovalStep] = Field(
        default_factory=lambda: [s.ApprovalStep(label="Lãnh đạo đơn vị", resolver="department_manager")],
        min_length=1,
        max_length=10,
    )


class ProcessFile(s.Input):
    """A process: the form people fill and the flow the dossier follows."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    form: FormSpec
    graph: Graph
    allowed_roles: list[Literal["staff", "manager", "director", "technical_admin"]] = Field(default_factory=list)
    required_file_count: int = Field(default=0, ge=0, le=30)
    publish: bool = True


class TemplateFile(s.Input):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    graph: Graph


class AutomationFile(s.Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    graph: Graph
    scope: Literal["all", "attached"] = "all"


# ---- Checks -----------------------------------------------------------------------------


def luminance(color: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(first: str, second: str) -> float:
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def contrast_report(colors: Colors | None) -> list[dict]:
    """Every checked pair in both themes with the pack's colours applied over the stock ones."""
    report = []
    for theme in ("light", "dark"):
        palette = {**DEFAULT_COLORS[theme], **(getattr(colors, theme) if colors else {})}
        for text, background, label in CONTRAST_PAIRS:
            ratio = contrast(palette[text], palette[background])
            report.append(
                {
                    "theme": theme,
                    "text": text,
                    "background": background,
                    "label": label,
                    "ratio": round(ratio, 2),
                    "ok": ratio >= 4.5,
                }
            )
    return report


def contrast_failures(colors: Colors | None) -> list[str]:
    theme_name = {"light": "sáng", "dark": "tối"}
    return [
        f"{item['label']} (giao diện {theme_name[item['theme']]}) chỉ đạt tương phản {item['ratio']}:1, cần 4,5:1."
        for item in contrast_report(colors)
        if not item["ok"]
    ]


def clean_svg(data: bytes) -> tuple[bytes, bool]:
    """An SVG with nothing that runs or reaches out; returns the cleaned bytes and whether anything went."""
    head = data[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in data.lower():
        raise AppError(422, "pack_svg_invalid", "Tệp SVG không được chứa khai báo DOCTYPE hay ENTITY.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise AppError(422, "pack_svg_invalid", "Tệp SVG không đọc được.") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise AppError(422, "pack_svg_invalid", "Tệp SVG phải có thẻ gốc <svg>.")
    removed = False
    banned = {"script", "foreignObject", "iframe", "object", "embed", "audio", "video", "set",
              "animate", "animateMotion", "animateTransform", "handler", "listener"}  # fmt: skip

    def local(name: str) -> str:
        return name.rsplit("}", 1)[-1]

    def safe_link(value: str) -> bool:
        value = value.strip()
        return value.startswith("#") or bool(re.match(r"data:image/(png|jpeg|webp);base64,", value))

    def safe_style(value: str) -> bool:
        lowered = value.lower()
        if "@import" in lowered or "javascript:" in lowered or "expression(" in lowered:
            return False
        return all(target.strip(" '\"").startswith("#") for target in re.findall(r"url\(([^)]*)\)", lowered))

    for parent in list(root.iter()):
        for child in list(parent):
            if local(child.tag) in banned or (local(child.tag) == "style" and not safe_style(child.text or "")):
                parent.remove(child)
                removed = True
    for element in root.iter():
        for name, value in list(element.attrib.items()):
            key = local(name).lower()
            if (
                key.startswith("on")
                or (key == "href" and not safe_link(value))
                or (key == "style" and not safe_style(value))
            ):
                del element.attrib[name]
                removed = True
    return ET.tostring(root, encoding="utf-8"), removed


def image_kind(data: bytes, path: str) -> str:
    if path.lower().endswith(".svg"):
        return "image/svg+xml"
    for magic, mime in IMAGE_MAGIC.items():
        if data.startswith(magic) and (mime != "image/webp" or data[8:12] == b"WEBP"):
            return mime
    raise AppError(422, "pack_asset_invalid", f"“{path}” không phải ảnh PNG, JPEG, WebP hay SVG.")


def check_asset(path: str, data: bytes, role: str) -> tuple[str, bytes, bool]:
    if len(data) > MAX_ASSET_BYTES[role]:
        raise AppError(
            422, "pack_asset_too_large", f"“{path}” quá lớn (tối đa {MAX_ASSET_BYTES[role] // 1024} KB)."
        )
    mime = image_kind(data, path)
    if role != "background" and mime == "image/jpeg":
        raise AppError(422, "pack_asset_invalid", "Logo và favicon cần là PNG, WebP hoặc SVG.")
    if mime == "image/svg+xml":
        if role == "background":
            raise AppError(422, "pack_asset_invalid", "Ảnh nền cần là PNG, JPEG hoặc WebP.")
        data, cleaned = clean_svg(data)
        return mime, data, cleaned
    return mime, data, False


def clean_path(name: str) -> str:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts or len(name) > 200:
        raise AppError(422, "pack_path_invalid", f"Đường dẫn “{name}” trong gói không hợp lệ.")
    return str(path)


# ---- Reading a pack -----------------------------------------------------------------------


@dataclass
class Pack:
    manifest: Manifest
    texts: dict[str, str] = field(default_factory=dict)
    processes: dict[str, ProcessFile] = field(default_factory=dict)
    forms: dict[str, s.FormCreate] = field(default_factory=dict)
    templates: dict[str, TemplateFile] = field(default_factory=dict)
    automations: dict[str, AutomationFile] = field(default_factory=dict)
    knowledge: dict[str, tuple[str, str]] = field(default_factory=dict)
    assets: dict[str, tuple[str, bytes]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(part) for part in error.get("loc", ()) if part != "__root__")
    message = str(error.get("msg", "")).removeprefix("Value error, ")
    return f"{where}: {message}" if where else message


def read_zip(data: bytes) -> dict[str, bytes]:
    if len(data) > MAX_ZIP_BYTES:
        raise AppError(413, "pack_too_large", "Gói tối đa 10 MB.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise AppError(422, "pack_not_zip", "Tệp tải lên không phải tệp .zip hợp lệ.") from exc
    entries = [info for info in archive.infolist() if not info.is_dir()]
    if len(entries) > MAX_FILES or sum(info.file_size for info in entries) > MAX_UNPACKED_BYTES:
        raise AppError(413, "pack_too_large", "Gói có quá nhiều tệp hoặc quá lớn khi giải nén.")
    files = {clean_path(info.filename): archive.read(info) for info in entries}
    # A pack zipped together with its folder: drop that one top folder.
    if "desktiny-pack.json" not in files:
        tops = {name.split("/", 1)[0] for name in files}
        if len(tops) == 1 and all("/" in name for name in files):
            files = {name.split("/", 1)[1]: content for name, content in files.items()}
    return files


def read_folder(folder: Path) -> dict[str, bytes]:
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            files[clean_path(path.relative_to(folder).as_posix())] = path.read_bytes()
    return files


def load_pack(files: dict[str, bytes]) -> Pack:
    """Read and check a whole pack; nothing is written. Raises with the first problem found."""
    if "desktiny-pack.json" not in files:
        raise AppError(422, "pack_manifest_missing", "Gói thiếu tệp desktiny-pack.json.")
    try:
        manifest = Manifest.model_validate(json.loads(files["desktiny-pack.json"]))
    except (ValueError, json.JSONDecodeError) as exc:
        message = first_error(exc) if isinstance(exc, ValidationError) else "không phải JSON hợp lệ"
        raise AppError(422, "pack_manifest_invalid", f"desktiny-pack.json: {message}") from None
    required = manifest.requires.get("desktiny", "*").strip()
    if required != "*" and parse_version(app_version()) < parse_version(required.lstrip(">= ")):
        raise AppError(
            422, "pack_requires_newer", f"Gói cần Desktiny {required}; bản đang chạy là {app_version()}."
        )
    pack = Pack(manifest)

    def text(path: str) -> str:
        path = clean_path(path)
        if path not in files:
            raise AppError(422, "pack_file_missing", f"Gói khai báo “{path}” nhưng không có tệp đó.")
        if len(files[path]) > MAX_FILE_BYTES:
            raise AppError(413, "pack_file_too_large", f"“{path}” quá lớn (tối đa 2 MB).")
        try:
            content = files[path].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AppError(422, "pack_file_invalid", f"“{path}” phải là văn bản UTF-8.") from exc
        pack.texts[path] = content
        return content

    def parsed(path: str, model):
        try:
            return model.model_validate(json.loads(text(path)))
        except ValidationError as exc:
            raise AppError(422, "pack_file_invalid", f"{path}: {first_error(exc)}") from None
        except json.JSONDecodeError:
            raise AppError(422, "pack_file_invalid", f"{path}: không phải JSON hợp lệ.") from None

    for path in manifest.processes:
        item = parsed(path, ProcessFile)
        if trigger_event(item.graph.model_dump()) != "case.submitted":
            raise AppError(422, "pack_file_invalid", f"{path}: quy trình phải bắt đầu khi hồ sơ được trình.")
        if any((n.data or {}).get("user_id") or (n.data or {}).get("user_ids") for n in item.graph.nodes):
            pack.warnings.append(
                f"“{item.name}” chỉ định người cụ thể; cài xong cần chọn lại người cho cơ quan này."
            )
        pack.processes[clean_path(path)] = item
    for path in manifest.forms:
        pack.forms[clean_path(path)] = parsed(path, s.FormCreate)
    keys = set()
    for path in manifest.templates:
        item = parsed(path, TemplateFile)
        if item.key in keys:
            raise AppError(422, "pack_file_invalid", f"{path}: khoá mẫu “{item.key}” bị trùng trong gói.")
        keys.add(item.key)
        pack.templates[clean_path(path)] = item
    for path in manifest.automations:
        pack.automations[clean_path(path)] = parsed(path, AutomationFile)
    for path in manifest.knowledge:
        body = text(path).strip()
        if not body:
            raise AppError(422, "pack_file_invalid", f"{path}: bài kiến thức trống.")
        heading = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
        pack.knowledge[clean_path(path)] = ((heading or PurePosixPath(path).stem)[:250], body)
    look = manifest.appearance
    if look:
        failures = contrast_failures(look.colors)
        if failures:
            raise AppError(422, "pack_contrast_too_low", "Màu của gói khó đọc: " + " ".join(failures))
        for role, path in (("logo", look.logo), ("favicon", look.favicon), ("background", look.login.background)):
            if not path:
                continue
            path = clean_path(path)
            if path not in files:
                raise AppError(422, "pack_file_missing", f"Gói khai báo “{path}” nhưng không có tệp đó.")
            mime, data, cleaned = check_asset(path, files[path], role)
            if cleaned:
                pack.warnings.append(f"Đã bỏ phần có thể chạy mã hoặc tải từ ngoài khỏi “{path}”.")
            pack.assets[path] = (mime, data)
        if look.login.style == "image" and not look.login.background:
            raise AppError(422, "pack_manifest_invalid", "Trang đăng nhập kiểu ảnh nền cần khai báo ảnh nền.")
    return pack


def packs_folder(settings) -> Path | None:
    candidates = [settings.packs_dir] if settings.packs_dir else []
    candidates += [str(Path(__file__).resolve().parents[4] / "packs"), "/app/packs"]
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    return None


def builtin_packs(settings) -> dict[str, Path]:
    folder = packs_folder(settings)
    found = {}
    for child in sorted(folder.iterdir()) if folder else []:
        manifest = child / "desktiny-pack.json"
        if manifest.is_file():
            try:
                found[json.loads(manifest.read_text("utf-8"))["id"]] = child
            except (ValueError, KeyError):
                continue
    return found


# ---- Installing ---------------------------------------------------------------------------


def slug(text: str) -> str:
    from .text import fold

    return re.sub(r"[^a-z0-9]+", "-", fold(text).lower()).strip("-")[:60] or "muc"


def asset_url(asset: m.PackAsset) -> str:
    return f"/workspace/v1/appearance/assets/{asset.id}?v={asset.digest[:10]}"


def store_assets(db: Session, pack_id: str, assets: dict[str, tuple[str, bytes]]):
    db.execute(delete(m.PackAsset).where(m.PackAsset.pack_id == pack_id, m.PackAsset.path.not_in(list(assets))))
    for path, (mime, data) in assets.items():
        row = db.scalar(select(m.PackAsset).where(m.PackAsset.pack_id == pack_id, m.PackAsset.path == path))
        digest = hashlib.sha256(data).hexdigest()
        if row:
            row.mime, row.data, row.digest = mime, data, digest
        else:
            db.add(m.PackAsset(pack_id=pack_id, path=path, mime=mime, data=data, digest=digest))


def store_templates(db: Session, pack_id: str, templates: dict[str, TemplateFile]):
    db.execute(delete(m.PackTemplate).where(m.PackTemplate.pack_id == pack_id))
    for position, item in enumerate(templates.values()):
        db.add(
            m.PackTemplate(
                pack_id=pack_id,
                key=item.key,
                title=item.title,
                description=item.description,
                graph=item.graph.model_dump(),
                position=position,
            )
        )


def ensure_builtin(db: Session, settings, pack_id: str = CORE_PACK) -> m.InstalledPack | None:
    """Keep a pack shipped in `packs/` that holds templates only (the core pack) at its shipped version."""
    folder = builtin_packs(settings).get(pack_id)
    if not folder:
        return None
    row = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == pack_id))
    shipped = json.loads((folder / "desktiny-pack.json").read_text("utf-8"))
    if row and row.version == shipped.get("version"):
        return row
    pack = load_pack(read_folder(folder))
    if pack.processes or pack.forms or pack.automations or pack.knowledge or pack.manifest.appearance:
        raise AppError(500, "core_pack_invalid", "Gói mặc định chỉ được chứa mẫu luồng.")
    store_templates(db, pack_id, pack.templates)
    if not row:
        row = m.InstalledPack(pack_id=pack_id, source="builtin")
        db.add(row)
    row.name, row.version = pack.manifest.name, pack.manifest.version
    row.manifest = pack.manifest.model_dump(by_alias=True, exclude_none=True)
    row.files, row.created, row.updated_at = pack.texts, {}, m.utcnow()
    db.flush()
    return row


def used_rule(db: Session, rule_id: str) -> bool:
    """A flow somebody's dossier or run depends on: it may be withdrawn but never deleted."""
    if db.scalar(select(m.AutomationRun.id).where(m.AutomationRun.rule_id == rule_id).limit(1)):
        return True
    versions = list(db.scalars(select(m.ProcessVersion.id).where(m.ProcessVersion.rule_id == rule_id)))
    return bool(
        versions
        and db.scalar(select(m.Case.id).where(m.Case.process_version_id.in_(versions)).limit(1))
    )


def drop_rule(db: Session, rule_id: str):
    """Delete a never-used flow with every row that only exists for it."""
    rule_table = m.AutomationRule.__table__
    # Children before parents, so a report goes before the scenario it belongs to.
    for table in reversed(m.Base.metadata.sorted_tables):
        if table is rule_table or "rule_id" not in table.c:
            continue
        if any(fk.column.table is rule_table for fk in table.c.rule_id.foreign_keys) or table.name in {
            "automation_runs",
        }:
            db.execute(table.delete().where(table.c.rule_id == rule_id))
    db.execute(rule_table.delete().where(rule_table.c.id == rule_id))


def drop_form(db: Session, form_id: str) -> bool:
    """Delete a form nothing refers to any more; returns False and keeps it otherwise."""
    form_table = m.Form.__table__
    for table in m.Base.metadata.sorted_tables:
        for column in table.c:
            if any(fk.column.table is form_table for fk in column.foreign_keys):
                if db.execute(select(column).where(column == form_id).limit(1)).first():
                    return False
    if db.scalar(select(m.AutomationRule.id).where(m.AutomationRule.form_id == form_id).limit(1)):
        return False
    db.execute(form_table.delete().where(form_table.c.id == form_id))
    return True


class Installer:
    """Creates, updates and removes what a pack brings, recording ids in `row.created`."""

    def __init__(self, app, db: Session, actor: Actor, user: m.User, row: m.InstalledPack):
        self.app, self.db, self.actor, self.user, self.row = app, db, actor, user, row
        self.created = {kind: dict(ids) for kind, ids in (row.created or {}).items()}
        self.notes: list[str] = []

    def made(self, kind: str) -> dict:
        return self.created.setdefault(kind, {})

    def form(self, path: str, spec: s.FormCreate, key: str) -> m.Form:
        return self.app.state.make_form(self.db, self.actor, self.user, spec, key)

    def process(self, path: str, item: ProcessFile):
        db, settings = self.db, self.app.state.settings
        made = self.made("processes")
        rule = db.get(m.AutomationRule, made.get(path)) if made.get(path) else None
        old_form = db.get(m.Form, rule.form_id) if rule and rule.form_id else None
        fields = [field.model_dump() for field in item.form.fields]
        if old_form and old_form.fields == fields and old_form.name == (item.form.name or item.name):
            form = old_form
        else:
            spec = s.FormCreate(
                name=item.form.name or item.name,
                description=item.form.description or item.description,
                fields=item.form.fields,
                approval_steps=item.form.approval_steps,
            )
            form = self.form(path, spec, f"pack:{self.row.pack_id}:{path}:{self.row.version}:{m.uid()}")
        graph = item.graph.model_dump()
        for node in graph["nodes"]:
            if node["type"] == "trigger":
                node["data"] = {**node.get("data", {}), "event": "case.submitted", "form_id": form.id}
        try:
            require_valid(db, settings, graph)
        except AppError as exc:
            raise AppError(422, "pack_process_invalid", f"{path}: {exc.detail}") from None
        values = {
            "name": item.name,
            "description": item.description,
            "graph": graph,
            "trigger": trigger_event(graph),
            "kind": "process",
            "form_id": trigger_form(graph),
            "scope": "all",
            "allowed_roles": list(item.allowed_roles),
            "required_file_count": item.required_file_count,
        }
        if rule:
            for key, value in values.items():
                setattr(rule, key, value)
            rule.revision += 1
            rule.updated_at = m.utcnow()
        else:
            rule = m.AutomationRule(conditions=[], actions=[], enabled=False, created_by=self.user.id, **values)
            db.add(rule)
            db.flush()
            made[path] = rule.id
        self.made("forms")[f"{path}#form"] = form.id
        if old_form and old_form.id != form.id:
            drop_form(db, old_form.id)
        named = any((n.data or {}).get("user_id") or (n.data or {}).get("user_ids") for n in item.graph.nodes)
        if item.publish and not named:
            try:
                self.app.state.publish_process(db, self.user, rule)
            except AppError as exc:
                self.notes.append(f"“{item.name}” chưa phát hành: {exc.detail}")
        else:
            self.notes.append(f"“{item.name}” cài ở dạng nháp; kiểm tra rồi phát hành trong Quy trình nghiệp vụ.")

    def automation(self, path: str, item: AutomationFile):
        db, settings = self.db, self.app.state.settings
        graph = item.graph.model_dump()
        if trigger_form(graph):
            raise AppError(422, "pack_file_invalid", f"{path}: luồng tự động không gắn với biểu mẫu.")
        try:
            require_valid(db, settings, graph)
        except AppError as exc:
            raise AppError(422, "pack_file_invalid", f"{path}: {exc.detail}") from None
        made = self.made("automations")
        rule = db.get(m.AutomationRule, made.get(path)) if made.get(path) else None
        values = {"name": item.name, "description": item.description, "graph": graph,
                  "trigger": trigger_event(graph), "scope": item.scope}  # fmt: skip
        if rule:
            for key, value in values.items():
                setattr(rule, key, value)
            rule.revision += 1
            rule.updated_at = m.utcnow()
        else:
            # Installed switched off: an organisation turns on what it wants to run.
            rule = m.AutomationRule(kind="automation", conditions=[], actions=[], enabled=False,
                                    created_by=self.user.id, **values)  # fmt: skip
            db.add(rule)
            db.flush()
            made[path] = rule.id

    def article(self, path: str, title: str, body: str):
        made = self.made("knowledge")
        article = self.db.get(m.AssistantArticle, made.get(path)) if made.get(path) else None
        if article:
            article.title, article.body = title, body
            article.revision += 1
        else:
            article = m.AssistantArticle(
                title=title, body=body, category="guide", source="pack", source_ref=self.row.id,
                author_id=self.user.id, published=True,
            )  # fmt: skip
            self.db.add(article)
            self.db.flush()
            made[path] = article.id

    def remove(self, kind: str, path: str, object_id: str) -> str | None:
        """Take back one thing the pack made; returns a note when it had to be kept."""
        db = self.db
        if kind in {"processes", "automations"}:
            rule = db.get(m.AutomationRule, object_id)
            if not rule:
                return None
            if used_rule(db, rule.id):
                if rule.kind == "process" and rule.active_version_id:
                    self.app.state.unpublish_process(db, self.user, rule)
                rule.enabled = False
                return f"Giữ lại “{rule.name}” (đã có hồ sơ hoặc lượt chạy), chỉ ngừng sử dụng."
            drop_rule(db, rule.id)
        elif kind == "forms":
            form = db.get(m.Form, object_id)
            if form and not drop_form(db, form.id):
                return f"Giữ lại biểu mẫu “{form.name}” vì đã có hồ sơ dùng nó."
        elif kind == "knowledge":
            article = db.get(m.AssistantArticle, object_id)
            if article:
                db.delete(article)
        return None

    def apply(self, pack: Pack):
        """Bring the database to what the pack says: create, update, and drop what it no longer has."""
        wanted = {
            "processes": set(pack.processes),
            "automations": set(pack.automations),
            "knowledge": set(pack.knowledge),
        }
        for path, item in pack.processes.items():
            self.process(path, item)
        for path, spec in pack.forms.items():
            if not self.made("forms").get(path):
                self.made("forms")[path] = self.form(path, spec, f"pack:{self.row.pack_id}:{path}:{m.uid()}").id
        for path, item in pack.automations.items():
            self.automation(path, item)
        for path, (title, body) in pack.knowledge.items():
            self.article(path, title, body)
        wanted["forms"] = set(pack.forms) | {f"{path}#form" for path in pack.processes}
        for kind, paths in wanted.items():
            for path in list(self.made(kind)):
                if path not in paths:
                    note = self.remove(kind, path, self.made(kind).pop(path))
                    if note:
                        self.notes.append(note)
        store_templates(self.db, self.row.pack_id, pack.templates)
        store_assets(self.db, self.row.pack_id, pack.assets)
        self.row.created = self.created

    def remove_all(self):
        for kind in ("processes", "automations", "knowledge", "forms"):
            for path, object_id in list(self.made(kind).items()):
                note = self.remove(kind, path, object_id)
                if note:
                    self.notes.append(note)
        self.db.execute(delete(m.PackTemplate).where(m.PackTemplate.pack_id == self.row.pack_id))
        self.db.execute(delete(m.PackAsset).where(m.PackAsset.pack_id == self.row.pack_id))


# ---- Exporting -----------------------------------------------------------------------------


def export_zip(db: Session, row: m.InstalledPack) -> bytes:
    """The pack as a .zip another organisation can install; a local pack is written out from its parts."""
    manifest = dict(row.manifest)
    files = dict(row.files or {})
    if row.source == "local":
        files = {}
        lists = {"processes": [], "automations": [], "knowledge": []}
        for rule_id in (row.includes or {}).get("processes", []):
            rule = db.get(m.AutomationRule, rule_id)
            if not rule:
                continue
            form = db.get(m.Form, rule.form_id) if rule.form_id else None
            graph = json.loads(json.dumps(rule.graph or {}))
            for node in graph.get("nodes", []):
                if node["type"] == "trigger":
                    node["data"] = {**node.get("data", {}), "form_id": None}
            path = f"processes/{slug(rule.name)}.json"
            files[path] = json.dumps(
                {
                    "name": rule.name,
                    "description": rule.description,
                    "form": {
                        "name": form.name if form else rule.name,
                        "description": form.description if form else "",
                        "fields": form.fields if form else [],
                        "approval_steps": form.approval_steps if form else [],
                    },
                    "graph": graph,
                    "allowed_roles": rule.allowed_roles or [],
                    "required_file_count": rule.required_file_count or 0,
                },
                ensure_ascii=False,
                indent=2,
            )
            lists["processes"].append(path)
        for rule_id in (row.includes or {}).get("automations", []):
            rule = db.get(m.AutomationRule, rule_id)
            if rule:
                path = f"automations/{slug(rule.name)}.json"
                files[path] = json.dumps(
                    {"name": rule.name, "description": rule.description, "graph": rule.graph, "scope": rule.scope},
                    ensure_ascii=False,
                    indent=2,
                )
                lists["automations"].append(path)
        for article_id in (row.includes or {}).get("knowledge", []):
            article = db.get(m.AssistantArticle, article_id)
            if article:
                path = f"knowledge/{slug(article.title)}.md"
                body = article.body if article.body.lstrip().startswith("# ") else f"# {article.title}\n\n{article.body}"
                files[path] = body
                lists["knowledge"].append(path)
        manifest.update({key: value for key, value in lists.items() if value})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("desktiny-pack.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path, content in sorted(files.items()):
            archive.writestr(path, content)
        for asset in db.scalars(select(m.PackAsset).where(m.PackAsset.pack_id == row.pack_id)):
            archive.writestr(asset.path, asset.data)
    return buffer.getvalue()


# ---- API --------------------------------------------------------------------------------


class AppearanceChoice(s.Revision):
    pack_id: str | None = None


class LocalInclude(s.Input):
    processes: list[str] = Field(default_factory=list, max_length=60)
    automations: list[str] = Field(default_factory=list, max_length=60)
    knowledge: list[str] = Field(default_factory=list, max_length=100)


class LocalPackInput(s.Input):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(default="1.0.0", pattern=SEMVER)
    description: str = Field(default="", max_length=1000)
    license: str = Field(default="Apache-2.0", min_length=1, max_length=60)
    appearance: Appearance | None = None
    include: LocalInclude = Field(default_factory=LocalInclude)
    expected_revision: int | None = None


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["packs"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def manager(db, actor) -> m.User:
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        user = current_user(db, actor)
        if MANAGE not in permissions(db, user):
            raise AppError(403, "permission_denied", "Chỉ người quản lý tổ chức được quản lý gói giao diện.")
        return user

    def needs(db, user, pack: Pack):
        """Installing processes, flows or knowledge needs the rights to make them by hand too."""
        held = permissions(db, user)
        wanted = []
        if pack.processes or pack.forms:
            wanted += ["forms.manage", "automations.manage"]
        if pack.automations:
            wanted.append("automations.manage")
        if pack.knowledge:
            wanted.append("assistant.manage")
        missing = sorted(set(wanted) - held)
        if missing:
            raise AppError(403, "permission_denied", "Gói cần thêm quyền: " + ", ".join(missing) + ".")

    def active(db) -> m.ActiveAppearance:
        row = db.get(m.ActiveAppearance, "default")
        if not row:
            row = m.ActiveAppearance(id="default", pack_id=None, revision=1)
            db.add(row)
            db.flush()
        return row

    def appearance_of(db, pack_id: str | None) -> dict | None:
        row = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == pack_id)) if pack_id else None
        look = (row.manifest or {}).get("appearance") if row else None
        if not look:
            return None
        assets = {a.path: a for a in db.scalars(select(m.PackAsset).where(m.PackAsset.pack_id == row.pack_id))}

        def url(path):
            return asset_url(assets[path]) if path and path in assets else None

        login = dict(look.get("login") or {})
        login["background_url"] = url(login.get("background"))
        return {**look, "login": login, "logo_url": url(look.get("logo")), "favicon_url": url(look.get("favicon"))}

    def counts(manifest: dict) -> dict:
        return {key: len(manifest.get(key) or []) for key in ("processes", "forms", "templates", "automations", "knowledge")}

    def pack_data(db, row: m.InstalledPack, current: str | None) -> dict:
        manifest = row.manifest or {}
        made = row.created or {}
        includes = row.includes or {}
        return {
            "id": row.id,
            "pack_id": row.pack_id,
            "name": row.name,
            "version": row.version,
            "source": row.source,
            "description": manifest.get("description", ""),
            "license": manifest.get("license", ""),
            "authors": manifest.get("authors", []),
            "has_appearance": bool(manifest.get("appearance")),
            "appearance": manifest.get("appearance"),
            "appearance_active": current == row.pack_id,
            "counts": {
                **counts(manifest),
                "templates": db.scalar(
                    select(func.count(m.PackTemplate.id)).where(m.PackTemplate.pack_id == row.pack_id)
                ),
            },
            "created": {kind: len(ids) for kind, ids in made.items()},
            "includes": includes,
            "removable": row.pack_id != CORE_PACK and row.source != "plugin",
            "revision": row.revision,
            "installed_at": row.installed_at,
            "updated_at": row.updated_at,
        }

    def preview_of(db, pack: Pack) -> dict:
        manifest = pack.manifest
        installed = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == manifest.id))
        conflicts = []
        names = {rule.name for rule in db.scalars(select(m.AutomationRule))}
        own = set((installed.created or {}).get("processes", {}).values()) if installed else set()
        own |= set((installed.created or {}).get("automations", {}).values()) if installed else set()
        own_names = {rule.name for rule in db.scalars(select(m.AutomationRule).where(m.AutomationRule.id.in_(own)))}
        for item in [*pack.processes.values(), *pack.automations.values()]:
            if item.name in names and item.name not in own_names:
                conflicts.append(f"Đã có quy trình hoặc luồng tên “{item.name}”.")
        titles = {article.title for article in db.scalars(select(m.AssistantArticle))}
        for title, _ in pack.knowledge.values():
            if title in titles and not installed:
                conflicts.append(f"Đã có bài kiến thức “{title}”.")
        other_keys = {
            t.key for t in db.scalars(select(m.PackTemplate).where(m.PackTemplate.pack_id != manifest.id))
        }
        for item in pack.templates.values():
            if item.key in other_keys:
                conflicts.append(f"Mẫu luồng “{item.key}” trùng khoá với một gói khác.")
        if installed and installed.source == "local":
            raise AppError(409, "pack_id_taken", "Mã gói này đang dùng cho gói của cơ quan; đổi mã gói rồi thử lại.")
        look = manifest.appearance
        return {
            "pack": {
                "id": manifest.id,
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "license": manifest.license,
                "authors": manifest.authors,
            },
            "upgrade_from": installed.version if installed else None,
            "appearance": look.model_dump() if look else None,
            "contrast": contrast_report(look.colors) if look else [],
            "adds": {
                "processes": [item.name for item in pack.processes.values()],
                "forms": [item.name for item in pack.forms.values()],
                "templates": [item.title for item in pack.templates.values()],
                "automations": [item.name for item in pack.automations.values()],
                "knowledge": [title for title, _ in pack.knowledge.values()],
            },
            "conflicts": conflicts,
            "warnings": pack.warnings,
        }

    async def incoming(file: UploadFile | None, builtin: str | None) -> tuple[Pack, str]:
        if builtin:
            folder = builtin_packs(settings).get(builtin)
            if not folder:
                raise AppError(404, "pack_not_found", "Không có gói có sẵn này.")
            return load_pack(read_folder(folder)), "builtin"
        if not file:
            raise AppError(422, "pack_missing", "Chọn tệp .zip của gói hoặc một gói có sẵn.")
        data = await file.read(MAX_ZIP_BYTES + 1)
        return load_pack(read_zip(data)), "file"

    # ---- Appearance: public, the login page needs it before anyone signs in ----

    @router.get("/appearance")
    def current_appearance(db: Session = Depends(db_dep)):
        row = db.get(m.ActiveAppearance, "default")
        pack_id = row.pack_id if row else None
        return {
            "pack_id": pack_id,
            "revision": row.revision if row else 0,
            "appearance": appearance_of(db, pack_id),
            "fonts": FONTS,
        }

    @router.get("/appearance/assets/{asset_id}")
    def appearance_asset(asset_id: str, db: Session = Depends(db_dep)):
        asset = db.get(m.PackAsset, asset_id)
        if not asset:
            raise AppError(404, "asset_not_found", "Không tìm thấy tệp giao diện.")
        return Response(
            asset.data,
            media_type=asset.mime,
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Content-Type-Options": "nosniff",
                # An SVG opened on its own still cannot run anything or load from elsewhere.
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
            },
        )

    @router.put("/appearance")
    def choose_appearance(body: AppearanceChoice, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        row = db.scalar(select(m.ActiveAppearance).where(m.ActiveAppearance.id == "default").with_for_update()) or active(db)
        if row.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Giao diện vừa được người khác đổi. Tải lại để xem.")
        if body.pack_id:
            pack = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == body.pack_id))
            if not pack or not (pack.manifest or {}).get("appearance"):
                raise AppError(422, "pack_without_appearance", "Gói này không có phần giao diện.")
        row.pack_id, row.revision, row.updated_at = body.pack_id, row.revision + 1, m.utcnow()
        audit(db, user, "appearance.changed", row.id, {"pack_id": body.pack_id})
        db.commit()
        return current_appearance(db)

    # ---- Packs ----

    @router.get("/packs/templates")
    def templates(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Ready-made flows from every installed pack, the core pack first."""
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        current_user(db, actor)
        ensure_builtin(db, settings)
        db.commit()
        rows = list(db.scalars(select(m.PackTemplate)))
        names = {row.pack_id: row.name for row in db.scalars(select(m.InstalledPack))}
        rows.sort(key=lambda t: (t.pack_id != CORE_PACK, t.pack_id, t.position))
        return {
            "items": [
                {
                    "key": t.key,
                    "pack_id": t.pack_id,
                    "pack_name": names.get(t.pack_id, t.pack_id),
                    "title": t.title,
                    "description": t.description,
                    "graph": t.graph,
                }
                for t in rows
            ]
        }

    @router.get("/packs")
    def packs(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        manager(db, actor)
        ensure_builtin(db, settings)
        current = active(db).pack_id
        db.commit()
        installed = list(db.scalars(select(m.InstalledPack).order_by(m.InstalledPack.installed_at)))
        versions = {row.pack_id: row.version for row in installed}
        available = []
        for pack_id, folder in builtin_packs(settings).items():
            shipped = json.loads((folder / "desktiny-pack.json").read_text("utf-8"))
            if pack_id == CORE_PACK:
                continue
            have = versions.get(pack_id)
            if have and parse_version(have) >= parse_version(shipped.get("version", "0.0.0")):
                continue
            available.append(
                {
                    "pack_id": pack_id,
                    "name": shipped.get("name", pack_id),
                    "version": shipped.get("version"),
                    "description": shipped.get("description", ""),
                    "installed_version": have,
                    "has_appearance": bool(shipped.get("appearance")),
                    "counts": counts(shipped),
                }
            )
        return {
            "installed": [pack_data(db, row, current) for row in installed],
            "available": available,
            "appearance_pack_id": current,
            "appearance_revision": active(db).revision,
            "limits": {"colors": list(COLOR_VARS), "fonts": FONTS, "login_styles": LOGIN_STYLES,
                       "menu": list(MENU_KEYS), "hideable": list(HIDEABLE), "home": HOME_BLOCKS},  # fmt: skip
        }

    @router.post("/packs/preview")
    async def preview(
        file: UploadFile | None = File(None),
        builtin: str | None = Form(None),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """What installing would add or change; writes nothing."""
        manager(db, actor)
        pack, _ = await incoming(file, builtin)
        return preview_of(db, pack)

    def install_pack(db, actor, user, pack: Pack, source: str, activate: bool = False):
        """Install or upgrade `pack` (no commit); returns the row and notes for the person installing.

        Also used by packaged plugins that bring a pack (`source` "plugin"): such a pack is then
        upgraded and removed only with its plugin.
        """
        needs(db, user, pack)
        manifest = pack.manifest
        if manifest.id == CORE_PACK:
            raise AppError(409, "core_pack_managed", "Gói mặc định được cài sẵn cùng hệ thống.")
        preview_of(db, pack)  # refuses ids the organisation's own pack uses
        row = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == manifest.id).with_for_update())
        if row and (row.source == "plugin") != (source == "plugin"):
            raise AppError(
                409,
                "pack_owned_by_plugin" if row.source == "plugin" else "pack_id_taken",
                "Gói này đi kèm một plugin; cài, nâng cấp hay gỡ plugin đó để thay đổi gói."
                if row.source == "plugin"
                else f"Đã có gói giao diện “{row.name}” cùng mã {manifest.id}; gỡ gói đó trước khi cài plugin.",
            )
        upgrade_from = row.version if row else None
        if not row:
            row = m.InstalledPack(
                pack_id=manifest.id,
                name=manifest.name,
                version=manifest.version,
                manifest={},
                installed_by=user.id,
                created={},
            )
            db.add(row)
            db.flush()
        installer = Installer(app, db, actor, user, row)
        installer.apply(pack)
        row.name, row.version, row.source = manifest.name, manifest.version, source
        row.manifest = manifest.model_dump(by_alias=True, exclude_none=True)
        row.files, row.updated_at = pack.texts, m.utcnow()
        row.revision = (row.revision or 0) + 1
        look = active(db)
        if activate and manifest.appearance:
            look.pack_id, look.revision = manifest.id, look.revision + 1
        elif look.pack_id == manifest.id and not manifest.appearance:
            look.pack_id, look.revision = None, look.revision + 1
        elif look.pack_id == manifest.id:
            look.revision += 1  # the new version's appearance takes effect
        audit(db, user, "pack.upgraded" if upgrade_from else "pack.installed", row.id,
              {"pack_id": manifest.id, "version": manifest.version, "from": upgrade_from})  # fmt: skip
        return row, installer.notes + pack.warnings

    def remove_pack(db, actor, user, row: m.InstalledPack) -> list[str]:
        """Take back what the pack made (no commit); a local pack only loses its assets."""
        installer = Installer(app, db, actor, user, row)
        if row.source != "local":  # a local pack only points at things the organisation made itself
            installer.remove_all()
        else:
            db.execute(delete(m.PackAsset).where(m.PackAsset.pack_id == row.pack_id))
        look = active(db)
        if look.pack_id == row.pack_id:
            look.pack_id, look.revision = None, look.revision + 1
        audit(db, user, "pack.removed", row.id, {"pack_id": row.pack_id, "version": row.version})
        db.delete(row)
        return installer.notes

    app.state.packs = SimpleNamespace(read=read_zip, load=load_pack, preview=preview_of, install=install_pack,
                                      remove=remove_pack)  # fmt: skip

    @router.post("/packs", status_code=201)
    async def install(
        file: UploadFile | None = File(None),
        builtin: str | None = Form(None),
        activate: bool = Form(False),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """Install a pack, or upgrade it when the same id is installed; one transaction."""
        user = manager(db, actor)
        pack, source = await incoming(file, builtin)
        row, notes = install_pack(db, actor, user, pack, source, activate)
        look = active(db)
        db.commit()
        return {"pack": pack_data(db, row, look.pack_id), "notes": notes}

    @router.delete("/packs/{pack_id}")
    def uninstall(pack_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        if pack_id == CORE_PACK:
            raise AppError(409, "core_pack_managed", "Gói mặc định không gỡ được.")
        row = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == pack_id).with_for_update())
        if not row:
            raise AppError(404, "pack_not_found", "Gói chưa được cài.")
        if row.source == "plugin":
            raise AppError(409, "pack_owned_by_plugin", "Gói này đi kèm một plugin; gỡ plugin đó để gỡ gói.")
        notes = remove_pack(db, actor, user, row)
        db.commit()
        return {"notes": notes}

    @router.get("/packs/{pack_id}/export")
    def export(pack_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = manager(db, actor)
        row = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == pack_id))
        if not row:
            raise AppError(404, "pack_not_found", "Gói chưa được cài.")
        data = export_zip(db, row)
        audit(db, user, "pack.exported", row.id, {"pack_id": pack_id})
        db.commit()
        return Response(
            data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{pack_id}-{row.version}.zip"'},
        )

    def local_id(pack_id: str) -> str:
        if not re.fullmatch(r"local\.[a-z0-9][a-z0-9-]{0,60}", pack_id):
            raise AppError(422, "pack_id_invalid", "Gói của cơ quan có mã dạng local.ten-goi (chữ thường, số, gạch ngang).")
        return pack_id

    @router.post("/packs/{pack_id}/assets", status_code=201)
    async def upload_asset(
        pack_id: str,
        role: Literal["logo", "favicon", "background"] = Form(...),
        file: UploadFile = File(...),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """A logo, favicon or login background for the organisation's own pack, checked like a pack file."""
        user = manager(db, actor)
        local_id(pack_id)
        data = await file.read(MAX_ASSET_BYTES[role] + 1)
        name = file.filename or role
        extension = "svg" if name.lower().endswith(".svg") else None
        mime, data, cleaned = check_asset(f"{role}.{extension or 'png'}", data, role)
        extension = {"image/png": "png", "image/webp": "webp", "image/jpeg": "jpg", "image/svg+xml": "svg"}[mime]
        path = f"assets/{role}.{extension}"
        db.execute(
            delete(m.PackAsset).where(m.PackAsset.pack_id == pack_id, m.PackAsset.path.like(f"assets/{role}.%"))
        )
        asset = m.PackAsset(pack_id=pack_id, path=path, mime=mime, data=data, digest=hashlib.sha256(data).hexdigest())
        db.add(asset)
        db.flush()
        audit(db, user, "pack.asset_uploaded", pack_id, {"role": role})
        db.commit()
        return {"path": path, "url": asset_url(asset), "cleaned": cleaned}

    @router.put("/packs/{pack_id}")
    def save_local(
        pack_id: str, body: LocalPackInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        """Create or update the organisation's own pack from the pack builder."""
        user = manager(db, actor)
        local_id(pack_id)
        row = db.scalar(select(m.InstalledPack).where(m.InstalledPack.pack_id == pack_id).with_for_update())
        if row and row.source != "local":
            raise AppError(409, "pack_id_taken", "Mã gói này đang dùng cho một gói đã cài.")
        if row and body.expected_revision is not None and row.revision != body.expected_revision:
            raise AppError(409, "revision_conflict", "Gói vừa được người khác sửa. Tải lại để xem.")
        look = body.appearance
        if look:
            failures = contrast_failures(look.colors)
            if failures:
                raise AppError(422, "pack_contrast_too_low", "Màu khó đọc: " + " ".join(failures))
            assets = {a.path for a in db.scalars(select(m.PackAsset).where(m.PackAsset.pack_id == pack_id))}
            for path in (look.logo, look.favicon, look.login.background):
                if path and path not in assets:
                    raise AppError(422, "pack_file_missing", f"Chưa tải lên “{path}”.")
            if look.login.style == "image" and not look.login.background:
                raise AppError(422, "pack_manifest_invalid", "Trang đăng nhập kiểu ảnh nền cần ảnh nền.")
        include = body.include
        for rule_id in [*include.processes, *include.automations]:
            rule = db.get(m.AutomationRule, rule_id)
            if not rule:
                raise AppError(422, "pack_include_invalid", "Có quy trình hoặc luồng được chọn không còn tồn tại.")
            if rule_id in include.processes and rule.kind != "process":
                raise AppError(422, "pack_include_invalid", f"“{rule.name}” không phải quy trình hồ sơ.")
        for article_id in include.knowledge:
            if not db.get(m.AssistantArticle, article_id):
                raise AppError(422, "pack_include_invalid", "Có bài kiến thức được chọn không còn tồn tại.")
        manifest = Manifest(
            schema_=SCHEMA,
            id=pack_id,
            name=body.name,
            version=body.version,
            license=body.license,
            description=body.description,
            authors=[user.display_name],
            appearance=look,
        )
        if not row:
            row = m.InstalledPack(pack_id=pack_id, source="local", installed_by=user.id, created={}, files={})
            db.add(row)
        row.name, row.version = body.name, body.version
        row.manifest = manifest.model_dump(by_alias=True, exclude_none=True)
        row.includes = include.model_dump()
        row.revision = (row.revision or 0) + 1
        row.updated_at = m.utcnow()
        current = active(db)
        if current.pack_id == pack_id:
            current.revision += 1 if look else 0
            if not look:
                current.pack_id, current.revision = None, current.revision + 1
        db.flush()
        audit(db, user, "pack.saved", row.id, {"pack_id": pack_id})
        db.commit()
        return pack_data(db, row, current.pack_id)

    return router
