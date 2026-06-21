# Multi-stage: build the static bundle with Node, serve it from nginx on :3000.
# The scaffold's normalize_frontend_service adds the matching `frontend` compose
# service (build: ./frontend, ports 3000:3000) wired to the backend.

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
# `npm install`, not `npm ci`: this starter ships package.json without a
# committed package-lock.json, and `npm ci` hard-fails without a lockfile.
# (Copying package*.json before the source keeps the deps layer cached.)
RUN npm install --no-audit --no-fund
COPY . .
# VITE_* values are baked at build time (Vite client env). VITE_AGENT_URL points
# at the host-mapped backend; VITE_AGENT_TITLE labels the chat UI. The scaffold
# passes both as build args (normalize_frontend_service); override with
# --build-arg VITE_AGENT_URL=... / VITE_AGENT_TITLE=... when building by hand.
ARG VITE_AGENT_URL=http://localhost:8000
ENV VITE_AGENT_URL=$VITE_AGENT_URL
ARG VITE_AGENT_TITLE="Agent Chat"
ENV VITE_AGENT_TITLE=$VITE_AGENT_TITLE
RUN npm run build

FROM nginx:alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
