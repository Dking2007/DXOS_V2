#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
#
# Chạy migration CSDL từ bản đã cài (make install), không cần thư mục mã nguồn.
#   desktiny-migrate core|workspace [tham số alembic, mặc định: upgrade head]
# Cần biến môi trường DATABASE_URL của service tương ứng (xem .env.example).
set -eu
service="${1:?cách dùng: desktiny-migrate core|workspace [tham số alembic]}"
shift
case "$service" in core | workspace) ;; *) echo "service phải là core hoặc workspace" >&2; exit 2 ;; esac
prefix=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
site=$(ls -d "$prefix"/lib/python3*/site-packages 2>/dev/null | head -n 1 || true)
if [ -n "$site" ]; then PYTHONPATH="$site${PYTHONPATH:+:$PYTHONPATH}"; export PYTHONPATH; fi
if [ "$#" -eq 0 ]; then set -- upgrade head; fi
# Dùng đúng phiên bản Python đã cài gói (lib/python3.X) thay vì python3 mặc định của hệ thống.
if [ -n "$site" ]; then default_python=$(basename -- "$(dirname -- "$site")"); else default_python=python3; fi
command -v "$default_python" >/dev/null 2>&1 || default_python=python3
exec "${PYTHON:-$default_python}" -m alembic -c "$prefix/share/desktiny/$service-api/alembic.ini" "$@"
