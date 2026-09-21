FROM node:22-bookworm-slim
WORKDIR /app
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN apt-get update \\
    && apt-get install -y --no-install-recommends chromium ca-certificates \\
    && rm -rf /var/lib/apt/lists/*
COPY apps/browser-collector/package.json .
RUN npm install --omit=dev
COPY apps/browser-collector/src ./src
USER node
ENV CHROMIUM_PATH=/usr/bin/chromium
CMD ["npm","start"]
