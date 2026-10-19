# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build
COPY . .

# Backend URL — value is sourced from .env.docker (see docker-compose.yml)
# or passed as: docker build --build-arg VITE_API_BASE_URL=...
# Never hardcode the value here; leave the ARG declaration empty.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ── Stage 2: serve ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# gettext provides envsubst, used to inject BACKEND_HOST into nginx.conf
RUN apk add --no-cache gettext

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx template — ${BACKEND_HOST} is substituted at start time
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

EXPOSE 80

# At start: substitute env vars into the nginx config, then launch nginx.
# BACKEND_HOST defaults to "backend:8000" (docker-compose service name).
CMD ["/bin/sh", "-c", \
     "BACKEND_HOST=${BACKEND_HOST:-backend:8000} \
      envsubst '${BACKEND_HOST}' \
        < /etc/nginx/conf.d/default.conf.template \
        > /etc/nginx/conf.d/default.conf && \
      nginx -g 'daemon off;'"]
