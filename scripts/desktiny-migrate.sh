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
exec "${PYTHON:-python3}" -m alembic -c "$prefix/share/desktiny/$service-api/alembic.ini" "$@"
