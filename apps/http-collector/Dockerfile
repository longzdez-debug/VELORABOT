FROM node:22-alpine
WORKDIR /app
COPY apps/http-collector/package.json ./
RUN npm install --omit=dev
COPY apps/http-collector/src ./src
CMD ["npm","start"]