FROM node:22-bookworm-slim

ENV BROWSER=none \
    EXPO_NO_DOTENV=1 \
    EXPO_NO_TELEMETRY=1

WORKDIR /app/frontend

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
COPY scripts ./scripts
RUN npm ci

COPY . .

EXPOSE 8081 19000 19001 19002

CMD ["npm", "run", "start", "--", "--port", "8081"]
