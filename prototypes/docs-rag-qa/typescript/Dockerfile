# Prototype Dockerfile — references the shared base pattern
# See common/docker/Dockerfile.typescript for the full multi-stage template

ARG NODE_VERSION=22

# --- Build stage ---
FROM node:${NODE_VERSION}-alpine AS builder

RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build
RUN pnpm prune --prod

# --- Runtime stage ---
FROM node:${NODE_VERSION}-alpine AS runtime

RUN addgroup --gid 1001 app && \
    adduser --uid 1001 --ingroup app --disabled-password app

WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8000/health || exit 1

CMD ["node", "dist/index.js"]
