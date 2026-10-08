FROM node:24-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
ARG VITE_WEBCAM_URL=
RUN npm run build

FROM node:24-alpine
WORKDIR /app/backend
COPY backend/package*.json ./
RUN npm ci --omit=dev
COPY backend/src ./src
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN mkdir -p data && chown node:node data
USER node
ENV NODE_ENV=production
EXPOSE 3000
CMD ["node", "src/index.js"]
