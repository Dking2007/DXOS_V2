"""Explicit development bootstrap; never runs automatically when an API process starts."""

import argparse
import json
from pathlib import Path

from dx_platform.database import make_engine
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Counter, Department, Organization, Role, User
from .policies import ROLE_TEMPLATES


def seed(engine, source):
    with Session(engine) as db:
        organization = db.scalar(select(Organization).limit(1))
        if not organization:
            db.add(Organization(name=source.get("organization", "Desktiny")))
        for key, (name, permissions) in ROLE_TEMPLATES.items():
            if not db.get(Role, key):
                db.add(Role(key=key, name=name, permissions=permissions))
        departments = {v.code: v for v in db.scalars(select(Department))}
        for entry in source["users"]:
            code = entry.get("department")
            if code and code not in departments:
                department = Department(
                    code=code,
                    name={"administration": "Phòng Hành chính", "engineering": "Phòng Kỹ thuật"}.get(
                        code, code
                    ),
                )
                db.add(department)
                db.flush()
                departments[code] = department
        for entry in source["users"]:
            existing = db.scalar(select(User).where(User.subject == entry["subject"]))
            if existing:
                continue
            department = departments.get(entry.get("department"))
            user = User(
                subject=entry["subject"],
                display_name=entry["display_name"],
                role=entry["role"],
                department_id=department.id if department else None,
            )
            db.add(user)
            db.flush()
            if department and user.role == "manager" and not department.manager_id:
                department.manager_id = user.id
        if not db.get(Counter, "case"):
            db.add(Counter(key="case", value=0))
        db.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Khởi tạo dữ liệu demo Workspace từ danh sách subject Keycloak."
    )
    parser.add_argument("--users-file", required=True)
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment == "production":
        parser.error("Không seed demo vào production.")
    source = json.loads(Path(args.users_file).read_text(encoding="utf-8"))
    seed(make_engine(settings.database_url), source)
    print("Đã khởi tạo tổ chức, phòng ban, vai trò và người dùng demo (không tạo mật khẩu hoặc hồ sơ).")


if __name__ == "__main__":
    main()
