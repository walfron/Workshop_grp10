# syntax=docker/dockerfile:1
# Sentinel-X : image API + dashboard (proposition INFRA pour DEV)
# Contexte de build = racine du dépôt (le backend sert ../../frontend/dist).
#   docker compose build api
# Arborescence finale : /app/backend/src/index.js et /app/frontend/dist

ARG NODE_IMAGE=node:24-alpine

# 1) Build du dashboard (Vite)
FROM ${NODE_IMAGE} AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# URL du flux webcam, figée au build : même origine (HTTPS, via le reverse proxy)
# pour éviter le contenu mixte http:// bloqué par le navigateur
ARG VITE_WEBCAM_URL=/webcam/video_feed
ENV VITE_WEBCAM_URL=${VITE_WEBCAM_URL}
RUN npm run build

# 2) Dépendances de production du backend
FROM ${NODE_IMAGE} AS backend-deps
WORKDIR /app/backend
COPY backend/package.json backend/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force

# 3) Image finale : Node seul, utilisateur non-root, aucun outil de build
FROM ${NODE_IMAGE}
ENV NODE_ENV=production \
    PORT=3000 \
    DB_PATH=/data/sentinel.db
WORKDIR /app/backend
# Code et dépendances appartiennent à root : non modifiables par l'utilisateur de l'API
COPY --from=backend-deps /app/backend/node_modules ./node_modules
COPY backend/package.json ./
COPY backend/src ./src
COPY --from=frontend /build/frontend/dist /app/frontend/dist
# Seul /data (SQLite) est inscriptible. UID dédié 10001 : l'utilisateur « node »
# de l'image a l'UID 1000, le même que le compte d'administration de l'hôte.
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 3000
CMD ["node", "src/index.js"]
