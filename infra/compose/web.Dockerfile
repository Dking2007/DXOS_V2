# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
FROM node:22.17.0-alpine AS build
ARG APP
WORKDIR /app
COPY package*.json ./
COPY apps ./apps
RUN npm ci
RUN npm run build --workspace apps/${APP}
RUN cp -R apps/${APP}/dist /web-dist

FROM nginx:1.28.0-alpine
COPY infra/compose/web.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web-dist /usr/share/nginx/html
EXPOSE 80
