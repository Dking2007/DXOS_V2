import hashlib
import io
import zipfile
from pathlib import Path

import boto3
from botocore.config import Config
from dx_platform.errors import AppError


class BlobStore:
    def __init__(self, settings):
        self.settings = settings
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint,
                aws_access_key_id=self.settings.s3_access_key,
                aws_secret_access_key=self.settings.s3_secret_key,
                region_name="us-east-1",
                config=Config(signature_version="s3v4", retries={"max_attempts": 2}),
            )
        return self._client

    def local_path(self, key):
        root = Path(self.settings.storage_local_path).resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root) or key.startswith("/"):
            raise ValueError("Invalid object key")
        return path

    def put(self, key: str, data: bytes, mime: str):
        if self.settings.storage_backend == "local":
            path = self.local_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        else:
            self.client.put_object(Bucket=self.settings.s3_bucket, Key=key, Body=data, ContentType=mime)

    def get(self, key: str) -> bytes:
        if self.settings.storage_backend == "local":
            return self.local_path(key).read_bytes()
        return self.client.get_object(Bucket=self.settings.s3_bucket, Key=key)["Body"].read()

    def ready(self):
        if self.settings.storage_backend == "local":
            return True
        self.client.head_bucket(Bucket=self.settings.s3_bucket)
        return True


def inspect_content(data: bytes, name: str, claimed_mime: str) -> str:
    """Conservative allowlist: active HTML/SVG/executables are not accepted as office attachments."""
    suffix = Path(name).suffix.lower()
    allowed = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    if suffix not in allowed:
        raise AppError(422, "unsupported_file_type", "Chỉ nhận PDF, ảnh PNG/JPEG, TXT/CSV và DOCX/XLSX/PPTX.")
    mime = allowed[suffix]
    if suffix == ".pdf" and not data.startswith(b"%PDF-"):
        raise AppError(422, "mime_mismatch", "Nội dung không phải PDF hợp lệ.")
    if suffix == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AppError(422, "mime_mismatch", "Nội dung không phải PNG.")
    if suffix in {".jpg", ".jpeg"} and not data.startswith(b"\xff\xd8\xff"):
        raise AppError(422, "mime_mismatch", "Nội dung không phải JPEG.")
    if suffix in {".txt", ".csv"}:
        try:
            data.decode("utf-8-sig")
            if b"\x00" in data:
                raise ValueError("binary")
        except (UnicodeError, ValueError):
            raise AppError(422, "mime_mismatch", "Văn bản cần mã hóa UTF-8.") from None
    if suffix in {".docx", ".xlsx", ".pptx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 5000 or sum(i.file_size for i in infos) > 200_000_000:
                    raise ValueError("archive limit")
                if any(i.filename.startswith("/") or ".." in Path(i.filename).parts for i in infos):
                    raise ValueError("archive path")
                names = archive.namelist()
                directory = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}[suffix]
                if "[Content_Types].xml" not in names or not any(n.startswith(directory) for n in names):
                    raise ValueError("not office")
                if any("vbaproject" in n.lower() for n in names):
                    raise ValueError("macros not accepted")
        except (zipfile.BadZipFile, ValueError):
            raise AppError(
                422, "invalid_office_file", "Tệp Office không hợp lệ, có macro hoặc vượt giới hạn giải nén."
            ) from None
    return mime


def checksum(data: bytes):
    return hashlib.sha256(data).hexdigest()
