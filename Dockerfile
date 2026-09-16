FROM node:22-bookworm-slim AS ui
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY data/catalogue.json ./data/catalogue.json
COPY --from=ui /build/dist ./frontend/dist
RUN useradd --create-home wikidex && chown -R wikidex:wikidex /app
USER wikidex
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.wikidex.api:app", "--host", "0.0.0.0", "--port", "8000"]
