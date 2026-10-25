# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
#
# Điểm vào duy nhất cho cài đặt/biên dịch/kiểm thử. Xem BUILD.md.
# Cấu hình bằng biến môi trường, không cần sửa mã nguồn:
#   make install PREFIX=/opt/desktiny     # cài ra ngoài thư mục mã nguồn
#   make up BASE_URL=http://localhost:8090
PREFIX   ?= /usr/local
DESTDIR  ?=
PYTHON   ?= python3
VENV     ?= .venv
BASE_URL ?= http://localhost:8080
VERSION  ?= $(shell $(PYTHON) -c "import re,sys;print(re.search(r'version = \"(.+?)\"',open('packages/platform-kit/pyproject.toml').read()).group(1))")
COMPOSE  := docker compose --env-file .env -f infra/compose/compose.yaml

.PHONY: help venv deps build test lint check install dist up down seed reuse licenses third-party clean

help:
	@echo "venv        tạo $(VENV) và cài phụ thuộc Python (khóa bằng requirements.lock)"
	@echo "deps        npm ci"
	@echo "build       biên dịch frontend (apps/*/dist)"
	@echo "test        pytest + vitest"
	@echo "lint        ruff + eslint + typecheck"
	@echo "install     cài vào $(DESTDIR)$(PREFIX) (gói Python + web tĩnh + migration + cấu hình mẫu)"
	@echo "dist        đóng gói nguồn dist/dxos-<phiên bản>.tar.gz + SHA256SUMS"
	@echo "up/down     chạy/dừng toàn bộ nền tảng bằng Docker Compose (tự bootstrap .env)"
	@echo "reuse       reuse lint (cần: pipx install reuse)"
	@echo "licenses    quét giấy phép thư viện, cập nhật THIRD_PARTY.md"

venv:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -r requirements-dev.txt

deps:
	npm ci

build: deps
	npm run build

test: deps
	$(VENV)/bin/python -m pytest -q
	npm run test

lint: deps
	$(VENV)/bin/python -m ruff check packages services scripts tests examples infra
	npm run lint
	npm run typecheck

check: lint test

install: build
	$(PYTHON) -m pip install --prefix "$(DESTDIR)$(PREFIX)" -c requirements.lock ./packages/platform-kit ./services/core-api ./services/workspace-api
	install -d "$(DESTDIR)$(PREFIX)/share/desktiny/workspace-web" "$(DESTDIR)$(PREFIX)/share/desktiny/core-admin" "$(DESTDIR)$(PREFIX)/share/desktiny/config"
	cp -r apps/workspace-web/dist/. "$(DESTDIR)$(PREFIX)/share/desktiny/workspace-web/"
	cp -r apps/core-admin/dist/. "$(DESTDIR)$(PREFIX)/share/desktiny/core-admin/"
	install -m 0644 .env.example "$(DESTDIR)$(PREFIX)/share/desktiny/config/env.example"
	for svc in core-api workspace-api; do 	  install -d "$(DESTDIR)$(PREFIX)/share/desktiny/$svc" && 	  cp services/$svc/alembic.ini "$(DESTDIR)$(PREFIX)/share/desktiny/$svc/" && 	  cp -r services/$svc/migrations "$(DESTDIR)$(PREFIX)/share/desktiny/$svc/"; 	done
	install -d "$(DESTDIR)$(PREFIX)/bin"
	install -m 0755 scripts/desktiny-migrate.sh "$(DESTDIR)$(PREFIX)/bin/desktiny-migrate"

dist:
	mkdir -p dist
	git archive --format=tar.gz --prefix=dxos-$(VERSION)/ -o dist/dxos-$(VERSION).tar.gz HEAD
	cd dist && sha256sum dxos-$(VERSION).tar.gz > SHA256SUMS

up:
	@test -f .env || $(PYTHON) scripts/bootstrap.py --base-url $(BASE_URL)
	$(COMPOSE) --profile workspace up --build -d
	$(PYTHON) scripts/seed.py --confirm-demo

down:
	$(COMPOSE) --profile workspace --profile office --profile core down

seed:
	$(PYTHON) scripts/seed.py --confirm-demo

reuse:
	reuse lint

licenses:
	npm ci
	node scripts/gen_third_party.mjs

third-party: licenses

clean:
	rm -rf dist apps/*/dist coverage playwright-report test-results
