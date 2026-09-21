FROM mcr.microsoft.com/playwright:v1.55.0-noble
WORKDIR /app
COPY apps/browser-collector/package.json .
RUN npm install --omit=dev
COPY apps/browser-collector/src ./src
CMD ["npm","start"]
