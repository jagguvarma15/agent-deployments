# Multi-stage: build the static bundle with Node, serve it from nginx on :3000.
# The scaffold's normalize_frontend_service adds the matching `frontend` compose
# service (build: ./frontend, ports 3000:3000) wired to the backend.

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_AGENT_URL is baked at build time (Vite client env). The default points at
# the host-mapped backend; override with --build-arg VITE_AGENT_URL=... if needed.
ARG VITE_AGENT_URL=http://localhost:8000
ENV VITE_AGENT_URL=$VITE_AGENT_URL
RUN npm run build

FROM nginx:alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
