FROM node:22-alpine AS web
WORKDIR /src
COPY app/web/package.json app/web/tsconfig.json ./
COPY app/web/src ./src
RUN npm install && npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY --from=web /src/dist ./app/web/generated
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["python","-m","app.main"]
