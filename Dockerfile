FROM node:22-alpine AS frontend-build
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim AS backend
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home app && mkdir /app/data && chown app:app /app/data
COPY --chown=app:app backend/app ./app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]

FROM nginx:1.28-alpine AS frontend
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html
EXPOSE 80
