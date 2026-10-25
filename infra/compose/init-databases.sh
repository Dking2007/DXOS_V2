#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
set -eu
# This file only runs when the PostgreSQL data volume is empty.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=core_password="$CORE_DB_PASSWORD" \
  --set=workspace_password="$WORKSPACE_DB_PASSWORD" \
  --set=identity_password="$IDENTITY_DB_PASSWORD" <<'SQL'
CREATE USER dx_core PASSWORD :'core_password';
CREATE DATABASE dx_core OWNER dx_core;
CREATE USER dx_workspace PASSWORD :'workspace_password';
CREATE DATABASE dx_workspace OWNER dx_workspace;
CREATE USER dx_identity PASSWORD :'identity_password';
CREATE DATABASE dx_identity OWNER dx_identity;
REVOKE CONNECT ON DATABASE dx_core FROM PUBLIC;
REVOKE CONNECT ON DATABASE dx_workspace FROM PUBLIC;
REVOKE CONNECT ON DATABASE dx_identity FROM PUBLIC;
GRANT CONNECT ON DATABASE dx_core TO dx_core;
GRANT CONNECT ON DATABASE dx_workspace TO dx_workspace;
GRANT CONNECT ON DATABASE dx_identity TO dx_identity;
SQL
