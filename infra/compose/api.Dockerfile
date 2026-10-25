# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
FROM python:3.13.5-slim-bookworm
ARG SERVICE
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock /app/requirements.lock
COPY packages/platform-kit /app/packages/platform-kit
RUN pip install -c /app/requirements.lock /app/packages/platform-kit
ARG SERVICE
COPY services/${SERVICE} /app/services/${SERVICE}
RUN pip install -c /app/requirements.lock /app/services/${SERVICE} && useradd --create-home --uid 10001 dx
WORKDIR /app/services/${SERVICE}
USER dx
EXPOSE 8001 8002
